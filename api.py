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

# Function to patch the ConstructionAnalyzer to respect selected drawings
def patch_analyzer():
    """Monkey patch the ConstructionAnalyzer to respect selected drawings"""
    if not ConstructionAnalyzer:
        logger.error("Cannot patch analyzer: ConstructionAnalyzer not available")
        return
    
    # Store original method
    original_identify_relevant_drawings = ConstructionAnalyzer.identify_relevant_drawings
    
    def patched_identify_relevant_drawings(self, query):
        if query.startswith("[DRAWINGS:"):
            end_bracket = query.find("]")
            if end_bracket > 0:
                drawings_str = query[10:end_bracket]
                selected_drawings = [d.strip() for d in drawings_str.split(",")]
                self._original_query = query[end_bracket + 1:].strip()
                available_drawings = self.drawing_manager.get_available_drawings()
                filtered_drawings = [d for d in selected_drawings if d in available_drawings]
                logger.info(f"Using selected drawings: {filtered_drawings}")
                return filtered_drawings
        return original_identify_relevant_drawings(self, query)
    
    # Apply the patch
    ConstructionAnalyzer.identify_relevant_drawings = patched_identify_relevant_drawings
    logger.info("Patched ConstructionAnalyzer to respect drawing selections")

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
        # Apply the patch to make sure drawing selection works
        patch_analyzer()
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

# Dictionary to track active analysis threads
active_analysis_threads = {}

# --- User Path Helper Function ---
def get_user_path(user_id=None):
    """
    Get the base path for a specific user, or the global path if no user_id
    Creates the user directory if it doesn't exist
    """
    if not user_id:
        return OUTPUT_DIR
        
    # Sanitize user_id to ensure filesystem safety
    # Replace characters that could cause path issues
    safe_user_id = str(user_id).replace('|', '_').replace('/', '_')
    
    # Create user-specific path
    user_path = os.path.join(OUTPUT_DIR, safe_user_id)
    
    # Ensure directory exists
    os.makedirs(user_path, exist_ok=True)
    
    logger.info(f"Using user-specific path: {user_path}")
    
    return user_path

# Helper function to refresh DrawingManager
def refresh_drawing_manager():
    """Re-initialize the DrawingManager to refresh its internal state"""
    global drawing_manager, analyzer
    
    if not DrawingManager:
        logger.error("Cannot refresh drawing manager: DrawingManager not available")
        return False
    
    try:
        # Re-initialize the global DrawingManager
        drawing_manager = DrawingManager(OUTPUT_DIR)
        logger.info("Re-initialized DrawingManager to refresh available drawings")
        
        # Update the analyzer's DrawingManager reference to point to the new one
        if analyzer:
            analyzer.drawing_manager = drawing_manager
            logger.info("Updated analyzer's DrawingManager reference")
        
        return True
    except Exception as e:
        logger.error(f"Failed to refresh DrawingManager: {e}")
        return False

# Helper function to refresh user-specific DrawingManager
def refresh_user_drawing_manager(user_id):
    """
    Refresh a user-specific drawing manager or the global one if no user_id.
    Returns a temporary DrawingManager for the user's drawings.
    """
    if not DrawingManager:
        logger.error("Cannot refresh user drawing manager: DrawingManager not available")
        return None
    
    try:
        # Get path for this user
        user_path = get_user_path(user_id)
        
        # Create a temporary DrawingManager for this user's path
        temp_manager = DrawingManager(user_path)
        logger.info(f"Created temporary DrawingManager for user {user_id}")
        
        return temp_manager
    except Exception as e:
        logger.error(f"Failed to refresh user drawing manager: {e}")
        return None

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
            "progress_messages": [],
            "is_running": True  # Always start as running
        }
    
    jobs[job_id]["status"] = status
    jobs[job_id]["progress"] = progress
    jobs[job_id]["updated_at"] = time.time()
    
    # Only update is_running flag if explicitly set to a stopped state
    if status in ["completed", "failed"]:
        jobs[job_id]["is_running"] = False
    # Don't change the is_running flag for "queued" or "processing" - let it stay as initially set
    
    if phase:
        jobs[job_id]["phase"] = phase
    if result:
        jobs[job_id]["result"] = result
    if error:
        jobs[job_id]["error"] = error
    if message:
        jobs[job_id]["progress_messages"] = jobs[job_id].get("progress_messages", []) + [message]
    
    logger.info(f"Updated job {job_id}: status={status}, progress={progress}, phase={phase}, is_running={jobs[job_id]['is_running']}")

def process_pdf_file(pdf_path, job_id, original_filename):
    """Process PDF file using the tile generator and tile analyzer directly"""
    try:
        if not all([ensure_dir, save_tiles_with_metadata, ensure_landscape, convert_from_path, analyze_all_tiles]):
            raise ImportError("Required functions not available. Check imports.")
        
        update_job_status(job_id, "processing", 5, "initializing", 
                         message="Starting PDF processing")
        
        # Get user_id from the job data if available
        user_id = None
        if job_id in jobs and "user_id" in jobs[job_id]:
            user_id = jobs[job_id]["user_id"]
            logger.info(f"Processing PDF for user_id: {user_id}")
        
        # Extract sheet name from original filename
        sheet_name = Path(original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
        
        # Use user-specific path if available
        base_dir = get_user_path(user_id)
        sheet_output_dir = Path(base_dir) / sheet_name
        
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
        
        # Now that the upload is complete and all JSON files are saved,
        # refresh the appropriate DrawingManager to ensure it recognizes the new drawing
        if user_id:
            # Create a temporary manager for this user's drawings
            user_manager = refresh_user_drawing_manager(user_id)
            logger.info(f"Refreshed user-specific DrawingManager for user {user_id}")
        else:
            # Standard global refresh
            refresh_drawing_manager()
            logger.info(f"Refreshed global DrawingManager after completing processing")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing PDF: {e}", exc_info=True)
        update_job_status(job_id, "failed", 0, "failed", 
                         error=str(e),
                         message=f"Processing failed: {str(e)}")
        return False

def process_analysis(job_id, query, drawings, use_cache):
    """Process a drawing analysis query using ConstructionAnalyzer directly"""
    # Store the original drawing manager reference so we can restore it
    original_drawing_manager = None
    temp_drawing_manager = None
    
    try:
        # Check if job has been manually stopped by an explicit API call
        if job_id in jobs and jobs[job_id].get("status") == "stopped":
            logger.info(f"Job {job_id} was manually stopped before processing started")
            return False

        if not analyzer:
            raise ImportError("ConstructionAnalyzer not available. Check imports.")
        
        update_job_status(job_id, "processing", 10, "initializing", 
                         message="Starting analysis")
        
        # Get user_id from the job data if available
        user_id = None
        if job_id in jobs and "user_id" in jobs[job_id]:
            user_id = jobs[job_id]["user_id"]
            logger.info(f"Processing analysis for user_id: {user_id}")
            
            # If we have a user_id, we need to temporarily redirect the analyzer
            # to use the user's drawings directory
            if user_id and DrawingManager:
                # Get user-specific base path
                user_path = get_user_path(user_id)
                
                # Create a temporary drawing manager for this user
                temp_drawing_manager = DrawingManager(user_path)
                
                # Store reference to the current global manager
                original_drawing_manager = analyzer.drawing_manager
                
                # Temporarily replace the analyzer's drawing manager with our user-specific one
                analyzer.drawing_manager = temp_drawing_manager
                logger.info(f"Temporarily set analyzer to use user {user_id}'s drawings path")
        
        # Format the query with the drawings prefix
        formatted_query = f"[DRAWINGS:{','.join(drawings)}] {query}"
        
        logger.info(f"Processing query with drawings {drawings}: {query}")
        
        # Check if job has been manually stopped only if the status is explicitly "stopped"
        if job_id in jobs and jobs[job_id].get("status") == "stopped":
            logger.info(f"Job {job_id} was manually stopped during initialization")
            return False
        
        # Call analyze_query with the formatted query
        response = analyzer.analyze_query(formatted_query, use_cache=use_cache)
        
        # Check again after analysis if we should continue,
        # only if status is explicitly "stopped"
        if job_id in jobs and jobs[job_id].get("status") == "stopped":
            logger.info(f"Job {job_id} was manually stopped after completion but before finalization")
            return False
        
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
    finally:
        # Restore the original drawing manager if we replaced it
        if original_drawing_manager and analyzer:
            analyzer.drawing_manager = original_drawing_manager
            logger.info("Restored analyzer's original drawing manager")
        
        # Clean up thread tracking
        if job_id in active_analysis_threads:
            del active_analysis_threads[job_id]

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
        # Get user_id from request parameters
        user_id = request.args.get('user_id')
        
        if user_id:
            # Use temporary DrawingManager with user-specific path
            user_path = get_user_path(user_id)
            # Only if DrawingManager class is available
            if DrawingManager:
                temp_manager = DrawingManager(user_path)
                drawings = temp_manager.get_available_drawings()
                logger.info(f"Retrieved {len(drawings)} drawings for user {user_id}")
            else:
                # Fallback if DrawingManager is not available
                logger.error("DrawingManager not available, cannot get user drawings")
                drawings = []
        else:
            # Use global drawing manager (existing behavior)
            drawings = drawing_manager.get_available_drawings()
            logger.info(f"Retrieved {len(drawings)} drawings (no user specified)")
        
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
        # Get user_id from form data or query parameters
        user_id = request.form.get('user_id') or request.args.get('user_id')
        logger.info(f"Upload request for user_id: {user_id}")
        
        # Create sanitized filename
        safe_filename = werkzeug.utils.secure_filename(file.filename)
        sheet_name = Path(safe_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
        
        # Get user-specific base path
        base_dir = get_user_path(user_id)
        
        # Create directory for this drawing within the user directory
        sheet_dir = Path(base_dir) / sheet_name
        os.makedirs(sheet_dir, exist_ok=True)
        
        # Save uploaded file
        pdf_path = sheet_dir / f"{sheet_name}.pdf"
        file.save(pdf_path)
        logger.info(f"Saved uploaded file to {pdf_path} for user {user_id}")
        
        # Create job with user_id stored in it
        job_id = str(uuid.uuid4())
        update_job_status(job_id, "queued", 0, "queued", 
                         message=f"Queued file for processing: {file.filename}")
        
        # Store user_id in the job data for later use
        if job_id in jobs:
            jobs[job_id]["user_id"] = user_id
        
        # Start processing in background thread - note the process_pdf_file function
        # may need to be modified separately to handle user_id
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
        
        # Get user_id from JSON data or query parameters
        user_id = data.get('user_id') or request.args.get('user_id')
        
        # Create job - force is_running to True
        job_id = str(uuid.uuid4())
        update_job_status(job_id, "queued", 0, "queued", 
                         message=f"Queued analysis: {query[:50]}...")
        
        # Store user_id in the job for later reference
        if user_id:
            jobs[job_id]["user_id"] = user_id
            logger.info(f"Analysis request for user_id: {user_id}, drawings: {drawings}")
        
        # Double check is_running is set to True and can't be misinterpreted
        jobs[job_id]["is_running"] = True
        
        # Start processing in background thread
        thread = threading.Thread(
            target=process_analysis,
            args=(job_id, query, drawings, use_cache)
        )
        thread.daemon = True
        thread.start()
        
        # Track the analysis thread
        active_analysis_threads[job_id] = thread
        
        return jsonify({"job_id": job_id})
        
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        return jsonify({"error": f"Failed to start analysis: {str(e)}"}), 500

@app.route('/stop-analysis/<job_id>', methods=['POST'])
def stop_analysis(job_id):
    """Stop a running analysis job"""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    
    if job.get("status") in ["completed", "failed", "stopped"]:
        return jsonify({"message": f"Job {job_id} is already {job.get('status')}"})
    
    # Mark the job as stopped - set both status and is_running flag
    jobs[job_id]["status"] = "stopped"
    jobs[job_id]["is_running"] = False
    
    # Add a message about the stop
    if "progress_messages" not in jobs[job_id]:
        jobs[job_id]["progress_messages"] = []
    jobs[job_id]["progress_messages"].append("Analysis stopped by user request")
    
    logger.info(f"Stopped job {job_id} by user request")
    
    return jsonify({"success": True, "message": f"Job {job_id} has been stopped"})

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
        # Get user_id from query parameters
        user_id = request.args.get('user_id')
        
        # Get base path for this user
        base_dir = get_user_path(user_id)
        
        # Path to drawing directory within user's space
        drawing_dir = Path(base_dir) / drawing_name
        
        # Log the operation
        if user_id:
            logger.info(f"Attempting to delete drawing {drawing_name} for user {user_id}")
        else:
            logger.info(f"Attempting to delete drawing {drawing_name} from global space")
        
        # Check if drawing exists
        if not drawing_dir.is_dir():
            return jsonify({"error": f"Drawing {drawing_name} not found"}), 404
        
        # Delete the directory and all contents
        import shutil
        shutil.rmtree(drawing_dir)
        logger.info(f"Deleted drawing: {drawing_name}")
        
        # Refresh DrawingManager for the appropriate path
        if user_id and DrawingManager:
            # Refresh a temporary drawing manager for this user
            temp_manager = DrawingManager(base_dir)
            # If we have an analyzer, we might need to update it separately
            # This depends on how the rest of the system uses the global drawing_manager
        else:
            # Refresh the global drawing manager (original behavior)
            refresh_drawing_manager()
        
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
        # Get user_id from query parameters to potentially clear only user-specific cache
        user_id = request.args.get('user_id')
        
        # Check if memory store directory exists
        if hasattr(Config, 'MEMORY_STORE') and Config.MEMORY_STORE:
            if user_id:
                # Create user-specific memory store path
                user_memory_path = os.path.join(Config.MEMORY_STORE, safe_user_id) 
                
                # Check if it exists before trying to delete
                if os.path.exists(user_memory_path):
                    shutil.rmtree(user_memory_path)
                
                # Recreate empty directory
                os.makedirs(user_memory_path, exist_ok=True)
                logger.info(f"Cleared cache for user {user_id} at: {user_memory_path}")
            else:
                # Clear global cache (all users)
                if os.path.exists(Config.MEMORY_STORE):
                    shutil.rmtree(Config.MEMORY_STORE)
                
                # Recreate empty directory
                os.makedirs(Config.MEMORY_STORE, exist_ok=True)
                logger.info(f"Cleared all cache at: {Config.MEMORY_STORE}")
            
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
