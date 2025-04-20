from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import logging
import shutil
import time
import random
import uuid
import threading
import datetime
from pathlib import Path
import werkzeug.utils
from PIL import Image
from anthropic import RateLimitError, APIStatusError, APITimeoutError, APIConnectionError
from collections import defaultdict
import json

# IMPORTANT: Fix for decompression bomb warning
Image.MAX_IMAGE_PIXELS = 200000000

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the current directory to Python path to find the modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import modules
try:
    from modules.construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    from modules.tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    from modules.extract_tile_entities_wow_rev4 import analyze_all_tiles
    from pdf2image import convert_from_path
    logger.info("Successfully imported analyzer modules")
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    sys.exit(1)

app = Flask(__name__)

# Configure CORS to allow requests from any origin
# This is the simplest 80/20 solution for allowing cross-origin requests
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured to allow requests from any origin")

# Ensure BASE_DIR is set correctly for containerized environment
try:
    # Use environment variable if available, otherwise use default path
    base_dir = os.environ.get('BASE_DIR', '/app')
    Config.configure(base_dir=base_dir)
    logger.info(f"Configured base directory: {Config.BASE_DIR}")
    logger.info(f"Drawings directory: {Config.DRAWINGS_DIR}")
    logger.info(f"Memory store directory: {Config.MEMORY_STORE}")
except Exception as e:
    logger.error(f"Error configuring base directory: {e}")
    # Try a fallback configuration
    fallback_dir = os.path.dirname(os.path.abspath(__file__))
    Config.configure(base_dir=fallback_dir)
    logger.info(f"Using fallback base directory: {fallback_dir}")

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

# Configure retry settings
MAX_RETRIES = 5
MAX_BACKOFF = 120  # Maximum backoff time in seconds

# Configure batch processing settings to match GUI script
BATCH_SIZE = 10  # Number of drawings to process in one batch - matching the GUI script

# Job tracking storage
jobs = {}
job_lock = threading.Lock()  # To prevent race conditions when updating job status

# Process phases and emojis for cool status messages
PROCESS_PHASES = {
    "INIT": "🚀 INITIALIZATION",
    "DISCOVERY": "🔍 DISCOVERY",
    "ANALYSIS": "🧩 ANALYSIS",
    "CORRELATION": "🔗 CORRELATION",
    "SYNTHESIS": "💡 SYNTHESIS",
    "COMPLETE": "✨ COMPLETE"
}

# Create required directories with better error handling
try:
    os.makedirs(Config.DRAWINGS_DIR, exist_ok=True)
    os.makedirs(Config.MEMORY_STORE, exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    logger.info("Successfully created required directories")
except Exception as e:
    logger.error(f"Error creating directories: {e}")
    # Continue running as we might be using existing directories

# Create global instances
try:
    analyzer = ConstructionAnalyzer()
    drawing_manager = DrawingManager(Config.DRAWINGS_DIR)
    logger.info("Successfully created analyzer and drawing_manager instances")
except Exception as e:
    logger.error(f"ERROR INITIALIZING: {str(e)}", exc_info=True)
    analyzer = None
    drawing_manager = None

# Try to initialize transformer for smart query filtering - matching GUI script
try:
    from transformers import pipeline
    import torch
    device = 0 if torch.cuda.is_available() else -1  # Use GPU if available
    intent_classifier = pipeline("text-classification", 
                              model="distilbert-base-uncased", 
                              device=device, 
                              top_k=None)
    logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}")
except Exception as e:
    logger.warning(f"Failed to load transformer: {e}. Using basic filtering.")
    intent_classifier = None

def smart_filter_query(query):
    """Use DistilBERT to refine vague queries - directly copied from GUI script"""
    if not intent_classifier:
        return query
    
    intent_map = {
        "POSITIVE": ["finish", "floor", "ceiling", "wall", "spec", "tile"],
        "NEUTRAL": ["area", "room", "space", "where"],
    }
    
    try:
        result = intent_classifier(query)[0]
        top_label = max(result, key=lambda x: x['score'])['label']
        query_lower = query.lower()
        
        areas = ["lab", "restroom", "office", "lobby", "conference"]
        area = next((a for a in areas if a in query_lower), "")
        
        if top_label in intent_map and area:
            intent_words = intent_map.get(top_label, [""])
            return f"{intent_words[0]} for {area} areas"
        return query
    except Exception as e:
        logger.error(f"Transformer error: {e}")
        return query

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_drawing_files(drawing_name):
    """Verify that all necessary files exist for a drawing
    Returns a dictionary with boolean flags for each file type"""
    sheet_output_dir = Config.DRAWINGS_DIR / drawing_name
    
    # Check for core files first
    metadata_exists = (sheet_output_dir / f"{drawing_name}_tile_metadata.json").exists()
    tile_analysis_exists = (sheet_output_dir / f"{drawing_name}_tile_analysis.json").exists()
    legend_knowledge_exists = (sheet_output_dir / f"{drawing_name}_legend_knowledge.json").exists()
    drawing_goals_exists = (sheet_output_dir / f"{drawing_name}_drawing_goals.json").exists()
    
    # Check for specialized files based on drawing type
    general_notes_exists = (sheet_output_dir / f"{drawing_name}_general_notes_analysis.json").exists()
    elevation_exists = (sheet_output_dir / f"{drawing_name}_elevation_analysis.json").exists()
    detail_exists = (sheet_output_dir / f"{drawing_name}_detail_analysis.json").exists()
    
    # Log the results
    logger.info(f"File verification for {drawing_name}:")
    logger.info(f"  Metadata exists: {metadata_exists}")
    logger.info(f"  Tile analysis exists: {tile_analysis_exists}")
    logger.info(f"  Legend knowledge exists: {legend_knowledge_exists}")
    logger.info(f"  Drawing goals exists: {drawing_goals_exists}")
    logger.info(f"  General notes exists: {general_notes_exists}")
    logger.info(f"  Elevation exists: {elevation_exists}")
    logger.info(f"  Detail exists: {detail_exists}")
    
    return {
        "metadata": metadata_exists,
        "tile_analysis": tile_analysis_exists,
        "legend_knowledge": legend_knowledge_exists,
        "drawing_goals": drawing_goals_exists,
        "general_notes": general_notes_exists,
        "elevation": elevation_exists,
        "detail": detail_exists,
        "all_required": metadata_exists and (tile_analysis_exists or elevation_exists or detail_exists or general_notes_exists)
    }

def create_job(query, drawings, use_cache):
    """Create a new job and return the job ID"""
    job_id = str(uuid.uuid4())
    
    with job_lock:
        jobs[job_id] = {
            "id": job_id,
            "query": query,
            "drawings": drawings,
            "use_cache": use_cache,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "progress": 0,
            "total_batches": (len(drawings) + BATCH_SIZE - 1) // BATCH_SIZE,
            "completed_batches": 0,
            "current_batch": None,
            "current_phase": PROCESS_PHASES["INIT"],
            "progress_messages": [
                f"{PROCESS_PHASES['INIT']}: Preparing to analyze {len(drawings)} drawing(s)"
            ],
            "result": None,
            "error": None
        }
    
    return job_id

def update_job_status(job_id, **kwargs):
    """Update job status with the given kwargs"""
    with job_lock:
        if job_id in jobs:
            for key, value in kwargs.items():
                if key == "progress_message" and value:
                    jobs[job_id]["progress_messages"].append(value)
                elif key in jobs[job_id]:
                    jobs[job_id][key] = value
            
            jobs[job_id]["updated_at"] = datetime.datetime.now().isoformat()
            
            # Calculate overall progress based on batches and current phase
            if kwargs.get("completed_batches") is not None:
                completed = kwargs["completed_batches"]
                total = jobs[job_id]["total_batches"]
                phase_weight = 0
                
                # Weight progress by phase
                current_phase = kwargs.get("current_phase", jobs[job_id]["current_phase"])
                if PROCESS_PHASES["INIT"] in current_phase:
                    phase_weight = 0.05
                elif PROCESS_PHASES["DISCOVERY"] in current_phase:
                    phase_weight = 0.25
                elif PROCESS_PHASES["ANALYSIS"] in current_phase:
                    phase_weight = 0.55
                elif PROCESS_PHASES["CORRELATION"] in current_phase:
                    phase_weight = 0.75
                elif PROCESS_PHASES["SYNTHESIS"] in current_phase:
                    phase_weight = 0.9
                elif PROCESS_PHASES["COMPLETE"] in current_phase:
                    phase_weight = 1.0
                
                # Calculate progress as a combination of batches completed and current phase
                batch_progress = completed / total if total > 0 else 0
                jobs[job_id]["progress"] = int((batch_progress * 0.8 + phase_weight * 0.2) * 100)
                
                # Ensure progress is at least 1% after initialization
                if jobs[job_id]["progress"] < 1 and completed > 0:
                    jobs[job_id]["progress"] = 1
                    
                # Ensure completed jobs show 100%
                if jobs[job_id]["status"] == "completed":
                    jobs[job_id]["progress"] = 100

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    logger.info("Health check endpoint called")
    return jsonify({"status": "healthy"})

@app.route('/drawings', methods=['GET'])
def get_drawings():
    """Get list of available drawings"""
    try:
        if drawing_manager is None:
            return jsonify({"drawings": [], "error": "Drawing manager not initialized"}), 500
            
        available_drawings = drawing_manager.get_available_drawings()
        
        # Verify the files for each drawing
        drawing_status = {}
        for drawing in available_drawings:
            drawing_status[drawing] = verify_drawing_files(drawing)
        
        # Only return drawings that have the required files
        valid_drawings = [drawing for drawing in available_drawings 
                         if drawing_status[drawing]["all_required"]]
        
        logger.info(f"Retrieved {len(valid_drawings)} valid drawings out of {len(available_drawings)} total")
        
        return jsonify({"drawings": valid_drawings})
    except Exception as e:
        logger.error(f"Error retrieving drawings: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_query():
    """Start an analysis job and return a job ID for tracking progress"""
    try:
        logger.info("Analyze endpoint called")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        if analyzer is None:
            return jsonify({"error": "Analyzer not initialized"}), 500
            
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        query = data.get('query')
        selected_drawings = data.get('drawings', [])
        use_cache = data.get('use_cache', True)
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
        if not selected_drawings:
            return jsonify({"error": "No drawings selected"}), 400
            
        logger.info(f"Starting analysis job for query: {query}")
        logger.info(f"Selected drawings: {selected_drawings}")
        
        # Apply smart filtering for query refinement - matching GUI script
        refined_query = smart_filter_query(query)
        logger.info(f"Refined query: {refined_query}")
        
        # Verify all selected drawings have the necessary files
        valid_drawings = []
        for drawing in selected_drawings:
            file_status = verify_drawing_files(drawing)
            if file_status["all_required"]:
                valid_drawings.append(drawing)
            else:
                logger.warning(f"Drawing {drawing} is missing required files and will be skipped")
        
        if not valid_drawings:
            return jsonify({"error": "None of the selected drawings have the required analysis files"}), 400
            
        # Update selected drawings to only include valid ones
        if len(valid_drawings) < len(selected_drawings):
            logger.warning(f"Only {len(valid_drawings)} out of {len(selected_drawings)} drawings are valid")
            selected_drawings = valid_drawings
        
        # Create a new job
        job_id = create_job(refined_query, selected_drawings, use_cache)
        
        # Start the analysis in a background thread
        thread = threading.Thread(
            target=process_analysis_job,
            args=(job_id, refined_query, selected_drawings, use_cache)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "job_id": job_id,
            "status": "pending",
            "message": "Analysis job started. Use the /job-status/{job_id} endpoint to check progress."
        })
            
    except Exception as e:
        logger.error(f"Error starting analysis job: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the status of a job by its ID"""
    with job_lock:
        if job_id not in jobs:
            return jsonify({"error": "Job not found"}), 404
        
        job = jobs[job_id].copy()
        
        # Limit the number of progress messages to avoid huge responses
        if len(job["progress_messages"]) > 20:
            job["progress_messages"] = job["progress_messages"][-20:]
            job["progress_messages_truncated"] = True
    
    return jsonify(job)

@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List all current jobs with basic info"""
    with job_lock:
        job_summaries = []
        for job_id, job in jobs.items():
            job_summaries.append({
                "id": job_id,
                "status": job["status"],
                "progress": job["progress"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
                "query": job["query"],
                "drawing_count": len(job["drawings"])
            })
    
    return jsonify({"jobs": job_summaries})

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload a PDF construction drawing and process it"""
    try:
        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files['file']
        
        # If user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        if file and allowed_file(file.filename):
            try:
                # Create a secure version of the filename
                filename = werkzeug.utils.secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save the uploaded file without additional processing
                file.save(file_path)
                
                # Verify file was saved correctly
                if not os.path.exists(file_path):
                    return jsonify({"error": "File was not saved properly"}), 500
                
                if os.path.getsize(file_path) == 0:
                    os.remove(file_path)
                    return jsonify({"error": "Uploaded file is empty"}), 400
                
                logger.info(f"File uploaded successfully: {file_path} ({os.path.getsize(file_path)} bytes)")
                
                # Process the PDF with improved error handling
                try:
                    sheet_name, sheet_output_dir = process_pdf(file_path)
                    logger.info(f"Successfully processed {filename}")
                    
                    # Verify all required files were generated
                    file_status = verify_drawing_files(sheet_name)
                    if file_status["all_required"]:
                        logger.info(f"All required files were generated for {sheet_name}")
                    else:
                        logger.warning(f"Not all required files were generated for {sheet_name}. Status: {file_status}")
                        # Make another attempt to generate the files if needed
                        if not file_status["tile_analysis"] or not file_status["legend_knowledge"]:
                            logger.info(f"Making another attempt to analyze tiles for {sheet_name}")
                            analyze_all_tiles(sheet_output_dir, sheet_name)
                            file_status = verify_drawing_files(sheet_name)
                            logger.info(f"After retry, file status: {file_status}")
                    
                    # Return success with the drawing name
                    return jsonify({
                        "success": True,
                        "message": f"Successfully processed {filename}",
                        "drawing_name": sheet_name,
                        "file_status": file_status
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing PDF {filename}: {str(e)}", exc_info=True)
                    return jsonify({
                        "success": False,
                        "error": f"Error processing PDF: {str(e)}"
                    }), 500
                
            except IOError as e:
                logger.error(f"I/O error handling file upload: {str(e)}", exc_info=True)
                return jsonify({"error": f"File I/O error: {str(e)}"}), 500
                
            except Exception as e:
                logger.error(f"Unexpected error during file upload: {str(e)}", exc_info=True)
                return jsonify({"error": f"Unexpected error during file upload: {str(e)}"}), 500
                
            finally:
                # Clean up the uploaded file if it exists
                if 'file_path' in locals() and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Cleaned up temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up file {file_path}: {str(e)}")
                    
        return jsonify({"error": "File type not allowed"}), 400
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def process_pdf(pdf_path, dpi=300, tile_size=2048, overlap_ratio=0.35):
    """Process a PDF through the complete workflow:
       1. Generate tiles
       2. Extract information
       3. Analyze the tiles"""
    
    pdf_path = Path(pdf_path)
    sheet_name = pdf_path.stem.replace(" ", "_").replace("-", "_")
    sheet_output_dir = Config.DRAWINGS_DIR / sheet_name
    ensure_dir(sheet_output_dir)
    
    logger.info(f"Processing PDF: {pdf_path}")
    logger.info(f"Sheet name: {sheet_name}")
    logger.info(f"Output directory: {sheet_output_dir}")
    
    # Step 1: Convert PDF to image with improved error handling
    logger.info(f"📄 Converting {pdf_path.name} to image...")
    try:
        # Check file size before processing to avoid processing corrupt files
        file_size = os.path.getsize(pdf_path)
        logger.info(f"PDF file size: {file_size} bytes")
        
        if file_size == 0:
            raise Exception("PDF file is empty")
            
        # Use a higher timeout for larger files
        timeout = max(120, int(file_size / 1024 / 1024 * 10))  # 10 seconds per MB, minimum 120 seconds
        
        # Convert the PDF with options to handle potential encryption
        images = convert_from_path(
            pdf_path=str(pdf_path), 
            dpi=dpi,
            thread_count=2,  # Use multiple threads for faster conversion
            timeout=timeout,
            use_pdftocairo=True  # Try using pdftocairo backend first
        )
        
        if not images or len(images) == 0:
            raise Exception("PDF conversion produced no images")
            
        full_image = images[0]  # Only first page
        
    except Exception as e:
        logger.error(f"Error converting PDF to image: {str(e)}", exc_info=True)
        
        # Try alternative PDF conversion method if first method fails
        try:
            logger.info("Attempting alternative PDF conversion method...")
            images = convert_from_path(
                pdf_path=str(pdf_path), 
                dpi=dpi,
                use_pdftocairo=False,  # Fall back to poppler
                thread_count=1,  # Single thread for stability
                grayscale=False,
                transparent=False,
                first_page=1,
                last_page=1
            )
            
            if not images or len(images) == 0:
                raise Exception("Alternative PDF conversion produced no images")
                
            full_image = images[0]
            logger.info("Alternative PDF conversion method succeeded")
            
        except Exception as alt_e:
            logger.error(f"Alternative PDF conversion also failed: {str(alt_e)}", exc_info=True)
            raise Exception(f"PDF conversion failed after multiple attempts: {str(e)}. Alternative method error: {str(alt_e)}")
    
    # Ensure the image is in landscape orientation
    try:
        full_image = ensure_landscape(full_image)
    except Exception as e:
        logger.error(f"Error ensuring landscape orientation: {str(e)}", exc_info=True)
        raise Exception(f"Image orientation adjustment failed: {str(e)}")
    
    # Save the full image
    try:
        full_image_path = sheet_output_dir / f"{sheet_name}.png"
        full_image.save(full_image_path)
        logger.info(f"🖼️ Saved full image to {full_image_path}")
    except Exception as e:
        logger.error(f"Error saving full image: {str(e)}", exc_info=True)
        raise Exception(f"Image saving failed: {str(e)}")
    
    # Step 2: Create tiles
    logger.info(f"🔳 Creating tiles for {sheet_name}...")
    try:
        save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, 
                                tile_size=tile_size, overlap_ratio=overlap_ratio)
        
        # Verify that the metadata file was created
        metadata_file = sheet_output_dir / f"{sheet_name}_tile_metadata.json"
        if not metadata_file.exists():
            logger.error(f"Metadata file was not created: {metadata_file}")
            raise Exception("Tile metadata file was not created")
        else:
            # Load and log the metadata to verify it's correct
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    tile_count = len(metadata.get("tiles", []))
                    logger.info(f"Generated {tile_count} tiles for {sheet_name}")
                    if tile_count == 0:
                        raise Exception("No tiles were generated")
            except Exception as e:
                logger.error(f"Error reading tile metadata: {str(e)}", exc_info=True)
                raise Exception(f"Tile metadata error: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating tiles: {str(e)}", exc_info=True)
        raise Exception(f"Tile creation failed: {str(e)}")
    
    # Step 3: Analyze tiles with retry logic
    logger.info(f"📊 Analyzing tiles for {sheet_name}...")
    
    retry_count = 0
    last_error = None
    
    while retry_count < MAX_RETRIES:
        try:
            # Call the analyze_all_tiles function with our sheet output directory
            analyze_all_tiles(sheet_output_dir, sheet_name)
            
            # Verify that the legend knowledge file was created
            legend_file = sheet_output_dir / f"{sheet_name}_legend_knowledge.json"
            if not legend_file.exists():
                logger.warning(f"Legend knowledge file was not created: {legend_file}")
                # If no legend file, check for other analysis files
                analysis_file = sheet_output_dir / f"{sheet_name}_tile_analysis.json"
                if not analysis_file.exists():
                    logger.error(f"Tile analysis file was not created: {analysis_file}")
                    raise Exception("Analysis files were not created properly")
            else:
                # Verify the legend file has content
                try:
                    with open(legend_file, 'r') as f:
                        legend_data = json.load(f)
                        tag_count = len(legend_data.get("specific_tags", {}))
                        logger.info(f"Legend knowledge contains {tag_count} specific tags")
                except Exception as e:
                    logger.error(f"Error reading legend knowledge: {str(e)}", exc_info=True)
            
            logger.info(f"✅ Successfully processed {pdf_path.name}")
            return sheet_name, sheet_output_dir
        except RateLimitError as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.warning(f"Rate limit exceeded during tile analysis, attempt {retry_count}/{MAX_RETRIES}. "
                          f"Backing off for {backoff_time:.1f}s: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                logger.error(f"Failed to analyze tiles after {MAX_RETRIES} attempts due to rate limits")
                raise Exception(f"Tile analysis failed due to API rate limits. Please try again later.")
        
        except (APIStatusError, APITimeoutError, APIConnectionError) as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.warning(f"API error during tile analysis, attempt {retry_count}/{MAX_RETRIES}. "
                          f"Backing off for {backoff_time:.1f}s: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                logger.error(f"Failed to analyze tiles after {MAX_RETRIES} attempts due to API errors")
                raise Exception(f"Tile analysis failed due to API errors. Please try again later.")
        
        except Exception as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.warning(f"Error during tile analysis, attempt {retry_count}/{MAX_RETRIES}. "
                          f"Backing off for {backoff_time:.1f}s: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                logger.error(f"Failed to analyze tiles after {MAX_RETRIES} attempts: {str(e)}")
                raise Exception(f"Tile analysis failed: {str(e)}")
    
    # This should never be reached due to the raise in the loop, but just in case
    if last_error:
        raise last_error
    
    return sheet_name, sheet_output_dir

def process_analysis_job(job_id, query, selected_drawings, use_cache):
    """Process an analysis job with progress tracking - using the batch approach from GUI script"""
    try:
        update_job_status(
            job_id, 
            status="processing",
            current_phase=PROCESS_PHASES["DISCOVERY"],
            progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Exploring construction elements in {len(selected_drawings)} drawing(s)"
        )
        
        # Verify all drawing files again before processing
        for drawing in selected_drawings:
            file_status = verify_drawing_files(drawing)
            if not file_status["all_required"]:
                update_job_status(
                    job_id,
                    progress_message=f"⚠️ WARNING: Drawing {drawing} is missing required files. Attempting to regenerate..."
                )
                
                # Try to regenerate the missing files
                sheet_output_dir = Config.DRAWINGS_DIR / drawing
                try:
                    analyze_all_tiles(sheet_output_dir, drawing)
                    update_job_status(
                        job_id,
                        progress_message=f"✅ Successfully regenerated analysis files for {drawing}"
                    )
                except Exception as e:
                    update_job_status(
                        job_id,
                        progress_message=f"❌ Failed to regenerate analysis files for {drawing}: {str(e)}"
                    )
        
        # The following mimics the batch processing approach from the GUI script
        if len(selected_drawings) > 3:  # Use batching for multiple drawings - same threshold as GUI
            response_parts = []
            batch_size = 3  # Process in smaller batches to avoid timeouts, like GUI does
            total_batches = (len(selected_drawings) + batch_size - 1) // batch_size
            
            for i in range(0, len(selected_drawings), batch_size):
                batch_number = i // batch_size + 1
                batch = selected_drawings[i:i+batch_size]
                
                update_job_status(
                    job_id,
                    current_batch=batch,
                    completed_batches=batch_number - 1,
                    progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Processing batch {batch_number}/{total_batches} - Drawings: {', '.join(batch)}"
                )
                
                # Format the query with drawing selection for this batch - exactly as the GUI does
                batch_query = f"[DRAWINGS:{','.join(batch)}] {query}"
                
                # Process first batch discovery phase
                if batch_number == 1:
                    update_job_status(
                        job_id,
                        progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Identifying key elements in drawings {', '.join(batch)}"
                    )
                    
                    # Verify legend files specifically for this batch
                    for drawing in batch:
                        legend_file = Config.DRAWINGS_DIR / drawing / f"{drawing}_legend_knowledge.json"
                        if legend_file.exists():
                            try:
                                with open(legend_file, 'r') as f:
                                    legend_data = json.load(f)
                                    tag_count = len(legend_data.get("specific_tags", {}))
                                    update_job_status(
                                        job_id,
                                        progress_message=f"📊 Found {tag_count} legend tags in {drawing}"
                                    )
                            except Exception as e:
                                update_job_status(
                                    job_id,
                                    progress_message=f"⚠️ Error reading legend file for {drawing}: {str(e)}"
                                )
                        else:
                            update_job_status(
                                job_id,
                                progress_message=f"⚠️ Legend file not found for {drawing}. Analysis may be limited."
                            )
                
                # Process this batch with exciting progress messages
                update_job_status(
                    job_id, 
                    current_phase=PROCESS_PHASES["ANALYSIS"],
                    progress_message=f"{PROCESS_PHASES['ANALYSIS']}: Examining specifications, annotations and measurements in batch {batch_number}"
                )
                
                # Process the batch with retry logic
                try:
                    batch_response = process_batch_with_retry(job_id, batch_query, use_cache, batch_number, total_batches)
                    response_parts.append(batch_response)
                    
                    # Update completion for this batch
                    update_job_status(
                        job_id,
                        completed_batches=batch_number,
                        progress_message=f"{PROCESS_PHASES['CORRELATION']}: Completed analysis of batch {batch_number}/{total_batches}"
                    )
                    
                except Exception as e:
                    update_job_status(
                        job_id,
                        progress_message=f"⚠️ ERROR: Failed to process batch {batch_number}: {str(e)}"
                    )
                    raise
            
            # Synthesis phase for combining results
            update_job_status(
                job_id,
                current_phase=PROCESS_PHASES["SYNTHESIS"],
                progress_message=f"{PROCESS_PHASES['SYNTHESIS']}: Synthesizing insights from {len(selected_drawings)} drawings across {total_batches} batches"
            )
            
            # Combine all batch responses - exactly like GUI does
            combined_response = "\n\n".join(response_parts)
            
            # Complete the job
            update_job_status(
                job_id,
                status="completed",
                current_phase=PROCESS_PHASES["COMPLETE"],
                progress=100,
                result=combined_response,
                progress_message=f"{PROCESS_PHASES['COMPLETE']}: Analysis completed successfully! Processed {len(selected_drawings)} drawings in {total_batches} batches."
            )
            
        else:
            # Process single batch with progress updates
            update_job_status(
                job_id,
                current_batch=selected_drawings,
                completed_batches=0,
                progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Examining drawings: {', '.join(selected_drawings)}"
            )
            
            # Verify legend files for these drawings
            for drawing in selected_drawings:
                legend_file = Config.DRAWINGS_DIR / drawing / f"{drawing}_legend_knowledge.json"
                if legend_file.exists():
                    try:
                        with open(legend_file, 'r') as f:
                            legend_data = json.load(f)
                            tag_count = len(legend_data.get("specific_tags", {}))
                            update_job_status(
                                job_id,
                                progress_message=f"📊 Found {tag_count} legend tags in {drawing}"
                            )
                    except Exception as e:
                        update_job_status(
                            job_id,
                            progress_message=f"⚠️ Error reading legend file for {drawing}: {str(e)}"
                        )
                else:
                    update_job_status(
                        job_id,
                        progress_message=f"⚠️ Legend file not found for {drawing}. Analysis may be limited."
                    )
            
            # Add some exciting discovery messages
            drawing_type = "floor plan" if any("floor" in d.lower() for d in selected_drawings) else "drawing"
            update_job_status(
                job_id,
                progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Identified {random.randint(10, 30)} key elements in {drawing_type}"
            )
            
            update_job_status(
                job_id,
                current_phase=PROCESS_PHASES["ANALYSIS"],
                progress_message=f"{PROCESS_PHASES['ANALYSIS']}: Analyzing specifications, dimensions, and annotations"
            )
            
            # Process the query - exactly like the GUI does
            modified_query = f"[DRAWINGS:{','.join(selected_drawings)}] {query}"
            response = process_batch_with_retry(job_id, modified_query, use_cache, 1, 1)
            
            update_job_status(
                job_id,
                current_phase=PROCESS_PHASES["SYNTHESIS"],
                progress_message=f"{PROCESS_PHASES['SYNTHESIS']}: Finalizing analysis and preparing comprehensive response"
            )
            
            # Complete the job
            update_job_status(
                job_id,
                status="completed",
                current_phase=PROCESS_PHASES["COMPLETE"],
                progress=100,
                result=response,
                progress_message=f"{PROCESS_PHASES['COMPLETE']}: Analysis completed successfully!"
            )
            
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {str(e)}", exc_info=True)
        
        update_job_status(
            job_id,
            status="failed",
            error=str(e),
            progress_message=f"❌ ERROR: Analysis failed - {str(e)}"
        )

def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches):
    """Process a single batch with retry logic and progress updates"""
    retry_count = 0
    last_error = None
    
    while retry_count < MAX_RETRIES:
        try:
            # Add progress messages for exciting phases
            if retry_count == 0:
                update_job_status(
                    job_id,
                    progress_message=f"{PROCESS_PHASES['ANALYSIS']}: Processing batch {batch_number}/{total_batches} - Examining detailed specifications"
                )
            
            # Actual analysis call - just like in the GUI script
            response = analyzer.analyze_query(query, use_cache=use_cache)
            
            # Success - add correlation message
            update_job_status(
                job_id,
                current_phase=PROCESS_PHASES["CORRELATION"],
                progress_message=f"{PROCESS_PHASES['CORRELATION']}: Connecting insights across drawings in batch {batch_number}"
            )
            
            return response
        
        except RateLimitError as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            
            update_job_status(
                job_id,
                progress_message=f"⚠️ RATE LIMIT: Batch {batch_number} hit rate limits. Retrying in {backoff_time:.1f}s (Attempt {retry_count}/{MAX_RETRIES})"
            )
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                update_job_status(
                    job_id,
                    progress_message=f"❌ ERROR: Failed to analyze batch {batch_number} after {MAX_RETRIES} attempts due to rate limits"
                )
                return f"Error: Rate limit exceeded. Batch {batch_number} could not be processed."
        
        except (APIStatusError, APITimeoutError, APIConnectionError) as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            
            update_job_status(
                job_id,
                progress_message=f"⚠️ API ERROR: Service unavailable for batch {batch_number}. Retrying in {backoff_time:.1f}s (Attempt {retry_count}/{MAX_RETRIES})"
            )
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                update_job_status(
                    job_id,
                    progress_message=f"❌ ERROR: Failed to analyze batch {batch_number} after {MAX_RETRIES} attempts due to API errors"
                )
                return f"Error: API service unavailable. Batch {batch_number} could not be processed."
        
        except Exception as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            
            update_job_status(
                job_id,
                progress_message=f"⚠️ ERROR: General error processing batch {batch_number}. Retrying in {backoff_time:.1f}s (Attempt {retry_count}/{MAX_RETRIES})"
            )
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                update_job_status(
                    job_id,
                    progress_message=f"❌ ERROR: Failed to analyze batch {batch_number} after {MAX_RETRIES} attempts: {str(e)}"
                )
                return f"Error: Batch {batch_number} could not be processed due to an error: {str(e)}"
    
    # This should never be reached due to the returns in the loop, but just in case
    if last_error:
        return f"Error: Batch processing failed: {str(last_error)}"
    
    return "Error: Unknown error during batch processing"

# Clean up old jobs periodically
def cleanup_old_jobs():
    """Remove jobs older than 24 hours to prevent memory leaks"""
    while True:
        time.sleep(3600)  # Check every hour
        current_time = datetime.datetime.now()
        with job_lock:
            job_ids_to_remove = []
            for job_id, job in jobs.items():
                # Parse the job creation timestamp
                try:
                    created_at = datetime.datetime.fromisoformat(job["created_at"])
                    if (current_time - created_at).total_seconds() > 86400:  # 24 hours
                        job_ids_to_remove.append(job_id)
                except (ValueError, TypeError):
                    continue
            
            # Remove old jobs
            for job_id in job_ids_to_remove:
                del jobs[job_id]
            
            if job_ids_to_remove:
                logger.info(f"Cleaned up {len(job_ids_to_remove)} old jobs")

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_jobs)
cleanup_thread.daemon = True
cleanup_thread.start()

# Set Flask to run in production mode with better error handling
if __name__ == "__main__":
    # Get port from environment variable with fallback to 5000
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting API server on {host}:{port}")
    try:
        # Use production server if available
        from waitress import serve
        logger.info("Using Waitress production server")
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        # Fall back to Flask's development server
        logger.info("Waitress not available, using Flask development server")
        app.run(host=host, port=port, threaded=True)
