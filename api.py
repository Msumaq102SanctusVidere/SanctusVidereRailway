# --- Filename: api.py (Backend Flask Application - Isolate Imports) ---

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
from PIL import Image # Keep this import separate as it seems okay
from anthropic import RateLimitError, APIStatusError, APITimeoutError, APIConnectionError # Keep separate
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

# Import 1: construction_drawing_analyzer
try:
    logger.info("Attempting import: construction_drawing_analyzer_rev2_wow_rev6")
    from construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer as CDA, Config as Cfg, DrawingManager as DM
    ConstructionAnalyzer, Config, DrawingManager = CDA, Cfg, DM # Assign if successful
    logger.info("SUCCESS: Imported from construction_drawing_analyzer_rev2_wow_rev6")
except ImportError as e:
    logger.error(f"FAILED Import from construction_drawing_analyzer_rev2_wow_rev6: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from construction_drawing_analyzer_rev2_wow_rev6: {e}", exc_info=True)

# Import 2: tile_generator
try:
    logger.info("Attempting import: tile_generator_wow")
    from tile_generator_wow import ensure_dir as ed, save_tiles_with_metadata as stwm, ensure_landscape as el
    ensure_dir, save_tiles_with_metadata, ensure_landscape = ed, stwm, el
    logger.info("SUCCESS: Imported from tile_generator_wow")
except ImportError as e:
    logger.error(f"FAILED Import from tile_generator_wow: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from tile_generator_wow: {e}", exc_info=True)

# Import 3: pdf2image
try:
    logger.info("Attempting import: pdf2image")
    from pdf2image import convert_from_path as cfp
    convert_from_path = cfp
    logger.info("SUCCESS: Imported from pdf2image")
except ImportError as e:
    logger.error(f"FAILED Import from pdf2image: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from pdf2image: {e}", exc_info=True)

# Import 4: extract_tile_entities
try:
    logger.info("Attempting import: extract_tile_entities_wow_rev4")
    from extract_tile_entities_wow_rev4 import analyze_all_tiles as aat
    analyze_all_tiles = aat
    logger.info("SUCCESS: Imported from extract_tile_entities_wow_rev4")
except ImportError as e:
    logger.error(f"FAILED Import from extract_tile_entities_wow_rev4: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from extract_tile_entities_wow_rev4: {e}", exc_info=True)

logger.info("--- Finished Custom Module Imports ---")

# --- Post-Import Checks (More specific) ---
if ConstructionAnalyzer and Config and DrawingManager:
    logger.info("ConstructionAnalyzer, Config, DrawingManager appear loaded.")
else:
    logger.error("One or more from construction_drawing_analyzer failed to load.")

if ensure_dir and save_tiles_with_metadata and ensure_landscape:
    logger.info("tile_generator_wow functions appear loaded.")
else:
    logger.error("One or more from tile_generator_wow failed to load.")

if convert_from_path:
    logger.info("pdf2image function appears loaded.")
else:
    logger.error("pdf2image failed to load.")

if analyze_all_tiles and callable(analyze_all_tiles):
     logger.info("Global 'analyze_all_tiles' function is available and callable after imports.")
else:
     logger.error("Global 'analyze_all_tiles' function is NOT available or not callable after import block.")
# --- End Post-Import Checks ---


app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured.")

# --- Configuration and Path Setup ---
# (Keep the robust version using Path objects from previous steps)
try:
    base_dir = os.environ.get('APP_BASE_DIR', '/app')
    if Config: # Check if Config was imported successfully
        Config.configure(base_dir=base_dir)
        logger.info(f"Configured base directory: {Config.BASE_DIR}")
        UPLOAD_FOLDER = os.path.join(Config.BASE_DIR, 'uploads')
        TEMP_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'temp_uploads')
        DRAWINGS_OUTPUT_DIR = Path(Config.DRAWINGS_DIR).resolve()
        MEMORY_STORE_DIR = Path(Config.MEMORY_STORE).resolve()
        logger.info(f"Uploads directory: {UPLOAD_FOLDER}")
        logger.info(f"Temporary uploads directory: {TEMP_UPLOAD_FOLDER}")
        logger.info(f"Processed drawings directory: {DRAWINGS_OUTPUT_DIR}")
        logger.info(f"Memory store directory: {MEMORY_STORE_DIR}")
    else:
        raise ValueError("Config object not loaded due to import error.") # Force fallback if Config missing
except Exception as e:
    logger.error(f"CRITICAL: Error configuring base directory/paths (possibly due to missing Config): {e}", exc_info=True)
    fallback_dir = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
    # Don't rely on Config here
    UPLOAD_FOLDER = fallback_dir / 'uploads'
    TEMP_UPLOAD_FOLDER = UPLOAD_FOLDER / 'temp_uploads'
    DRAWINGS_OUTPUT_DIR = fallback_dir / 'processed_drawings'
    MEMORY_STORE_DIR = fallback_dir / 'memory_store'
    logger.warning(f"Using fallback directories based on: {fallback_dir}")

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
PROCESS_PHASES = { # Keep as before }

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
    if ConstructionAnalyzer: # Check if class was imported
        analyzer = ConstructionAnalyzer()
    else:
        logger.error("Skipping ConstructionAnalyzer instantiation - import failed.")

    if DrawingManager and DRAWINGS_OUTPUT_DIR: # Check if class was imported
        drawing_manager = DrawingManager(DRAWINGS_OUTPUT_DIR)
    else:
         logger.error("Skipping DrawingManager instantiation - import failed or DRAWINGS_OUTPUT_DIR missing.")

    if analyzer and drawing_manager:
        logger.info("Successfully created analyzer and drawing_manager instances.")
    else:
        logger.warning("Could not create analyzer and/or drawing_manager instances.")
except Exception as e:
    logger.error(f"ERROR INITIALIZING analyzer/drawing_manager: {str(e)}", exc_info=True)
    analyzer = None # Reset on error
    drawing_manager = None

# Initialize Transformer (optional)
intent_classifier = None
# (Keep transformer loading logic as before)
try:
    if os.environ.get('ENABLE_INTENT_CLASSIFIER', 'false').lower() == 'true':
        from transformers import pipeline
        import torch
        device = 0 if torch.cuda.is_available() else -1
        intent_classifier = pipeline("text-classification", model="distilbert-base-uncased", device=device, top_k=None)
        logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}.")
    else: logger.info("Intent classifier (transformer) is disabled.")
except Exception as e: logger.warning(f"Failed to load transformer: {e}. Intent filtering disabled.")


# --- Utility Functions ---
# (allowed_file, verify_drawing_files - keep as before)
def allowed_file(filename): # Keep as before
def verify_drawing_files(drawing_name): # Keep as before

# --- Job Management Functions ---
# (update_job_status, create_analysis_job - keep as before)
def update_job_status(job_id, **kwargs): # Keep as before
def create_analysis_job(query, drawings, use_cache): # Keep as before


# --- PDF Processing (Now runs in background) ---
def process_pdf_job(temp_file_path, job_id, original_filename,
                    dpi=300, tile_size=2048, overlap_ratio=0.35):
    # Use potentially None functions - check before calling
    global analyze_all_tiles, convert_from_path, ensure_landscape, save_tiles_with_metadata, ensure_dir

    # ... (setup sheet_name, sheet_output_dir as before) ...
    pdf_path_obj = Path(temp_file_path)
    safe_original_filename = werkzeug.utils.secure_filename(original_filename)
    sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name
    start_time = time.time()
    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} (Sheet Name: {sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")

    try:
        # Check directory function before calling
        if not ensure_dir: raise Exception("ensure_dir function not available due to import error.")
        ensure_dir(sheet_output_dir)
        logger.info(f"[Job {job_id}] Output directory ensured: {sheet_output_dir}")

        # --- 1. PDF Conversion ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        full_image = None
        if not convert_from_path: raise Exception("pdf2image function (convert_from_path) not available due to import error.")
        # (Keep pdf conversion try/except block as before, using convert_from_path variable)
        try:
            file_size = os.path.getsize(temp_file_path); #... rest of conversion logic ...
        except Exception as e: #... rest of conversion error handling ...

        # --- 2. Image Orientation & Saving ---
        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation & saving...")
        if not ensure_landscape: raise Exception("ensure_landscape function not available due to import error.")
        # (Keep orientation try/except block as before, using ensure_landscape variable)
        try:
            save_start_time = time.time(); full_image = ensure_landscape(full_image); #... rest of saving logic ...
        except Exception as e: #... rest of saving error handling ...

        # --- 3. Tiling ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        if not save_tiles_with_metadata: raise Exception("save_tiles_with_metadata function not available due to import error.")
        # (Keep tiling try/except block as before, using save_tiles_with_metadata variable)
        try:
            tile_start_time = time.time(); save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, #... rest of tiling logic ...
        except Exception as e: #... rest of tiling error handling ...
        del full_image; gc.collect(); logger.info(f"[Job {job_id}] Full image object released from memory.")


        # --- 4. Tile Analysis ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (API calls)...")

        # --- Check is now simpler ---
        if not analyze_all_tiles: # Check if it was successfully imported/assigned
             logger.error(f"[Job {job_id}] 'analyze_all_tiles' function is not available at the point of execution.")
             raise Exception("Tile analysis function (analyze_all_tiles) is not available.")
        else:
             logger.info(f"[Job {job_id}] 'analyze_all_tiles' function confirmed available for call.")

        # (Keep analysis loop try/except block as before, calling analyze_all_tiles)
        retry_count = 0 #... rest of analysis loop ...

        # --- Final Update ---
        # (Keep final update logic as before)

    except Exception as e:
        # (Keep main exception handling as before)
    finally:
        # (Keep finally block as before)


# --- Flask Routes ---
# (Keep /health, /drawings, /delete_drawing, /analyze, /job-status, /jobs, /upload as before)
# Make sure checks for `analyzer` and `drawing_manager` being None are kept

# --- Background Job Processors ---
# (Keep process_analysis_job and process_batch_with_retry as before)
# Make sure checks for `analyzer` being None are kept

# --- Cleanup Thread ---
# (Keep cleanup_old_jobs as before)

# --- Server Start ---
# (Keep server start logic as before)
