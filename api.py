# --- Filename: api.py (Backend Flask Application - Enhanced Delete Logging) ---

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import sys
import logging
import shutil # Ensure shutil is imported
import time
import random
import uuid
import threading
import datetime
from pathlib import Path
import werkzeug.utils
from PIL import Image
from anthropic import RateLimitError, APIStatusError, APITimeoutError, APIConnectionError
import json
import gc
from urllib.parse import unquote

# --- Initialize all potentially imported names to None ---
ConstructionAnalyzer, Config, DrawingManager = None, None, None
ensure_dir, save_tiles_with_metadata, ensure_landscape = None, None, None
convert_from_path = None
analyze_all_tiles = None

# IMPORTANT: Fix for decompression bomb warning
IMAGE_MAX_PIXELS = int(os.environ.get('IMAGE_MAX_PIXELS', 200000000))
Image.MAX_IMAGE_PIXELS = IMAGE_MAX_PIXELS
if IMAGE_MAX_PIXELS != 200000000:
     print(f"Warning: Image.MAX_IMAGE_PIXELS set to {IMAGE_MAX_PIXELS}")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - API - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[ logging.StreamHandler(sys.stdout) ]
)
logger = logging.getLogger(__name__)

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.join(current_dir, 'modules')
if current_dir not in sys.path: sys.path.append(current_dir)
if modules_dir not in sys.path: sys.path.append(modules_dir)
logger.info(f"Python sys.path includes: {current_dir}, {modules_dir}")

# --- ISOLATED IMPORTS ---
logger.info("--- Starting Custom Module Imports ---")
try: # Import 1
    logger.info("Attempting import: construction_drawing_analyzer_rev2_wow_rev6")
    from construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    logger.info("SUCCESS: Imported from construction_drawing_analyzer_rev2_wow_rev6")
except Exception as e: logger.error(f"FAILED Import from construction_drawing_analyzer_rev2_wow_rev6: {e}", exc_info=True)
try: # Import 2
    logger.info("Attempting import: tile_generator_wow")
    from tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    logger.info("SUCCESS: Imported from tile_generator_wow")
except Exception as e: logger.error(f"FAILED Import from tile_generator_wow: {e}", exc_info=True)
try: # Import 3
    logger.info("Attempting import: pdf2image")
    from pdf2image import convert_from_path
    logger.info("SUCCESS: Imported from pdf2image")
except Exception as e: logger.error(f"FAILED Import from pdf2image: {e}", exc_info=True)
try: # Import 4
    logger.info("Attempting import: extract_tile_entities_wow_rev4")
    from extract_tile_entities_wow_rev4 import analyze_all_tiles
    logger.info("SUCCESS: Imported from extract_tile_entities_wow_rev4")
except Exception as e: logger.error(f"FAILED Import from extract_tile_entities_wow_rev4: {e}", exc_info=True)
logger.info("--- Finished Custom Module Imports ---")

# --- Post-Import Checks ---
if ConstructionAnalyzer and Config and DrawingManager: logger.info("ConstructionAnalyzer, Config, DrawingManager appear loaded.")
else: logger.error("One or more from construction_drawing_analyzer failed to load.")
if ensure_dir and save_tiles_with_metadata and ensure_landscape: logger.info("tile_generator_wow functions appear loaded.")
else: logger.error("One or more from tile_generator_wow failed to load.")
if convert_from_path: logger.info("pdf2image function appears loaded.")
else: logger.error("pdf2image failed to load.")
if analyze_all_tiles and callable(analyze_all_tiles): logger.info("Global 'analyze_all_tiles' function is available and callable after imports.")
else: logger.error("Global 'analyze_all_tiles' function is NOT available or not callable after import block.")


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured.")

# --- Configuration and Path Setup ---
fallback_dir_default = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
UPLOAD_FOLDER_DEFAULT = fallback_dir_default / 'uploads'
TEMP_UPLOAD_FOLDER_DEFAULT = UPLOAD_FOLDER_DEFAULT / 'temp_uploads'
DRAWINGS_OUTPUT_DIR_DEFAULT = fallback_dir_default / 'processed_drawings'
MEMORY_STORE_DIR_DEFAULT = fallback_dir_default / 'memory_store'
UPLOAD_FOLDER = UPLOAD_FOLDER_DEFAULT
TEMP_UPLOAD_FOLDER = TEMP_UPLOAD_FOLDER_DEFAULT
DRAWINGS_OUTPUT_DIR = DRAWINGS_OUTPUT_DIR_DEFAULT
MEMORY_STORE_DIR = MEMORY_STORE_DIR_DEFAULT

try:
    base_dir = os.environ.get('APP_BASE_DIR', '/app')
    if Config:
        Config.configure(base_dir=base_dir)
        logger.info(f"Configured base directory using Config: {Config.BASE_DIR}")
        UPLOAD_FOLDER = os.path.join(Config.BASE_DIR, 'uploads')
        TEMP_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'temp_uploads')
        DRAWINGS_OUTPUT_DIR = Path(Config.DRAWINGS_DIR).resolve()
        MEMORY_STORE_DIR = Path(Config.MEMORY_STORE).resolve()
    else:
        logger.error("Config class not available from import, using fallback paths.")
        logger.warning(f"Using fallback directories based on: {fallback_dir_default}")
except Exception as e:
    logger.error(f"CRITICAL: Error during Config setup: {e}", exc_info=True)
    UPLOAD_FOLDER = UPLOAD_FOLDER_DEFAULT
    TEMP_UPLOAD_FOLDER = TEMP_UPLOAD_FOLDER_DEFAULT
    DRAWINGS_OUTPUT_DIR = DRAWINGS_OUTPUT_DIR_DEFAULT
    MEMORY_STORE_DIR = MEMORY_STORE_DIR_DEFAULT
    logger.warning(f"Using fallback directories due to error, based on: {fallback_dir_default}")

logger.info(f"Final Uploads directory: {UPLOAD_FOLDER}")
logger.info(f"Final Temporary uploads directory: {TEMP_UPLOAD_FOLDER}")
logger.info(f"Final Processed drawings directory: {DRAWINGS_OUTPUT_DIR}")
logger.info(f"Final Memory store directory: {MEMORY_STORE_DIR}")

# Flask App Config
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 100)) * 1024 * 1024
logger.info(f"Max upload size: {app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024} MB")

# Processing Settings
MAX_RETRIES = int(os.environ.get('API_MAX_RETRIES', 5))
MAX_BACKOFF = int(os.environ.get('API_MAX_BACKOFF_SECONDS', 120))
ANALYSIS_BATCH_SIZE = int(os.environ.get('ANALYSIS_BATCH_SIZE', 3))

# Job Tracking
jobs = {}
job_lock = threading.Lock()

# Process phases
PROCESS_PHASES = { # Keep definitions }

# Create required directories
try: # Keep directory creation logic
except Exception as e: logger.error(f"Error creating required directories: {e}", exc_info=True)

# Create global instances
analyzer = None
drawing_manager = None
try: # Keep instantiation logic
except Exception as e: # Keep error handling
# Initialize Transformer (optional)
intent_classifier = None
try: # Keep transformer logic
except Exception as e: logger.warning(f"Failed to load transformer: {e}. Intent filtering disabled.")

# --- Utility Functions ---
def allowed_file(filename): # Keep implementation
def verify_drawing_files(drawing_name): # Keep implementation

# --- Job Management Functions ---
def update_job_status(job_id, **kwargs): # Keep implementation
def create_analysis_job(query, drawings, use_cache): # Keep implementation

# --- PDF Processing (Now runs in background) ---
def process_pdf_job(temp_file_path, job_id, original_filename, dpi=300, tile_size=2048, overlap_ratio=0.35): # Keep implementation

# --- Flask Routes ---
@app.route('/health', methods=['GET']) # Keep implementation
@app.route('/drawings', methods=['GET']) # Keep implementation

# --- REVISED /delete_drawing ENDPOINT ---
@app.route('/delete_drawing/<path:drawing_name>', methods=['DELETE'])
def delete_drawing_route(drawing_name):
    """Deletes a drawing directory and its contents with enhanced logging."""
    if drawing_manager is None or not DRAWINGS_OUTPUT_DIR:
        logger.error(f"Delete request failed: Drawing manager or DRAWINGS_OUTPUT_DIR not initialized.")
        return jsonify({"success": False, "error": "Drawing manager not initialized"}), 500

    decoded_drawing_name = None # Initialize for logging in case of early failure
    target_dir = None
    try:
        decoded_drawing_name = unquote(drawing_name)
        logger.info(f"DELETE Request received for drawing: '{decoded_drawing_name}'")

        # Construct the target directory path using resolved base path
        target_dir = (DRAWINGS_OUTPUT_DIR / decoded_drawing_name).resolve()
        logger.info(f"DELETE Target resolved path: {target_dir}")

        # --- Security Check ---
        if not target_dir.is_relative_to(DRAWINGS_OUTPUT_DIR.resolve()):
             logger.error(f"SECURITY ALERT: Attempted deletion outside designated directory. Target='{target_dir}', Base='{DRAWINGS_OUTPUT_DIR.resolve()}'")
             return jsonify({"success": False, "error": "Invalid drawing path"}), 400

        # --- Existence and Type Check ---
        if not target_dir.exists():
            logger.warning(f"DELETE Request: Directory not found for '{decoded_drawing_name}' at '{target_dir}'")
            # Even if not found, return success=false but a specific error message
            return jsonify({"success": False, "error": f"Drawing '{decoded_drawing_name}' not found on server."}), 404

        if not target_dir.is_dir():
            logger.error(f"DELETE Request: Target path exists but is not a directory: '{target_dir}'")
            return jsonify({"success": False, "error": "Target path is not a directory"}), 400

        # --- Attempt Deletion ---
        logger.info(f"Attempting to delete directory recursively: '{target_dir}'")
        shutil.rmtree(target_dir)
        logger.info(f"Successfully deleted directory: '{target_dir}'")

        # --- Success Response ---
        return jsonify({"success": True, "message": f"Drawing '{decoded_drawing_name}' deleted successfully."}), 200

    except OSError as os_err:
        # Specific OS-level errors (permissions, etc.)
        logger.error(f"OS error deleting directory '{target_dir}' for drawing '{decoded_drawing_name}': [Errno {os_err.errno}] {os_err.strerror}", exc_info=False) # Log errno too
        return jsonify({"success": False, "error": f"Server OS error during deletion: {os_err.strerror}"}), 500
    except Exception as e:
        # Catch-all for other unexpected errors during the process
        logger.error(f"Unexpected error deleting directory '{target_dir}' for drawing '{decoded_drawing_name}': {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Unexpected server error during deletion: {str(e)}"}), 500
# --- END REVISED /delete_drawing ---

@app.route('/analyze', methods=['POST']) # Keep implementation
@app.route('/job-status/<job_id>', methods=['GET']) # Keep implementation
@app.route('/jobs', methods=['GET']) # Keep implementation
@app.route('/upload', methods=['POST']) # Keep implementation

# --- Background Job Processors ---
def process_analysis_job(job_id): # Keep implementation
def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches): # Keep implementation

# --- Cleanup Thread ---
def cleanup_old_jobs(): # Keep implementation

cleanup_thread = threading.Thread(target=cleanup_old_jobs, name="JobCleanupThread"); cleanup_thread.daemon = True; cleanup_thread.start()

# --- Server Start ---
if __name__ == "__main__": # Keep implementation
    # (Waitress/Flask dev server logic)
