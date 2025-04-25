# --- Filename: api.py (Backend Flask Application - Corrected Indentation v4) ---

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
# Keep PIL and anthropic imports separate as they seem okay
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

# --- ISOLATED IMPORTS (Corrected Syntax) ---
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
# (Keep other post-import checks as before)
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
# Define fallback paths outside the try block in case Config fails completely
fallback_dir_default = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
UPLOAD_FOLDER_DEFAULT = fallback_dir_default / 'uploads'
TEMP_UPLOAD_FOLDER_DEFAULT = UPLOAD_FOLDER_DEFAULT / 'temp_uploads'
DRAWINGS_OUTPUT_DIR_DEFAULT = fallback_dir_default / 'processed_drawings'
MEMORY_STORE_DIR_DEFAULT = fallback_dir_default / 'memory_store'

try:
    base_dir = os.environ.get('APP_BASE_DIR', '/app')
    if Config: # Check if Config class was imported successfully
        Config.configure(base_dir=base_dir)
        logger.info(f"Configured base directory using Config: {Config.BASE_DIR}")
        UPLOAD_FOLDER = os.path.join(Config.BASE_DIR, 'uploads')
        TEMP_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'temp_uploads')
        DRAWINGS_OUTPUT_DIR = Path(Config.DRAWINGS_DIR).resolve()
        MEMORY_STORE_DIR = Path(Config.MEMORY_STORE).resolve()
    else:
        logger.error("Config class not available from import, using fallback paths.")
        raise ValueError("Config object not loaded due to import error.") # Trigger except block

# --- CORRECTED EXCEPTION BLOCK ---
except Exception as e:
    # This block MUST be indented
    logger.error(f"CRITICAL: Error during Config setup or Config class missing: {e}", exc_info=True)
    # Assign fallback paths
    UPLOAD_FOLDER = UPLOAD_FOLDER_DEFAULT
    TEMP_UPLOAD_FOLDER = TEMP_UPLOAD_FOLDER_DEFAULT
    DRAWINGS_OUTPUT_DIR = DRAWINGS_OUTPUT_DIR_DEFAULT
    MEMORY_STORE_DIR = MEMORY_STORE_DIR_DEFAULT
    logger.warning(f"Using fallback directories based on: {fallback_dir_default}")
# --- END CORRECTION ---

# Log final paths being used
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
PROCESS_PHASES = {
    "INIT": "🚀 INITIALIZATION", "QUEUED": "⏳ QUEUED", "CONVERTING": "📄 CONVERTING",
    "TILING": "🖼️ TILING", "ANALYZING_LEGENDS": "🔍 ANALYZING LEGENDS",
    "ANALYZING_CONTENT": "🧩 ANALYZING CONTENT", "COMPLETE": "✨ COMPLETE",
    "FAILED": "❌ FAILED", "DISCOVERY": "🔍 DISCOVERY", "ANALYSIS": "🧩 ANALYSIS",
    "CORRELATION": "🔗 CORRELATION", "SYNTHESIS": "💡 SYNTHESIS",
}

# Create required directories
try:
    if DRAWINGS_OUTPUT_DIR: os.makedirs(DRAWINGS_OUTPUT_DIR, exist_ok=True)
    if MEMORY_STORE_DIR: os.makedirs(MEMORY_STORE_DIR, exist_ok=True)
    if UPLOAD_FOLDER: os.makedirs(Path(UPLOAD_FOLDER), exist_ok=True)
    if TEMP_UPLOAD_FOLDER: os.makedirs(Path(TEMP_UPLOAD_FOLDER), exist_ok=True)
    logger.info(f"Ensured directories exist.")
except Exception as e:
    logger.error(f"Error creating required directories: {e}", exc_info=True)

# Create global instances (Check if imports succeeded)
analyzer = None
drawing_manager = None
try:
    if ConstructionAnalyzer: analyzer = ConstructionAnalyzer()
    else: logger.error("Skipping ConstructionAnalyzer instantiation - import failed.")
    if DrawingManager and DRAWINGS_OUTPUT_DIR: drawing_manager = DrawingManager(DRAWINGS_OUTPUT_DIR)
    else: logger.error("Skipping DrawingManager instantiation - import failed or DRAWINGS_OUTPUT_DIR missing.")
    if analyzer and drawing_manager: logger.info("Successfully created analyzer and drawing_manager instances.")
    else: logger.warning("Could not create analyzer and/or drawing_manager instances.")
except Exception as e:
    logger.error(f"ERROR INITIALIZING analyzer/drawing_manager: {str(e)}", exc_info=True)
    analyzer = None; drawing_manager = None

# Initialize Transformer (optional)
intent_classifier = None
try: # Transformer loading logic
    if os.environ.get('ENABLE_INTENT_CLASSIFIER', 'false').lower() == 'true':
        from transformers import pipeline; import torch; device = 0 if torch.cuda.is_available() else -1
        intent_classifier = pipeline("text-classification", model="distilbert-base-uncased", device=device, top_k=None)
        logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}.")
    else: logger.info("Intent classifier (transformer) is disabled.")
except Exception as e: logger.warning(f"Failed to load transformer: {e}. Intent filtering disabled.")

# --- Utility Functions ---
def allowed_file(filename): # Keep as before
def verify_drawing_files(drawing_name): # Keep Corrected Version from v2

# --- Job Management Functions ---
def update_job_status(job_id, **kwargs): # Keep Corrected Version from v2
def create_analysis_job(query, drawings, use_cache): # Keep Corrected Version from v2

# --- PDF Processing (Now runs in background) ---
def process_pdf_job(temp_file_path, job_id, original_filename, dpi=300, tile_size=2048, overlap_ratio=0.35): # Keep Corrected Version from v3

# --- Flask Routes ---
# (Keep all routes as before: /health, /drawings, /delete_drawing, /analyze, /job-status, /jobs, /upload)
@app.route('/health', methods=['GET']) # Keep as before
@app.route('/drawings', methods=['GET']) # Keep as before
@app.route('/delete_drawing/<path:drawing_name>', methods=['DELETE']) # Keep as before
@app.route('/analyze', methods=['POST']) # Keep as before
@app.route('/job-status/<job_id>', methods=['GET']) # Keep as before
@app.route('/jobs', methods=['GET']) # Keep as before
@app.route('/upload', methods=['POST']) # Keep as before


# --- Background Job Processors ---
def process_analysis_job(job_id): # Keep as before
def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches): # Keep as before

# --- Cleanup Thread ---
def cleanup_old_jobs(): # Keep as before

cleanup_thread = threading.Thread(target=cleanup_old_jobs, name="JobCleanupThread"); cleanup_thread.daemon = True; cleanup_thread.start()

# --- Server Start ---
if __name__ == "__main__": # Keep as before
    port = int(os.environ.get('PORT', 5000)); host = os.environ.get('HOST', '0.0.0.0')
    logger.info(f"Starting API server on {host}:{port}")
    try: # Waitress setup
        from waitress import serve
        # (Waitress config and serve call)
    except ImportError: # Flask dev server fallback
        # (Flask run call)
    except Exception as e: logger.critical(f"Failed to start server: {e}", exc_info=True); sys.exit("Server failed to start.")
