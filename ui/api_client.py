import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # Disables warnings for verify=False

import requests
import logging # Import the logging library
import os # Import os for file path operations and env vars

# --- Add Logging Setup ---
# Configure logging to show messages from this client
logging.basicConfig(
    level=logging.INFO, # Set the logging level (INFO, DEBUG, ERROR, etc.)
    format='%(asctime)s - CLIENT - %(levelname)s - %(message)s' # Define log message format
)
logger = logging.getLogger(__name__) # Create a logger instance for this module
# --- End Logging Setup ---

# --- Load API_BASE_URL Safely ---
# It's better to load environment variables here or ensure they are loaded where needed.
# Make sure the BACKEND_API_URL environment variable is set in your Railway UI service.
API_BASE_URL = os.environ.get("BACKEND_API_URL")
if not API_BASE_URL:
    logger.error("CRITICAL: BACKEND_API_URL environment variable is not set!")
    # You might want to raise an error or set a default for local testing,
    # but in production, it should be set.
    # For now, we'll let it proceed, but requests will fail if it's None.
# --- End API_BASE_URL Loading ---


def health_check():
    """Ping the API to make sure it’s up."""
    if not API_BASE_URL: return {"status": "error", "message": "Backend URL not configured"}
    url = f"{API_BASE_URL}/health"
    logger.info(f"Sending health check to: {url}")
    try:
        resp = requests.get(url, verify=False, timeout=10) # Added timeout
        resp.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error during health check: {e}")
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}

def get_drawings():
    """Fetch the list of available drawings you can analyze."""
    if not API_BASE_URL: return [] # Return empty list if URL not set
    url = f"{API_BASE_URL}/drawings"
    logger.info(f"Fetching drawings from: {url}")
    try:
        resp = requests.get(url, verify=False, timeout=60) # Added timeout
        resp.raise_for_status()
        data = resp.json()
        return data.get("drawings", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get drawings: {e}")
        return [] # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error getting drawings: {e}")
        return []


def upload_drawing(file_path):
    """Upload a PDF file for processing. Includes debugging and error handling."""
    if not API_BASE_URL:
        logger.error("Cannot upload drawing: BACKEND_API_URL not configured.")
        return {"success": False, "error": "Backend URL not configured"}

    api_url = f"{API_BASE_URL}/upload"
    logger.info(f"Attempting to upload: {file_path} to {api_url}")

    try:
        # Check if file exists before opening
        if not os.path.exists(file_path):
             logger.error(f"File not found at path: {file_path}")
             # Return a dictionary structure similar to successful/failed uploads
             return {"success": False, "error": f"Client-side error: File not found at {file_path}"}
        if os.path.getsize(file_path) == 0:
            logger.error(f"File is empty: {file_path}")
            return {"success": False, "error": f"Client-side error: File is empty {file_path}"}

        # Use context manager for file opening
        with open(file_path, "rb") as f:
            # Pass filename and content type for better backend handling (esp. werkzeug)
            files = {"file": (os.path.basename(file_path), f, 'application/pdf')}

            # --- Make the request with a timeout ---
            # A long timeout is needed because backend processing can take time
            # 300 seconds = 5 minutes. Adjust if needed.
            logger.info(f"POSTing file to {api_url}...")
            resp = requests.post(api_url, files=files, verify=False, timeout=300)
            logger.info(f"Received response from {api_url}")

        # --- DEBUGGING: Log status and raw response text ---
        logger.info(f"Upload Response Status Code: {resp.status_code}")
        response_text = resp.text
        # Log only the beginning of the response to avoid flooding logs if it's large HTML
        logger.info(f"Upload Response Text (first 500 chars): {response_text[:500]}")
        # --- END DEBUGGING ---

        # Check status code *before* trying to parse JSON
        # Use raise_for_status() which handles 4xx/5xx errors
        resp.raise_for_status()

        # If status code was OK (2xx), *now* try to parse JSON
        # This is the line that originally caused the error if response wasn't JSON
        json_response = resp.json()
        logger.info("Successfully parsed JSON response.")
        return json_response

    # --- Specific Error Handling ---
    except requests.exceptions.HTTPError as http_err:
        # Handle HTTP errors (4xx, 5xx) after logging the response text
        logger.error(f"HTTP error occurred: {http_err} - Status Code: {resp.status_code}")
        logger.error(f"Response Body: {response_text}") # Log the full text on error
        return {"success": False, "error": f"Server returned error: {resp.status_code}", "details": response_text}
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out uploading {file_path} to {api_url}")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.ConnectionError as conn_err:
        # Errors connecting to the server (DNS issues, refused connection etc.)
        logger.error(f"Connection error uploading {file_path} to {api_url}: {conn_err}", exc_info=True)
        return {"success": False, "error": f"Connection error: {str(conn_err)}"}
    except requests.exceptions.JSONDecodeError as json_err:
        # This happens if raise_for_status didn't catch an error, but the body isn't JSON
        logger.error(f"Failed to decode JSON response even after status {resp.status_code}: {json_err}")
        logger.error(f"Response text that failed decoding: {response_text}") # Log the problematic text
        return {"success": False, "error": "Received non-JSON response from server", "details": response_text}
    except requests.exceptions.RequestException as req_err:
        # Catch other requests-related errors
        logger.error(f"Request failed during upload: {req_err}", exc_info=True)
        return {"success": False, "error": f"Network or request error: {str(req_err)}"}
    except FileNotFoundError:
        # This is redundant due to the os.path.exists check, but good practice
        logger.error(f"File not found error for {file_path}")
        return {"success": False, "error": f"Client-side error: File not found at {file_path}"}
    except Exception as e:
        # Catch any other unexpected errors (like file reading issues, permissions)
        logger.error(f"Unexpected error in upload_drawing for {file_path}: {e}", exc_info=True)
        return {"success": False, "error": f"Client-side error during upload: {str(e)}"}


def start_analysis(query, drawings, use_cache=True):
    """Kick off a new analysis job; returns the job ID."""
    if not API_BASE_URL: return {"error": "Backend URL not configured"}
    url = f"{API_BASE_URL}/analyze"
    logger.info(f"Starting analysis via: {url}")
    payload = {
        "query": query,
        "drawings": drawings,
        "use_cache": use_cache
    }
    try:
        # Analysis can also take time, add a timeout
        resp = requests.post(url, json=payload, verify=False, timeout=300)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to start analysis: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error starting analysis: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

def get_job_status(job_id):
    """Check on a running job’s status and progress."""
    if not API_BASE_URL: return {"error": "Backend URL not configured"}
    url = f"{API_BASE_URL}/job-status/{job_id}"
    logger.info(f"Getting job status for {job_id} from: {url}")
    try:
        resp = requests.get(url, verify=False, timeout=60) # Added timeout
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        return {"error": str(e), "status": "error"} # Include status for polling loops
    except Exception as e:
        logger.error(f"Unexpected error getting job status: {e}")
        return {"error": f"Unexpected error: {str(e)}", "status": "error"}
