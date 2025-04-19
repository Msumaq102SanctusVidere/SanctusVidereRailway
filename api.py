from flask import Flask, request, jsonify
import os
import sys
import logging
import shutil
import time
import random
from pathlib import Path
import werkzeug.utils
from PIL import Image
from anthropic import RateLimitError, APIStatusError, APITimeoutError, APIConnectionError

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
    """Analyze a query against selected drawings with batch processing"""
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
            
        logger.info(f"Processing query: {query}")
        logger.info(f"Selected drawings: {selected_drawings}")
        
        # Process drawings in batches if there are more than BATCH_SIZE
        if len(selected_drawings) > BATCH_SIZE:
            logger.info(f"Processing {len(selected_drawings)} drawings in batches of {BATCH_SIZE}")
            
            response_parts = []
            batch_count = 0
            total_batches = (len(selected_drawings) + BATCH_SIZE - 1) // BATCH_SIZE  # Ceiling division
            
            for i in range(0, len(selected_drawings), BATCH_SIZE):
                batch_count += 1
                batch = selected_drawings[i:i+BATCH_SIZE]
                logger.info(f"Processing batch {batch_count}/{total_batches}: {batch}")
                
                # Format the query with drawing selection for this batch
                batch_query = f"[DRAWINGS:{','.join(batch)}] {query}"
                
                # Process this batch with retry logic
                batch_response = process_batch_with_retry(batch_query, use_cache)
                response_parts.append(batch_response)
            
            # Combine all batch responses
            combined_response = "\n\n".join(response_parts)
            return jsonify({
                "result": combined_response,
                "query": query,
                "drawings": selected_drawings,
                "processed_in_batches": True,
                "batch_count": total_batches
            })
        else:
            # Process single batch directly
            modified_query = f"[DRAWINGS:{','.join(selected_drawings)}] {query}"
            response = process_batch_with_retry(modified_query, use_cache)
            
            return jsonify({
                "result": response,
                "query": query,
                "drawings": selected_drawings,
                "processed_in_batches": False
            })
            
    except Exception as e:
        logger.error(f"Error analyzing query: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

def process_batch_with_retry(query, use_cache):
    """Process a single batch with retry logic"""
    retry_count = 0
    last_error = None
    
    while retry_count < MAX_RETRIES:
        try:
            return analyzer.analyze_query(query, use_cache=use_cache)
        
        except RateLimitError as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.warning(f"Rate limit exceeded, attempt {retry_count}/{MAX_RETRIES}. "
                          f"Backing off for {backoff_time:.1f}s: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                logger.error(f"Failed to analyze batch after {MAX_RETRIES} attempts due to rate limits")
                return "Error: Rate limit exceeded. This batch could not be processed."
        
        except (APIStatusError, APITimeoutError, APIConnectionError) as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.warning(f"API error, attempt {retry_count}/{MAX_RETRIES}. "
                          f"Backing off for {backoff_time:.1f}s: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                logger.error(f"Failed to analyze batch after {MAX_RETRIES} attempts due to API errors")
                return "Error: API service unavailable. This batch could not be processed."
        
        except Exception as e:
            retry_count += 1
            last_error = e
            
            # Exponential backoff with jitter
            backoff_time = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.warning(f"General error, attempt {retry_count}/{MAX_RETRIES}. "
                          f"Backing off for {backoff_time:.1f}s: {str(e)}")
            
            if retry_count < MAX_RETRIES:
                time.sleep(backoff_time)
            else:
                logger.error(f"Failed to analyze batch after {MAX_RETRIES} attempts: {str(e)}")
                return f"Error: This batch could not be processed due to an error: {str(e)}"
    
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
