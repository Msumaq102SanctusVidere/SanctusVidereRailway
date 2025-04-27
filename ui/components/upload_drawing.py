# --- Filename: components/upload_drawing.py ---

import streamlit as st
import os
import time
import logging

try:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    grandparent_dir = os.path.dirname(parent_dir)
    if grandparent_dir not in sys.path:
        sys.path.append(grandparent_dir)

    from api_client import upload_drawing, get_job_status
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("Successfully imported api_client in upload_drawing_component.")

except ImportError as e:
    st.error(f"Failed to import api_client in upload component: {e}")
    def upload_drawing_component():
        st.error("Upload component disabled due to import error.")
        return False
    raise ImportError(f"Stopping due to failed api_client import in upload_drawing.py: {e}")

# Define polling interval and timeout
POLLING_INTERVAL_SECONDS = 5
MAX_POLLING_TIME_SECONDS = 1800

def upload_drawing_component():
    """
    Render a file uploader for PDFs.
    Uses st.status for displaying progress while polling the background job.
    Returns True only if the background job completes successfully.
    """
    st.header("Upload New Drawing")
    uploaded_file = st.file_uploader(
        label="Select a PDF drawing to upload and process",
        type=["pdf"],
        key="pdf_uploader",
        help="Upload a construction drawing in PDF format. Processing will start automatically."
    )

    # Use session state to track the upload job ID and prevent re-submission
    if 'upload_job_id' not in st.session_state:
        st.session_state.upload_job_id = None

    # --- Handle File Upload ---
    if uploaded_file is not None:
        # Check if this specific file upload is already being processed or has been processed
        current_file_key = f"upload_status_{uploaded_file.name}_{uploaded_file.size}"
        if current_file_key not in st.session_state:
             st.session_state[current_file_key] = {"job_id": None, "status": "new"}

        file_status_info = st.session_state[current_file_key]

        # Only start a new upload if status is 'new'
        if file_status_info["status"] == "new":
            st.info(f"⏳ Starting upload for {uploaded_file.name}...")
            try:
                # Get file bytes directly from Streamlit's uploaded_file
                file_bytes = uploaded_file.getbuffer()
                logger.info(f"Uploading {uploaded_file.name} ({len(file_bytes)} bytes) directly to API")
                
                # Pass directly to the API - no temp files!
                resp = upload_drawing(file_bytes, uploaded_file.name)
                logger.info(f"Initial response from /upload for {uploaded_file.name}: {resp}")

                # Get the job_id
                job_id = resp.get("job_id")
                if job_id:
                    st.session_state[current_file_key]["job_id"] = job_id
                    st.session_state[current_file_key]["status"] = "processing"
                    logger.info(f"Upload processing job started for {uploaded_file.name}: {job_id}")
                    st.rerun()
                else:
                    error_msg = resp.get('error', 'Failed to initiate upload processing job.')
                    st.error(f"❌ Upload initiation failed: {error_msg}")
                    logger.error(f"Failed to get job_id for {uploaded_file.name}. Response: {resp}")
                    st.session_state[current_file_key]["status"] = "failed"
                    st.session_state[current_file_key]["error"] = error_msg

            except Exception as e:
                st.error(f"❌ Error during upload setup: {e}")
                logger.error(f"Error in upload component before polling for {uploaded_file.name}: {e}", exc_info=True)
                st.session_state[current_file_key]["status"] = "failed"
                st.session_state[current_file_key]["error"] = str(e)

        # --- Monitor Job Progress using st.status ---
        job_id = file_status_info.get("job_id")
        current_status = file_status_info.get("status")

        if job_id and current_status == "processing":
            # Use st.status to show progress for the ongoing job
            with st.status(f"Processing {uploaded_file.name} (Job: {job_id[:8]}...)", expanded=True) as status_container:
                start_time = time.time()
                consecutive_error_count = 0
                MAX_CONSECUTIVE_ERRORS = 5

                while True:
                    elapsed_time = time.time() - start_time
                    if elapsed_time > MAX_POLLING_TIME_SECONDS:
                         error_msg = f"Processing timed out after {MAX_POLLING_TIME_SECONDS // 60} minutes."
                         logger.error(f"Polling timeout for upload job {job_id}")
                         status_container.update(label=f"⌛ {error_msg}", state="error", expanded=True)
                         st.session_state[current_file_key]["status"] = "failed"
                         st.session_state[current_file_key]["error"] = "Polling Timeout"
                         return False

                    try:
                        job = get_job_status(job_id)
                        consecutive_error_count = 0

                        percent = job.get("progress", 0)
                        backend_status = job.get("status", "unknown")
                        messages = job.get("progress_messages", [])
                        current_phase = job.get("current_phase", "")
                        error = job.get("error")

                        # Update UI INSIDE the status container
                        status_container.write(f"**Phase:** {current_phase}")
                        st.progress(int(percent), text=f"Overall Progress: {percent}%")
                        st.write("--- Recent Updates ---")
                        for msg in messages[-5:]:
                            st.text(msg.split(" - ", 1)[-1])

                        # Check for job completion or failure reported by backend
                        if backend_status == "completed":
                            result_info = job.get("result", {})
                            drawing_name = result_info.get('drawing_name', uploaded_file.name)
                            logger.info(f"Upload job {job_id} completed successfully.")
                            
                            # Update status container
                            status_container.update(label=f"✅ Processing Complete", state="complete", expanded=True)
                            
                            # Show prominent success message OUTSIDE the status container
                            st.success(f"✅ UPLOAD COMPLETE: {drawing_name} has been successfully processed!")
                            st.info("The drawing is now available for analysis in the drawing list.")
                            
                            # Add a refresh button
                            if st.button("Refresh Drawings List", key="refresh_after_upload"):
                                # Set refresh flag in session state
                                st.session_state["refresh_drawings"] = True
                                # Signal the main app
                                return True
                            
                            # Update session state
                            st.session_state[current_file_key]["status"] = "completed"
                            st.session_state[current_file_key]["drawing_name"] = drawing_name
                            
                            # Signal completion to main app
                            return True

                        elif backend_status == "failed":
                            fail_msg = f"❌ Processing Failed: {error or 'Unknown backend error.'}"
                            logger.error(f"Upload job {job_id} failed. Error: {error}")
                            status_container.update(label=fail_msg, state="error", expanded=True)
                            st.session_state[current_file_key]["status"] = "failed"
                            st.session_state[current_file_key]["error"] = error or 'Unknown backend error.'
                            return False

                        # Wait before next poll if still processing
                        time.sleep(POLLING_INTERVAL_SECONDS)

                    except Exception as poll_e:
                        consecutive_error_count += 1
                        logger.error(f"Error polling upload job status {job_id} (Attempt {consecutive_error_count}/{MAX_CONSECUTIVE_ERRORS}): {poll_e}", exc_info=False)
                        status_container.write(f"⚠️ Warning: Could not retrieve job status (Attempt {consecutive_error_count}). Retrying...")

                        if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                             error_msg = f"Polling failed after {MAX_CONSECUTIVE_ERRORS} consecutive errors."
                             logger.error(f"Stopping polling for upload job {job_id}. Last error: {poll_e}")
                             status_container.update(label=f"❌ {error_msg}", state="error", expanded=True)
                             st.session_state[current_file_key]["status"] = "failed"
                             st.session_state[current_file_key]["error"] = "Polling Failed"
                             return False

                        # Wait a bit longer after an error
                        time.sleep(POLLING_INTERVAL_SECONDS * (consecutive_error_count + 1))

        elif current_status == "completed":
             # For previously completed uploads, show success status with drawing name
             drawing_name = file_status_info.get("drawing_name", uploaded_file.name)
             st.success(f"✅ Already processed: {drawing_name}")
             
             # Provide a way to view/use the drawing
             st.info("This drawing is available for analysis in the drawing list.")

        elif current_status == "failed":
             # Show detailed error for failed uploads
             st.error(f"❌ Upload failed: {uploaded_file.name}")
             st.error(f"Error: {file_status_info.get('error', 'Unknown error')}")
             st.info("You can try uploading this file again.")

    # Default return if no file uploaded in this run, or process finished/failed in previous run
    return False
