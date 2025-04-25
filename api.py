# --- Filename: api.py (Backend Flask Application - Enhanced Import Logging) ---

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

# --- Initialize analyze_all_tiles to None globally for checking ---
analyze_all_tiles = None

# IMPORTANT: Fix for decompression bomb warning
IMAGE_MAX_PIXELS = int(os.environ.get('IMAGE_MAX_PIXELS', 200000000))
Image.MAX_IMAGE_PIXELS = IMAGE_MAX_PIXELS
if IMAGE_MAX_PIXELS != 200000000:
     print(f"Warning: Image.MAX_IMAGE_PIXELS set to {IMAGE_MAX_PIXELS}")


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - API - %(levelname)s - [%(threadName)s] - %(message)s', # Added ThreadName
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Add the current directory and 'modules' subdirectory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
modules_dir = os.path.join(current_dir, 'modules')
if current_dir not in sys.path:
    sys.path.append(current_dir)
if modules_dir not in sys.path:
     sys.path.append(modules_dir)
logger.info(f"Python sys.path includes: {current_dir}, {modules_dir}")

# Import custom modules
try:
    logger.info("Attempting to import custom modules...")
    # Import other modules first
    from construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    from tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    from pdf2image import convert_from_path
    logger.info("Imported base custom modules.")

    # --- Specific import attempt for analyze_all_tiles ---
    logger.info("Attempting to import 'analyze_all_tiles' from 'extract_tile_entities_wow_rev4'...")
    from extract_tile_entities_wow_rev4 import analyze_all_tiles as imported_analyze_all_tiles
    # Assign to the global variable if import succeeded
    analyze_all_tiles = imported_analyze_all_tiles
    logger.info("Successfully imported 'analyze_all_tiles'.")
    # --- End specific import ---

except ImportError as e:
    logger.error(f"CRITICAL: Error importing custom modules: {e}. Check module paths and dependencies.", exc_info=True)
    # Keep analyze_all_tiles as None if import fails
except Exception as e:
    logger.error(f"CRITICAL: Unexpected error during module import: {e}", exc_info=True)
    # Keep analyze_all_tiles as None if import fails

# --- Check analyze_all_tiles after imports ---
if analyze_all_tiles and callable(analyze_all_tiles):
     logger.info("Global 'analyze_all_tiles' function is available and callable after imports.")
else:
     logger.error("CRITICAL: Global 'analyze_all_tiles' function is NOT available or not callable after import block. PDF processing will fail analysis.")


app = Flask(__name__)

# Configure CORS
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured to allow requests from any origin (consider restricting in production)")

# --- Configuration and Path Setup ---
# (Keep the robust version using Path objects from previous steps)
try:
    base_dir = os.environ.get('APP_BASE_DIR', '/app')
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
except Exception as e:
    logger.error(f"CRITICAL: Error configuring base directory/paths: {e}", exc_info=True)
    fallback_dir = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
    Config.configure(base_dir=str(fallback_dir))
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
    logger.info(f"Ensured directories exist: Processed drawings, Memory store, Uploads, Temp Uploads")
except Exception as e:
    logger.error(f"Error creating required directories: {e}", exc_info=True)

# Create global instances
try:
    analyzer = ConstructionAnalyzer() if 'ConstructionAnalyzer' in locals() else None
    drawing_manager = DrawingManager(DRAWINGS_OUTPUT_DIR) if 'DrawingManager' in locals() and DRAWINGS_OUTPUT_DIR else None
    if analyzer and drawing_manager:
        logger.info("Successfully created analyzer and drawing_manager instances.")
    else:
        logger.error("Failed to create analyzer or drawing_manager instances. Check imports and config.")
except Exception as e:
    logger.error(f"ERROR INITIALIZING analyzer/drawing_manager: {str(e)}", exc_info=True)
    analyzer = None
    drawing_manager = None

# Initialize Transformer (optional)
intent_classifier = None
# (Keep transformer loading logic as before)
try:
    if os.environ.get('ENABLE_INTENT_CLASSIFIER', 'false').lower() == 'true':
        from transformers import pipeline
        import torch
        device = 0 if torch.cuda.is_available() else -1
        intent_classifier = pipeline("text-classification",
                                  model="distilbert-base-uncased",
                                  device=device, top_k=None)
        logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}.")
    else:
        logger.info("Intent classifier (transformer) is disabled.")
except Exception as e:
    logger.warning(f"Failed to load transformer: {e}. Intent filtering disabled.")


# --- Utility Functions ---
# (allowed_file, verify_drawing_files - keep as before)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_drawing_files(drawing_name):
    if not drawing_manager:
        logger.warning("Drawing manager not initialized, cannot verify files.")
        return {"all_required": False, "error": "Drawing manager not ready"}
    sheet_output_dir = Path(drawing_manager.drawings_dir) / drawing_name
    if not sheet_output_dir.is_dir():
         logger.warning(f"Verification failed: Output directory not found for {drawing_name} at {sheet_output_dir}")
         return {"all_required": False, "error": "Drawing directory not found"}
    expected = {
        "metadata": sheet_output_dir / f"{drawing_name}_tile_metadata.json",
        "tile_analysis": sheet_output_dir / f"{drawing_name}_tile_analysis.json",
        "legend_knowledge": sheet_output_dir / f"{drawing_name}_legend_knowledge.json",
        "drawing_goals": sheet_output_dir / f"{drawing_name}_drawing_goals.json",
        "general_notes": sheet_output_dir / f"{drawing_name}_general_notes_analysis.json",
        "elevation": sheet_output_dir / f"{drawing_name}_elevation_analysis.json",
        "detail": sheet_output_dir / f"{drawing_name}_detail_analysis.json",
    }
    status = {key: path.exists() for key, path in expected.items()}
    has_analysis = (status.get("tile_analysis", False) or
                    status.get("general_notes", False) or
                    status.get("elevation", False) or
                    status.get("detail", False))
    status["all_required"] = status.get("metadata", False) and \
                             status.get("legend_knowledge", False) and \
                             has_analysis
    logger.info(f"File verification for {drawing_name}: {status}")
    return status

# --- Job Management Functions ---
# (update_job_status, create_analysis_job - keep as before)
def update_job_status(job_id, **kwargs):
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

def create_analysis_job(query, drawings, use_cache):
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
                    dpi=300, tile_size=2048, overlap_ratio=0.35):
    """
    Processes the uploaded PDF. Runs in a background thread.
    Updates job status via update_job_status.
    """
    # Use global analyze_all_tiles which might be None if import failed
    global analyze_all_tiles

    pdf_path_obj = Path(temp_file_path)
    safe_original_filename = werkzeug.utils.secure_filename(original_filename)
    sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name

    start_time = time.time()
    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} (Sheet Name: {sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")

    try:
        ensure_dir(sheet_output_dir)
        logger.info(f"[Job {job_id}] Output directory ensured: {sheet_output_dir}")

        # --- 1. PDF Conversion ---
        # (Keep conversion logic as before)
        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        full_image = None
        try:
            file_size = os.path.getsize(temp_file_path); logger.info(f"[Job {job_id}] PDF file size: {file_size / 1024 / 1024:.2f} MB")
            if file_size == 0: raise Exception("PDF file is empty")
            logger.info(f"[Job {job_id}] Using DPI: {dpi}"); poppler_path = os.environ.get('POPPLER_PATH')
            conversion_start_time = time.time()
            images = convert_from_path(str(temp_file_path), dpi=dpi, fmt='png', thread_count=int(os.environ.get('PDF2IMAGE_THREADS', 2)), timeout=max(300, int(file_size / 1024 / 1024 * 15)), use_pdftocairo=True, poppler_path=poppler_path)
            conversion_time = time.time() - conversion_start_time
            if not images: raise Exception("PDF conversion (pdftocairo) produced no images")
            full_image = images[0]; logger.info(f"[Job {job_id}] PDF conversion (pdftocairo) successful in {conversion_time:.2f}s.")
        except Exception as e:
            logger.error(f"[Job {job_id}] Error converting PDF (pdftocairo): {str(e)}", exc_info=True); update_job_status(job_id, progress_message=f"⚠️ PDF conversion error (pdftocairo): {str(e)}. Trying legacy...")
            try:
                 conversion_start_time = time.time(); images = convert_from_path(str(temp_file_path), dpi=dpi, fmt='png', thread_count=1, use_pdftocairo=False, poppler_path=poppler_path)
                 conversion_time = time.time() - conversion_start_time
                 if not images: raise Exception("Alternative PDF conversion produced no images")
                 full_image = images[0]; logger.info(f"[Job {job_id}] Alternative PDF conversion successful in {conversion_time:.2f}s.")
            except Exception as alt_e: logger.error(f"[Job {job_id}] Alternative PDF conversion failed: {str(alt_e)}", exc_info=True); raise Exception(f"PDF conversion failed completely. Error: {str(alt_e)}")


        # --- 2. Image Orientation & Saving ---
        # (Keep orientation logic as before)
        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation & saving...")
        try:
            save_start_time = time.time(); full_image = ensure_landscape(full_image); full_image_path = sheet_output_dir / f"{sheet_name}.png"
            full_image.save(str(full_image_path)); save_time = time.time() - save_start_time
            logger.info(f"[Job {job_id}] Oriented and saved full image to {full_image_path} in {save_time:.2f}s")
        except Exception as e: logger.error(f"[Job {job_id}] Error ensuring landscape or saving full image: {str(e)}", exc_info=True); raise Exception(f"Image orientation/saving failed: {str(e)}")


        # --- 3. Tiling ---
        # (Keep tiling logic as before)
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        try:
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


        # --- 4. Tile Analysis (Long Part) ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (API calls)...")

        # --- ADDED CHECK AND LOGGING ---
        logger.info(f"[Job {job_id}] Checking availability of 'analyze_all_tiles' within thread...")
        # Check the global variable we tried to populate during import
        if analyze_all_tiles is None or not callable(analyze_all_tiles):
             logger.error(f"[Job {job_id}] 'analyze_all_tiles' function is None or not callable at the point of execution.")
             raise Exception("Tile analysis function (analyze_all_tiles) is not available.")
        else:
             logger.info(f"[Job {job_id}] 'analyze_all_tiles' function confirmed available and callable.")
        # --- END ADDED CHECK ---

        retry_count = 0
        last_error = None
        analysis_successful = False
        analysis_start_time = time.time()

        while retry_count < MAX_RETRIES:
            progress_percent = 40 + int((retry_count / MAX_RETRIES) * 55)
            try:
                update_job_status(job_id, progress=progress_percent, progress_message=f"🧠 Analyzing tiles (Attempt {retry_count+1}/{MAX_RETRIES})...")
                # Call the function (already confirmed callable)
                analyze_all_tiles(sheet_output_dir, sheet_name) # Pass Path object

                legend_file = sheet_output_dir / f"{sheet_name}_legend_knowledge.json"
                if not legend_file.exists():
                     logger.warning(f"[Job {job_id}] Legend knowledge file missing after analysis attempt {retry_count+1}.")

                logger.info(f"[Job {job_id}] Tile analysis attempt {retry_count+1} completed.")
                analysis_successful = True
                break

            except (RateLimitError, APIStatusError, APITimeoutError, APIConnectionError) as api_err:
                retry_count += 1; last_error = api_err; backoff = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
                err_type = type(api_err).__name__
                logger.warning(f"[Job {job_id}] {err_type} during tile analysis, attempt {retry_count}/{MAX_RETRIES}. Backing off {backoff:.1f}s: {str(api_err)}")
                update_job_status(job_id, progress_message=f"⚠️ {err_type}, retrying in {backoff:.1f}s ({retry_count}/{MAX_RETRIES})")
                if retry_count < MAX_RETRIES: time.sleep(backoff)
                else: logger.error(f"[Job {job_id}] Failed analysis after {MAX_RETRIES} attempts due to API errors.")

            except Exception as e:
                retry_count += 1; last_error = e; backoff = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
                logger.error(f"[Job {job_id}] Error during tile analysis attempt {retry_count}/{MAX_RETRIES}: {str(e)}", exc_info=True)
                update_job_status(job_id, progress_message=f"⚠️ Analysis error, retrying in {backoff:.1f}s ({retry_count}/{MAX_RETRIES})")
                if retry_count < MAX_RETRIES: time.sleep(backoff)
                else: logger.error(f"[Job {job_id}] Failed analysis after {MAX_RETRIES} attempts: {str(e)}")

        analysis_time = time.time() - analysis_start_time
        logger.info(f"[Job {job_id}] Tile analysis phase took {analysis_time:.2f}s.")

        if not analysis_successful:
            raise Exception(f"Tile analysis failed after {MAX_RETRIES} attempts. Last error: {str(last_error)}")

        # --- Final Update ---
        update_job_status(job_id, progress=99, progress_message="✔️ Verifying final files...")
        final_status = verify_drawing_files(sheet_name)
        total_time = time.time() - start_time

        result_data = {
            "drawing_name": sheet_name,
            "file_status": final_status,
            "processing_time_seconds": round(total_time, 2)
        }

        update_job_status(job_id, status="completed", current_phase=PROCESS_PHASES["COMPLETE"], progress=100, result=result_data, progress_message=f"✅ Successfully processed {original_filename} in {total_time:.2f}s")
        logger.info(f"[Job {job_id}] ✅ Successfully processed {original_filename} in {total_time:.2f}s")

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"[Job {job_id}] Processing failed for {original_filename} after {total_time:.2f}s: {str(e)}", exc_info=True)
        update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(e), progress_message=f"❌ Processing failed after {total_time:.2f}s. Error: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
             try: os.remove(temp_file_path); logger.info(f"[Job {job_id}] Cleaned up temporary upload file: {temp_file_path}")
             except Exception as clean_e: logger.warning(f"[Job {job_id}] Failed to clean up temp file {temp_file_path}: {str(clean_e)}")


# --- Flask Routes ---
# (Keep /health, /drawings, /delete_drawing, /analyze, /job-status, /jobs, /upload as before)
@app.route('/health', methods=['GET'])
def health_check():
    is_manager_ok = drawing_manager is not None
    return jsonify({"status": "healthy" if is_manager_ok else "degraded", "drawing_manager_initialized": is_manager_ok}), 200

@app.route('/drawings', methods=['GET'])
def get_drawings():
    if drawing_manager is None:
        logger.error("get_drawings failed: Drawing manager not initialized")
        return jsonify({"drawings": [], "error": "Drawing manager not initialized"}), 500
    try:
        available_drawings = drawing_manager.get_available_drawings()
        logger.info(f"Retrieved {len(available_drawings)} drawings from {drawing_manager.drawings_dir}")
        return jsonify({"drawings": available_drawings})
    except Exception as e:
        logger.error(f"Error retrieving drawings: {str(e)}", exc_info=True)
        return jsonify({"error": f"Error retrieving drawings: {str(e)}"}), 500

@app.route('/delete_drawing/<path:drawing_name>', methods=['DELETE'])
def delete_drawing_route(drawing_name):
    if drawing_manager is None or not DRAWINGS_OUTPUT_DIR:
        logger.error(f"Delete request failed: Drawing manager or DRAWINGS_OUTPUT_DIR not initialized.")
        return jsonify({"success": False, "error": "Drawing manager not initialized"}), 500
    try:
        decoded_drawing_name = unquote(drawing_name)
        logger.info(f"Received request to delete drawing: {decoded_drawing_name}")
        target_dir = (DRAWINGS_OUTPUT_DIR / decoded_drawing_name).resolve()
        if not target_dir.is_relative_to(DRAWINGS_OUTPUT_DIR.resolve()):
             logger.error(f"SECURITY ALERT: Attempted deletion outside designated directory. Target: {target_dir}, Base: {DRAWINGS_OUTPUT_DIR.resolve()}")
             return jsonify({"success": False, "error": "Invalid drawing path (outside allowed directory)"}), 400
        if not target_dir.exists():
            logger.warning(f"Delete request: Directory not found for '{decoded_drawing_name}' at {target_dir}")
            return jsonify({"success": False, "error": "Drawing not found"}), 404
        if not target_dir.is_dir():
            logger.error(f"Delete request: Target path exists but is not a directory: {target_dir}")
            return jsonify({"success": False, "error": "Target is not a directory"}), 400
        logger.info(f"Attempting to delete directory recursively: {target_dir}")
        shutil.rmtree(target_dir)
        logger.info(f"Successfully deleted directory: {target_dir}")
        return jsonify({"success": True, "message": f"Drawing '{decoded_drawing_name}' deleted successfully."}), 200
    except OSError as os_err:
        logger.error(f"OS error deleting directory {target_dir} for drawing '{decoded_drawing_name}': {os_err}", exc_info=True)
        return jsonify({"success": False, "error": f"Server error during deletion (OS Error): {os_err.strerror}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting directory {target_dir} for drawing '{decoded_drawing_name}': {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Unexpected server error during deletion: {str(e)}"}), 500

@app.route('/analyze', methods=['POST'])
def analyze_query():
    if analyzer is None:
        logger.error("analyze_query failed: Analyzer not initialized")
        return jsonify({"error": "Analyzer not initialized"}), 500
    data = request.json
    if not data: return jsonify({"error": "No JSON data provided"}), 400
    query = data.get('query'); selected_drawings = data.get('drawings', []); use_cache = data.get('use_cache', True)
    if not query or not selected_drawings: return jsonify({"error": "Missing 'query' or 'drawings' in request"}), 400
    logger.info(f"Received analysis request for query: '{query[:50]}...' on drawings: {selected_drawings}")
    if intent_classifier: query = query # Placeholder for actual filtering
    valid_drawings = selected_drawings
    if not valid_drawings: return jsonify({"error": "No valid drawings selected for analysis."}), 400
    job_id = create_analysis_job(query, valid_drawings, use_cache)
    thread = threading.Thread(target=process_analysis_job, args=(job_id,), name=f"AnalysisJob-{job_id[:8]}")
    thread.daemon = True; thread.start()
    logger.info(f"Started analysis thread '{thread.name}' for job {job_id}")
    return jsonify({"job_id": job_id, "status": "queued", "message": "Analysis job queued. Use /job-status/{job_id} to check progress."}), 202

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status_route(job_id):
    with job_lock:
        if job_id not in jobs: return jsonify({"error": "Job not found"}), 404
        job = json.loads(json.dumps(jobs[job_id])) # Deep copy
        MAX_MESSAGES_RETURNED = 20
        if "progress_messages" in job and isinstance(job["progress_messages"], list) and len(job["progress_messages"]) > MAX_MESSAGES_RETURNED:
            job["progress_messages"] = ["... (truncated history) ..."] + job["progress_messages"][-MAX_MESSAGES_RETURNED:]
    return jsonify(job)

@app.route('/jobs', methods=['GET'])
def list_jobs_route():
    job_summaries = []
    with job_lock: current_jobs = list(jobs.values())
    for job in sorted(current_jobs, key=lambda x: x.get('created_at', ''), reverse=True):
        try: summary = {k: v for k, v in job.items() if k not in ['progress_messages', 'result']}; job_summaries.append(summary)
        except Exception as e: logger.error(f"Error summarizing job {job.get('id')}: {e}"); continue
    MAX_JOBS_LIST = 100
    return jsonify({"jobs": job_summaries[:MAX_JOBS_LIST]})

@app.route('/upload', methods=['POST'])
def upload_file_async():
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if not file or not file.filename: return jsonify({"error": "No selected file"}), 400
    if allowed_file(file.filename):
        original_filename = werkzeug.utils.secure_filename(file.filename); temp_file_path = None
        try:
            temp_upload_dir_path = Path(TEMP_UPLOAD_FOLDER); os.makedirs(temp_upload_dir_path, exist_ok=True)
            temp_filename = str(uuid.uuid4()) + "_" + original_filename; temp_file_path = temp_upload_dir_path / temp_filename
            logger.info(f"Attempting to save uploaded file '{original_filename}' to temp path: {temp_file_path}")
            file.save(str(temp_file_path)); logger.info(f"File temporarily saved to: {temp_file_path}")
            if not temp_file_path.exists() or temp_file_path.stat().st_size == 0:
                logger.error(f"File not saved correctly or empty: {temp_file_path}")
                if temp_file_path.exists(): temp_file_path.unlink()
                return jsonify({"error": "Uploaded file is empty or save failed"}), 400
            job_id = str(uuid.uuid4())
            with job_lock:
                jobs[job_id] = {
                    "id": job_id, "type": "upload_processing", "original_filename": original_filename, "status": "queued",
                    "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
                    "progress": 0, "current_phase": PROCESS_PHASES["QUEUED"],
                    "progress_messages": [f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - {PROCESS_PHASES['QUEUED']}: {original_filename}"],
                    "result": None, "error": None
                }
            thread = threading.Thread(target=process_pdf_job, args=(str(temp_file_path), job_id, original_filename), name=f"UploadJob-{job_id[:8]}")
            thread.daemon = True; thread.start()
            logger.info(f"Started background processing thread '{thread.name}' for job {job_id} ({original_filename})")
            return jsonify({"job_id": job_id, "status": "processing_queued", "message": f"File '{original_filename}' accepted. Processing started (Job ID: {job_id})."}), 202
        except Exception as e:
            logger.error(f"Error during upload setup for {original_filename}: {str(e)}", exc_info=True)
            if temp_file_path and isinstance(temp_file_path, Path) and temp_file_path.exists():
                 try: temp_file_path.unlink()
                 except Exception as clean_e: logger.warning(f"Failed cleanup on error: {clean_e}")
            return jsonify({"error": f"Server error during upload initiation: {str(e)}"}), 500
    else: return jsonify({"error": "File type not allowed. Only PDF is supported."}), 400


# --- Background Job Processors ---
# process_pdf_job is defined above

def process_analysis_job(job_id):
     # (Keep analysis job processing logic as before)
     with job_lock:
          if job_id not in jobs: logger.error(f"[Job {job_id}] Analysis job not found!"); return
          job = json.loads(json.dumps(jobs[job_id]))
     query = job.get("query"); selected_drawings = job.get("drawings", []); use_cache = job.get("use_cache", True)
     logger.info(f"[Job {job_id}] Starting analysis: Query='{query[:50]}...', Drawings={selected_drawings}")
     update_job_status(job_id, status="processing", current_phase=PROCESS_PHASES["DISCOVERY"], progress=5, progress_message=f"{PROCESS_PHASES['DISCOVERY']}: Exploring {len(selected_drawings)} drawing(s)")
     try:
         if len(selected_drawings) > ANALYSIS_BATCH_SIZE:
             logger.info(f"[Job {job_id}] Processing analysis in batches of {ANALYSIS_BATCH_SIZE}.")
             response_parts = []; total_batches = (len(selected_drawings) + ANALYSIS_BATCH_SIZE - 1) // ANALYSIS_BATCH_SIZE
             update_job_status(job_id, total_batches=total_batches)
             for i in range(0, len(selected_drawings), ANALYSIS_BATCH_SIZE):
                 batch_number = i // ANALYSIS_BATCH_SIZE + 1; batch_drawings = selected_drawings[i:i+ANALYSIS_BATCH_SIZE]
                 logger.info(f"[Job {job_id}] Processing batch {batch_number}/{total_batches}: {batch_drawings}")
                 update_job_status(job_id, current_batch=batch_drawings, completed_batches=batch_number - 1, current_phase=PROCESS_PHASES["ANALYSIS"], progress=10 + int((batch_number / total_batches) * 80), progress_message=f"{PROCESS_PHASES['ANALYSIS']}: Batch {batch_number}/{total_batches} on {batch_drawings}")
                 batch_query = f"[DRAWINGS:{','.join(batch_drawings)}] {query}"
                 try: batch_response = process_batch_with_retry(job_id, batch_query, use_cache, batch_number, total_batches); response_parts.append(str(batch_response))
                 except Exception as batch_e: logger.error(f"[Job {job_id}] Error processing batch {batch_number}: {batch_e}", exc_info=True); update_job_status(job_id, progress_message=f"❌ ERROR in batch {batch_number}: {str(batch_e)}"); raise
             update_job_status(job_id, current_phase=PROCESS_PHASES["SYNTHESIS"], progress=95, progress_message="📝 Synthesizing results from batches...")
             final_result = "\n\n---\n\n".join(response_parts)
         else:
             logger.info(f"[Job {job_id}] Processing analysis as single batch: {selected_drawings}")
             update_job_status(job_id, current_batch=selected_drawings, completed_batches=0, total_batches=1, current_phase=PROCESS_PHASES["ANALYSIS"], progress=20, progress_message=f"{PROCESS_PHASES['ANALYSIS']}: Processing {len(selected_drawings)} drawings...")
             modified_query = f"[DRAWINGS:{','.join(selected_drawings)}] {query}"
             final_result = process_batch_with_retry(job_id, modified_query, use_cache, 1, 1)
             update_job_status(job_id, current_phase=PROCESS_PHASES["SYNTHESIS"], progress=95, progress_message="📝 Finalizing response...")
         update_job_status(job_id, status="completed", current_phase=PROCESS_PHASES["COMPLETE"], result=str(final_result), progress=100, progress_message="✅ Analysis complete!")
         logger.info(f"[Job {job_id}] Analysis job completed successfully.")
     except Exception as e:
         logger.error(f"[Job {job_id}] Error processing analysis job: {str(e)}", exc_info=True)
         update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], error=str(e), progress=100, progress_message=f"❌ Analysis failed: {str(e)}")

def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches):
    # (Keep batch processing logic as before)
    if not analyzer: raise Exception("Analyzer is not initialized, cannot process batch.")
    retry_count = 0; last_error = None; progress_base = 10 + int(((batch_number-1) / total_batches) * 80)
    while retry_count < MAX_RETRIES:
        attempt_progress = progress_base + int((retry_count / MAX_RETRIES) * (80 / total_batches))
        try:
            update_job_status(job_id, progress=attempt_progress, progress_message=f"🧠 Analyzing Batch {batch_number} (Attempt {retry_count+1})...")
            response = analyzer.analyze_query(query, use_cache=use_cache)
            logger.info(f"[Job {job_id}] Batch {batch_number} analysis (Attempt {retry_count+1}) successful.")
            final_batch_progress = progress_base + int(80 / total_batches)
            update_job_status(job_id, progress=final_batch_progress, progress_message=f"✔️ Completed Batch {batch_number} analysis.")
            return response
        except (RateLimitError, APIStatusError, APITimeoutError, APIConnectionError) as api_err:
             retry_count += 1; last_error = api_err; backoff = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random())); err_type = type(api_err).__name__
             logger.warning(f"[Job {job_id}] Batch {batch_number}: {err_type} (Attempt {retry_count}/{MAX_RETRIES}). Backing off {backoff:.1f}s: {str(api_err)}")
             update_job_status(job_id, progress_message=f"⚠️ Batch {batch_number}: {err_type}, retrying in {backoff:.1f}s ({retry_count}/{MAX_RETRIES})")
             if retry_count < MAX_RETRIES: time.sleep(backoff)
             else: logger.error(f"[Job {job_id}] Batch {batch_number} failed after {MAX_RETRIES} attempts due to API errors.")
        except Exception as e:
            retry_count += 1; last_error = e; backoff = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
            logger.error(f"[Job {job_id}] Batch {batch_number} error (Attempt {retry_count}/{MAX_RETRIES}): {str(e)}", exc_info=True)
            update_job_status(job_id, progress_message=f"⚠️ Batch {batch_number} error, retrying in {backoff:.1f}s ({retry_count}/{MAX_RETRIES})")
            if retry_count < MAX_RETRIES: time.sleep(backoff)
            else: logger.error(f"[Job {job_id}] Batch {batch_number} failed after {MAX_RETRIES} attempts: {str(e)}")
    raise Exception(f"Batch {batch_number} failed processing after {MAX_RETRIES} attempts. Last error: {str(last_error)}")


# --- Cleanup Thread ---
# (Keep cleanup logic as before)
def cleanup_old_jobs():
    JOB_RETENTION_HOURS = int(os.environ.get('JOB_RETENTION_HOURS', 24)); CLEANUP_INTERVAL_SECONDS = 3600
    logger.info(f"Job cleanup thread started. Will remove jobs older than {JOB_RETENTION_HOURS} hours.")
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=JOB_RETENTION_HOURS)
            job_ids_to_remove = []; logger.debug(f"Running job cleanup. Cutoff time: {cutoff_time.isoformat()}")
            with job_lock:
                all_job_ids = list(jobs.keys())
                for job_id in all_job_ids:
                    job = jobs.get(job_id); ts_str = job.get("updated_at", job.get("created_at"))
                    if not job or not ts_str: continue
                    try:
                        job_ts = datetime.datetime.fromisoformat(ts_str.replace('Z','+00:00'))
                        if job_ts.tzinfo is None: job_ts = job_ts.replace(tzinfo=datetime.timezone.utc)
                        if job_ts < cutoff_time: job_ids_to_remove.append(job_id)
                    except ValueError: logger.warning(f"Error parsing timestamp for job {job_id}: Invalid format '{ts_str}'. Skipping.")
                    except Exception as e: logger.warning(f"Error comparing timestamp for job {job_id}: {e}. Timestamp: '{ts_str}'. Skipping.")
                for job_id in job_ids_to_remove:
                    if job_id in jobs: del jobs[job_id]
            if job_ids_to_remove: logger.info(f"Cleaned up {len(job_ids_to_remove)} old jobs (older than {JOB_RETENTION_HOURS} hours).")
            else: logger.debug("Job cleanup ran, no old jobs found.")
        except Exception as e: logger.error(f"Error in cleanup_old_jobs thread: {e}", exc_info=True); time.sleep(CLEANUP_INTERVAL_SECONDS / 4)

cleanup_thread = threading.Thread(target=cleanup_old_jobs, name="JobCleanupThread"); cleanup_thread.daemon = True; cleanup_thread.start()

# --- Server Start ---
# (Keep server start logic as before)
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000)); host = os.environ.get('HOST', '0.0.0.0')
    logger.info(f"Starting API server on {host}:{port}")
    try:
        from waitress import serve
        waitress_threads = int(os.environ.get('WAITRESS_THREADS', 8)); waitress_conn_limit = int(os.environ.get('WAITRESS_CONNECTION_LIMIT', 200))
        waitress_backlog = int(os.environ.get('WAITRESS_BACKLOG', 4096)); waitress_channel_timeout = int(os.environ.get('WAITRESS_CHANNEL_TIMEOUT', 300))
        logger.info(f"Using Waitress production server with config: Threads={waitress_threads}, ConnLimit={waitress_conn_limit}, Backlog={waitress_backlog}, ChannelTimeout={waitress_channel_timeout}")
        serve(app, host=host, port=port, threads=waitress_threads, connection_limit=waitress_conn_limit, backlog=waitress_backlog, channel_timeout=waitress_channel_timeout, expose_tracebacks=bool(os.environ.get('WAITRESS_EXPOSE_TRACEBACKS', 'False').lower() == 'true'))
    except ImportError:
        logger.warning("Waitress not found. Using Flask development server (NOT recommended for production)")
        flask_debug = bool(os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'); logger.warning(f"Flask Debug mode: {flask_debug}")
        app.run(host=host, port=port, threaded=True, debug=flask_debug)
    except Exception as e: logger.critical(f"Failed to start server: {e}", exc_info=True); sys.exit("Server failed to start.")
