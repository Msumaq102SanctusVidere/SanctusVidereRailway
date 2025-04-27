# --- Filename: api.py (Backend Flask Application - Enhanced with DB Persistence) ---

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
import sqlite3
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
# Updated to use the specified tiles_output directory
base_dir = os.environ.get('APP_BASE_DIR', '/app')
TILES_OUTPUT_DIR = "/app/tiles_output"  # Primary storage location for all drawing files

# Create fallback directories based on current path
fallback_dir_default = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
DRAWINGS_OUTPUT_DIR_DEFAULT = Path(TILES_OUTPUT_DIR).resolve()  # Use the specified path
MEMORY_STORE_DIR_DEFAULT = fallback_dir_default / 'memory_store'
DATABASE_DIR_DEFAULT = fallback_dir_default / 'database'

# Initialize with defaults
DRAWINGS_OUTPUT_DIR = DRAWINGS_OUTPUT_DIR_DEFAULT
MEMORY_STORE_DIR = MEMORY_STORE_DIR_DEFAULT
DATABASE_DIR = DATABASE_DIR_DEFAULT

try:
    if Config:
        # Override Config.DRAWINGS_DIR to ensure it uses the correct path
        Config.configure(base_dir=base_dir)
        Config.DRAWINGS_DIR = TILES_OUTPUT_DIR  # Force the drawings directory to the specified path
        logger.info(f"Configured base directory using Config: {Config.BASE_DIR}")
        logger.info(f"Configured drawings directory using Config: {Config.DRAWINGS_DIR}")
        
        # Set up other directories
        DRAWINGS_OUTPUT_DIR = Path(Config.DRAWINGS_DIR).resolve()  # Use the specified path from Config
        MEMORY_STORE_DIR = Path(Config.MEMORY_STORE).resolve() if hasattr(Config, 'MEMORY_STORE') else Path(os.path.join(base_dir, 'memory_store')).resolve()
        DATABASE_DIR = Path(os.path.join(base_dir, 'database')).resolve()
    else:
        logger.error("Config class not available from import, using fallback paths.")
        logger.warning(f"Using fallback directories based on: {fallback_dir_default}")
        # Maintain the configured drawings directory even without Config
        DRAWINGS_OUTPUT_DIR = Path(TILES_OUTPUT_DIR).resolve()
except Exception as e:
    logger.error(f"CRITICAL: Error during Config setup: {e}", exc_info=True)
    # Maintain the configured drawings directory even after an error
    DRAWINGS_OUTPUT_DIR = Path(TILES_OUTPUT_DIR).resolve()
    logger.warning(f"Using fallback directories due to error, with DRAWINGS_OUTPUT_DIR={DRAWINGS_OUTPUT_DIR}")

logger.info(f"Final Processed drawings directory: {DRAWINGS_OUTPUT_DIR}")
logger.info(f"Final Memory store directory: {MEMORY_STORE_DIR}")
logger.info(f"Final Database directory: {DATABASE_DIR}")

# Flask App Config
ALLOWED_EXTENSIONS = {'pdf'}
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 100)) * 1024 * 1024
logger.info(f"Max upload size: {app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024} MB")

# Processing Settings
MAX_RETRIES = int(os.environ.get('API_MAX_RETRIES', 5))
MAX_BACKOFF = int(os.environ.get('API_MAX_BACKOFF_SECONDS', 120))
ANALYSIS_BATCH_SIZE = int(os.environ.get('ANALYSIS_BATCH_SIZE', 3))

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
    if DATABASE_DIR: os.makedirs(Path(DATABASE_DIR), exist_ok=True)
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

# --- Database Setup for Job Persistence ---
DB_PATH = os.path.join(DATABASE_DIR, 'jobs.db')
DB_SCHEMA = '''
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    total_batches INTEGER DEFAULT 0,
    completed_batches INTEGER DEFAULT 0,
    current_phase TEXT,
    result TEXT,
    error TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS job_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
'''

def init_database():
    """Initialize the SQLite database for job persistence."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(DB_SCHEMA)
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

# Initialize database on startup
init_database()

# --- Database Access Functions ---
def get_db_connection():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def json_serializable(value):
    """Make a value JSON serializable."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    elif isinstance(value, (list, tuple)):
        return [json_serializable(x) for x in value]
    elif isinstance(value, dict):
        return {str(k): json_serializable(v) for k, v in value.items()}
    else:
        return str(value)

def create_job(job_data):
    """Create a new job in the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare data for the jobs table
        job_id = job_data.get('id', str(uuid.uuid4()))
        details = {k: v for k, v in job_data.items() 
                if k not in ('id', 'type', 'status', 'created_at', 'updated_at', 
                            'progress', 'total_batches', 'completed_batches', 
                            'current_phase', 'result', 'error', 'progress_messages')}
        
        # Insert into jobs table
        cursor.execute('''
        INSERT INTO jobs (
            id, type, status, created_at, updated_at, 
            progress, total_batches, completed_batches, 
            current_phase, result, error, details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_id,
            job_data.get('type', 'unknown'),
            job_data.get('status', 'created'),
            job_data.get('created_at', datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z'),
            job_data.get('updated_at', datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z'),
            job_data.get('progress', 0),
            job_data.get('total_batches', 0),
            job_data.get('completed_batches', 0),
            job_data.get('current_phase', PROCESS_PHASES.get('INIT')),
            json.dumps(json_serializable(job_data.get('result', None))) if job_data.get('result') else None,
            job_data.get('error', None),
            json.dumps(details) if details else None
        ))
        
        # Insert initial progress message if provided
        if 'progress_messages' in job_data and isinstance(job_data['progress_messages'], list):
            for message in job_data['progress_messages']:
                timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z'
                cursor.execute('''
                INSERT INTO job_messages (job_id, timestamp, message)
                VALUES (?, ?, ?)
                ''', (job_id, timestamp, message))
        
        conn.commit()
        logger.info(f"Created job {job_id} in database")
        return job_id
    except Exception as e:
        logger.error(f"Error creating job in database: {e}", exc_info=True)
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def update_job(job_id, **kwargs):
    """Update a job in the database."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Prepare update fields
        update_fields = []
        update_values = []
        
        # Process regular fields
        for key in ('status', 'progress', 'completed_batches', 'current_phase', 'error'):
            if key in kwargs:
                update_fields.append(f"{key} = ?")
                update_values.append(kwargs[key])
        
        # Process JSON fields
        if 'result' in kwargs:
            update_fields.append("result = ?")
            update_values.append(json.dumps(json_serializable(kwargs['result'])))
        
        # Process details - we'll merge with existing details
        if any(k for k in kwargs.keys() if k not in ('status', 'progress', 'completed_batches', 
                                                   'current_phase', 'error', 'result', 
                                                   'progress_message', 'updated_at')):
            # Get existing details
            cursor.execute("SELECT details FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row and row['details']:
                existing_details = json.loads(row['details'])
            else:
                existing_details = {}
            
            # Merge with new details
            new_details = {k: v for k, v in kwargs.items() 
                         if k not in ('status', 'progress', 'completed_batches', 
                                     'current_phase', 'error', 'result', 
                                     'progress_message', 'updated_at')}
            existing_details.update(new_details)
            
            # Update details field
            update_fields.append("details = ?")
            update_values.append(json.dumps(existing_details))
        
        # Always update the updated_at timestamp
        update_fields.append("updated_at = ?")
        update_values.append(datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z')
        
        # Execute update if we have fields to update
        if update_fields:
            query = f"UPDATE jobs SET {', '.join(update_fields)} WHERE id = ?"
            update_values.append(job_id)
            cursor.execute(query, update_values)
        
        # Add progress message if provided
        if 'progress_message' in kwargs and kwargs['progress_message']:
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z'
            cursor.execute('''
            INSERT INTO job_messages (job_id, timestamp, message)
            VALUES (?, ?, ?)
            ''', (job_id, timestamp, kwargs['progress_message']))
        
        conn.commit()
        logger.debug(f"Updated job {job_id} in database")
    except Exception as e:
        logger.error(f"Error updating job in database: {e}", exc_info=True)
        raise
    finally:
        if 'conn' in locals():
            conn.close()

def get_job(job_id, include_messages=True):
    """Get a job from the database with its messages."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get job data
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        
        if not job_row:
            return None
        
        # Convert row to dict
        job_data = dict(job_row)
        
        # Parse JSON fields
        if job_data.get('result'):
            try:
                job_data['result'] = json.loads(job_data['result'])
            except:
                job_data['result'] = None
        
        if job_data.get('details'):
            try:
                details = json.loads(job_data['details'])
                # Merge details into job data
                for k, v in details.items():
                    if k not in job_data:
                        job_data[k] = v
            except:
                pass
            
        # Remove details field from output
        if 'details' in job_data:
            del job_data['details']
        
        # Get progress messages if requested
        if include_messages:
            cursor.execute("SELECT timestamp, message FROM job_messages WHERE job_id = ? ORDER BY id", (job_id,))
            messages = [f"{row['timestamp']} - {row['message']}" for row in cursor.fetchall()]
            job_data['progress_messages'] = messages
        
        return job_data
    except Exception as e:
        logger.error(f"Error getting job from database: {e}", exc_info=True)
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def list_active_jobs():
    """List active jobs (queued or processing)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM jobs WHERE status IN ('queued', 'processing')")
        job_ids = [row['id'] for row in cursor.fetchall()]
        
        active_jobs = {}
        for job_id in job_ids:
            job_data = get_job(job_id, include_messages=False)
            if job_data:
                active_jobs[job_id] = job_data
        
        return active_jobs
    except Exception as e:
        logger.error(f"Error listing active jobs: {e}", exc_info=True)
        return {}
    finally:
        if 'conn' in locals():
            conn.close()

def cleanup_old_jobs(hours=24):
    """Clean up completed/failed jobs older than the specified hours."""
    try:
        conn = get_db_connection()
        cutoff_time = (datetime.datetime.now(datetime.timezone.utc) - 
                     datetime.timedelta(hours=hours)).isoformat(timespec='milliseconds') + 'Z'
        
        # Delete old jobs
        cursor = conn.cursor()
        cursor.execute("""
        DELETE FROM jobs 
        WHERE status IN ('completed', 'failed') 
        AND updated_at < ?
        """, (cutoff_time,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old jobs")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up old jobs: {e}", exc_info=True)
        return 0
    finally:
        if 'conn' in locals():
            conn.close()

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
    """Update job status and add progress message if provided."""
    try:
        # Update the job in the database
        update_job(job_id, **kwargs)
        
        # Log the update (but not the full result)
        log_update = {k:v for k,v in kwargs.items() if k not in ['result', 'progress_messages']}
        job = get_job(job_id, include_messages=False)
        if job:
            logger.info(f"Job {job_id} updated: Status='{job.get('status')}', Progress={job.get('progress', 0)}%, Details={log_update}")
        else:
            logger.warning(f"Attempted to update status for unknown job_id: {job_id}")
    except Exception as e:
        logger.error(f"Error updating job status: {e}", exc_info=True)

def create_analysis_job(query, drawings, use_cache):
    """Create a new analysis job."""
    try:
        total_batches = (len(drawings) + ANALYSIS_BATCH_SIZE - 1) // ANALYSIS_BATCH_SIZE if drawings else 0
        
        # Create job data
        job_data = {
            "id": str(uuid.uuid4()),
            "type": "analysis",
            "query": query,
            "drawings": drawings,
            "use_cache": use_cache,
            "status": "queued",
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds') + 'Z',
            "progress": 0,
            "total_batches": total_batches,
            "completed_batches": 0,
            "current_batch": None,
            "current_phase": PROCESS_PHASES["QUEUED"],
            "progress_messages": [f"{datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')}Z - {PROCESS_PHASES['QUEUED']}: Analyze {len(drawings)} drawing(s)"],
            "result": None,
            "error": None
        }
        
        # Create the job in the database
        job_id = create_job(job_data)
        logger.info(f"Created analysis job {job_id} for query: {query[:50]}...")
        
        return job_id
    except Exception as e:
        logger.error(f"Error creating analysis job: {e}", exc_info=True)
        raise

# --- PDF Processing (Direct file saving with no temp files) ---
def process_pdf_job(pdf_file_path, job_id, original_filename, dpi=300, tile_size=2048, overlap_ratio=0.35):
    """Process a PDF file with direct processing from final location"""
    global analyze_all_tiles, convert_from_path, ensure_landscape, save_tiles_with_metadata, ensure_dir
    
    # Extract sheet name from original filename or PDF path
    if original_filename:
        safe_original_filename = werkzeug.utils.secure_filename(original_filename)
        sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    else:
        sheet_name = Path(pdf_file_path).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
    
    sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name
    
    start_time = time.time()
    logger.info(f"[Job {job_id}] Starting processing for: {original_filename} (Sheet Name: {sheet_name})")
    update_job_status(job_id, status="processing", progress=1, current_phase=PROCESS_PHASES["INIT"], progress_message="🚀 Starting PDF processing")
    
    try:
        # Ensure output directory exists
        if not ensure_dir: raise ImportError("ensure_dir function not available due to import error.")
        ensure_dir(sheet_output_dir)
        logger.info(f"[Job {job_id}] Output directory ensured: {sheet_output_dir}")
        
        # Convert PDF to image
        update_job_status(job_id, current_phase=PROCESS_PHASES["CONVERTING"], progress=5, progress_message=f"📄 Converting {original_filename} to image...")
        full_image = None
        if not convert_from_path: raise ImportError("convert_from_path function not available due to import error.")
        
        try: # Main conversion
            file_size = os.path.getsize(pdf_file_path)
            logger.info(f"[Job {job_id}] PDF file size: {file_size / 1024 / 1024:.2f} MB")
            if file_size == 0: raise Exception("PDF file is empty")
            logger.info(f"[Job {job_id}] Using DPI: {dpi}")
            
            conversion_start_time = time.time()
            images = convert_from_path(str(pdf_file_path), dpi=dpi)
            conversion_time = time.time() - conversion_start_time
            
            if not images: raise Exception("PDF conversion produced no images")
            full_image = images[0]
            logger.info(f"[Job {job_id}] PDF conversion successful in {conversion_time:.2f}s.")
        
        except Exception as e: # Alternative conversion
            logger.error(f"[Job {job_id}] Error converting PDF: {str(e)}", exc_info=False)
            update_job_status(job_id, progress_message=f"⚠️ PDF conversion error: {str(e)}. Trying alternative method...")
            
            try:
                conversion_start_time = time.time()
                images = convert_from_path(str(pdf_file_path), dpi=dpi, thread_count=1)
                conversion_time = time.time() - conversion_start_time
                
                if not images: raise Exception("Alternative PDF conversion produced no images")
                full_image = images[0]
                logger.info(f"[Job {job_id}] Alternative PDF conversion successful in {conversion_time:.2f}s.")
            
            except Exception as alt_e:
                logger.error(f"[Job {job_id}] Alternative PDF conversion also failed: {str(alt_e)}", exc_info=True)
                raise Exception(f"PDF conversion failed completely. Last error: {str(alt_e)}")
        
        # Save oriented image
        update_job_status(job_id, progress=15, progress_message="📐 Adjusting image orientation & saving...")
        if not ensure_landscape: raise ImportError("ensure_landscape function not available due to import error.")
        
        try: # Orientation
            save_start_time = time.time()
            full_image = ensure_landscape(full_image)
            full_image_path = sheet_output_dir / f"{sheet_name}.png"
            full_image.save(str(full_image_path))
            save_time = time.time() - save_start_time
            logger.info(f"[Job {job_id}] Oriented and saved full image to {full_image_path} in {save_time:.2f}s")
        
        except Exception as e: 
            logger.error(f"[Job {job_id}] Error ensuring landscape or saving full image: {str(e)}", exc_info=True)
            raise Exception(f"Image orientation/saving failed: {str(e)}")
        
        # Generate tiles
        update_job_status(job_id, current_phase=PROCESS_PHASES["TILING"], progress=25, progress_message=f"🔳 Creating tiles for {sheet_name}...")
        if not save_tiles_with_metadata: raise ImportError("save_tiles_with_metadata function not available due to import error.")
        
        try: # Tiling
            tile_start_time = time.time()
            # Generate tiles using the sheet name consistently
            save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, tile_size=tile_size, overlap_ratio=overlap_ratio)
            tile_time = time.time() - tile_start_time
            
            metadata_file = sheet_output_dir / f"{sheet_name}_tile_metadata.json"
            if not metadata_file.exists(): raise Exception("Tile metadata file was not created")
            
            with open(metadata_file, 'r') as f: metadata = json.load(f)
            tile_count = len(metadata.get("tiles", []))
            logger.info(f"[Job {job_id}] Generated {tile_count} tiles for {sheet_name} in {tile_time:.2f}s")
            
            if tile_count == 0: raise Exception("No tiles were generated")
            update_job_status(job_id, progress=35, progress_message=f"✅ Generated {tile_count} tiles.")
        
        except Exception as e: 
            logger.error(f"[Job {job_id}] Error creating tiles: {str(e)}", exc_info=True)
            raise Exception(f"Tile creation failed: {str(e)}")
        
        # Clean up image from memory
        del full_image
        gc.collect()
        logger.info(f"[Job {job_id}] Full image object released from memory.")
        
        # Analyze tiles
        update_job_status(job_id, current_phase=PROCESS_PHASES["ANALYZING_LEGENDS"], progress=40, progress_message=f"📊 Analyzing tiles for {sheet_name} (API calls)...")
        if not analyze_all_tiles: raise ImportError("analyze_all_tiles function not available due to import error.")
        else: logger.info(f"[Job {job_id}] 'analyze_all_tiles' function confirmed available for call.")
        
        # Analysis loop with retries
        retry_count = 0
        last_error = None
        analysis_successful = False
        analysis_start_time = time.time()
        
        while retry_count < MAX_RETRIES:
            try:
                logger.info(f"[Job {job_id}] Analysis attempt #{retry_count+1}/{MAX_RETRIES}")
                update_job_status(job_id, progress_message=f"🔄 Analysis attempt #{retry_count+1}/{MAX_RETRIES}")
                
                # Pass the sheet_name to analyze_all_tiles
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
                
        analysis_time = time.time() - analysis_start_time
        logger.info(f"[Job {job_id}] Tile analysis phase took {analysis_time:.2f}s.")
        
        if not analysis_successful: 
            raise Exception(f"Tile analysis failed after {MAX_RETRIES} attempts. Last error: {str(last_error)}")
        
        # Final Update
        update_job_status(job_id, progress=99, progress_message="✔️ Verifying final files...")
        final_status = verify_drawing_files(sheet_name)
        total_time = time.time() - start_time
        
        result_data = {
            "drawing_name": sheet_name, 
            "file_status": final_status, 
            "processing_time_seconds": round(total_time, 2)
        }
        
        update_job_status(
            job_id, 
            status="completed", 
            current_phase=PROCESS_PHASES["COMPLETE"], 
            progress=100, 
            result=result_data, 
            progress_message=f"✅ Successfully processed {original_filename} in {total_time:.2f}s"
        )
        
        logger.info(f"[Job {job_id}] ✅ Successfully processed {original_filename} in {total_time:.2f}s")
    
    except ImportError as imp_err:
         total_time = time.time() - start_time
         logger.error(f"[Job {job_id}] Processing failed due to missing function after {total_time:.2f}s: {imp_err}", exc_info=False)
         update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(imp_err), progress_message=f"❌ Processing failed due to import error: {imp_err}")
    
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"[Job {job_id}] Processing failed for {original_filename} after {total_time:.2f}s: {str(e)}", exc_info=True)
        update_job_status(job_id, status="failed", current_phase=PROCESS_PHASES["FAILED"], progress=100, error=str(e), progress_message=f"❌ Processing failed after {total_time:.2f}s. Error: {str(e)}")

# --- Background Job Processors ---
def process_analysis_job(job_id):
    try:
        # Get job from database
        job = get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found for processing")
            return
        
        query = job.get("query", "")
        drawings = job.get("drawings", [])
        use_cache = job.get("use_cache", True)
        
        logger.info(f"Starting analysis job {job_id} for query: '{query[:50]}...', drawings: {len(drawings)}")
        update_job_status(job_id, status="processing", progress=5, progress_message=f"🚀 Starting analysis of {len(drawings)} drawing(s)")
        
        total_batches = job.get("total_batches", 1)
        batch_size = ANALYSIS_BATCH_SIZE
        
        # Store accumulated results from all batches
        accumulated_results = {
            "message": f"Analysis of {len(drawings)} drawing(s)",
            "batches": []
        }
        
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
            batch_result = process_batch_with_retry(job_id, query, current_batch, use_cache, batch_num+1, total_batches)
            
            # Add batch result to accumulated results
            accumulated_results["batches"].append({
                "batch_number": batch_num+1,
                "drawings": current_batch,
                "result": batch_result
            })
            
            # Also preserve the analysis text from the most recent batch for backward compatibility
            if "analysis" in batch_result:
                accumulated_results["analysis"] = batch_result["analysis"]
            
            update_job_status(
                job_id,
                completed_batches=batch_num+1,
                progress=5 + int(90 * (batch_num+1) / total_batches),
                progress_message=f"✅ Completed batch {batch_num+1}/{total_batches}",
                # Update result as we go so it's always available
                result=accumulated_results
            )
        
        # All batches complete - preserve the accumulated results
        update_job_status(
            job_id,
            status="completed",
            progress=100,
            current_phase=PROCESS_PHASES["COMPLETE"],
            progress_message=f"✨ Analysis complete for all {len(drawings)} drawing(s)",
            result=accumulated_results
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

def process_batch_with_retry(job_id, query, batch_drawings, use_cache, batch_number, total_batches):
    """Process a batch of drawings with retry logic."""
    retry_count = 0
    max_retries = MAX_RETRIES
    
    while retry_count < max_retries:
        try:
            # Check if analyzer is available
            if not analyzer:
                raise Exception("Analyzer not available")
            
            logger.info(f"[Job {job_id}] Processing batch {batch_number}/{total_batches} with {len(batch_drawings)} drawing(s)")
            
            # Call the actual analyze_query method from ConstructionAnalyzer
            update_job_status(
                job_id,
                progress_message=f"🧩 Running analysis using ConstructionAnalyzer for query: {query[:50]}..."
            )
            
            # Store results for all drawings in the batch
            batch_results = {}
            
            for i, drawing_name in enumerate(batch_drawings):
                progress = 5 + int(90 * (batch_number - 1) / total_batches) + int(90 / total_batches * (i / len(batch_drawings)))
                update_job_status(
                    job_id,
                    progress=progress,
                    progress_message=f"🔍 Analyzing drawing {drawing_name} ({i+1}/{len(batch_drawings)} in batch {batch_number})"
                )
            
            # When finished processing all drawings in the batch, call analyze_query once
            analysis_start_time = time.time()
            response_text = analyzer.analyze_query(query, use_cache)
            analysis_time = time.time() - analysis_start_time
            
            logger.info(f"[Job {job_id}] Analysis completed in {analysis_time:.2f}s for query: {query[:50]}...")
            
            # Update job with comprehensive analysis result
            update_job_status(
                job_id,
                progress_message=f"✅ Analysis complete in {analysis_time:.2f}s",
                result={
                    "message": f"Successfully analyzed {len(batch_drawings)} drawing(s)",
                    "analysis": response_text
                }
            )
            
            # Return success result
            return {
                "success": True, 
                "batch_number": batch_number,
                "analysis": response_text
            }
            
        except (RateLimitError, APIStatusError, APITimeoutError, APIConnectionError) as api_err:
            retry_count += 1
            backoff_time = min(2 ** retry_count + random.uniform(0, 1), MAX_BACKOFF)
            logger.warning(f"[Job {job_id}] API error during batch {batch_number} (attempt {retry_count}/{max_retries}): {str(api_err)}. Retrying in {backoff_time:.1f}s")
            update_job_status(
                job_id,
                progress_message=f"⚠️ API error in batch {batch_number}: {str(api_err)}. Retrying in {backoff_time:.1f}s ({retry_count}/{max_retries})"
            )
            time.sleep(backoff_time)
            
        except Exception as e:
            retry_count += 1
            backoff_time = min(2 ** retry_count + random.uniform(0, 1), MAX_BACKOFF)
            logger.error(f"[Job {job_id}] Error during batch {batch_number} (attempt {retry_count}/{max_retries}): {str(e)}", exc_info=True)
            update_job_status(
                job_id,
                progress_message=f"❌ Error in batch {batch_number}: {str(e)}. Retrying in {backoff_time:.1f}s ({retry_count}/{max_retries})"
            )
            time.sleep(backoff_time)
    
    # If we get here, all retries failed
    raise Exception(f"Failed to process batch {batch_number} after {max_retries} attempts")

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
        },
        "database": os.path.exists(DB_PATH),
        "paths": {
            "drawings_output_dir": str(DRAWINGS_OUTPUT_DIR),
            "memory_store_dir": str(MEMORY_STORE_DIR),
            "database_dir": str(DATABASE_DIR)
        }
    }
    return jsonify(status)

@app.route('/drawings', methods=['GET'])
def get_drawings():
    if not drawing_manager:
        return jsonify({"error": "Drawing manager not available"}), 500
    try:
        include_details = request.args.get('include_details', 'false').lower() == 'true'
        logger.info(f"Getting drawings list with include_details={include_details}")
        
        try:
            # Call the new list_drawings method (instead of the previous approach)
            drawings = drawing_manager.list_drawings(include_details=include_details)
            
            # Check if we got a valid response
            if drawings is None:
                logger.error("Drawing manager returned None for list_drawings")
                drawings = []
                
            # Log successful retrieval
            logger.info(f"Successfully retrieved {len(drawings)} drawings")
            
            # Return the drawings list
            return jsonify({"drawings": drawings})
            
        except AttributeError as e:
            # Fallback to get_available_drawings if list_drawings doesn't exist
            # (This is for backward compatibility during deployment transition)
            logger.warning(f"list_drawings method not available, falling back to get_available_drawings: {e}")
            
            drawings = drawing_manager.get_available_drawings()
            logger.info(f"Fallback retrieved {len(drawings)} drawings using get_available_drawings")
            
            # If details were requested but we couldn't provide them, log a warning
            if include_details:
                logger.warning("Could not provide detailed drawing information as requested")
                
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
        
        # Create the job in the database
        job_id = create_analysis_job(query, drawings, use_cache)
        
        # Start processing in background
        analysis_thread = threading.Thread(
            target=process_analysis_job,
            args=(job_id,),
            name=f"AnalysisJob-{job_id[:8]}"
        )
        analysis_thread.daemon = True
        analysis_thread.start()
        
        # Return immediately with job ID
        return jsonify({"job_id": job_id})
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to start analysis: {str(e)}"}), 500

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    try:
        job = get_job(job_id)
        if job:
            return jsonify(job)
        else:
            return jsonify({"error": f"Job {job_id} not found"}), 404
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get job status: {str(e)}"}), 500

@app.route('/job-logs/<job_id>', methods=['GET'])
def get_job_logs(job_id):
    """Get detailed logs for a job."""
    try:
        limit = int(request.args.get('limit', 100))
        since_id = request.args.get('since_id', None)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if since_id:
            cursor.execute("""
            SELECT id, timestamp, message FROM job_messages 
            WHERE job_id = ? AND id > ? 
            ORDER BY id DESC LIMIT ?
            """, (job_id, since_id, limit))
        else:
            cursor.execute("""
            SELECT id, timestamp, message FROM job_messages 
            WHERE job_id = ? 
            ORDER BY id DESC LIMIT ?
            """, (job_id, limit))
        
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            "job_id": job_id,
            "logs": logs,
            "count": len(logs)
        })
    except Exception as e:
        logger.error(f"Error getting job logs: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to get job logs: {str(e)}"}), 500

@app.route('/jobs', methods=['GET'])
def list_jobs():
    try:
        active_jobs = list_active_jobs()
        return jsonify({"active_jobs": active_jobs})
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}", exc_info=True)
        return jsonify({"error": f"Failed to list jobs: {str(e)}"}), 500

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
        # Create a sanitized filename
        safe_original_filename = werkzeug.utils.secure_filename(file.filename)
        sheet_name = Path(safe_original_filename).stem.replace(" ", "_").replace("-", "_").replace(".", "_")
        
        # Create the proper directory structure for this drawing
        sheet_output_dir = DRAWINGS_OUTPUT_DIR / sheet_name
        os.makedirs(sheet_output_dir, exist_ok=True)
        
        # Save file directly to its final destination
        pdf_file_path = sheet_output_dir / f"{sheet_name}.pdf"
        file.save(pdf_file_path)
        
        # Create job in database
        job_data = {
            "id": str(uuid.uuid4()),
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
        job_id = create_job(job_data)
        logger.info(f"Created job {job_id} for file {file.filename}")
        
        # Start processing in background
        thread = threading.Thread(
            target=process_pdf_job,
            args=(pdf_file_path, job_id, file.filename),
            name=f"Upload-{job_id[:8]}"
        )
        thread.daemon = True
        thread.start()
        
        # Return immediately with job ID
        return jsonify({"job_id": job_id})
    except Exception as e:
        logger.error(f"Error during upload: {str(e)}", exc_info=True)
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

# --- Cleanup Thread ---
def cleanup_old_jobs_thread():
    while True:
        try:
            time.sleep(3600)  # Check once per hour
            deleted_count = cleanup_old_jobs(hours=24)
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old jobs")
        except Exception as e:
            logger.error(f"Error in job cleanup thread: {str(e)}", exc_info=True)

cleanup_thread = threading.Thread(target=cleanup_old_jobs_thread, name="JobCleanupThread")
cleanup_thread.daemon = True
cleanup_thread.start()

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
