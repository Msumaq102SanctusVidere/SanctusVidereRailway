# --- Filename: ui/app.py (Frontend Streamlit UI - Revised for Modern Look) ---

import streamlit as st
import time
import logging
import sys
import os

# --- Path Setup (Ensure API client is found) ---
try:
    current_dir = os.path.dirname(os.path.abspath(__file__)) # ui/
    parent_dir = os.path.dirname(current_dir) # main/
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    logger = logging.getLogger(__name__)
    # Check if logger has handlers to avoid duplicate messages if run multiple times
    if not logger.hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - UI - %(levelname)s - %(message)s')

    from api_client import health_check, get_drawings, start_analysis, get_job_status
    logger.info("Successfully imported api_client functions.")

except ImportError as e:
    st.error(f"Fatal Error: Failed to import api_client: {e}. Check paths.")
    logger.error(f"API Client Import Error: {e}", exc_info=True)
    st.stop()

# --- Import UI Components ---
try:
    from components.upload_drawing import upload_drawing_component
    from components.drawing_list import drawing_list
    from components.query_box import query_box
    from components.control_row import control_row
    from components.progress_bar import progress_indicator
    from components.results_pane import results_pane
    logger.info("Successfully imported UI components.")
except ImportError as e:
    st.error(f"Fatal Error: Failed to import UI components: {e}. Check component paths.")
    logger.error(f"Component Import Error: {e}", exc_info=True)
    st.stop()


# --- Main Application Logic ---
def main():
    # --- Page Configuration (Apply Theme) ---
    st.set_page_config(
        page_title="Sanctus Videre 1.0",
        layout="wide", # Wide layout often feels more modern for dashboards
        page_icon="🏗️",
        initial_sidebar_state="expanded" # Keep sidebar open initially
    )

    # --- Title Area ---
    # Use standard Streamlit titles - they will inherit the theme font/color
    st.title("🏗️ Sanctus Videre 1.0")
    st.caption("Visionary Construction Insights") # Use caption for subtitle
    st.divider()

    # --- Initialize Session State ---
    # (Ensures variables persist across reruns)
    if 'available_drawings' not in st.session_state:
        st.session_state.available_drawings = []
    if 'analysis_job_id' not in st.session_state:
        st.session_state.analysis_job_id = None
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'selected_drawings' not in st.session_state:
         st.session_state.selected_drawings = [] # Store selected drawings

    # --- Backend Health Check ---
    try:
        # Perform health check only once per session or periodically if needed
        if 'backend_status' not in st.session_state:
            health_info = health_check()
            st.session_state.backend_status = health_info.get("status", "error")
            if st.session_state.backend_status != "healthy":
                 logger.error(f"Backend unhealthy: {health_info}")
            else:
                 logger.info("Backend health check successful.")
                 # Initial fetch drawings only if backend is healthy and list is empty
                 if not st.session_state.available_drawings:
                     st.session_state.available_drawings = get_drawings()
                     logger.info(f"Fetched initial drawings: {len(st.session_state.available_drawings)}")

        if st.session_state.backend_status != "healthy":
            st.error(f"🚨 API connection issue. Status: '{st.session_state.backend_status}'. Please check the backend service.")
            st.stop()

    except Exception as e:
        st.error(f"🚨 Failed to connect to API: {e}")
        logger.error(f"API connection failed during health check/init: {e}", exc_info=True)
        st.stop()

    # --- Sidebar for Upload ---
    with st.sidebar:
        # Use the revised upload component which handles async processing/polling internally
        upload_completed = upload_drawing_component() # This now polls internally

        if upload_completed:
            # Upload component shows its own success message now
            # Refresh drawing list from API and force UI update
            st.session_state.available_drawings = get_drawings()
            logger.info("Upload complete, refreshed drawing list.")
            # Clear selection after upload? Optional.
            # st.session_state.selected_drawings = []
            st.rerun()

    # --- Main Layout (Two Columns) ---
    col1, col2 = st.columns([1, 2]) # Adjusted ratio slightly

    # --- Left Column: Drawing Selection ---
    with col1:
        st.subheader("Select Drawings") # Use subheader
        with st.container(border=True): # Add a border for visual grouping
            if not st.session_state.available_drawings:
                st.info("No drawings processed yet. Upload a PDF via the sidebar.")
            else:
                # Use drawing_list component, store selection in session state
                st.session_state.selected_drawings = drawing_list(st.session_state.available_drawings)
                st.caption(f"{len(st.session_state.selected_drawings)} selected.")


    # --- Right Column: Query, Controls, Progress, Results ---
    with col2:
        st.subheader("Analyze Selected Drawings") # Use subheader

        # Group query and controls
        with st.container(border=True):
             query = query_box()
             st.divider() # Visual separator
             force_new, analyze_clicked, stop_clicked = control_row()


        # --- Handle Analysis Request ---
        if analyze_clicked:
            selected_list = st.session_state.get('selected_drawings', []) # Get from state
            if not selected_list:
                st.warning("👈 Please select one or more drawings from the list first.")
            elif not query:
                st.warning("❓ Please enter a query or question above.")
            else:
                st.success(f"🚀 Starting analysis for '{query[:30]}...' on {len(selected_list)} drawing(s)...")
                logger.info(f"User requested analysis. Query: '{query}', Drawings: {selected_list}, ForceNew: {force_new}")
                try:
                    resp = start_analysis(query, selected_list, use_cache=not force_new)
                    job_id = resp.get("job_id")
                    if job_id:
                        st.session_state.analysis_job_id = job_id
                        st.session_state.analysis_result = None # Clear previous result
                        st.session_state.analysis_running = True
                        logger.info(f"Analysis job started: {job_id}")
                        st.rerun() # Rerun immediately to show progress indicator
                    else:
                        st.error(f"Failed to start analysis: {resp.get('error', 'Unknown API error')}")
                        st.session_state.analysis_job_id = None
                        st.session_state.analysis_running = False
                except Exception as e:
                     st.error(f"API Error: Could not start analysis. {e}")
                     logger.error(f"API call start_analysis failed: {e}", exc_info=True)
                     st.session_state.analysis_job_id = None
                     st.session_state.analysis_running = False

        st.divider() # Separate controls from progress/results

        # --- Display Analysis Progress ---
        analysis_job_id = st.session_state.get('analysis_job_id')
        if st.session_state.get('analysis_running') and analysis_job_id:
            st.subheader("Analysis Progress") # Add header for this section
            # progress_indicator handles its own polling and UI updates (using st.status)
            final_job_status = progress_indicator(analysis_job_id)

            # Check if the indicator returned a final status dict
            if final_job_status:
                st.session_state.analysis_running = False # Stop polling loop
                job_status = final_job_status.get("status")
                if job_status == "completed":
                     st.session_state.analysis_result = final_job_status.get("result", "Analysis complete, but no result returned.")
                     logger.info(f"Analysis job {analysis_job_id} completed.")
                     # Don't rerun here, let results display below
                else: # Job failed or polling failed
                     error_msg = final_job_status.get("error", "Analysis failed with unknown error.")
                     # Error already shown by progress_indicator, just log it
                     logger.error(f"Analysis job {analysis_job_id} failed or polling error: {error_msg}")
                     st.session_state.analysis_result = f"Error during analysis: {error_msg}" # Display error in results area

        # --- Display Analysis Results ---
        if not st.session_state.get('analysis_running') and st.session_state.get('analysis_result'):
             st.subheader("Analysis Results") # Add header
             with st.container(border=True): # Put results in a bordered container
                results_pane(st.session_state.analysis_result)


        # Handle the Stop button (placeholder - requires backend implementation)
        if stop_clicked:
            st.warning("Stopping analysis… (Functionality not yet implemented)")
            # TODO: Implement stop job functionality in backend and api_client

# --- Run the App ---
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
         logger.critical(f"A critical error occurred in the main UI thread: {e}", exc_info=True)
         st.error(f"A critical error occurred: {e}. Please check the logs.")
