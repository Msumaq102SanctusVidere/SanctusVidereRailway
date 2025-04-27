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
