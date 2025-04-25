import streamlit as st
import tempfile
import os
import time # Import the time module for sleep
import logging # Optional: Add logging for debugging

# Import API client functions, including the new one we need
# Ensure api_client.py is accessible from this component's location
try:
    # Assuming api_client is two levels up (components -> ui -> main -> api_client.py)
    # Adjust path if necessary based on your execution context
    import sys
    # Get the directory containing the current file (components/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (ui/)
    parent_dir = os.path.dirname(current_dir)
    # Get the grandparent directory (main/)
    grandparent_dir = os.path.dirname(parent_dir)
    if grandparent_dir not in sys.path:
        sys.path.append(grandparent_dir)

    from api_client import upload_drawing, get_job_status # Need get_job_status now!
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported api_client in upload_drawing_component.")

except ImportError as e:
    st.error(f"Failed to import api_client in upload component: {e}")
    # Make the component unusable if imports fail
    def upload_drawing_component():
        st.error("Upload component disabled due to import error.")
        return False
    # Exit the module loading here if imports failed
    # This prevents NameErrors later if api_client functions aren't defined
    raise ImportError(f"Stopping due to failed api_client import in upload_drawing.py: {e}")
except NameError: # Handle case where logging wasn't set up yet
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Logging re-initialized in upload_drawing_component.")
    from api_client import upload_drawing, get_job_status


# Define polling interval and timeout
POLLING_INTERVAL_SECONDS = 5 # Check status every 5 seconds
MAX_POLLING_TIME_SECONDS = 600 # Stop polling after 10 minutes regardless


def upload_drawing_component():
    """
    Render a file uploader for PDFs.
    When a file is uploaded:
    1. Saves it temporarily on the frontend side.
    2. Calls the backend API's async /upload endpoint.
    3. Receives a job_id immediately.
    4. Polls the /job-status/<job_id> endpoint until the job completes or fails.
    5. Displays progress messages to the user.
    Returns True only if the background job completes successfully.
    """
    st.subheader("Upload New Drawing")
    uploaded_file = st.file_uploader(
        label="Select a PDF to upload",
        type=["pdf"],
        key="pdf_uploader" # Add a key for stability across reruns
    )

    # Use session state to track the upload job ID and prevent re-submission
    if 'upload_job_id' not in st.session_state:
        st.session_state.upload_job_id = None
    if 'upload_in_progress' not in st.session_state:
        st.session_state.upload_in_progress = False
    if 'upload_status_message' not in st.session_state:
        st.session_state.upload_status_message = ""


    if uploaded_file is not None and not st.session_state.upload_in_progress:
        # --- Start new upload process ---
        st.session_state.upload_in_progress = True
        st.session_state.upload_job_id = None # Reset job id
        st.session_state.upload_status_message = f"⏳ Uploading {uploaded_file.name}..."

        # Use a status indicator that persists across reruns during polling
        status_placeholder = st.empty()
        status_placeholder.info(st.session_state.upload_status_message)

        tmp_path = None # Initialize for finally block
        try:
            # 1. Save to a temporary file on the frontend runner
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getbuffer())
                tmp_path = tmp.name
            logger.info(f"Frontend temporary file created: {tmp_path}")

            # 2. Call the (now async) API endpoint
            resp = upload_drawing(tmp_path) # api_client handles logging the call
            logger.info(f"Initial response from /upload: {resp}")

            # 3. Get the job_id
            job_id = resp.get("job_id")
            if job_id:
                st.session_state.upload_job_id = job_id
                st.session_state.upload_status_message = f"✅ File uploaded. Processing started (Job ID: {job_id}). Waiting for completion..."
                status_placeholder.info(st.session_state.upload_status_message)
                logger.info(f"Upload processing job started: {job_id}")

                # --- 4. Poll for status ---
                start_time = time.time()
                while True:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > MAX_POLLING_TIME_SECONDS:
                        st.session_state.upload_status_message = "❌ Polling timed out. Processing might be ongoing in background or failed."
                        status_placeholder.error(st.session_state.upload_status_message)
                        logger.error(f"Polling timeout for job {job_id} after {MAX_POLLING_TIME_SECONDS}s")
                        st.session_state.upload_in_progress = False
                        st.session_state.upload_job_id = None
                        # Need to clear the uploader to allow new attempts
                        # st.session_state.pdf_uploader = None # Requires widget key
                        return False # Indicate failure

                    try:
                        job_status_resp = get_job_status(job_id)
                        status = job_status_resp.get("status", "unknown")
                        progress = job_status_resp.get("progress", 0)
                        messages = job_status_resp.get("progress_messages", [])
                        last_message = messages[-1] if messages else "Waiting..."

                        # Update status display
                        st.session_state.upload_status_message = f"Status: {status.capitalize()} ({progress}%) - {last_message}"
                        status_placeholder.info(st.session_state.upload_status_message)
                        logger.info(f"Polling job {job_id}: Status={status}, Progress={progress}%, LastMsg='{last_message}'")

                        if status == "completed":
                            st.session_state.upload_status_message = f"✅ Successfully processed: {job_status_resp.get('result', {}).get('drawing_name', uploaded_file.name)}"
                            status_placeholder.success(st.session_state.upload_status_message)
                            logger.info(f"Job {job_id} completed successfully.")
                            st.session_state.upload_in_progress = False
                            st.session_state.upload_job_id = None
                            # Clear the uploader state after success to allow new uploads
                            # Setting the key to None might work depending on Streamlit version
                            # st.session_state.pdf_uploader = None # Requires widget key
                            return True # Signal success to main app

                        elif status == "failed":
                            error_msg = job_status_resp.get("error", "Unknown processing error.")
                            st.session_state.upload_status_message = f"❌ Processing failed: {error_msg}"
                            status_placeholder.error(st.session_state.upload_status_message)
                            logger.error(f"Job {job_id} failed: {error_msg}")
                            st.session_state.upload_in_progress = False
                            st.session_state.upload_job_id = None
                            # st.session_state.pdf_uploader = None # Requires widget key
                            return False # Signal failure

                        # Wait before next poll
                        time.sleep(POLLING_INTERVAL_SECONDS)

                    except Exception as poll_e:
                        # Error during polling itself
                        st.session_state.upload_status_message = f"⚠️ Error checking job status: {poll_e}"
                        status_placeholder.warning(st.session_state.upload_status_message)
                        logger.warning(f"Polling error for job {job_id}: {poll_e}", exc_info=True)
                        # Continue polling for a while, but maybe add a counter?
                        time.sleep(POLLING_INTERVAL_SECONDS * 2) # Wait longer after error

            else:
                # Initial /upload call failed to return a job_id
                error_msg = resp.get('error', 'Failed to initiate upload processing.')
                st.session_state.upload_status_message = f"❌ Upload initiation failed: {error_msg}"
                status_placeholder.error(st.session_state.upload_status_message)
                logger.error(f"Failed to get job_id from initial /upload call. Response: {resp}")
                st.session_state.upload_in_progress = False
                st.session_state.upload_job_id = None
                # st.session_state.pdf_uploader = None # Requires widget key
                return False # Signal failure

        except Exception as e:
            # Catch errors during temp file creation or initial API call
            st.session_state.upload_status_message = f"❌ Error during upload setup: {e}"
            status_placeholder.error(st.session_state.upload_status_message)
            logger.error(f"Error in upload component before polling: {e}", exc_info=True)
            st.session_state.upload_in_progress = False
            st.session_state.upload_job_id = None
            # st.session_state.pdf_uploader = None # Requires widget key
            return False # Signal failure

        finally:
            # 5. Clean up the frontend temporary file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    logger.info(f"Frontend temporary file removed: {tmp_path}")
                except Exception as clean_e:
                    logger.warning(f"Failed to remove frontend temp file {tmp_path}: {clean_e}")
            # Reset upload_in_progress if not done by success/failure paths above
            # (e.g., if an exception happened unexpectedly)
            # st.session_state.upload_in_progress = False # Maybe too aggressive?

    elif st.session_state.upload_in_progress:
        # --- Upload is already running, just display current status ---
        # This prevents starting multiple jobs if the user interacts while polling
        status_placeholder = st.empty()
        status_placeholder.info(st.session_state.upload_status_message)
        # We might need to restart the polling loop visually here if Streamlit works
        # in a way that stops the previous loop on interaction. This can get complex.
        # For now, just displaying the last known status message. A full solution
        # might involve managing the polling loop state more carefully across reruns.
        logger.debug("Upload component rerun while upload_in_progress=True")


    # Default return if no file or already processing
    return False
