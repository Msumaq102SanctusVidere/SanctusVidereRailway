# --- Filename: ui/app.py (Frontend Streamlit UI - Simplified Delete Handling) ---

import streamlit as st
import time
import logging
import sys
import os
import json
from pathlib import Path

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
        get_job_status
    )
    
    # Import components from components folder
    from components.control_row import control_row
    from components.drawing_list import drawing_list
    from components.progress_bar import progress_indicator
    from components.query_box import query_box
    from components.results_pane import results_pane
    from components.upload_drawing import upload_drawing_component
    
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
    if "drawing_to_delete" not in st.session_state:
        st.session_state.drawing_to_delete = None
    if "upload_job_id" not in st.session_state:
        st.session_state.upload_job_id = None
    logger.info("Session state initialized")

initialize_session_state()

# --- Main Application Logic ---
def main():
    # --- Page Configuration ---
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")
    # --- Title Area ---
    st.title("🏗️ Sanctus Videre 1.0"); st.caption("Visionary Construction Insights"); st.divider()
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
            st.error("⚠️ Backend service unhealthy. Please check server status.")
            logger.error(f"Backend unhealthy: {health_status}")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Unable to connect to backend service: {e}")
        logger.error(f"Backend connection error: {e}", exc_info=True)

    # --- Sidebar for Upload ---
    with st.sidebar:
        upload_success = upload_drawing_component()
        if upload_success:
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

                        # --- SIMPLIFIED ERROR HANDLING ---
                        # Trust only the "success" boolean from the backend
                        if isinstance(response, dict) and response.get("success") is True:
                            st.success(f"Drawing `{target_drawing}` deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")

                            # Refresh UI only on explicit success from backend
                            if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)
                            st.session_state.drawing_to_delete = None
                            refresh_drawings()
                            st.rerun()
                        else:
                            # If not success==True, show the error from the backend
                            default_error = f"Failed to delete '{target_drawing}'. Unknown error."
                            error_message = response.get("error", default_error) if isinstance(response, dict) else default_error
                            st.error(error_message) # Display the error received
                            logger.error(f"API call delete_drawing failed for '{target_drawing}'. Response: {response}")
                            # Do NOT clear drawing_to_delete or rerun here - let user Cancel
                        # --- END SIMPLIFIED HANDLING ---

                    except Exception as e:
                        # Handle exceptions during the API call itself (e.g., network error)
                        st.error(f"Error communicating with server during deletion: {e}")
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
                if st.button("🔄 Refresh", key="refresh_drawings", use_container_width=True):
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
                        if st.button(f"🗑️ Delete '{drawing}'", key=f"delete_{drawing}"):
                            st.session_state.drawing_to_delete = drawing
                            st.rerun()
                else:
                    st.caption("Select drawings to analyze or delete")

    # --- Right Column: Query, Controls, Progress, Results ---
    try:
        with col2:
            # Use the query_box component
            query = query_box(disabled=not st.session_state.backend_healthy)
            st.session_state.query = query
            
            # Use the control_row component
            disabled = not (st.session_state.backend_healthy and 
                          st.session_state.selected_drawings and 
                          st.session_state.query.strip())
            force_new, analyze_clicked, stop_clicked = control_row(disabled=disabled)
            
            # Handle analyze button click
            if analyze_clicked and st.session_state.selected_drawings and st.session_state.query.strip():
                with st.spinner("Starting analysis..."):
                    try:
                        response = analyze_drawings(
                            st.session_state.query,
                            st.session_state.selected_drawings,
                            use_cache=not force_new
                        )
                        
                        if response and "job_id" in response:
                            st.session_state.current_job_id = response["job_id"]
                            st.session_state.job_status = None
                            st.session_state.analysis_results = None
                            logger.info(f"Started analysis job: {st.session_state.current_job_id}")
                            st.rerun()
                        else:
                            st.error(f"Failed to start analysis: {response}")
                            logger.error(f"Failed to start analysis: {response}")
                    except Exception as e:
                        st.error(f"Error starting analysis: {e}")
                        logger.error(f"Error starting analysis: {e}", exc_info=True)
            
            # Handle stop button click
            if stop_clicked and st.session_state.current_job_id:
                st.session_state.current_job_id = None
                st.success("Analysis stopped.")
                st.rerun()
            
            # Display job progress or results using progress_indicator
            if st.session_state.current_job_id:
                result = progress_indicator(st.session_state.current_job_id)
                
                if result and result.get("status") == "completed":
                    st.session_state.analysis_results = result.get("result", {})
                    st.session_state.current_job_id = None
                    st.success("Analysis completed successfully!")
                elif result and result.get("status") == "failed":
                    error_msg = result.get("error", "Unknown error")
                    st.error(f"Analysis failed: {error_msg}")
                    st.session_state.current_job_id = None
            
            # Show stored results if available
            if st.session_state.analysis_results:
                results_text = json.dumps(st.session_state.analysis_results, indent=2)
                results_pane(results_text)
                
                # Clear results button
                if st.button("Clear Results", key="clear_results"):
                    st.session_state.analysis_results = None
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
