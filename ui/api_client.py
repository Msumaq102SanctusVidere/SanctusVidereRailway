# --- Filename: ui/api_client.py (Revised for Direct File Uploads) ---

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # Disables warnings for verify=False

import requests
import logging # Import the logging library
import os # Import os for env vars
from urllib.parse import quote #<-- Import quote for URL encoding
import re # Import re for pattern matching

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

# --- REVISED DELETE DRAWING FUNCTION ---
def delete_drawing(drawing_name):
    """Request deletion of a specific drawing file from the backend."""
    if not API_BASE_URL:
        logger.error("Cannot delete drawing: BACKEND_API_URL not configured.")
        return {"success": False, "error": "Backend URL not configured"}

    # First get the list of actual drawings from the backend to find the closest match
    try:
        available_drawings = get_drawings()
        logger.info(f"Fetched {len(available_drawings)} drawings to find match for '{drawing_name}'")
        
        # Try to find an exact match first (case-sensitive)
        if drawing_name in available_drawings:
            logger.info(f"Found exact match for '{drawing_name}'")
            actual_drawing_name = drawing_name
        else:
            # If no exact match, look for a case-insensitive match or similar name
            # This covers cases where the UI name differs slightly from backend storage
            for available_drawing in available_drawings:
                # Case-insensitive comparison
                if available_drawing.lower() == drawing_name.lower():
                    logger.info(f"Found case-insensitive match: '{available_drawing}' for '{drawing_name}'")
                    actual_drawing_name = available_drawing
                    break
                # Normalize comparison (remove common separators)
                normalized_available = re.sub(r'[_\s-]', '', available_drawing.lower())
                normalized_requested = re.sub(r'[_\s-]', '', drawing_name.lower())
                if normalized_available == normalized_requested:
                    logger.info(f"Found normalized match: '{available_drawing}' for '{drawing_name}'")
                    actual_drawing_name = available_drawing
                    break
            else:
                # No match found after trying case-insensitive and normalized approaches
                logger.error(f"No matching drawing found for '{drawing_name}' in {available_drawings}")
                return {"success": False, "error": f"Drawing {drawing_name} not found or cannot be matched"}
    except Exception as e:
        logger.error(f"Error while trying to find matching drawing: {e}")
        # Fall back to using the original name if we can't fetch the list
        actual_drawing_name = drawing_name

    # URL-encode the actual drawing name to handle spaces, slashes, etc., safely in the URL path
    encoded_drawing_name = quote(actual_drawing_name)
    url = f"{API_BASE_URL}/delete_drawing/{encoded_drawing_name}"
    logger.info(f"Requesting deletion of drawing '{actual_drawing_name}' (original request: '{drawing_name}') via DELETE to: {url}")

    try:
        # Use requests.delete method
        resp = requests.delete(url, verify=False, timeout=60) # Add a reasonable timeout
        response_text = resp.text # Get text before potential raise_for_status

        logger.info(f"Delete Response Status Code: {resp.status_code}")
        logger.info(f"Delete Response Text (first 500 chars): {response_text[:500]}")

        # Check for HTTP errors (4xx, 5xx)
        resp.raise_for_status()

        # Attempt to parse JSON response, assuming backend sends success/error info
        try:
            json_response = resp.json()
            logger.info("Successfully parsed delete response JSON.")
             # Assume response contains 'success' field based on the UI logic
            if not json_response.get("success", False):
                 logger.warning(f"Deletion request for '{actual_drawing_name}' returned success=false or missing: {json_response}")
            return json_response
        except requests.exceptions.JSONDecodeError:
             # If the response was successful (2xx) but not JSON, maybe it's just a 204 No Content
             if 200 <= resp.status_code < 300:
                  logger.warning(f"Deletion request for '{actual_drawing_name}' succeeded (status {resp.status_code}) but returned non-JSON content. Assuming success.")
                  return {"success": True} # Assume success on 2xx non-JSON
             else:
                 # This case should technically be caught by raise_for_status, but for safety:
                 logger.error(f"Deletion request for '{actual_drawing_name}' failed with status {resp.status_code} and non-JSON response: {response_text}")
                 return {"success": False, "error": f"Server returned status {resp.status_code}", "details": response_text}

    # --- Specific Error Handling ---
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error during delete for '{actual_drawing_name}': {http_err} - Status Code: {resp.status_code}")
        logger.error(f"Response Body: {response_text}")
        # Try to parse error details from response if possible
        try:
            error_details = resp.json()
        except requests.exceptions.JSONDecodeError:
            error_details = response_text
        return {"success": False, "error": f"Server returned error: {resp.status_code}", "details": error_details}
    except requests.exceptions.Timeout:
        logger.error(f"Request timed out deleting '{actual_drawing_name}' from {url}")
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error deleting '{actual_drawing_name}' from {url}: {conn_err}", exc_info=True)
        return {"success": False, "error": f"Connection error: {str(conn_err)}"}
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request failed during delete for '{actual_drawing_name}': {req_err}", exc_info=True)
        return {"success": False, "error": f"Network or request error: {str(req_err)}"}
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error in delete_drawing for '{actual_drawing_name}': {e}", exc_info=True)
        return {"success": False, "error": f"Client-side error during delete request: {str(e)}"}
# --- END REVISED DELETE FUNCTION ---
