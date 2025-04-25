import streamlit as st
import time
import logging # Add logging

# Assuming api_client is accessible (adjust path if needed)
try:
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    grandparent_dir = os.path.dirname(parent_dir)
    if grandparent_dir not in sys.path:
        sys.path.append(grandparent_dir)
    from api_client import get_job_status
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported api_client in progress_bar.")
except ImportError as e:
    st.error(f"Failed to import api_client in progress component: {e}")
    # Define a dummy function if import fails
    def progress_indicator(job_id):
        st.error("Progress component disabled due to import error.")
        return {"status": "failed", "error": "Component import failed"}
    raise ImportError(f"Stopping due to failed api_client import in progress_bar.py: {e}")
except NameError: # Handle case where logging wasn't set up yet
     import logging
     logging.basicConfig(level=logging.INFO)
     logger = logging.getLogger(__name__)
     logger.warning("Logging re-initialized in progress_bar.")
     from api_client import get_job_status


# --- Constants for Polling ---
POLLING_INTERVAL_SECONDS = 3 # Increased polling interval
MAX_POLLING_TIME_SECONDS = 1800 # Stop polling after 30 minutes


def progress_indicator(job_id):
    """
    Polls the /job-status endpoint, updates a progress bar and status messages,
    includes error handling and timeout, and returns the final job dict when done.

    Args:
        job_id (str): The ID of the job to monitor.

    Returns:
        dict: The final job status dictionary when the job is completed or failed,
              or an error dictionary if polling times out or fails persistently.
    """
    if not job_id:
        logger.warning("progress_indicator called with no job_id.")
        return {"status": "failed", "error": "No job ID provided to progress indicator."}

    logger.info(f"Starting progress monitoring for job_id: {job_id}")

    # Placeholders for the progress bar and messages
    prog_bar = st.progress(0)
    status_box = st.empty() # Placeholder for status text/messages
    status_box.info(f"✨ Starting process for Job ID: {job_id}...")

    start_time = time.time()
    last_error = None
    consecutive_error_count = 0
    MAX_CONSECUTIVE_ERRORS = 5 # Stop polling after too many errors

    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_POLLING_TIME_SECONDS:
            error_msg = f"Polling timed out after {MAX_POLLING_TIME_SECONDS} seconds."
            logger.error(f"Polling timeout for job {job_id}.")
            status_box.error(f"⌛ {error_msg}")
            return {"status": "failed", "error": error_msg, "job_id": job_id}

        try:
            # --- Get Job Status ---
            job = get_job_status(job_id)
            last_error = None # Reset error on successful call
            consecutive_error_count = 0

            # --- Extract Status Info ---
            percent = job.get("progress", 0)
            status = job.get("status", "unknown")
            messages = job.get("progress_messages", [])
            current_phase = job.get("current_phase", "") # Get current phase if available
            error = job.get("error") # Check for error reported by the job itself

            # --- Update UI ---
            prog_bar.progress(int(percent)) # Ensure integer for progress bar

            status_text = f"**Status:** {status.capitalize()}"
            if current_phase:
                status_text += f" | **Phase:** {current_phase}"

            # Display latest messages
            message_display = "\n".join(messages[-5:]) # Show last 5 messages

            status_box.info(f"{status_text}\n\n---\n{message_display}")

            # --- Check for Completion or Failure ---
            if status == "completed":
                logger.info(f"Job {job_id} completed.")
                status_box.success(f"✅ Job Completed!\n\n{message_display}") # Final success message
                return job # Return the final job state

            elif status == "failed":
                logger.error(f"Job {job_id} failed. Reported error: {error}")
                fail_msg = f"❌ Job Failed: {error or 'Unknown reason'}"
                status_box.error(f"{fail_msg}\n\n---\n{message_display}") # Final failure message
                return job # Return the final job state (contains error)

            # --- Wait before next poll ---
            time.sleep(POLLING_INTERVAL_SECONDS)

        except Exception as e:
            # --- Handle Errors During Polling ---
            last_error = str(e)
            consecutive_error_count += 1
            logger.error(f"Error polling job status for {job_id} (Attempt {consecutive_error_count}/{MAX_CONSECUTIVE_ERRORS}): {e}", exc_info=True)
            status_box.warning(
                f"⚠️ Warning: Could not retrieve job status (Attempt {consecutive_error_count}/{MAX_CONSECUTIVE_ERRORS}). Retrying...\nError: {e}"
            )

            if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                 error_msg = f"Polling failed after {MAX_CONSECUTIVE_ERRORS} consecutive errors."
                 logger.error(f"Stopping polling for job {job_id} due to repeated errors. Last error: {last_error}")
                 status_box.error(f"❌ {error_msg} Please check logs or try again later.")
                 return {"status": "failed", "error": error_msg, "last_known_error": last_error, "job_id": job_id}

            # Wait a bit longer after an error before retrying
            time.sleep(POLLING_INTERVAL_SECONDS * (consecutive_error_count + 1))
