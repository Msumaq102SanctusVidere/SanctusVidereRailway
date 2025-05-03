from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import logging
import threading
import uuid
import json
import time
import shutil
from pathlib import Path
import werkzeug.utils

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - API - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Add paths for importing modules
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.join(current_dir, 'modules')
if current_dir not in sys.path: sys.path.append(current_dir)
if modules_dir not in sys.path: sys.path.append(modules_dir)

# Direct imports from foundational scripts
logger.info("Importing foundational scripts...")
try:
    # Import tile generator
    from tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    logger.info("Successfully imported tile_generator_wow")
except Exception as e:
    logger.error(f"Failed to import tile_generator_wow: {e}")
    ensure_dir, save_tiles_with_metadata, ensure_landscape = None, None, None

try:
    # Import PDF converter
    from pdf2image import convert_from_path
    logger.info("Successfully imported pdf2image")
except Exception as e:
    logger.error(f"Failed to import pdf2image: {e}")
    convert_from_path = None

try:
    # Import tile analyzer
    from extract_tile_entities_wow_rev4 import analyze_all_tiles
    logger.info("Successfully imported extract_tile_entities_wow_rev4")
except Exception as e:
    logger.error(f"Failed to import extract_tile_entities_wow_rev4: {e}")
    analyze_all_tiles = None

try:
    # Import drawing analyzer
    from construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    logger.info("Successfully imported construction_drawing_analyzer_rev2_wow_rev6")
except Exception as e:
    logger.error(f"Failed to import construction_drawing_analyzer_rev2_wow_rev6: {e}")
    ConstructionAnalyzer, Config, DrawingManager = None, None, None

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("Flask app initialized with CORS")

# Configuration
base_dir = os.environ.get('APP_BASE_DIR', '/app')
OUTPUT_DIR = os.path.join(base_dir, "tiles_output")
ALLOWED_EXTENSIONS = {'pdf'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB limit

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.info(f"Ensured output directory exists: {OUTPUT_DIR}")

# Initialize Config if available
if Config:
    Config.configure(base_dir=base_dir)
    logger.info(f"Configured base directory: {Config.BASE_DIR}")

# Create global analyzer and drawing manager instances
analyzer = None
drawing_manager = None
if ConstructionAnalyzer and Config:
    try:
        analyzer = ConstructionAnalyzer()
        logger.info("Created ConstructionAnalyzer instance")
    except Exception as e:
        logger.error(f"Failed to create ConstructionAnalyzer: {e}")

if DrawingManager:
    try:
        drawing_manager = DrawingManager(OUTPUT_DIR)
        logger.info(f"Created DrawingManager instance with output dir: {OUTPUT_DIR}")
    except Exception as e:
        logger.error(f"Failed to create DrawingManager: {e}")

# Simple job tracking (would use a database in production)
jobs = {}

def allowed_file(filename):
    """Check if filename has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_job_status(job_id, status, progress=0, phase=None, result=None, error=None, message=None):
    """Update job status in memory (would use a database in production)"""
    if job_id not in jobs:
        jobs[job_id] = {
            "id": job_id,
            "status": "created",
            "progress": 0,
            "phase": None,
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": None,
            "error": None,
            "progress_messages": []
        }
    
    jobs[job_id]["status"] = status
    jobs[job_id]["progress"] = progress
    jobs[job_id]["updated_at"] = time.time()
    
    if phase:
        jobs[job_id]["phase"] = phase
    if result:
        jobs[job_id]["result"] = result
    if error:
        jobs[job_id]["error"] = error
    if message:
        jobs[job_id]["progress_messages"] = jobs[job_id].get("progress_messages", []) + [message]
    
    logger.info(f"Updated job {job_id}: status={status}, progress={progress}, phase={phase}")

def process_pdf_file(pdf_path, job_id, original_filename):
    """Process PDF file using the tile generator and tile analyzer directly"""
    try:
        if not all([ensure_dir, save_tiles_with_metadata, ensure_landscape, convert_from_path, analyze_all_tiles]):
            raise ImportError("Required functions not available. Check imports.")
        
        update_job_status(job_id, "processing", 5, "initializing", 
                         message="Starting PDF processing")
        
        # Extract sheet name from original filename
        sheet_name = Path(original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
        sheet_output_dir = Path(OUTPUT_DIR) / sheet_name
        
        # Ensure output directory exists
        ensure_dir(sheet_output_dir)
        logger.info(f"Created output directory: {sheet_output_dir}")
        
        # Convert PDF to image (just like in tile_generator_wow.py)
        update_job_status(job_id, "processing", 10, "converting", 
                         message="Converting PDF to image")
        
        images = convert_from_path(str(pdf_path), dpi=300)
        if not images:
            raise Exception("PDF conversion produced no images")
        
        full_image = images[0]  # First page only
        logger.info("Successfully converted PDF to image")
        
        # Ensure landscape orientation
        update_job_status(job_id, "processing", 20, "orienting", 
                         message="Setting image orientation")
        
        full_image = ensure_landscape(full_image)
        full_image_path = sheet_output_dir / f"{sheet_name}.png"
        full_image.save(str(full_image_path))
        logger.info(f"Saved oriented image to {full_image_path}")
        
        # Generate tiles
        update_job_status(job_id, "processing", 30, "tiling", 
                         message="Creating image tiles")
        
        save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name)
        logger.info("Generated tiles with metadata")
        
        # Free up memory
        del full_image
        
        # Process tiles with analyzer
        update_job_status(job_id, "processing", 50, "analyzing", 
                         message="Analyzing tiles")
        
        analyze_all_tiles(sheet_folder=sheet_output_dir, sheet_name=sheet_name)
        logger.info("Completed tile analysis")
        
        # Complete the job
        update_job_status(job_id, "completed", 100, "complete", 
                         result={"drawing_name": sheet_name},
                         message="Processing completed successfully")
        
        logger.info(f"Successfully processed {sheet_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing PDF: {e}", exc_info=True)
        update_job_status(job_id, "failed", 0, "failed", 
                         error=str(e),
                         message=f"Processing failed: {str(e)}")
        return False

def process_analysis(job_id, query, drawings, use_cache):
    """Process a drawing analysis query using ConstructionAnalyzer directly"""
    try:
        if not analyzer:
            raise ImportError("ConstructionAnalyzer not available. Check imports.")
        
        update_job_status(job_id, "processing", 10, "initializing", 
                         message="Starting analysis")
        
        # REMOVE THIS LINE:
        # formatted_query = f"[DRAWINGS:{','.join(drawings)}] {query}"
        
        logger.info(f"Processing query with drawings {drawings}: {query}")
        
        # CHANGE THIS LINE TO:
        # Call analyze_query directly with explicit drawings parameter
        from construction_drawing_analyzer_rev2_wow_rev6 import extract_drawings_from_query
        response = analyzer.analyze_query(query, use_cache=use_cache, specified_drawings=drawings)
        
        # Complete the job
        update_job_status(job_id, "completed", 100, "complete", 
                         result=response,
                         message="Analysis completed successfully")
        
        logger.info(f"Successfully analyzed query: {query[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error analyzing query: {e}", exc_info=True)
        update_job_status(job_id, "failed", 0, "failed", 
                         error=str(e),
                         message=f"Analysis failed: {str(e)}")
        return False

# --- API Endpoints ---

@app.route('/health', methods=['GET'])
def health_check():
    """Check the health of the API and its components"""
    status = {
        "status": "ok",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "components": {
            "tile_generator": all([ensure_dir, save_tiles_with_metadata, ensure_landscape]),
            "pdf_converter": convert_from_path is not None,
            "tile_analyzer": analyze_all_tiles is not None,
            "drawing_analyzer": analyzer is not None,
            "drawing_manager": drawing_manager is not None
        },
        "paths": {
            "output_dir": OUTPUT_DIR
        }
    }
    
    # If any component is missing, change status
    if not all(status["components"].values()):
        status["status"] = "degraded"
    
    return jsonify(status)

@app.route('/drawings', methods=['GET'])
def get_drawings():
    """Get list of available drawings"""
    if not drawing_manager:
        return jsonify({"error": "Drawing manager not available"}), 500
    
    try:
        # Direct call to drawing_manager's method
        drawings = drawing_manager.get_available_drawings()
        return jsonify({"drawings": drawings})
    except Exception as e:
        logger.error(f"Error listing drawings: {e}", exc_info=True)
        return jsonify({"error": f"Failed to list drawings: {str(e)}"}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
    
    try:
        # Create sanitized filename
        safe_filename = werkzeug.utils.secure_filename(file.filename)
        sheet_name = Path(safe_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
        
        # Create directory for this drawing
        sheet_dir = Path(OUTPUT_DIR) / sheet_name
        os.makedirs(sheet_dir, exist_ok=True)
        
        # Save uploaded file
        pdf_path = sheet_dir / f"{sheet_name}.pdf"
        file.save(pdf_path)
        logger.info(f"Saved uploaded file to {pdf_path}")
        
        # Create job
        job_id = str(uuid.uuid4())
        update_job_status(job_id, "queued", 0, "queued", 
                         message=f"Queued file for processing: {file.filename}")
        
        # Start processing in background thread
        thread = threading.Thread(
            target=process_pdf_file,
            args=(pdf_path, job_id, file.filename)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({"job_id": job_id})
        
    except Exception as e:
        logger.error(f"Error during upload: {e}", exc_info=True)
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

@app.route('/analyze', methods=['POST'])
def analyze_drawings():
    """Handle drawing analysis requests"""
    if not analyzer:
        return jsonify({"error": "Analyzer not available"}), 500
    
    try:
        # Parse request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        query = data.get('query', '').strip()
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        drawings = data.get('drawings', [])
        if not drawings:
            return jsonify({"error": "At least one drawing must be specified"}), 400
        
        use_cache = data.get('use_cache', True)
        
        # Create job
        job_id = str(uuid.uuid4())
        update_job_status(job_id, "queued", 0, "queued", 
                         message=f"Queued analysis: {query[:50]}...")
        
        # Start processing in background thread
        thread = threading.Thread(
            target=process_analysis,
            args=(job_id, query, drawings, use_cache)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({"job_id": job_id})
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        return jsonify({"error": f"Failed to start analysis: {str(e)}"}), 500

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get status of a job"""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    # Return the entire job object
    return jsonify(jobs[job_id])

@app.route('/delete_drawing/<path:drawing_name>', methods=['DELETE'])
def delete_drawing(drawing_name):
    """Delete a drawing and all its files"""
    if not drawing_manager:
        return jsonify({"error": "Drawing manager not available"}), 500
    
    try:
        # Path to drawing directory
        drawing_dir = Path(OUTPUT_DIR) / drawing_name
        
        # Check if drawing exists
        if not drawing_dir.is_dir():
            return jsonify({"error": f"Drawing {drawing_name} not found"}), 404
        
        # Delete the directory and all contents
        import shutil
        shutil.rmtree(drawing_dir)
        logger.info(f"Deleted drawing: {drawing_name}")
        
        return jsonify({"success": True, "message": f"Drawing {drawing_name} deleted"})
        
    except Exception as e:
        logger.error(f"Error deleting drawing {drawing_name}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to delete drawing: {str(e)}"}), 500

@app.route('/clear-cache', methods=['DELETE'])
def clear_cache():
    """Clear the memory cache used by the analyzer"""
    if not Config:
        return jsonify({"error": "Config not available"}), 500
    
    try:
        # Check if memory store directory exists
        if hasattr(Config, 'MEMORY_STORE') and Config.MEMORY_STORE:
            # Delete the directory and recreate it
            if os.path.exists(Config.MEMORY_STORE):
                shutil.rmtree(Config.MEMORY_STORE)
            
            # Recreate empty directory
            os.makedirs(Config.MEMORY_STORE, exist_ok=True)
            logger.info(f"Cleared cache at: {Config.MEMORY_STORE}")
            
            return jsonify({"success": True, "message": "Cache cleared successfully"})
        else:
            return jsonify({"error": "Memory store path not configured"}), 500
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}", exc_info=True)
        return jsonify({"error": f"Failed to clear cache: {str(e)}"}), 500

# --- Server Startup ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting API server on port {port} (debug={debug})")
    
    try:
        app.run(host='0.0.0.0', port=port, debug=debug)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
