# --- Filename: api.py (Backend Flask Application - Corrected Indentation v3) ---

# --- Keep all imports and initial setup the same as the previous "Corrected Syntax v2" version ---
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
import json
import gc
from urllib.parse import unquote

ConstructionAnalyzer, Config, DrawingManager = None, None, None
ensure_dir, save_tiles_with_metadata, ensure_landscape = None, None, None
convert_from_path = None
analyze_all_tiles = None
IMAGE_MAX_PIXELS = int(os.environ.get('IMAGE_MAX_PIXELS', 200000000))
Image.MAX_IMAGE_PIXELS = IMAGE_MAX_PIXELS
if IMAGE_MAX_PIXELS != 200000000: print(f"Warning: Image.MAX_IMAGE_PIXELS set to {IMAGE_MAX_PIXELS}")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - API - %(levelname)s - [%(threadName)s] - %(message)s', handlers=[ logging.StreamHandler(sys.stdout) ])
logger = logging.getLogger(__name__)
current_dir = os.path.dirname(os.path.abspath(__file__)); modules_dir = os.path.join(current_dir, 'modules')
if current_dir not in sys.path: sys.path.append(current_dir)
if modules_dir not in sys.path: sys.path.append(modules_dir)
logger.info(f"Python sys.path includes: {current_dir}, {modules_dir}")
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
# Post-Import Checks (keep as before)
if ConstructionAnalyzer and Config and DrawingManager: logger.info("ConstructionAnalyzer, Config, DrawingManager appear loaded.") # etc...
if ensure_dir and save_tiles_with_metadata and ensure_landscape: logger.info("tile_generator_wow functions appear loaded.") # etc...
if convert_from_path: logger.info("pdf2image function appears loaded.") # etc...
if analyze_all_tiles and callable(analyze_all_tiles): logger.info("Global 'analyze_all_tiles' function is available and callable.") # etc...

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured.")
# Configuration and Path Setup (keep as before)
try: # Config setup ...
except Exception as e: # Fallback config ...
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 100)) * 1024 * 1024
logger.info(f"Max upload size: {app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024} MB")
MAX_RETRIES = int(os.environ.get('API_MAX_RETRIES', 5))
MAX_BACKOFF = int(os.environ.get('API_MAX_BACKOFF_SECONDS', 120))
ANALYSIS_BATCH_SIZE = int(os.environ.get('ANALYSIS_BATCH_SIZE', 3))
jobs = {}; job_lock = threading.Lock()
PROCESS_PHASES = { # Keep definitions as before }
# Create required directories (keep as before)
try: # Making directories...
except Exception as e: logger.error(f"Error creating required directories: {e}", exc_info=True)
# Create global instances (keep as before)
analyzer = None; drawing_manager = None
try: # Instantiation...
except Exception as e: # Error handling...
# Initialize Transformer (keep as before)
intent_classifier = None
try: # Transformer loading...
except Exception as e: logger.warning(f"Failed to load transformer: {e}. Intent filtering disabled.")

# --- Utility Functions ---
def allowed_file(filename): # Keep as before
def verify_drawing_files(drawing_name): # Keep Corrected Version from v2

# --- Job Management Functions ---
def update_job_status(job_id, **kwargs): # Keep Corrected Version from v2
def create_analysis_job(query, drawings, use_cache): # Keep Corrected Version from v2

# --- PDF Processing (Now runs in background) ---
def process_pdf_job(temp_file_path, job_id, original_filename,
                    dpi=300, tile_size=2048, overlap_ratio=0.35):
    global analyze_all_tiles, convert_from_path, ensure_landscape, save_tiles_with_metadata, ensure_dir

    pdf_path_obj = Path(temp_file_path)
    safe_original_filename = werkzeug.utils.secure_filename(original_filename)
    sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name
    start_time = time.time()
    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} (Sheet Name: {sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")

    try:
        if not ensure_dir: raise ImportError("ensure_dir function not available due to import error.")
        ensure_dir(sheet_output_dir); logger.info(f"[Job {job_id}] Output directory ensured.")

        # --- 1. PDF Conversion ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        full_image = None
        if not convert_from_path: raise ImportError("convert_from_path function not available due to import error.")
        try: # Try main conversion (pdftocairo)
            file_size = os.path.getsize(temp_file_path); logger.info(f"[Job {job_id}] PDF file size: {file_size / 1024 / 1024:.2f} MB")
            if file_size == 0: raise Exception("PDF file is empty")
            logger.info(f"[Job {job_id}] Using DPI: {dpi}"); poppler_path = os.environ.get('POPPLER_PATH')
            conversion_start_time = time.time()
            images = convert_from_path(str(temp_file_path), dpi=dpi, fmt='png', thread_count=int(os.environ.get('PDF2IMAGE_THREADS', 2)), timeout=max(300, int(file_size / 1024 / 1024 * 15)), use_pdftocairo=True, poppler_path=poppler_path)
            conversion_time = time.time() - conversion_start_time
            if not images: raise Exception("PDF conversion (pdftocairo) produced no images")
            full_image = images[0]; logger.info(f"[Job {job_id}] PDF conversion (pdftocairo) successful in {conversion_time:.2f}s.")
        except Exception as e:
            # Main conversion failed, try alternative
            logger.error(f"[Job {job_id}] Error converting PDF (pdftocairo): {str(e)}", exc_info=False) # Don't need full trace here
            update_job_status(job_id, progress_message=f"⚠️ PDF conversion error (pdftocairo): {str(e)}. Trying legacy...")
            try: # Try alternative conversion
                 conversion_start_time = time.time()
                 images = convert_from_path(str(temp_file_path), dpi=dpi, fmt='png', thread_count=1, use_pdftocairo=False, poppler_path=poppler_path)
                 conversion_time = time.time() - conversion_start_time
                 if not images: raise Exception("Alternative PDF conversion produced no images")
                 full_image = images[0]
                 logger.info(f"[Job {job_id}] Alternative PDF conversion successful in {conversion_time:.2f}s.")
            # --- CORRECTED BLOCK ---
            except Exception as alt_e:
                 # This block requires indentation and code
                 logger.error(f"[Job {job_id}] Alternative PDF conversion also failed: {str(alt_e)}", exc_info=True)
                 # Raise a new exception to stop processing for this job
                 raise Exception(f"PDF conversion failed completely. Last error: {str(alt_e)}")
            # --- END CORRECTION ---

        # --- 2. Image Orientation & Saving ---
        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation & saving...")
        if not ensure_landscape: raise ImportError("ensure_landscape function not available due to import error.")
        try: # Orientation logic
             save_start_time = time.time(); full_image = ensure_landscape(full_image); full_image_path = sheet_output_dir / f"{sheet_name}.png"
             full_image.save(str(full_image_path)); save_time = time.time() - save_start_time
             logger.info(f"[Job {job_id}] Oriented and saved full image to {full_image_path} in {save_time:.2f}s")
        except Exception as e: logger.error(f"[Job {job_id}] Error ensuring landscape or saving full image: {str(e)}", exc_info=True); raise Exception(f"Image orientation/saving failed: {str(e)}")

        # --- 3. Tiling ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        if not save_tiles_with_metadata: raise ImportError("save_tiles_with_metadata function not available due to import error.")
        try: # Tiling logic
            tile_start_time = time.time(); save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, tile_size=tile_size, overlap_ratio=overlap_ratio)
            tile_time = time.time() - tile_start_time; metadata_file = sheet_output_dir / f"{sheet_name}_tile_metadata.json"
            if not metadata_file.exists(): raise Exception("Tile metadata file was not created")
            with open(metadata_file, 'r') as f: metadata = json.load(f)
            tile_count = len(metadata.get("tiles", []))
            if tile_count == 0: raise Exception("No tiles were generated")
            logger.info(f"[Job {job_id}] Generated {tile_count} tiles for {sheet_name} in {tile_time:.2f}s")
            update_job_status(job_id, progress=35, progress_message=f"✅ Generated {tile_count} tiles.")
        except Exception as e: logger.error(f"[Job {job_id}] Error creating tiles: {str(e)}", exc_info=True); raise Exception(f"Tile creation failed: {str(e)}")
        del full_image; gc.collect(); logger.info(f"[Job {job_id}] Full image object released from memory.")

        # --- 4. Tile Analysis ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (API calls)...")
        if not analyze_all_tiles: raise ImportError("analyze_all_tiles function not available due to import error.")
        else: logger.info(f"[Job {job_id}] 'analyze_all_tiles' function confirmed available for call.")
        # (Keep analysis loop as before)
        retry_count = 0 # ... rest of analysis loop ...

        # --- Final Update ---
        # (Keep final update logic as before)

    except ImportError as imp_err: # Catch specific import errors raised in the checks
         total_time = time.time() - start_time
         logger.error(f"[Job {job_id}] Processing failed due to missing function after {total_time:.2f}s: {imp_err}", exc_info=False)
         update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(imp_err), progress_message=f"❌ Processing failed due to import error: {imp_err}")
    except Exception as e: # Catch other errors
        total_time = time.time() - start_time
        logger.error(f"[Job {job_id}] Processing failed for {original_filename} after {total_time:.2f}s: {str(e)}", exc_info=True)
        update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(e), progress_message=f"❌ Processing failed after {total_time:.2f}s. Error: {str(e)}")
    finally: # Cleanup
        if os.path.exists(temp_file_path):
             try: os.remove(temp_file_path); logger.info(f"[Job {job_id}] Cleaned up temporary upload file.")
             except Exception as clean_e: logger.warning(f"[Job {job_id}] Failed to clean up temp file: {clean_e}")


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
# (Keep process_analysis_job and process_batch_with_retry as before)
def process_analysis_job(job_id): # Keep as before
def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches): # Keep as before

# --- Cleanup Thread ---
def cleanup_old_jobs(): # Keep as before

cleanup_thread = threading.Thread(target=cleanup_old_jobs, name="JobCleanupThread"); cleanup_thread.daemon = True; cleanup_thread.start()

# --- Server Start ---
if __name__ == "__main__": # Keep as before
    # (Waitress/Flask dev server logic)
