# --- Filename: api.py (Backend Flask Application - Corrected Syntax v2) ---

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

# Import 1: construction_drawing_analyzer
try:
    logger.info("Attempting import: construction_drawing_analyzer_rev2_wow_rev6")
    from construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    logger.info("SUCCESS: Imported from construction_drawing_analyzer_rev2_wow_rev6")
except ImportError as e:
    logger.error(f"FAILED Import from construction_drawing_analyzer_rev2_wow_rev6: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from construction_drawing_analyzer_rev2_wow_rev6: {e}", exc_info=True)

# Import 2: tile_generator
try:
    logger.info("Attempting import: tile_generator_wow")
    from tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    logger.info("SUCCESS: Imported from tile_generator_wow")
except ImportError as e:
    logger.error(f"FAILED Import from tile_generator_wow: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from tile_generator_wow: {e}", exc_info=True)

# Import 3: pdf2image
try:
    logger.info("Attempting import: pdf2image")
    from pdf2image import convert_from_path
    logger.info("SUCCESS: Imported from pdf2image")
except ImportError as e:
    logger.error(f"FAILED Import from pdf2image: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from pdf2image: {e}", exc_info=True)

# Import 4: extract_tile_entities
try:
    logger.info("Attempting import: extract_tile_entities_wow_rev4")
    from extract_tile_entities_wow_rev4 import analyze_all_tiles
    logger.info("SUCCESS: Imported from extract_tile_entities_wow_rev4")
except ImportError as e:
    logger.error(f"FAILED Import from extract_tile_entities_wow_rev4: {e}", exc_info=True)
except Exception as e:
    logger.error(f"FAILED (Other Exception) during import from extract_tile_entities_wow_rev4: {e}", exc_info=True)

logger.info("--- Finished Custom Module Imports ---")

# --- Post-Import Checks (More specific) ---
if ConstructionAnalyzer and Config and DrawingManager: logger.info("ConstructionAnalyzer, Config, DrawingManager appear loaded.")
else: logger.error("One or more from construction_drawing_analyzer failed to load.")
if ensure_dir and save_tiles_with_metadata and ensure_landscape: logger.info("tile_generator_wow functions appear loaded.")
else: logger.error("One or more from tile_generator_wow failed to load.")
if convert_from_path: logger.info("pdf2image function appears loaded.")
else: logger.error("pdf2image failed to load.")
if analyze_all_tiles and callable(analyze_all_tiles): logger.info("Global 'analyze_all_tiles' function is available and callable after imports.")
else: logger.error("Global 'analyze_all_tiles' function is NOT available or not callable after import block.")


app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured.")

# --- Configuration and Path Setup ---
try:
    base_dir = os.environ.get('APP_BASE_DIR', '/app')
    if Config:
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
        raise ValueError("Config object not loaded due to import error.")
except Exception as e:
    logger.error(f"CRITICAL: Error configuring base directory/paths (possibly due to missing Config): {e}", exc_info=True)
    fallback_dir = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
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
try:
    if os.environ.get('ENABLE_INTENT_CLASSIFIER', 'false').lower() == 'true':
        from transformers import pipeline; import torch; device = 0 if torch.cuda.is_available() else -1
        intent_classifier = pipeline("text-classification", model="distilbert-base-uncased", device=device, top_k=None)
        logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}.")
    else: logger.info("Intent classifier (transformer) is disabled.")
except Exception as e: logger.warning(f"Failed to load transformer: {e}. Intent filtering disabled.")


# --- Utility Functions ---
def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- CORRECTED verify_drawing_files ---
def verify_drawing_files(drawing_name):
    """Verify that all necessary files exist for a processed drawing"""
    if not drawing_manager:
        logger.warning("Drawing manager not initialized, cannot verify files.")
        return {"all_required": False, "error": "Drawing manager not ready"}

    # Ensure DRAWINGS_OUTPUT_DIR is a Path object before constructing sub-path
    sheet_output_dir = Path(drawing_manager.drawings_dir) / drawing_name
    if not sheet_output_dir.is_dir(): # Check if it's actually a directory
         logger.warning(f"Verification failed: Output directory not found for {drawing_name} at {sheet_output_dir}")
         return {"all_required": False, "error": "Drawing directory not found"}

    # Define expected files (can be made more dynamic)
    # Use Path objects for checking existence
    expected = {
        "metadata": sheet_output_dir / f"{drawing_name}_tile_metadata.json",
        "tile_analysis": sheet_output_dir / f"{drawing_name}_tile_analysis.json",
        "legend_knowledge": sheet_output_dir / f"{drawing_name}_legend_knowledge.json",
        "drawing_goals": sheet_output_dir / f"{drawing_name}_drawing_goals.json",
        "general_notes": sheet_output_dir / f"{drawing_name}_general_notes_analysis.json",
        "elevation": sheet_output_dir / f"{drawing_name}_elevation_analysis.json",
        "detail": sheet_output_dir / f"{drawing_name}_detail_analysis.json",
    } # <-- Removed the problematic comment here
    status = {key: path.exists() for key, path in expected.items()}

    # Define what constitutes "all required" - adjust as needed
    has_analysis = (status.get("tile_analysis", False) or
                    status.get("general_notes", False) or
                    status.get("elevation", False) or
                    status.get("detail", False))

    status["all_required"] = status.get("metadata", False) and \
                             status.get("legend_knowledge", False) and \
                             has_analysis

    logger.info(f"File verification for {drawing_name}: {status}")
    return status
# --- END CORRECTION ---

# --- Job Management Functions ---
def update_job_status(job_id, **kwargs): # Keep as before
    # (Implementation from previous correct version)
    with job_lock:
        if job_id in jobs:
            job = jobs[job_id]
            if "progress_messages" not in job or not isinstance(job.get("progress_messages"), list):
                job["progress_messages"] = []
            new_message = kwargs.pop("progress_message", None)
            if new_message:
                 log_msg = f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - {new_message}"
                 job["progress_messages"].append(log_msg)
                 MAX_MESSAGES = 50
                 if len(job["progress_messages"]) > MAX_MESSAGES:
                     job["progress_messages"] = [job["progress_messages"][0]] + job["progress_messages"][- (MAX_MESSAGES - 1):]
            job.update(kwargs)
            job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z'
            log_update = {k:v for k,v in kwargs.items() if k not in ['result', 'progress_messages']}
            logger.info(f"Job {job_id} updated: Status='{job.get('status')}', Progress={job.get('progress', 0)}%, Details={log_update}")
        else:
            logger.warning(f"Attempted to update status for unknown job_id: {job_id}")

def create_analysis_job(query, drawings, use_cache): # Keep as before
    # (Implementation from previous correct version)
     job_id = str(uuid.uuid4())
     total_batches = (len(drawings) + ANALYSIS_BATCH_SIZE - 1) // ANALYSIS_BATCH_SIZE if drawings else 0
     with job_lock:
         jobs[job_id] = {
            "id": job_id, "type": "analysis", "query": query, "drawings": drawings,
            "use_cache": use_cache, "status": "queued",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
            "progress": 0, "total_batches": total_batches, "completed_batches": 0,
            "current_batch": None, "current_phase": PROCESS_PHASES["QUEUED"],
            "progress_messages": [f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - {PROCESS_PHASES['QUEUED']}: Analyze {len(drawings)} drawing(s)"],
            "result": None, "error": None
         }
     logger.info(f"Created analysis job {job_id} for query: {query[:50]}...")
     return job_id


# --- PDF Processing (Now runs in background) ---
def process_pdf_job(temp_file_path, job_id, original_filename,
                    dpi=300, tile_size=2048, overlap_ratio=0.35): # Keep as before
    # (Implementation from previous correct version, including checks for None functions)
    global analyze_all_tiles, convert_from_path, ensure_landscape, save_tiles_with_metadata, ensure_dir
    pdf_path_obj = Path(temp_file_path); safe_original_filename = werkzeug.utils.secure_filename(original_filename)
    sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name; start_time = time.time()
    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} (Sheet Name: {sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")
    try:
        if not ensure_dir: raise ImportError("ensure_dir function not available due to import error.")
        ensure_dir(sheet_output_dir); logger.info(f"[Job {job_id}] Output directory ensured.")
        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        full_image = None
        if not convert_from_path: raise ImportError("convert_from_path function not available due to import error.")
        try: # Conversion logic
             file_size = os.path.getsize(temp_file_path); #... rest of conversion logic ...
        except Exception as e: # Conversion error handling
             # ... rest of conversion error handling ...
        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation & saving...")
        if not ensure_landscape: raise ImportError("ensure_landscape function not available due to import error.")
        try: # Orientation logic
             save_start_time = time.time(); full_image = ensure_landscape(full_image); #... rest of saving logic ...
        except Exception as e: # Orientation error handling
             # ... rest of saving error handling ...
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        if not save_tiles_with_metadata: raise ImportError("save_tiles_with_metadata function not available due to import error.")
        try: # Tiling logic
            tile_start_time = time.time(); save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, #... rest of tiling logic ...
        except Exception as e: # Tiling error handling
            # ... rest of tiling error handling ...
        del full_image; gc.collect(); logger.info(f"[Job {job_id}] Full image object released from memory.")
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (API calls)...")
        if not analyze_all_tiles: raise ImportError("analyze_all_tiles function not available due to import error.")
        else: logger.info(f"[Job {job_id}] 'analyze_all_tiles' function confirmed available for call.")
        # Analysis loop
        retry_count = 0 # ... rest of analysis loop ...
        # Final Update
        # ... final update logic ...
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
# (Keep /health, /drawings, /delete_drawing, /analyze, /job-status, /jobs, /upload as before)
@app.route('/health', methods=['GET']) # Keep as before
@app.route('/drawings', methods=['GET']) # Keep as before
@app.route('/delete_drawing/<path:drawing_name>', methods=['DELETE']) # Keep as before
@app.route('/analyze', methods=['POST']) # Keep as before, check analyzer is not None
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
