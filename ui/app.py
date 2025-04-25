# --- Filename: ui/app.py (Frontend Streamlit UI - Revised with Delete Functionality) ---

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

    # --- MODIFIED: Import delete_drawing ---
    from api_client import (
        health_check,
        get_drawings,
        start_analysis,
        get_job_status,
        delete_drawing # <-- Added import
    )
    logger.info("Successfully imported api_client functions.")

except ImportError as e:
    # Try importing from current directory if running standalone for dev
    try:
        logger.warning(f"Could not find api_client in parent dir ({parent_dir}), trying local import...")
        from api_client import health_check, get_drawings, start_analysis, get_job_status, delete_drawing
        logger.info("Successfully imported api_client functions (local).")
    except ImportError:
        st.error(f"Fatal Error: Failed to import api_client: {e}. Check paths and ensure api_client.py exists.")
        logger.error(f"API Client Import Error: {e}", exc_info=True)
        st.stop()


# --- Import UI Components ---
try:
    from components.upload_drawing import upload_drawing_component
    # --- REMOVED: drawing_list component import (integrated below) ---
    # from components.drawing_list import drawing_list
    from components.query_box import query_box
    from components.control_row import control_row
    from components.progress_bar import progress_indicator
    from components.results_pane import results_pane
    logger.info("Successfully imported UI components.")
except ImportError as e:
    st.error(f"Fatal Error: Failed to import UI components: {e}. Check component paths.")
    logger.error(f"Component Import Error: {e}", exc_info=True)
    st.stop()


# --- Helper Function for Refreshing Drawings ---
def refresh_drawings():
    """Fetches drawings from the API and updates session state."""
    try:
        st.session_state.available_drawings = get_drawings()
        logger.info(f"Refreshed drawing list: {len(st.session_state.available_drawings)} drawings.")
    except Exception as e:
        st.error(f"Failed to refresh drawing list from API: {e}")
        logger.error(f"API call get_drawings failed during refresh: {e}", exc_info=True)
        st.session_state.available_drawings = [] # Clear list on error


# --- Main Application Logic ---
def main():
    # --- Page Configuration ---
    st.set_page_config(
        page_title="Sanctus Videre 1.0",
        layout="wide",
        page_icon="🏗️",
        initial_sidebar_state="expanded"
    )

    # --- Title Area ---
    st.title("🏗️ Sanctus Videre 1.0")
    st.caption("Visionary Construction Insights")
    st.divider()

    # --- Initialize Session State ---
    if 'available_drawings' not in st.session_state:
        st.session_state.available_drawings = []
    if 'analysis_job_id' not in st.session_state:
        st.session_state.analysis_job_id = None
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'selected_drawings' not in st.session_state:
         st.session_state.selected_drawings = []
    # --- ADDED: State for pending deletion ---
    if 'drawing_to_delete' not in st.session_state:
         st.session_state.drawing_to_delete = None


    # --- Backend Health Check & Initial Drawing Fetch ---
    try:
        if 'backend_status' not in st.session_state:
            health_info = health_check()
            st.session_state.backend_status = health_info.get("status", "error")
            if st.session_state.backend_status != "healthy":
                 logger.error(f"Backend unhealthy: {health_info}")
            else:
                 logger.info("Backend health check successful.")
                 # Initial fetch only if backend is healthy and list is empty
                 if not st.session_state.available_drawings:
                     refresh_drawings() # Use helper function

        if st.session_state.backend_status != "healthy":
            st.error(f"🚨 API connection issue. Status: '{st.session_state.backend_status}'. Please check the backend service.")
            # Optionally clear drawing_to_delete if backend dies mid-process
            st.session_state.drawing_to_delete = None
            st.stop()

    except Exception as e:
        st.error(f"🚨 Failed to connect to API: {e}")
        logger.error(f"API connection failed during health check/init: {e}", exc_info=True)
        st.session_state.drawing_to_delete = None # Clear on connection error
        st.stop()

    # --- Sidebar for Upload ---
    with st.sidebar:
        upload_completed = upload_drawing_component()

        if upload_completed:
            refresh_drawings() # Use helper function
            st.session_state.selected_drawings = [] # Clear selection after upload
            # Clear any pending delete action if upload happens
            st.session_state.drawing_to_delete = None
            st.rerun()

    # --- Main Layout (Two Columns) ---
    col1, col2 = st.columns([1, 2])

    # --- Left Column: Drawing Selection & Deletion ---
    with col1:
        st.subheader("Select Drawings")

        # --- Deletion Confirmation UI (appears only when needed) ---
        if st.session_state.drawing_to_delete:
            st.warning(f"**Confirm Deletion:** Are you sure you want to permanently delete `{st.session_state.drawing_to_delete}`?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Yes, Delete", type="primary", key="confirm_delete_button", use_container_width=True):
                    try:
                        target_drawing = st.session_state.drawing_to_delete
                        logger.info(f"Attempting to delete drawing: {target_drawing}")
                        response = delete_drawing(target_drawing) # Call API
                        if response.get("success"):
                            st.success(f"Drawing `{target_drawing}` deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")
                            # Remove from selection if it was selected
                            if target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)
                            st.session_state.drawing_to_delete = None # Clear pending delete state
                            refresh_drawings() # Refresh the list from backend
                            st.rerun() # Force redraw
                        else:
                            error_msg = response.get("error", "Unknown error during deletion.")
                            st.error(f"Failed to delete drawing `{target_drawing}`: {error_msg}")
                            logger.error(f"API error deleting {target_drawing}: {error_msg}")
                            # Keep drawing_to_delete state so user can cancel
                    except Exception as e:
                        st.error(f"Error during deletion call for `{st.session_state.drawing_to_delete}`: {e}")
                        logger.error(f"Exception during delete_drawing API call: {e}", exc_info=True)
                        # Keep drawing_to_delete state so user can cancel
            with cancel_col:
                 if st.button("Cancel", key="cancel_delete_button", use_container_width=True):
                    logger.info(f"Deletion cancelled for: {st.session_state.drawing_to_delete}")
                    st.session_state.drawing_to_delete = None # Clear pending delete state
                    st.rerun()
            st.divider() # Separate confirmation from the list

        # --- Drawing List Rendering (Integrated) ---
        with st.container(border=True):
            if not st.session_state.available_drawings:
                st.info("No drawings processed yet. Upload a PDF via the sidebar.")
            else:
                # Track selections locally within this run
                current_selection = []
                # Disable list interactions if confirmation is active
                disable_list = bool(st.session_state.drawing_to_delete)

                if disable_list:
                    st.caption("Confirm or cancel deletion above before selecting drawings.")

                # --- Select All Checkbox ---
                select_all_key = "select_all_drawings"
                # Handle "Select All" logic carefully with session state persistence
                if disable_list:
                     st.checkbox("Select All Drawings", key=select_all_key, disabled=True)
                else:
                    # Check if all are currently selected
                    all_selected = set(st.session_state.selected_drawings) == set(st.session_state.available_drawings)
                    select_all = st.checkbox("Select All Drawings", value=all_selected, key=select_all_key)

                    # If "Select All" state changes, update the session state selection
                    if select_all and not all_selected:
                        st.session_state.selected_drawings = list(st.session_state.available_drawings)
                        st.rerun() # Rerun needed to reflect changes in individual checkboxes
                    elif not select_all and all_selected and st.session_state.available_drawings:
                         st.session_state.selected_drawings = []
                         st.rerun() # Rerun needed

                st.divider()

                # --- Individual Drawing Rows ---
                for drawing_name in sorted(st.session_state.available_drawings):
                    list_col1, list_col2 = st.columns([0.9, 0.1]) # Name | Delete Button
                    with list_col1:
                        # Use session state for checkbox persistence
                        is_selected = drawing_name in st.session_state.selected_drawings
                        new_state = st.checkbox(
                            drawing_name,
                            value=is_selected,
                            key=f"select_{drawing_name}",
                            disabled=disable_list # Disable checkbox during confirmation
                        )
                        # Update selection list based on checkbox interaction
                        if not disable_list and new_state != is_selected:
                            if new_state: # Checked
                                if drawing_name not in st.session_state.selected_drawings:
                                    st.session_state.selected_drawings.append(drawing_name)
                            else: # Unchecked
                                if drawing_name in st.session_state.selected_drawings:
                                    st.session_state.selected_drawings.remove(drawing_name)
                            st.rerun() # Rerun immediately to reflect selection count change

                    with list_col2:
                         # Delete button - sets state to trigger confirmation
                         if st.button("🗑️", key=f"delete_{drawing_name}", help=f"Delete {drawing_name}", disabled=disable_list):
                             st.session_state.drawing_to_delete = drawing_name
                             logger.debug(f"Delete button clicked for {drawing_name}, setting state.")
                             st.rerun() # Rerun to show confirmation dialog

                # Display selection count based on the reliable session state
                st.caption(f"{len(st.session_state.selected_drawings)} selected.")


    # --- Right Column: Query, Controls, Progress, Results ---
    with col2:
        # Disable analysis if deletion confirmation is active
        disable_analysis = bool(st.session_state.drawing_to_delete)

        st.subheader("Analyze Selected Drawings")

        with st.container(border=True):
             query = query_box(disabled=disable_analysis) # Pass disabled state
             st.divider()
             force_new, analyze_clicked, stop_clicked = control_row(disabled=disable_analysis) # Pass disabled state


        # --- Handle Analysis Request ---
        if analyze_clicked and not disable_analysis: # Ensure analyze button works only when not deleting
            selected_list = st.session_state.get('selected_drawings', [])
            if not selected_list:
                st.warning("👈 Please select one or more drawings from the list first.")
            elif not query:
                st.warning("❓ Please enter a query or question above.")
            else:
                # Reset analysis state before starting
                st.session_state.analysis_result = None
                st.session_state.analysis_running = False
                st.session_state.analysis_job_id = None

                st.success(f"🚀 Starting analysis for '{query[:30]}...' on {len(selected_list)} drawing(s)...")
                logger.info(f"User requested analysis. Query: '{query}', Drawings: {selected_list}, ForceNew: {force_new}")
                try:
                    resp = start_analysis(query, selected_list, use_cache=not force_new)
                    job_id = resp.get("job_id")
                    if job_id:
                        st.session_state.analysis_job_id = job_id
                        st.session_state.analysis_running = True
                        logger.info(f"Analysis job started: {job_id}")
                        st.rerun()
                    else:
                        st.error(f"Failed to start analysis: {resp.get('error', 'Unknown API error')}")
                except Exception as e:
                     st.error(f"API Error: Could not start analysis. {e}")
                     logger.error(f"API call start_analysis failed: {e}", exc_info=True)

        # --- Display Analysis Progress ---
        st.divider() # Separate controls from progress/results
        analysis_job_id = st.session_state.get('analysis_job_id')
        if st.session_state.get('analysis_running') and analysis_job_id and not disable_analysis:
            st.subheader("Analysis Progress")
            final_job_status = progress_indicator(analysis_job_id)

            if final_job_status:
                st.session_state.analysis_running = False
                job_status = final_job_status.get("status")
                if job_status == "completed":
                     st.session_state.analysis_result = final_job_status.get("result", "Analysis complete, but no result returned.")
                     logger.info(f"Analysis job {analysis_job_id} completed.")
                     st.rerun() # Rerun to display results immediately
                else:
                     error_msg = final_job_status.get("error", "Analysis failed with unknown error.")
                     logger.error(f"Analysis job {analysis_job_id} failed or polling error: {error_msg}")
                     st.session_state.analysis_result = f"Error during analysis: {error_msg}"
                     st.rerun() # Rerun to display error in results area

        # --- Display Analysis Results ---
        if not st.session_state.get('analysis_running') and st.session_state.get('analysis_result') and not disable_analysis:
             st.subheader("Analysis Results")
             with st.container(border=True):
                results_pane(st.session_state.analysis_result)


        # Handle the Stop button
        if stop_clicked and not disable_analysis:
            job_id_to_stop = st.session_state.get('analysis_job_id')
            if st.session_state.get('analysis_running') and job_id_to_stop:
                st.warning(f"Stopping analysis job {job_id_to_stop}…")
                logger.warning(f"Stop requested for job {job_id_to_stop}")
                # TODO: Implement stop job functionality in backend and api_client
                # try:
                #     stop_response = stop_analysis_job(job_id_to_stop) # Assuming function exists
                #     if stop_response.get("success"):
                #         st.info("Stop request sent successfully.")
                #         st.session_state.analysis_running = False # Assume it stops quickly
                #         st.session_state.analysis_job_id = None
                #         st.session_state.analysis_result = "Analysis stopped by user."
                #     else:
                #          st.error(f"Failed to stop job: {stop_response.get('error')}")
                # except Exception as e:
                #      st.error(f"Error sending stop request: {e}")
                st.session_state.analysis_running = False # Temporarily set to false
                st.session_state.analysis_job_id = None
                st.session_state.analysis_result = "Analysis stopped by user (Stop functionality pending backend)."
                time.sleep(1) # Give user feedback time
                st.rerun()
            else:
                 st.info("No analysis job is currently running.")


# --- Run the App ---
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
         logger.critical(f"A critical error occurred in the main UI thread: {e}", exc_info=True)
         # Avoid showing raw exception in UI if possible, rely on logging
         st.error(f"A critical application error occurred. Please check the logs or contact support.")
