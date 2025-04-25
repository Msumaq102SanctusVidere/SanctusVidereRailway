from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import os
import sys
import logging
import shutil
import time
import random
import uuid
import threading # Make sure threading is imported
import datetime
from pathlib import Path
import werkzeug.utils
from PIL import Image
from anthropic import RateLimitError, APIStatusError, APITimeoutError, APIConnectionError
from collections import defaultdict
import json

# IMPORTANT: Fix for decompression bomb warning
Image.MAX_IMAGE_PIXELS = 200000000 # Consider if this needs to be even higher for large drawings

# Set up logging with more detail for SSL issues
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout for Railway
    ]
)
logger = logging.getLogger(__name__)

# Add the current directory to Python path to find the modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import modules
try:
    from modules.construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    from modules.tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    from modules.extract_tile_entities_wow_rev4 import analyze_all_tiles # This likely makes the Anthropic calls
    from pdf2image import convert_from_path
    logger.info("Successfully imported analyzer modules")
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    # Consider if exiting is the right approach or if the app could run partially
    # sys.exit(1) # For now, let's keep it running but log the error

app = Flask(__name__)

# Configure CORS to allow requests from any origin
CORS(app, resources={r"/*": {"origins": "*"}})
logger.info("CORS configured to allow requests from any origin")

# Ensure BASE_DIR is set correctly for containerized environment
try:
    # Use dedicated environment variables if possible, fall back to defaults
    base_dir = os.environ.get('APP_BASE_DIR', '/app') # More specific name?
    Config.configure(base_dir=base_dir)
    logger.info(f"Configured base directory: {Config.BASE_DIR}")
    logger.info(f"Drawings directory: {Config.DRAWINGS_DIR}")
    logger.info(f"Memory store directory: {Config.MEMORY_STORE}")
except Exception as e:
    logger.error(f"Error configuring base directory: {e}")
    fallback_dir = os.path.dirname(os.path.abspath(__file__))
    Config.configure(base_dir=fallback_dir)
    logger.warning(f"Using fallback base directory: {fallback_dir}") # Log as warning

# Configure upload folder
# Make separate folders for initial uploads vs processed drawings
UPLOAD_FOLDER = os.path.join(Config.BASE_DIR, 'uploads') # Use configured base dir
TEMP_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'temp_uploads') # For initial saves
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER # Keep for reference, but use TEMP_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload - OK

# Configure retry settings
MAX_RETRIES = 5
MAX_BACKOFF = 120  # Maximum backoff time in seconds

# Configure batch processing settings for analysis jobs
BATCH_SIZE = 3 # Reduce batch size for analysis if needed to manage resources

# --- Job Tracking (Shared State) ---
jobs = {} # Dictionary to store job status
job_lock = threading.Lock()  # Lock for safe access to the jobs dictionary
# --- End Job Tracking ---

# Process phases and emojis for cool status messages
PROCESS_PHASES = {
    "INIT": "🚀 INITIALIZATION",
    "QUEUED": "⏳ QUEUED",
    "CONVERTING": "📄 CONVERTING",
    "TILING": "🖼️ TILING",
    "ANALYZING_LEGENDS": "🔍 ANALYZING LEGENDS",
    "ANALYZING_CONTENT": "🧩 ANALYZING CONTENT",
    "COMPLETE": "✨ COMPLETE",
    "FAILED": "❌ FAILED",
    # Add phases for analysis jobs if different
    "DISCOVERY": "🔍 DISCOVERY",
    "ANALYSIS": "🧩 ANALYSIS",
    "CORRELATION": "🔗 CORRELATION",
    "SYNTHESIS": "💡 SYNTHESIS",
}

# Create required directories with better error handling
try:
    os.makedirs(Config.DRAWINGS_DIR, exist_ok=True)
    os.makedirs(Config.MEMORY_STORE, exist_ok=True)
    # Create both upload folders
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)
    logger.info("Successfully created required directories (incl. temp_uploads)")
except Exception as e:
    logger.error(f"Error creating directories: {e}")

# Create global instances
try:
    # Initialize analyzer carefully, handle potential errors
    analyzer = ConstructionAnalyzer() if 'ConstructionAnalyzer' in locals() else None
    drawing_manager = DrawingManager(Config.DRAWINGS_DIR) if 'DrawingManager' in locals() and Config.DRAWINGS_DIR else None
    if analyzer and drawing_manager:
        logger.info("Successfully created analyzer and drawing_manager instances")
    else:
        logger.error("Failed to create analyzer or drawing_manager instances due to import or config errors.")
except Exception as e:
    logger.error(f"ERROR INITIALIZING analyzer/drawing_manager: {str(e)}", exc_info=True)
    analyzer = None
    drawing_manager = None

# Try to initialize transformer for smart query filtering - matching GUI script
try:
    from transformers import pipeline
    import torch
    device = 0 if torch.cuda.is_available() else -1  # Use GPU if available
    intent_classifier = pipeline("text-classification",
                              model="distilbert-base-uncased",
                              device=device,
                              top_k=None)
    logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}")
except Exception as e:
    logger.warning(f"Failed to load transformer: {e}. Using basic filtering.")
    intent_classifier = None

# --- Utility Functions ---

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def verify_drawing_files(drawing_name):
    """Verify that all necessary files exist for a drawing (no changes needed)"""
    # ... (keep existing logic) ...
    sheet_output_dir = Config.DRAWINGS_DIR / drawing_name
    # ... (rest of checks) ...
    return { ... } # Return status dict


# --- Job Management Functions ---

def update_job_status(job_id, **kwargs):
    """Update job status safely using the lock."""
    with job_lock:
        if job_id in jobs:
            job = jobs[job_id]
            # Ensure progress_messages list exists
            if "progress_messages" not in job or job["progress_messages"] is None:
                job["progress_messages"] = []

            # Append new message if provided
            if "progress_message" in kwargs and kwargs["progress_message"]:
                 log_msg = f"{datetime.datetime.now().strftime('%H:%M:%S')} - {kwargs['progress_message']}"
                 job["progress_messages"].append(log_msg)
                 # Optional: limit message history length
                 if len(job["progress_messages"]) > 50:
                     job["progress_messages"] = job["progress_messages"][-50:]
                 # Remove the single key after appending to list
                 del kwargs["progress_message"]

            # Update other fields
            job.update(kwargs)
            job["updated_at"] = datetime.datetime.now().isoformat()

            # Log the update
            log_update = {k:v for k,v in kwargs.items() if k != 'progress_messages'} # Avoid logging full list every time
            logger.info(f"Job {job_id} status updated: {log_update}")
        else:
            logger.warning(f"Attempted to update status for unknown job_id: {job_id}")

def create_analysis_job(query, drawings, use_cache):
     """Creates a job specific to analysis tasks."""
     job_id = str(uuid.uuid4())
     total_batches = (len(drawings) + BATCH_SIZE - 1) // BATCH_SIZE if drawings else 0
     with job_lock:
         jobs[job_id] = {
            "id": job_id,
            "type": "analysis", # Job type
            "query": query,
            "drawings": drawings,
            "use_cache": use_cache,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat(),
            "progress": 0,
            "total_batches": total_batches,
            "completed_batches": 0,
            "current_batch": None,
            "current_phase": PROCESS_PHASES["INIT"],
            "progress_messages": [ f"{PROCESS_PHASES['INIT']}: Preparing to analyze {len(drawings)} drawing(s)"],
            "result": None,
            "error": None
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
    pdf_path_obj = Path(temp_file_path)
    # Use original filename for sheet name, ensure it's safe
    safe_original_filename = werkzeug.utils.secure_filename(original_filename)
    sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_")
    sheet_output_dir = Config.DRAWINGS_DIR / sheet_name # Final destination

    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} ({sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")

    try:
        ensure_dir(sheet_output_dir)
        logger.info(f"[Job {job_id}] Output directory: {sheet_output_dir}")

        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        # --- PDF Conversion ---
        try:
            file_size = os.path.getsize(temp_file_path)
            logger.info(f"[Job {job_id}] PDF file size: {file_size} bytes")
            if file_size == 0: raise Exception("PDF file is empty")

            timeout = max(120, int(file_size / 1024 / 1024 * 10)) # Dynamic timeout

            images = convert_from_path(
                pdf_path=str(temp_file_path), dpi=dpi, thread_count=2, # Use multiple threads if safe
                timeout=timeout, use_pdftocairo=True # pdftocairo is often better
            )
            if not images: raise Exception("PDF conversion (pdftocairo) produced no images")
            full_image = images[0]
            logger.info(f"[Job {job_id}] PDF conversion (pdftocairo) successful.")

        except Exception as e:
            logger.error(f"[Job {job_id}] Error converting PDF (pdftocairo): {str(e)}", exc_info=True)
            update_job_status(job_id, progress_message=f"⚠️ PDF conversion error (pdftocairo): {str(e)}. Trying alternative...")
            try:
                images = convert_from_path(
                    pdf_path=str(temp_file_path), dpi=dpi, use_pdftocairo=False, thread_count=1
                )
                if not images: raise Exception("Alternative PDF conversion produced no images")
                full_image = images[0]
                logger.info(f"[Job {job_id}] Alternative PDF conversion successful.")
            except Exception as alt_e:
                logger.error(f"[Job {job_id}] Alternative PDF conversion failed: {str(alt_e)}", exc_info=True)
                raise Exception(f"PDF conversion failed completely. Main error: {str(e)}. Alt error: {str(alt_e)}") # Re-raise

        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation...")
        try:
            full_image = ensure_landscape(full_image)
        except Exception as e:
            logger.error(f"[Job {job_id}] Error ensuring landscape orientation: {str(e)}", exc_info=True)
            # Decide if this is fatal or can be skipped
            update_job_status(job_id, progress_message="⚠️ Failed to adjust orientation, proceeding anyway.")


        update_job_status(job_id, progress=20, progress_message="💾 Saving full image...")
        try:
            full_image_path = sheet_output_dir / f"{sheet_name}.png"
            full_image.save(full_image_path)
            logger.info(f"[Job {job_id}] Saved full image to {full_image_path}")
        except Exception as e:
            logger.error(f"[Job {job_id}] Error saving full image: {str(e)}", exc_info=True)
            raise Exception(f"Image saving failed: {str(e)}") # Likely fatal

        # --- Tiling ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        try:
            save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name,
                                    tile_size=tile_size, overlap_ratio=overlap_ratio)
            metadata_file = sheet_output_dir / f"{sheet_name}_tile_metadata.json"
            if not metadata_file.exists(): raise Exception("Tile metadata file was not created")
            with open(metadata_file, 'r') as f: metadata = json.load(f)
            tile_count = len(metadata.get("tiles", []))
            if tile_count == 0: raise Exception("No tiles were generated")
            logger.info(f"[Job {job_id}] Generated {tile_count} tiles for {sheet_name}")
            update_job_status(job_id, progress=35, progress_message=f"✅ Generated {tile_count} tiles.")
        except Exception as e:
            logger.error(f"[Job {job_id}] Error creating tiles: {str(e)}", exc_info=True)
            raise Exception(f"Tile creation failed: {str(e)}") # Fatal


        # --- Tile Analysis (Long Part) ---
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (this may take time)...")
        retry_count = 0
        last_error = None
        analysis_successful = False
        while retry_count < MAX_RETRIES:
            try:
                update_job_status(job_id, progress=40 + retry_count*10, progress_message=f"🧠 Analyzing tiles (Attempt {retry_count+1}/{MAX_RETRIES})...")
                # Assuming analyze_all_tiles does both legend and content or needs to be split
                # For simplicity, let's assume it does everything needed now
                analyze_all_tiles(sheet_output_dir, sheet_name) # This calls Anthropic repeatedly

                # Basic verification after analysis
                legend_file = sheet_output_dir / f"{sheet_name}_legend_knowledge.json"
                analysis_file = sheet_output_dir / f"{sheet_name}_tile_analysis.json"
                if not legend_file.exists() and not analysis_file.exists(): # Check if at least one exists
                     logger.warning(f"[Job {job_id}] Neither legend nor tile analysis file was created.")
                     # Decide if this is an error or acceptable for some drawings
                     # raise Exception("Analysis files were not created properly")

                logger.info(f"[Job {job_id}] Tile analysis attempt {retry_count+1} successful.")
                analysis_successful = True
                break # Exit retry loop on success

            except (RateLimitError, APIStatusError, APITimeoutError, APIConnectionError) as api_err:
                retry_count += 1
                last_error = api_err
                backoff = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
                err_type = type(api_err).__name__
                logger.warning(f"[Job {job_id}] {err_type} during tile analysis, attempt {retry_count}/{MAX_RETRIES}. Backing off {backoff:.1f}s: {str(api_err)}")
                update_job_status(job_id, progress_message=f"⚠️ {err_type}, retrying in {backoff:.1f}s ({retry_count}/{MAX_RETRIES})")
                if retry_count < MAX_RETRIES: time.sleep(backoff)
                else: logger.error(f"[Job {job_id}] Failed analysis after {MAX_RETRIES} attempts due to API errors.")

            except Exception as e:
                retry_count += 1
                last_error = e
                backoff = min(MAX_BACKOFF, (2 ** retry_count) * (0.8 + 0.4 * random.random()))
                logger.error(f"[Job {job_id}] Error during tile analysis attempt {retry_count}/{MAX_RETRIES}: {str(e)}", exc_info=True)
                update_job_status(job_id, progress_message=f"⚠️ Analysis error, retrying in {backoff:.1f}s ({retry_count}/{MAX_RETRIES})")
                if retry_count < MAX_RETRIES: time.sleep(backoff)
                else: logger.error(f"[Job {job_id}] Failed analysis after {MAX_RETRIES} attempts: {str(e)}")

        if not analysis_successful:
            raise Exception(f"Tile analysis failed after {MAX_RETRIES} attempts. Last error: {str(last_error)}")

        # --- Final Update ---
        final_status = verify_drawing_files(sheet_name)
        update_job_status(job_id,
                          status="completed",
                          current_phase=PROCESS_PHASES["COMPLETE"],
                          progress=100,
                          result={"drawing_name": sheet_name, "file_status": final_status}, # Store result in job
                          progress_message=f"✅ Successfully processed {original_filename}"
                          )
        logger.info(f"[Job {job_id}] ✅ Successfully processed {original_filename}")

    except Exception as e:
        logger.error(f"[Job {job_id}] Error processing PDF {original_filename}: {str(e)}", exc_info=True)
        update_job_status(job_id,
                          status="failed",
                          current_phase=PROCESS_PHASES["FAILED"],
                          error=str(e),
                          progress_message=f"❌ Error: {str(e)}"
                          )
    finally:
        # Clean up the temporary uploaded file now that processing is done (or failed)
        if os.path.exists(temp_file_path):
             try:
                 os.remove(temp_file_path)
                 logger.info(f"[Job {job_id}] Cleaned up temporary upload file: {temp_file_path}")
             except Exception as clean_e:
                 logger.warning(f"[Job {job_id}] Failed to clean up temp file {temp_file_path}: {str(clean_e)}")


# --- Flask Routes ---

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint (no changes)"""
    logger.info("Health check endpoint called")
    return jsonify({"status": "healthy"}), 200

@app.route('/drawings', methods=['GET'])
def get_drawings():
    """Get list of available drawings (no changes)"""
    # ... (keep existing logic) ...
    return jsonify({"drawings": valid_drawings})

@app.route('/analyze', methods=['POST'])
def analyze_query():
    """Start an analysis job (no major changes, uses job system)"""
    # ... (keep most existing logic) ...
    if not data: return jsonify({"error": "No data provided"}), 400
    query = data.get('query')
    selected_drawings = data.get('drawings', [])
    if not query or not selected_drawings:
         return jsonify({"error": "Missing query or drawings"}), 400

    # Reuse existing job creation and threading for analysis
    job_id = create_analysis_job(query, selected_drawings, data.get('use_cache', True)) # Use specific creator

    thread = threading.Thread(
        target=process_analysis_job, # Your existing analysis processor
        args=(job_id, query, selected_drawings, data.get('use_cache', True))
    )
    thread.daemon = True
    thread.start()
    logger.info(f"Started analysis thread for job {job_id}")

    return jsonify({
        "job_id": job_id,
        "status": "pending", # Or queued? Match job system
        "message": "Analysis job started. Use /job-status/{job_id} to check progress."
    }), 202 # Return 202 Accepted

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get the status of ANY job by its ID (upload or analysis)"""
    with job_lock:
        if job_id not in jobs:
            return jsonify({"error": "Job not found"}), 404

        job = jobs[job_id].copy() # Return a copy
        # Optionally truncate messages if they get too long
        if "progress_messages" in job and len(job["progress_messages"]) > 20:
            job["progress_messages"] = ["... (truncated history) ..."] + job["progress_messages"][-20:]

    return jsonify(job)

@app.route('/jobs', methods=['GET'])
def list_jobs():
    """List all current jobs with basic info (no changes)"""
    # ... (keep existing logic) ...
    return jsonify({"jobs": job_summaries})


# --- NEW ASYNCHRONOUS UPLOAD ENDPOINT ---
@app.route('/upload', methods=['POST'])
def upload_file_async():
    """
    Handles PDF upload, saves file, creates a job, starts a background thread
    for processing, and returns the job ID immediately.
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        original_filename = werkzeug.utils.secure_filename(file.filename)
        temp_file_path = None # Define to ensure cleanup scope
        try:
            # Save to the *temporary* location first
            os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True) # Ensure temp dir exists
            # Create a unique name for the temp file to avoid collisions
            temp_filename = str(uuid.uuid4()) + "_" + original_filename
            temp_file_path = os.path.join(TEMP_UPLOAD_FOLDER, temp_filename)

            file.save(temp_file_path)
            logger.info(f"File temporarily saved to: {temp_file_path}")

            # Basic file check
            if not os.path.exists(temp_file_path) or os.path.getsize(temp_file_path) == 0:
                logger.error(f"File not saved correctly or empty: {temp_file_path}")
                if os.path.exists(temp_file_path): os.remove(temp_file_path) # Clean up if empty
                return jsonify({"error": "Uploaded file is empty or save failed"}), 400

            # --- Create Job & Start Background Thread ---
            job_id = str(uuid.uuid4())
            with job_lock:
                jobs[job_id] = {
                    "id": job_id,
                    "type": "upload_processing", # Differentiate from analysis jobs
                    "original_filename": original_filename,
                    "status": "queued", # Initial status
                    "created_at": datetime.datetime.now().isoformat(),
                    "updated_at": datetime.datetime.now().isoformat(),
                    "progress": 0,
                    "current_phase": PROCESS_PHASES["QUEUED"],
                    "progress_messages": [f"{PROCESS_PHASES['QUEUED']}: {original_filename}"],
                    "result": None, # Will be populated upon completion
                    "error": None
                }

            # Start the long processing in a separate thread
            thread = threading.Thread(
                target=process_pdf_job, # Target the modified processing function
                args=(temp_file_path, job_id, original_filename) # Pass needed info
            )
            thread.daemon = True # Allow main app to exit even if thread runs
            thread.start()
            logger.info(f"Started background processing thread for job {job_id} ({original_filename})")

            # --- Return Immediately ---
            return jsonify({
                "job_id": job_id,
                "status": "processing_queued",
                "message": f"File '{original_filename}' uploaded. Processing started (Job ID: {job_id})."
            }), 202 # HTTP 202 Accepted: Request accepted, processing not complete

        except Exception as e:
            logger.error(f"Error during upload setup for {original_filename}: {str(e)}", exc_info=True)
            # Clean up temp file if it exists and an error occurred before thread start
            if temp_file_path and os.path.exists(temp_file_path):
                 try: os.remove(temp_file_path)
                 except Exception as clean_e: logger.warning(f"Failed cleanup on error: {clean_e}")
            return jsonify({"error": f"Server error during upload initiation: {str(e)}"}), 500
    else:
        # This path is for disallowed file types
        return jsonify({"error": "File type not allowed. Only PDF is supported."}), 400

# --- Background Job Processors ---
# process_pdf_job is defined above

# process_analysis_job needs to be defined or kept as is if already working
def process_analysis_job(job_id, query, selected_drawings, use_cache):
     """ Your existing analysis job processor (keep as is) """
     logger.info(f"[Job {job_id}] Starting analysis job...")
     try:
        # ... (Your existing logic for analysis) ...
        # Make sure it calls update_job_status(job_id, ...) appropriately
        # Example structure:
        update_job_status(job_id, status="processing", current_phase=PROCESS_PHASES["DISCOVERY"], ...)
        # ... do discovery ...
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYSIS"], ...)
        # ... do analysis (potentially calling process_batch_with_retry) ...
        # ...
        final_result = "Some analysis result" # Placeholder
        update_job_status(job_id, status="completed", current_phase=PROCESS_PHASES["COMPLETE"], result=final_result, progress=100, progress_message="✅ Analysis complete!")
        logger.info(f"[Job {job_id}] Analysis job completed successfully.")

     except Exception as e:
         logger.error(f"[Job {job_id}] Error processing analysis job: {str(e)}", exc_info=True)
         update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], error=str(e), progress_message=f"❌ Analysis failed: {str(e)}")


# process_batch_with_retry needs to be defined or kept as is
def process_batch_with_retry(job_id, query, use_cache, batch_number, total_batches):
    """ Your existing batch processor (keep as is) """
    # ... (Your existing logic) ...
    # Ensure it calls update_job_status(job_id, ...) for progress/errors within the batch
    return "Batch response placeholder" # Return actual response


# --- Cleanup Thread ---
def cleanup_old_jobs():
    """Remove jobs older than 24 hours (no changes needed)"""
    # ... (keep existing logic) ...

cleanup_thread = threading.Thread(target=cleanup_old_jobs)
cleanup_thread.daemon = True
cleanup_thread.start()

# --- Server Start ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')

    logger.info(f"Starting API server on {host}:{port}")
    try:
        from waitress import serve
        logger.info("Using Waitress production server")
        serve(
            app,
            host=host,
            port=port,
            threads=8, # Adjust threads based on workload and CPU cores
            connection_limit=200, # Increased limit
            backlog=4096,         # Increased backlog
            channel_timeout=300   # Increased channel timeout (might not matter much for async)
        )
    except ImportError:
        logger.info("Waitress not available, using Flask development server (NOT recommended for production)")
        app.run(host=host, port=port, threaded=True) # threaded=True is important for Flask dev server with background threads
