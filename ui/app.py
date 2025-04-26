# --- Filename: ui/app.py (Frontend Streamlit UI - Enhanced Progress Tracking) ---

import streamlit as st
import time
import logging
import sys
import os
import json
import re
from pathlib import Path
import datetime
from typing import List, Dict, Any, Tuple, Optional

# --- Path Setup ---
try:
    # Add the current directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
        
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - UI - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)
    logger.info("Path and logging setup complete")
except ImportError as e:
    print(f"Error setting up paths: {e}")
    sys.exit(1)

# --- Import API Client and UI Components ---
try:
    # Import api_client.py from ui folder (root level)
    from api_client import (
        health_check as check_backend_health,
        get_drawings,
        delete_drawing,
        upload_drawing,
        start_analysis as analyze_drawings,
        get_job_status,
        get_job_logs  # New function to get detailed logs
    )
    
    # Import components from components folder
    from components.control_row import control_row
    from components.drawing_list import drawing_list
    from components.progress_bar import progress_indicator
    from components.query_box import query_box
    from components.results_pane import results_pane
    from components.upload_drawing import upload_drawing_component
    from components.log_console import log_console  # Component for log display
    
    logger.info("Successfully imported UI components and API client")
except ImportError as e:
    logger.error(f"Failed to import UI components or API client: {e}")
    st.error(f"Failed to load UI components: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Unexpected error during imports: {e}", exc_info=True)
    st.error(f"Unexpected error during startup: {e}")
    sys.exit(1)

# --- Helper Function for Refreshing Drawings ---
def refresh_drawings():
    try:
        st.session_state.drawings = get_drawings()
        st.session_state.drawings_last_updated = time.time()
        logger.info(f"Refreshed drawings list, found {len(st.session_state.drawings)} drawings")
        return True
    except Exception as e:
        logger.error(f"Failed to refresh drawings: {e}", exc_info=True)
        return False

# --- Get Current Job Status ---
def get_current_job_status(job_id: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Get the current job status with error handling and caching.
    
    Args:
        job_id: The ID of the job to query
        force_refresh: Whether to force a fresh API call
        
    Returns:
        Dict containing the job status
    """
    # Use cached status if available and not forcing refresh
    if not force_refresh and "job_status" in st.session_state and st.session_state.job_status:
        cached_status = st.session_state.job_status
        # Only use cache if it's for the right job and fresh (less than 1 second old)
        if (cached_status.get("id") == job_id and 
            "cached_at" in cached_status and 
            time.time() - cached_status["cached_at"] < 1.0):
            return cached_status
    
    # Get fresh status from API
    try:
        status = get_job_status(job_id)
        if status and isinstance(status, dict):
            # Add cache timestamp
            status["cached_at"] = time.time()
            # Store in session state
            st.session_state.job_status = status
            return status
        else:
            logger.warning(f"Received invalid status for job {job_id}: {status}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching job status for {job_id}: {e}", exc_info=True)
        return {}

# --- Process Completed Jobs ---
def process_completed_job(job_status: Dict[str, Any]) -> None:
    """Process a completed job and extract results."""
    try:
        # Get the result object
        result = job_status.get("result", {})
        
        # Store the complete result object for debugging
        st.session_state.raw_job_result = result
        
        # If result is a string, try to parse it
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                # If not valid JSON, store as-is
                st.session_state.analysis_results = result
                return
        
        # Extract analysis text from result structure
        if isinstance(result, dict):
            # Direct analysis field
            if "analysis" in result:
                st.session_state.analysis_results = result["analysis"]
                return
                
            # Check for batch structure
            if "batches" in result and isinstance(result["batches"], list) and result["batches"]:
                for batch in result["batches"]:
                    if isinstance(batch, dict) and "result" in batch:
                        batch_result = batch["result"]
                        if isinstance(batch_result, dict) and "analysis" in batch_result:
                            st.session_state.analysis_results = batch_result["analysis"]
                            return
        
        # Fallback: store the whole result
        st.session_state.analysis_results = json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error processing completed job: {e}", exc_info=True)
        st.session_state.analysis_results = f"Error processing results: {str(e)}"

# --- Initialize Session State ---
def initialize_session_state():
    if "backend_healthy" not in st.session_state:
        st.session_state.backend_healthy = False
    if "drawings" not in st.session_state:
        st.session_state.drawings = []
    if "drawings_last_updated" not in st.session_state:
        st.session_state.drawings_last_updated = 0
    if "selected_drawings" not in st.session_state:
        st.session_state.selected_drawings = []
    if "query" not in st.session_state:
        st.session_state.query = ""
    if "current_job_id" not in st.session_state:
        st.session_state.current_job_id = None
    if "job_status" not in st.session_state:
        st.session_state.job_status = None
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = None
    if "raw_job_result" not in st.session_state:
        st.session_state.raw_job_result = None
    if "drawing_to_delete" not in st.session_state:
        st.session_state.drawing_to_delete = None
    if "upload_job_id" not in st.session_state:
        st.session_state.upload_job_id = None
    if "show_advanced_logs" not in st.session_state:
        st.session_state.show_advanced_logs = False
    if "log_level_filter" not in st.session_state:
        st.session_state.log_level_filter = "INFO"
    if "upload_success" not in st.session_state:
        st.session_state.upload_success = False
    if "last_poll_time" not in st.session_state:
        st.session_state.last_poll_time = 0
    logger.info("Session state initialized")

initialize_session_state()

# --- Main Application Logic ---
def main():
    # --- Page Configuration ---
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")
    
    # --- Title Area ---
    st.title("Sanctus Videre 1.0")
    st.caption("Construction Drawing Analysis Platform")
    st.divider()
    
    # --- Backend Health Check & Initial Drawing Fetch ---
    backend_healthy = False
    try:
        health_status = check_backend_health()
        backend_healthy = health_status.get("status") == "ok"
        if backend_healthy:
            st.session_state.backend_healthy = True
            # If drawings haven't been loaded or it's been over 30 seconds
            if not st.session_state.drawings or (time.time() - st.session_state.drawings_last_updated) > 30:
                refresh_drawings()
            logger.info("Backend health check passed, drawings refreshed if needed")
        else:
            st.session_state.backend_healthy = False
            st.error("⚠️ Backend service unavailable. Please check server status.")
            logger.error(f"Backend unhealthy: {health_status}")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Unable to connect to backend service: {e}")
        logger.error(f"Backend connection error: {e}", exc_info=True)

    # --- Sidebar for Upload ---
    with st.sidebar:
        st.header("Upload Drawing")
        upload_success = upload_drawing_component()
        if upload_success:
            # Mark successful upload for refreshing drawings
            st.session_state.upload_success = True
            # Refresh drawings if upload was successful
            refresh_drawings()
            st.rerun()

    # --- Main Layout (Two Columns) ---
    col1, col2 = st.columns([1, 2])

    # --- Left Column: Drawing Selection & Deletion ---
    with col1:
        st.subheader("Select Drawings")

        # --- Deletion Confirmation UI ---
        if st.session_state.drawing_to_delete:
            st.warning(f"**Confirm Deletion:** Are you sure you want to permanently delete `{st.session_state.drawing_to_delete}`?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Yes, Delete", type="primary", key="confirm_delete_button", use_container_width=True):
                    try:
                        target_drawing = st.session_state.drawing_to_delete
                        logger.info(f"Attempting to delete drawing: {target_drawing}")
                        response = delete_drawing(target_drawing) # Call API

                        # Trust only the "success" boolean from the backend
                        if isinstance(response, dict) and response.get("success") is True:
                            st.success(f"Drawing deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")

                            # Refresh UI only on explicit success from backend
                            if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)
                            st.session_state.drawing_to_delete = None
                            refresh_drawings()
                            st.rerun()
                        else:
                            # If not success==True, show the error from the backend
                            default_error = f"Failed to delete drawing. Unknown error."
                            error_message = response.get("error", default_error) if isinstance(response, dict) else default_error
                            st.error(error_message) # Display the error received
                            logger.error(f"API call delete_drawing failed for '{target_drawing}'. Response: {response}")
                    except Exception as e:
                        # Handle exceptions during the API call itself (e.g., network error)
                        st.error(f"Error communicating with server: {e}")
                        logger.error(f"Exception during delete_drawing API call: {e}", exc_info=True)
                        # Clear pending delete on communication exception and rerun
                        st.session_state.drawing_to_delete = None
                        st.rerun()

            with cancel_col:
                if st.button("Cancel", key="cancel_delete_button", use_container_width=True):
                    logger.info(f"Deletion cancelled for: {st.session_state.drawing_to_delete}")
                    st.session_state.drawing_to_delete = None # Clear pending delete state
                    st.rerun()
            st.divider()

        # --- Drawing List Rendering ---
        with st.container(border=True):
            if not st.session_state.backend_healthy:
                st.warning("⚠️ Cannot load drawings. Backend is unavailable.")
            elif not st.session_state.drawings:
                st.info("No drawings available. Upload a drawing to get started.")
            else:
                # Refresh button
                if st.button("Refresh Drawings", key="refresh_drawings", use_container_width=True):
                    with st.spinner("Refreshing drawings..."):
                        refresh_drawings()
                        st.rerun()
                
                # Use the drawing_list component
                selected_drawing_names = drawing_list(st.session_state.drawings)
                
                # Update selection in session state
                if selected_drawing_names is not None:
                    st.session_state.selected_drawings = selected_drawing_names
                    
                # Display delete buttons for each selected drawing
                if st.session_state.selected_drawings:
                    st.divider()
                    for drawing in st.session_state.selected_drawings:
                        if st.button(f"Delete '{drawing}'", key=f"delete_{drawing}"):
                            st.session_state.drawing_to_delete = drawing
                            st.rerun()
                else:
                    st.caption("Select one or more drawings to analyze")

    # --- Right Column: Query, Controls, Progress, Results ---
    try:
        with col2:
            # --- Query Input ---
            # Use a form for the query and submit button
            with st.form(key="query_form", clear_on_submit=False):
                # Query text area
                query = st.text_area(
                    "Type your question here...",
                    value=st.session_state.get("query", ""),
                    height=120,
                    disabled=not st.session_state.backend_healthy,
                    placeholder="Example: What are the finishes specified for the private offices?"
                )
                
                # Force new analysis checkbox
                force_new = st.checkbox("Force new analysis (ignore cache)", value=False)
                
                # Submit button
                disabled = not (st.session_state.backend_healthy and 
                              st.session_state.selected_drawings and 
                              query.strip())
                submit_clicked = st.form_submit_button(
                    "Analyze Drawings",
                    type="primary",
                    disabled=disabled,
                    use_container_width=True
                )
            
            # Store the query in session state
            st.session_state.query = query
            
            # Stop analysis button
            if st.session_state.current_job_id:
                if st.button("Stop Analysis", key="stop_analysis", use_container_width=True):
                    st.session_state.current_job_id = None
                    st.info("Analysis stopped.")
                    st.rerun()
            
            # Handle form submission
            if submit_clicked and st.session_state.selected_drawings and query.strip():
                with st.spinner("Starting analysis..."):
                    try:
                        response = analyze_drawings(
                            query,
                            st.session_state.selected_drawings,
                            use_cache=not force_new
                        )
                        
                        if response and "job_id" in response:
                            st.session_state.current_job_id = response["job_id"]
                            st.session_state.job_status = None
                            st.session_state.analysis_results = None
                            st.session_state.raw_job_result = None
                            logger.info(f"Started analysis job: {st.session_state.current_job_id}")
                            st.rerun()
                        else:
                            st.error(f"Failed to start analysis: {response}")
                            logger.error(f"Failed to start analysis: {response}")
                    except Exception as e:
                        st.error(f"Error starting analysis: {e}")
                        logger.error(f"Error starting analysis: {e}", exc_info=True)
            
            # --- Progress Display ---
            if st.session_state.current_job_id:
                # Get fresh job status (force refresh every 2 seconds to avoid stale data)
                current_time = time.time()
                force_refresh = (current_time - st.session_state.get("last_poll_time", 0)) >= 2.0
                
                job_status = get_current_job_status(st.session_state.current_job_id, force_refresh)
                if force_refresh:
                    st.session_state.last_poll_time = current_time
                
                # Display progress using the progress_indicator component
                if job_status:
                    # Update the progress bar
                    progress = job_status.get("progress", 0)
                    status = job_status.get("status", "")
                    
                    # Progress container
                    with st.container(border=True):
                        # Progress header
                        if status == "completed":
                            st.success("Processing Complete (100%)")
                        elif status == "failed":
                            st.error("Processing Failed")
                            error_msg = job_status.get("error", "Unknown error")
                            st.error(f"Error: {error_msg}")
                        else:
                            st.subheader(f"Processing: {progress}% Complete")
                        
                        # Main progress bar
                        st.progress(progress / 100)
                        
                        # Status information
                        current_phase = job_status.get("current_phase", "")
                        
                        # Clean up phase text
                        if current_phase:
                            # Remove emojis from phase 
                            current_phase = re.sub(r'[^\w\s]', '', current_phase).strip()
                            st.info(f"Current Phase: {current_phase}")
                        
                        # Show latest message
                        messages = job_status.get("progress_messages", [])
                        if messages:
                            latest_message = messages[-1]
                            # Extract just the message part without timestamp
                            if " - " in latest_message:
                                latest_message = latest_message.split(" - ", 1)[1]
                            
                            # Remove emojis
                            latest_message = re.sub(r'[^\w\s,.\-;:()/]', '', latest_message).strip()
                            
                            # Show latest update
                            st.write(f"Latest Update: {latest_message}")
                    
                    # Check if job is complete or failed
                    if status == "completed":
                        # Process completed job
                        process_completed_job(job_status)
                        st.session_state.current_job_id = None
                        st.success("Analysis completed successfully!")
                        st.rerun()
                    elif status == "failed":
                        error_msg = job_status.get("error", "Unknown error")
                        st.error(f"Analysis failed: {error_msg}")
                        st.session_state.current_job_id = None
                else:
                    # Fallback to basic progress if detailed status not available
                    st.warning("Unable to retrieve job status. Retrying...")
                    time.sleep(1)  # Brief delay
                    st.rerun()  # Force refresh
            
            # --- Results Display ---
            if st.session_state.analysis_results:
                st.header("Analysis Results")
                
                # Display results using the results_pane component
                if isinstance(st.session_state.analysis_results, dict):
                    results_text = json.dumps(st.session_state.analysis_results, indent=2)
                else:
                    results_text = str(st.session_state.analysis_results)
                
                # Use the results_pane component
                results_pane(results_text)
                
                # Clear results button
                if st.button("Clear Results", key="clear_results"):
                    st.session_state.analysis_results = None
                    st.session_state.raw_job_result = None
                    st.rerun()
            
            # --- Technical Information (Expandable) ---
            if st.session_state.raw_job_result:
                with st.expander("Technical Information", expanded=False):
                    st.json(st.session_state.raw_job_result)
                    
                    if st.button("Copy Raw JSON", key="copy_json"):
                        # Copy to clipboard via JavaScript
                        raw_json = json.dumps(st.session_state.raw_job_result)
                        st.write("JSON copied to clipboard!")
                    
                    if st.button("Clear Technical Data", key="clear_tech_data"):
                        st.session_state.raw_job_result = None
                        st.rerun()
                
    except Exception as e:
        st.error(f"An error occurred in the UI: {e}")
        logger.error(f"Unhandled UI exception: {e}", exc_info=True)


# --- Run the App ---
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}", exc_info=True)
