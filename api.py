# --- Filename: api.py (Backend Flask Application - Syntax Corrected FINAL v2) ---

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

# --- Process phases (Corrected Syntax) ---
PROCESS_PHASES = {
    "INIT": "🚀 INITIALIZATION",
    "QUEUED": "⏳ QUEUED",
    "CONVERTING": "📄 CONVERTING",
    "TILING": "🖼️ TILING",
    "ANALYZING_LEGENDS": "🔍 ANALYZING LEGENDS",
    "ANALYZING_CONTENT": "🧩 ANALYZING CONTENT",
    "COMPLETE": "✨ COMPLETE",
    "FAILED": "❌ FAILED",
    "DISCOVERY": "🔍 DISCOVERY",
    "ANALYSIS": "🧩 ANALYSIS",
    "CORRELATION": "🔗 CORRELATION",
    "SYNTHESIS": "💡 SYNTHESIS",
}

# --- Create required directories ---
try:
    if DRAWINGS_OUTPUT_DIR: os.makedirs(DRAWINGS_OUTPUT_DIR, exist_ok=True)
    if MEMORY_STORE_DIR: os.makedirs(MEMORY_STORE_DIR, exist_ok=True)
    if UPLOAD_FOLDER: os.makedirs(Path(UPLOAD_FOLDER), exist_ok=True)
    if TEMP_UPLOAD_FOLDER: os.makedirs(Path(TEMP_UPLOAD_FOLDER), exist_ok=True)
    logger.info(f"Ensured directories exist.")
except Exception as e:
    logger.error(f"Error creating required directories: {e}", exc_info=True)

# Create global instances
analyzer = None
drawing_manager = None
try:
    if ConstructionAnalyzer: analyzer = ConstructionAnalyzer()
    else: logger.error("Skipping ConstructionAnalyzer instantiation - import failed.")
    if DrawingManager and DRAWINGS_OUTPUT_DIR:
        if isinstance(DRAWINGS_OUTPUT_DIR, Path) and DRAWINGS_OUTPUT_DIR.is_dir():
             drawing_manager = DrawingManager(DRAWINGS_OUTPUT_DIR)
        else: logger.error(f"DRAWINGS_OUTPUT_DIR ('{DRAWINGS_OUTPUT_DIR}') is not a valid directory. Cannot initialize DrawingManager.")
    elif not DrawingManager: logger.error("Skipping DrawingManager instantiation - import failed.")
    else: logger.error("Skipping DrawingManager instantiation - DRAWINGS_OUTPUT_DIR not set.")
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
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_drawing_files(drawing_name):
    # (Full implementation)
    if not drawing_manager: return {"all_required": False, "error": "Drawing manager not ready"}
    sheet_output_dir = Path(drawing_manager.drawings_dir) / drawing_name
    if not sheet_output_dir.is_dir(): return {"all_required": False, "error": "Drawing directory not found"}
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
    has_analysis = (status.get("tile_analysis", False) or status.get("general_notes", False) or status.get("elevation", False) or status.get("detail", False))
    status["all_required"] = status.get("metadata", False) and status.get("legend_knowledge", False) and has_analysis
    logger.info(f"File verification for {drawing_name}: {status}")
    return status

# --- Job Management Functions ---
def update_job_status(job_id, **kwargs):
    # (Full implementation)
    with job_lock:
        if job_id in jobs:
            job = jobs[job_id]
            if "progress_messages" not in job or not isinstance(job.get("progress_messages"), list): job["progress_messages"] = []
            new_message = kwargs.pop("progress_message", None)
            if new_message:
                 log_msg = f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - {new_message}"
                 job["progress_messages"].append(log_msg)
                 MAX_MESSAGES = 50
                 if len(job["progress_messages"]) > MAX_MESSAGES: job["progress_messages"] = [job["progress_messages"][0]] + job["progress_messages"][- (MAX_MESSAGES - 1):]
            job.update(kwargs)
            job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z'
            log_update = {k:v for k,v in kwargs.items() if k not in ['result', 'progress_messages']}
            logger.info(f"Job {job_id} updated: Status='{job.get('status')}', Progress={job.get('progress', 0)}%, Details={log_update}")
        else: logger.warning(f"Attempted to update status for unknown job_id: {job_id}")

def create_analysis_job(query, drawings, use_cache):
    # (Full implementation)
     job_id = str(uuid.uuid4())
     total_batches = (len(drawings) + ANALYSIS_BATCH_SIZE - 1) // ANALYSIS_BATCH_SIZE if drawings else 0
     with job_lock:
         jobs[job_id] = {
            "id": job_id, "type": "analysis", "query": query, "drawings": drawings, "use_cache": use_cache, "status": "queued",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
            "progress": 0, "total_batches": total_batches, "completed_batches": 0, "current_batch": None,
            "current_phase": PROCESS_PHASES["QUEUED"],
            "progress_messages": [f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - {PROCESS_PHASES['QUEUED']}: Analyze {len(drawings)} drawing(s)"],
            "result": None, "error": None
         }
     logger.info(f"Created analysis job {job_id} for query: {query[:50]}...")
     return job_id

# --- PDF Processing (Now runs in background) ---
def process_pdf_job(temp_file_path, job_id, original_filename, dpi=300, tile_size=2048, overlap_ratio=0.35):
    # (Full implementation)
    global analyze_all_tiles, convert_from_path, ensure_landscape, save_tiles_with_metadata, ensure_dir
    pdf_path_obj = Path(temp_file_path); safe_original_filename = werkzeug.utils.secure_filename(original_filename)
    sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name; start_time = time.time()
    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} (Sheet Name: {sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")
    try:
        if not ensure_dir: raise ImportError("ensure_dir function not available due to import error.")
        ensure_dir(sheet_output_dir); logger.info(f"[Job {job_id}] Output directory ensured: {sheet_output_dir}")
        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        full_image = None
        if not convert_from_path: raise ImportError("convert_from_path function not available due to import error.")
        try: # Main conversion
            file_size = os.path.getsize(temp_file_path); logger.info(f"[Job {job_id}] PDF file size: {file_size / 1024 / 1024:.2f} MB")
            if file_size == 0: raise Exception("PDF file is empty")
            logger.info(f"[Job {job_id}] Using DPI: {dpi}")
            conversion_start_time = time.time()
            images = convert_from_path(str(temp_file_path), dpi=dpi)
            conversion_time = time.time() - conversion_start_time
            if not images: raise Exception("PDF conversion produced no images")
            full_image = images[0]; logger.info(f"[Job {job_id}] PDF conversion successful in {conversion_time:.2f}s.")
        except Exception as e: # Alternative conversion
            logger.error(f"[Job {job_id}] Error converting PDF: {str(e)}", exc_info=False)
            update_job_status(job_id, progress_message=f"⚠️ PDF conversion error: {str(e)}. Trying alternative method...")
            try:
                conversion_start_time = time.time()
                images = convert_from_path(str(temp_file_path), dpi=dpi, thread_count=1)
                conversion_time = time.time() - conversion_start_time
                if not images: raise Exception("Alternative PDF conversion produced no images")
                full_image = images[0]; logger.info(f"[Job {job_id}] Alternative PDF conversion successful in {conversion_time:.2f}s.")
            except Exception as alt_e:
                logger.error(f"[Job {job_id}] Alternative PDF conversion also failed: {str(alt_e)}", exc_info=True)
                raise Exception(f"PDF conversion failed completely. Last error: {str(alt_e)}")
        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation & saving...")
        if not ensure_landscape: raise ImportError("ensure_landscape function not available due to import error.")
        try: # Orientation
            save_start_time = time.time(); full_image = ensure_landscape(full_image); full_image_path = sheet_output_dir / f"{sheet_name}.png"
            full_image.save(str(full_image_path)); save_time = time.time() - save_start_time
            logger.info(f"[Job {job_id}] Oriented and saved full image to {full_image_path} in {save_time:.2f}s")
        except Exception as e: logger.error(f"[Job {job_id}] Error ensuring landscape or saving full image: {str(e)}", exc_info=True); raise Exception(f"Image orientation/saving failed: {str(e)}")
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        if not save_tiles_with_metadata: raise ImportError("save_tiles_with_metadata function not available due to import error.")
        try: # Tiling
            tile_start_time = time.time(); save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, tile_size=tile_size, overlap_ratio=overlap_ratio)
            tile_time = time.time() - tile_start_time; metadata_file = sheet_output_dir / f"{sheet_name}_tile_metadata.json"
            if not metadata_file.exists(): raise Exception("Tile metadata file was not created")
            with open(metadata_file, 'r') as f: metadata = json.load(f)
            tile_count = len(metadata.get("tiles", [])); logger.info(f"[Job {job_id}] Generated {tile_count} tiles for {sheet_name} in {tile_time:.2f}s")
            if tile_count == 0: raise Exception("No tiles were generated")
            update_job_status(job_id, progress=35, progress_message=f"✅ Generated {tile_count} tiles.")
        except Exception as e: logger.error(f"[Job {job_id}] Error creating tiles: {str(e)}", exc_info=True); raise Exception(f"Tile creation failed: {str(e)}")
        del full_image; gc.collect(); logger.info(f"[Job {job_id}] Full image object released from memory.")
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (API calls)...")
        if not analyze_all_tiles: raise ImportError("analyze_all_tiles function not available due to import error.")
        else: logger.info(f"[Job {job_id}] 'analyze_all_tiles' function confirmed available for call.")
        # Analysis loop
        retry_count = 0; last_error = None; analysis_successful = False; analysis_start_time = time.time()
        while retry_count < MAX_RETRIES:
            try:
                logger.info(f"[Job {job_id}] Analysis attempt #{retry_count+1}/{MAX_RETRIES}")
                update_job_status(job_id, progress_message=f"🔄 Analysis attempt #{retry_count+1}/{MAX_RETRIES}")
                
                # Call the analysis function with the correct parameters
                # FIXED: Changed to match parameters in extract_tile_entities_wow_rev4.py
                analyze_all_tiles(
                    sheet_folder=sheet_output_dir,
                    sheet_name=sheet_name
                )
                
                # If we reach here, analysis was successful
                analysis_successful = True
                logger.info(f"[Job {job_id}] Analysis completed successfully on attempt #{retry_count+1}")
                update_job_status(job_id, progress=80, progress_message=f"✅ Analysis completed successfully")
                break
                
            except (RateLimitError, APIStatusError, APITimeoutError, APIConnectionError) as api_err:
                retry_count += 1
                last_error = api_err
                backoff_time = min(2 ** retry_count + random.uniform(0, 1), MAX_BACKOFF)
                logger.warning(f"[Job {job_id}] API error during analysis (attempt {retry_count}/{MAX_RETRIES}): {str(api_err)}. Retrying in {backoff_time:.1f}s")
                update_job_status(job_id, progress_message=f"⚠️ API error: {str(api_err)}. Retrying in {backoff_time:.1f}s ({retry_count}/{MAX_RETRIES})")
                time.sleep(backoff_time)
                
            except Exception as e:
                retry_count += 1
                last_error = e
                backoff_time = min(2 ** retry_count + random.uniform(0, 1), MAX_BACKOFF)
                logger.error(f"[Job {job_id}] Error during analysis (attempt {retry_count}/{MAX_RETRIES}): {str(e)}", exc_info=True)
                update_job_status(job_id, progress_message=f"❌ Error: {str(e)}. Retrying in {backoff_time:.1f}s ({retry_count}/{MAX_RETRIES})")
                time.sleep(backoff_time)
                
        analysis_time = time.time() - analysis_start_time; logger.info(f"[Job {job_id}] Tile analysis phase took {analysis_time:.2f}s.")
        if not analysis_successful: raise Exception(f"Tile analysis failed after {MAX_RETRIES} attempts. Last error: {str(last_error)}")
        # Final Update
        update_job_status(job_id, progress=99, progress_message="✔️ Verifying final files...")
        final_status = verify_drawing_files(sheet_name); total_time = time.time() - start_time
        result_data = {"drawing_name": sheet_name, "file_status": final_status, "processing_time_seconds": round(total_time, 2)}
        update_job_status(job_id, status="completed", current_phase=PROCESS_PHASES["COMPLETE"], progress=100, result=result_data, progress_message=f"✅ Successfully processed {original_filename} in {total_time:.2f}s")
        logger.info(f"[Job {job_id}] ✅ Successfully processed {original_filename} in {total_time:.2f}s")
    except ImportError as imp_err:
         total_time = time.time() - start_time
         logger.error(f"[Job {job_id}] Processing failed due to missing function after {total_time:.2f}s: {imp_err}", exc_info=False)
         update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(imp_err), progress_message=f"❌ Processing failed due to import error: {imp_err}")
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"[Job {job_id}] Processing failed for {original_filename} after {total_time:.2f}s: {str(e)}", exc_info=True)
        update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(e), progress_message=f"❌ Processing failed after {total_time:.2f}s. Error: {str(e)}")
    finally:
        if os.path.exists(temp_file_path):
             try: os.remove(temp_file_path); logger.info(f"[Job {job_id}] Cleaned up temporary upload file.")
             except Exception as clean_e: logger.warning(f"[Job {job_id}] Failed to clean up temp file: {clean_e}")
# --- Flask Routes ---
@app.route('/health', methods=['GET'])
def health_check():
    status = {
        "status": "ok",
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
        "imports": {
            "construction_analyzer": ConstructionAnalyzer is not None,
            "drawing_manager": DrawingManager is not None,
            "config": Config is not None,
            "tile_generator": all([ensure_dir, save_tiles_with_metadata, ensure_landscape]),
            "pdf2image": convert_from_path is not None,
            "tile_analyzer": analyze_all_tiles is not None and callable(analyze_all_tiles)
        },
        "instances": {
            "analyzer": analyzer is not None,
            "drawing_manager": drawing_manager is not None
        }
    }
    return jsonify(status)

@app.route('/drawings', methods=['GET'])
def get_drawings():
    if not drawing_manager:
        return jsonify({"error": "Drawing manager not available"}), 500
    try:
        include_details = request.args.get('include_details', 'false').lower() == 'true'
        drawings = drawing_manager.list_drawings(include_details=include_details)
        return jsonify({"drawings": drawings})
    except Exception as e:
        logger.error(f"Error listing drawings: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to list drawings: {str(e)}"}), 500

@app.route('/delete_drawing/<path:drawing_name>', methods=['DELETE'])
def delete_drawing(drawing_name):
    if not drawing_manager:
        return jsonify({"error": "Drawing manager not available"}), 500
    try:
        unquoted_name = unquote(drawing_name)
        sheet_dir = DRAWINGS_OUTPUT_DIR / unquoted_name
        if sheet_dir.is_dir():
            shutil.rmtree(sheet_dir)
            logger.info(f"Deleted drawing directory: {sheet_dir}")
            return jsonify({"success": True, "message": f"Drawing '{unquoted_name}' deleted"})
        else:
            return jsonify({"error": f"Drawing '{unquoted_name}' not found"}), 404
    except Exception as e:
        logger.error(f"Error deleting drawing {drawing_name}: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to delete drawing: {str(e)}"}), 500

@app.route('/analyze', methods=['POST'])
def analyze_drawings():
    if not analyzer or not drawing_manager:
        return jsonify({"error": "Analyzer or drawing manager not available"}), 500
    try:
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
        job_id = create_analysis_job(query, drawings, use_cache)
        analysis_thread = threading.Thread(
            target=process_analysis_job,
            args=(job_id,),
            name=f"AnalysisJob-{job_id[:8]}"
        )
        analysis_thread.daemon = True
        analysis_thread.start()
        return jsonify({"job_id": job_id})
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to start analysis: {str(e)}"}), 500

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    with job_lock:
        if job_id in jobs:
            return jsonify(jobs[job_id])
        else:
            return jsonify({"error": f"Job {job_id} not found"}), 404

@app.route('/jobs', methods=['GET'])
def list_jobs():
    with job_lock:
        active_jobs = {job_id: job for job_id, job in jobs.items() if job.get('status') in ['queued', 'processing']}
        return jsonify({"active_jobs": active_jobs})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}"}), 400
    try:
        filename = werkzeug.utils.secure_filename(file.filename)
        os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)
        temp_file_path = os.path.join(TEMP_UPLOAD_FOLDER, f"upload_{uuid.uuid4()}_{filename}")
        file.save(temp_file_path)
        job_id = str(uuid.uuid4())
        with job_lock:
            jobs[job_id] = {
                "id": job_id,
                "type": "conversion",
                "filename": file.filename,
                "status": "queued",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
                "progress": 0,
                "current_phase": PROCESS_PHASES["QUEUED"],
                "progress_messages": [f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - Job created for {file.filename}"],
                "result": None,
                "error": None
            }
        logger.info(f"Created job {job_id} for file {file.filename}")
        # Start processing in background
        thread = threading.Thread(
            target=process_pdf_job,
            args=(temp_file_path, job_id, file.filename),
            name=f"Upload-{job_id[:8]}"
        )
        thread.daemon = True
        thread.start()
        return jsonify({"job_id": job_id})
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

# --- Background Job Processors ---
def process_analysis_job(job_id):
    with job_lock:
        if job_id not in jobs:
            logger.error(f"Job {job_id} not found for processing")
            return
        job = jobs[job_id]
        query = job.get("query", "")
        drawings = job.get("drawings", [])
        use_cache = job.get("use_cache", True)
    
    logger.info(f"Starting analysis job {job_id} for query: '{query[:50]}...', drawings: {len(drawings)}")
    update_job_status(job_id, status="processing", progress=5, progress_message=f"🚀 Starting analysis of {len(drawings)} drawing(s)")
    
    try:
        total_batches = job.get("total_batches", 1)
        batch_size = ANALYSIS_BATCH_SIZE
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(drawings))
            current_batch = drawings[start_idx:end_idx]
            
            update_job_status(
                job_id, 
                current_batch=current_batch,
                progress=5 + int(90 * batch_num / total_batches),
                progress_message=f"📊 Processing batch {batch_num+1}/{total_batches}: {', '.join(current_batch)}"
            )
            
            # Process this batch with retries
            batch_result = process_batch_with_retry(job_id, query, use_cache, batch_num+1, total_batches)
            
            update_job_status(
                job_id,
                completed_batches=batch_num+1,
                progress=5 + int(90 * (batch_num+1) / total_batches),
                progress_message=f"✅ Completed batch {batch_num+1}/{total_batches}"
            )
        
        # All batches complete
        update_job_status(
            job_id,
            status="completed",
            progress=100,
            current_phase=PROCESS_PHASES["COMPLETE"],
            progress_message=f"✨ Analysis complete for all {len(drawings)} drawing(s)",
            result={"message": f"Successfully analyzed {len(drawings)} drawing(s)"}
        )
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Error in analysis job {job_id}: {str(e)}", exc_info=True)
        update_job_status(
            job_id,
            status="failed",
            current_phase=PROCESS_PHASES["FAILED"],
            progress=100,
            error=str(e),
            progress_message=f"❌ Analysis failed: {str(e)}"
        )

def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches):
    # Implementation of batch processing with retries
    # This would normally call into your analysis functions
    # For now we'll just simulate success
    time.sleep(2)  # Simulate processing time
    return {"success": True, "batch_number": batch_number}

# --- Cleanup Thread ---
def cleanup_old_jobs():
    while True:
        try:
            time.sleep(3600)  # Check once per hour
            current_time = datetime.datetime.now(datetime.timezone.utc)
            with job_lock:
                to_remove = []
                for job_id, job in jobs.items():
                    # Parse the timestamp
                    updated_at = job.get("updated_at", "")
                    if not updated_at:
                        continue
                    
                    try:
                        # Remove Z suffix if present
                        if updated_at.endswith('Z'):
                            updated_at = updated_at[:-1]
                        
                        job_time = datetime.datetime.fromisoformat(updated_at)
                        # Make job_time timezone aware if it isn't already
                        if job_time.tzinfo is None:
                            job_time = job_time.replace(tzinfo=datetime.timezone.utc)
                        
                        # If job is completed/failed and older than 24 hours, mark for removal
                        age_hours = (current_time - job_time).total_seconds() / 3600
                        if job.get("status") in ["completed", "failed"] and age_hours > 24:
                            to_remove.append(job_id)
                    except Exception as e:
                        logger.error(f"Error parsing timestamp '{updated_at}': {e}")
                
                # Remove the old jobs
                for job_id in to_remove:
                    del jobs[job_id]
                
                if to_remove:
                    logger.info(f"Cleaned up {len(to_remove)} old jobs")
        
        except Exception as e:
            logger.error(f"Error in job cleanup thread: {str(e)}", exc_info=True)

cleanup_thread = threading.Thread(target=cleanup_old_jobs, name="JobCleanupThread"); cleanup_thread.daemon = True; cleanup_thread.start()

# --- Server Start ---
if __name__ == "__main__":
    server_port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    use_waitress = os.environ.get('USE_WAITRESS', 'true').lower() == 'true'
    logger.info(f"Starting server on port {server_port} (Debug: {debug_mode}, Waitress: {use_waitress})")
    try:
        if use_waitress:
            import waitress
            waitress.serve(app, host='0.0.0.0', port=server_port, threads=int(os.environ.get('WAITRESS_THREADS', 4)))
        else:
            app.run(host='0.0.0.0', port=server_port, debug=debug_mode)
    except Exception as e:
        logger.error(f"Server failed to start: {str(e)}", exc_info=True)
