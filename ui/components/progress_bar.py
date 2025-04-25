# --- Filename: components/progress_bar.py ---

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
    # Check if logger has handlers to avoid duplicate messages
    if not logger.hasHandlers():
         logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Successfully imported api_client in progress_bar.")
except ImportError as e:
    st.error(f"Failed to import api_client in progress component: {e}")
    # Define a dummy function if import fails
    def progress_indicator(job_id):
        st.error("Progress component disabled due to import error.")
        return {"status": "failed", "error": "Component import failed"}
    raise ImportError(f"Stopping due to failed api_client import in progress_bar.py: {e}")


# --- Constants for Polling ---
POLLING_INTERVAL_SECONDS = 3 # Check status every 3 seconds for analysis
MAX_POLLING_TIME_SECONDS = 1800 # Stop polling after 30 minutes


def progress_indicator(job_id):
    """
    Polls the /job-status endpoint for an ANALYSIS job, updates a status
    container with progress bar and messages, includes error handling and timeout,
    and returns the final job dict when done.

    Args:
        job_id (str): The ID of the analysis job to monitor.

    Returns:
        dict or None: The final job status dictionary when the job is completed or failed,
                      or None if the job is still running. Returns an error dictionary
                      if polling times out or fails persistently.
    """
    if not job_id:
        logger.warning("progress_indicator called with no job_id.")
        # Don't display error directly, just return None as if not running
        return None

    logger.info(f"Monitoring analysis progress for job_id: {job_id}")

    # Use st.status for combined progress display
    # The label can be updated dynamically if needed, but a generic one works
    with st.status(f"Analyzing Job {job_id[:8]}...", expanded=True) as status_container:
        start_time = time.time()
        consecutive_error_count = 0
        MAX_CONSECUTIVE_ERRORS = 5

        # We don't use an infinite loop here; instead, we rely on Streamlit's rerun
        # mechanism. We perform ONE poll attempt per rerun if the job is still running.
        try:
            elapsed_time = time.time() - start_time # Check timeout first
            if elapsed_time > MAX_POLLING_TIME_SECONDS:
                 error_msg = f"Analysis polling timed out after {MAX_POLLING_TIME_SECONDS // 60} minutes."
                 logger.error(f"Polling timeout for analysis job {job_id}.")
                 status_container.update(label=f"⌛ {error_msg}", state="error", expanded=True)
                 # Return a dict indicating failure to the main app
                 return {"status": "failed", "error": error_msg, "job_id": job_id}

            # --- Get Job Status ---
            job = get_job_status(job_id)

            # --- Extract Status Info ---
            percent = job.get("progress", 0)
            status = job.get("status", "unknown")
            messages = job.get("progress_messages", [])
            current_phase = job.get("current_phase", "")
            error = job.get("error")

            # --- Update UI ---
            status_container.write(f"**Phase:** {current_phase}")
            st.progress(int(percent), text=f"Overall Progress: {percent}%")
            st.write("--- Recent Updates ---")
            for msg in messages[-5:]: # Show last 5 messages
                 # Show message part after timestamp, if timestamp exists
                 msg_parts = msg.split(" - ", 1)
                 display_msg = msg_parts[-1] if len(msg_parts) > 1 else msg
                 st.text(f"- {display_msg}")

            # --- Check for Completion or Failure ---
            if status == "completed":
                logger.info(f"Analysis job {job_id} completed.")
                status_container.update(label="✅ Analysis Completed!", state="complete", expanded=False)
                return job # Return final job data

            elif status == "failed":
                logger.error(f"Analysis job {job_id} failed. Reported error: {error}")
                fail_msg = f"❌ Analysis Failed: {error or 'Unknown reason'}"
                status_container.update(label=fail_msg, state="error", expanded=True)
                return job # Return final job data (contains error)

            # --- If still running, schedule next check ---
            # No infinite loop here, rely on Streamlit rerun + time.sleep
            time.sleep(POLLING_INTERVAL_SECONDS)
            st.rerun() # Trigger a rerun to poll again

        except Exception as e:
             # Handle Errors During Polling (only log once per error burst)
             # Using session state to track polling errors for this job
             error_key = f"poll_error_count_{job_id}"
             if error_key not in st.session_state: st.session_state[error_key] = 0
             st.session_state[error_key] += 1
             consecutive_error_count = st.session_state[error_key]

             logger.error(f"Error polling analysis job {job_id} (Attempt {consecutive_error_count}): {e}", exc_info=False)
             status_container.write(f"⚠️ Warning: Could not retrieve job status (Attempt {consecutive_error_count}). Retrying...")

             if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                 error_msg = f"Polling failed after {MAX_CONSECUTIVE_ERRORS} consecutive errors."
                 logger.error(f"Stopping polling for analysis job {job_id}. Last error: {e}")
                 status_container.update(label=f"❌ {error_msg}", state="error", expanded=True)
                 # Reset error count in state
                 st.session_state[error_key] = 0
                 return {"status": "failed", "error": error_msg, "job_id": job_id}
             else:
                 # Wait longer after error and rerun
                 time.sleep(POLLING_INTERVAL_SECONDS * (consecutive_error_count + 1))
                 st.rerun() # Trigger rerun to try polling again

    # If the code reaches here, it means the status container was exited
    # normally, likely because the job finished in a previous run. Return None.
    return None
