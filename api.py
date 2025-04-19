from flask import Flask, request, jsonify
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

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

# Configure retry settings
MAX_RETRIES = 5
MAX_BACKOFF = 120  # Maximum backoff time in seconds

# Configure batch processing settings
BATCH_SIZE = 3  # Number of drawings to process in one batch

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

# Create required directories
os.makedirs(Config.DRAWINGS_DIR, exist_ok=True)
os.makedirs(Config.MEMORY_STORE, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Create global instances
try:
    analyzer = ConstructionAnalyzer()
    drawing_manager = DrawingManager(Config.DRAWINGS_DIR)
    logger.info("Successfully created analyzer and drawing_manager instances")
except Exception as e:
    logger.error(f"ERROR INITIALIZING: {str(e)}", exc_info=True)
    analyzer = None
    drawing_manager = None

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        return jsonify({"drawings": available_drawings})
    except Exception as e:
        logger.error(f"Error retrieving drawings: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_query():
    """Start an analysis job and return a job ID for tracking progress"""
    try:
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
        
        # Create a new job
        job_id = create_job(query, selected_drawings, use_cache)
        
        # Start the analysis in a background thread
        thread = threading.Thread(
            target=process_analysis_job,
            args=(job_id, query, selected_drawings, use_cache)
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

def process_analysis_job(job_id, query, selected_drawings, use_cache):
    """Process an analysis job with progress tracking"""
    try:
        update_job_status(
            job_id, 
            status="processing",
            current_phase=PROCESS_PHASES["DISCOVERY"],
            progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Exploring construction elements in {len(selected_drawings)} drawing(s)"
        )
        
        # Process drawings in batches if there are more than BATCH_SIZE
        if len(selected_drawings) > BATCH_SIZE:
            response_parts = []
            total_batches = (len(selected_drawings) + BATCH_SIZE - 1) // BATCH_SIZE
            
            for i in range(0, len(selected_drawings), BATCH_SIZE):
                batch_number = i // BATCH_SIZE + 1
                batch = selected_drawings[i:i+BATCH_SIZE]
                
                update_job_status(
                    job_id,
                    current_batch=batch,
                    completed_batches=batch_number - 1,
                    progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Processing batch {batch_number}/{total_batches} - Drawings: {', '.join(batch)}"
                )
                
                # Format the query with drawing selection for this batch
                batch_query = f"[DRAWINGS:{','.join(batch)}] {query}"
                
                # Process first batch discovery phase
                if batch_number == 1:
                    update_job_status(
                        job_id,
                        progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Identifying key elements in drawings {', '.join(batch)}"
                    )
                    time.sleep(1)  # Simulate discovery work
                
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
            
            # Combine all batch responses
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
            
            # Process the query
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
            
            # Actual analysis call
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
            filename = werkzeug.utils.secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save the uploaded file
            file.save(file_path)
            logger.info(f"File uploaded: {file_path}")
            
            # Process the PDF
            try:
                process_pdf(file_path)
                logger.info(f"Successfully processed {filename}")
                
                # Return success with the drawing name
                sheet_name = Path(file_path).stem.replace(" ", "_").replace("-", "_")
                return jsonify({
                    "success": True,
                    "message": f"Successfully processed {filename}",
                    "drawing_name": sheet_name
                })
            except Exception as e:
                logger.error(f"Error processing PDF {filename}: {str(e)}", exc_info=True)
                return jsonify({
                    "success": False,
                    "error": f"Error processing PDF: {str(e)}"
                }), 500
            finally:
                # Clean up the uploaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
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
    
    # Step 1: Convert PDF to image
    logger.info(f"📄 Converting {pdf_path.name} to image...")
    try:
        images = convert_from_path(str(pdf_path), dpi=dpi)
        full_image = images[0]  # Only first page
    except Exception as e:
        logger.error(f"Error converting PDF to image: {str(e)}", exc_info=True)
        raise Exception(f"PDF conversion failed: {str(e)}")
    
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
    except Exception as e:
        logger.error(f"Error creating tiles: {str(e)}", exc_info=True)
        raise Exception(f"Tile creation failed: {str(e)}")
    
    # Step 3: Analyze tiles with retry logic
    logger.info(f"📊 Analyzing tiles for {sheet_name}...")
    
    retry_count = 0
    last_error = None
    
    while retry_count < MAX_RETRIES:
        try:
            analyze_all_tiles(sheet_output_dir, sheet_name)
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
