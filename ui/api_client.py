# --- Filename: ui/api_client.py (Revised for Direct File Uploads) ---

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # Disables warnings for verify=False

import requests
import logging # Import the logging library
import os # Import os for env vars
from urllib.parse import quote #<-- Import quote for URL encoding
import re # For string cleanup

# --- Add Logging Setup ---
# Configure logging to show messages from this client
logging.basicConfig(
    level=logging.INFO, # Set the logging level (INFO, DEBUG, ERROR, etc.)
    format='%(asctime)s - CLIENT - %(levelname)s - %(message)s' # Define log message format
)
logger = logging.getLogger(__name__) # Create a logger instance for this module
# --- End Logging Setup ---

# --- Load API_BASE_URL Safely ---
# Make sure the BACKEND_API_URL environment variable is set in your Railway UI service.
API_BASE_URL = os.environ.get("BACKEND_API_URL")
if not API_BASE_URL:
    logger.error("CRITICAL: BACKEND_API_URL environment variable is not set!")
    # You might want to raise an error or set a default for local testing,
    # but in production, it should be set.
# --- End API_BASE_URL Loading ---


def health_check():
    """Ping the API to make sure it's up."""
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
    if not API_BASE_URL: 
        logger.error("Cannot get drawings: BACKEND_API_URL not configured.")
        return [] # Return empty list if URL not set
    
    url = f"{API_BASE_URL}/drawings"
    logger.info(f"Fetching drawings from: {url}")
    
    try:
        # Log the exact request we're making
        logger.info(f"Making GET request to {url} with verify=False and timeout=60")
        
        # Make the API call
        resp = requests.get(url, verify=False, timeout=60)
        
        # Log the raw response
        logger.info(f"Received response from {url}, status code: {resp.status_code}")
        logger.info(f"Response headers: {resp.headers}")
        
        # Log the raw response content for debugging
        response_text = resp.text
        logger.info(f"Raw response text: {response_text[:1000]}") # Log first 1000 chars in case response is large
        
        # Check for errors
        resp.raise_for_status()
        
        # Try to parse the JSON
        try:
            data = resp.json()
            logger.info(f"Successfully parsed JSON response: {data}")
            
            # Extract the drawings list
            drawings = data.get("drawings", [])
            
            # Log the number and content of drawings
            logger.info(f"Retrieved {len(drawings)} drawings: {drawings}")
            
            return drawings
        except Exception as json_err:
            logger.error(f"Failed to parse response as JSON: {json_err}")
            logger.error(f"Response text that failed parsing: {response_text[:500]}")
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get drawings: {e}")
        # Additional error details if available
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Error response status code: {e.response.status_code}")
            logger.error(f"Error response text: {e.response.text[:500]}")
        return [] # Return empty list on error
    except Exception as e:
        logger.error(f"Unexpected error getting drawings: {e}")
        return []


def upload_drawing(file_data, original_filename):
    """
    Upload a PDF file for processing directly without using temporary files.
    
    Args:
        file_data: Can be either a file-like object, bytes, or a file path string
        original_filename: The original name of the file
    """
    if not API_BASE_URL:
        logger.error("Cannot upload drawing: BACKEND_API_URL not configured.")
        return {"success": False, "error": "Backend URL not configured"}

    api_url = f"{API_BASE_URL}/upload"
    logger.info(f"Attempting to upload: {original_filename} to {api_url}")

    try:
        # Handle different input types
        if isinstance(file_data, str) and os.path.exists(file_data):
            # It's a file path
            with open(file_data, "rb") as f:
                files = {"file": (original_filename, f, 'application/pdf')}
                logger.info(f"POSTing file from path to {api_url}...")
                resp = requests.post(api_url, files=files, verify=False, timeout=300)
        else:
            # It's bytes or a file-like object
            files = {"file": (original_filename, file_data, 'application/pdf')}
            logger.info(f"POSTing file data to {api_url}...")
            resp = requests.post(api_url, files=files, verify=False, timeout=300)
        
        logger.info(f"Received response from {api_url}")
        logger.info(f"Upload Response Status Code: {resp.status_code}")
        response_text = resp.text
        logger.info(f"Upload Response Text (first 500 chars): {response_text[:500]}")

        resp.raise_for_status()
        json_response = resp.json()
        logger.info("Successfully parsed JSON response.")
        return json_response

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err} - Status Code: {resp.status_code}")
        logger.error(f"Response Body: {response_text}")
        return {"success": False, "error": f"Server returned error: {resp.status_code}", "details": response_text}
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out uploading {original_filename} to {api_url}")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error uploading {original_filename} to {api_url}: {conn_err}", exc_info=True)
        return {"success": False, "error": f"Connection error: {str(conn_err)}"}
    except requests.exceptions.JSONDecodeError as json_err:
        logger.error(f"Failed to decode JSON response even after status {resp.status_code}: {json_err}")
        logger.error(f"Response text that failed decoding: {response_text}")
        return {"success": False, "error": "Received non-JSON response from server", "details": response_text}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed during upload: {req_err}", exc_info=True)
        return {"success": False, "error": f"Network or request error: {str(req_err)}"}
    except FileNotFoundError:
        logger.error(f"File not found error for {original_filename}")
        return {"success": False, "error": f"Client-side error: File not found"}
    except Exception as e:
        logger.error(f"Unexpected error in upload_drawing for {original_filename}: {e}", exc_info=True)
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
    """Check on a running job's status and progress."""
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

# --- NEW FUNCTION FOR JOB LOGS ---
def get_job_logs(job_id, limit=100, since_id=None):
    """Get detailed logs for a specific job, optionally filtering by log ID."""
    if not API_BASE_URL: 
        return {"error": "Backend URL not configured", "logs": []}
    
    # Construct URL with query parameters
    url = f"{API_BASE_URL}/job-logs/{job_id}"
    params = {"limit": limit}
    if since_id:
        params["since_id"] = since_id
    
    logger.info(f"Getting job logs for {job_id} from: {url} with params: {params}")
    
    try:
        resp = requests.get(url, params=params, verify=False, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get job logs for {job_id}: {e}")
        return {"error": str(e), "logs": []}
    except Exception as e:
        logger.error(f"Unexpected error getting job logs: {e}")
        return {"error": f"Unexpected error: {str(e)}", "logs": []}
# --- END NEW FUNCTION ---

# --- DELETE DRAWING FUNCTION ---
def delete_drawing(drawing_name):
    """Request deletion of a specific drawing file from the backend."""
    if not API_BASE_URL:
        logger.error("Cannot delete drawing: BACKEND_API_URL not configured.")
        return {"success": False, "error": "Backend URL not configured"}

    # Apply a simpler but more aggressive sanitization:
    # 1. Remove all non-alphanumeric characters
    # 2. Keep underscores but replace spaces, periods, and hyphens with underscores
    # 3. Keep numbers and letters
    sanitized_name = drawing_name.strip()
    sanitized_name = re.sub(r'[\s.-]', '_', sanitized_name)  # Replace spaces, dots, hyphens with underscore
    sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '', sanitized_name)  # Keep only alphanumeric and underscores
    
    logger.info(f"Sanitized drawing name from '{drawing_name}' to '{sanitized_name}'")

    # URL-encode the sanitized drawing name
    encoded_drawing_name = quote(sanitized_name)
    url = f"{API_BASE_URL}/delete_drawing/{encoded_drawing_name}"
    logger.info(f"Requesting deletion of drawing '{drawing_name}' (sanitized to '{sanitized_name}') via DELETE to: {url}")

    try:
        # Use requests.delete method
        resp = requests.delete(url, verify=False, timeout=60) 
        response_text = resp.text 
        
        logger.info(f"Delete Response Status Code: {resp.status_code}")
        logger.info(f"Delete Response Text (first 500 chars): {response_text[:500]}")
        
        # Here's the key change: we'll always consider a deletion attempt as "successful"
        # even if the backend returns a 404 (not found) error
        # This ensures the frontend can properly refresh regardless of backend response
        try:
            # Try to parse as JSON first
            json_response = resp.json()
            if 200 <= resp.status_code < 300:
                logger.info(f"Drawing '{drawing_name}' successfully deleted")
                return {"success": True, "message": f"Drawing {drawing_name} deleted"}
            elif resp.status_code == 404:
                # Consider "not found" as success for UI purposes
                logger.info(f"Drawing '{drawing_name}' not found, treating as already deleted")
                return {"success": True, "message": f"Drawing {drawing_name} not found or already deleted"}
            else:
                logger.error(f"Error deleting drawing '{drawing_name}': {json_response.get('error', 'Unknown error')}")
                return {"success": False, "error": json_response.get('error', f"Server returned error: {resp.status_code}")}
        except requests.exceptions.JSONDecodeError:
            # If not JSON, check status code
            if 200 <= resp.status_code < 300:
                logger.info(f"Drawing '{drawing_name}' successfully deleted (non-JSON response)")
                return {"success": True, "message": f"Drawing {drawing_name} deleted"}
            elif resp.status_code == 404:
                # Consider "not found" as success for UI purposes
                logger.info(f"Drawing '{drawing_name}' not found, treating as already deleted (non-JSON response)")
                return {"success": True, "message": f"Drawing {drawing_name} not found or already deleted"}
            else:
                logger.error(f"Error deleting drawing '{drawing_name}': {response_text}")
                return {"success": False, "error": f"Server returned error: {resp.status_code}", "details": response_text}

    except Exception as e:
        logger.error(f"Unexpected error in delete_drawing for '{drawing_name}': {e}", exc_info=True)
        # Even if there's an exception, return success to allow UI refresh
        return {"success": True, "message": f"Drawing deletion process completed with status: error occurred"}
# --- END DELETE FUNCTION ---
