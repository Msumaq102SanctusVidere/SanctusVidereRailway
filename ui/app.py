# --- Filename: ui/app.py (Frontend Streamlit UI - Graceful 404 Delete Handling) ---

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

    from api_client import (
        health_check,
        get_drawings,
        start_analysis,
        get_job_status,
        delete_drawing
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
    # Ensure components are correctly placed relative to this script or PYTHONPATH is set
    from components.upload_drawing import upload_drawing_component
    from components.query_box import query_box
    from components.control_row import control_row
    from components.progress_bar import progress_indicator
    from components.results_pane import results_pane
    logger.info("Successfully imported UI components.")
except ImportError as e:
    st.error(f"Fatal Error: Failed to import UI components: {e}. Check component paths (e.g., components/upload_drawing.py).")
    logger.error(f"Component Import Error: {e}", exc_info=True)
    st.stop()
except Exception as e:
    st.error(f"Fatal Error: An unexpected error occurred importing UI components: {e}")
    logger.error(f"Unexpected Component Import Error: {e}", exc_info=True)
    st.stop()


# --- Helper Function for Refreshing Drawings ---
def refresh_drawings():
    """Fetches drawings from the API and updates session state. Handles errors."""
    try:
        # Ensure the get_drawings() function returns a list, even on API error
        api_result = get_drawings()
        if isinstance(api_result, list):
            st.session_state.available_drawings = api_result
            logger.info(f"Refreshed drawing list: {len(st.session_state.available_drawings)} drawings.")
        else:
            # Handle case where API might return something unexpected instead of raising error
            logger.error(f"API get_drawings returned unexpected type: {type(api_result)}. Setting empty list.")
            st.session_state.available_drawings = []
            st.warning("Could not retrieve drawings from API. Received unexpected data.")

    except Exception as e:
        st.error(f"Failed to refresh drawing list from API: {e}")
        logger.error(f"API call get_drawings failed during refresh: {e}", exc_info=True)
        st.session_state.available_drawings = [] # Ensure it's an empty list on error

# --- Initialize Session State ---
# Do this *before* page config potentially? Or right after. Crucial it runs early.
def initialize_session_state():
    """Initializes required session state variables if they don't exist."""
    defaults = {
        'available_drawings': [],
        'analysis_job_id': None,
        'analysis_result': None,
        'analysis_running': False,
        'selected_drawings': [],
        'drawing_to_delete': None,
        'backend_status': None, # Initialize backend status too
        'select_all_checkbox_state': False # Add state for the checkbox widget itself
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    # Ensure list types after initialization (in case state was somehow corrupted)
    if not isinstance(st.session_state.available_drawings, list):
        st.session_state.available_drawings = []
    if not isinstance(st.session_state.selected_drawings, list):
        st.session_state.selected_drawings = []

# Call initialization immediately
initialize_session_state()

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

    # --- Backend Health Check & Initial Drawing Fetch ---
    # This block needs careful error handling as it's early in execution
    backend_healthy = False
    try:
        if st.session_state.backend_status is None: # Check only once per session ideally
            logger.info("Performing initial backend health check...")
            health_info = health_check()
            st.session_state.backend_status = health_info.get("status", "error")
            if st.session_state.backend_status == "healthy":
                 logger.info("Backend health check successful.")
                 backend_healthy = True
                 # Initial fetch only if backend is healthy and list is empty
                 # Use len() check for robustness
                 if not st.session_state.available_drawings or len(st.session_state.available_drawings) == 0:
                     logger.info("Available drawings list is empty, fetching initial list.")
                     refresh_drawings() # Use helper function with error handling
                 else:
                     logger.info("Drawings already loaded in session state.")
            else:
                 logger.error(f"Backend unhealthy: {health_info}")
                 st.error(f"🚨 API connection issue. Status: '{st.session_state.backend_status}'. Please check the backend service.")

        elif st.session_state.backend_status == "healthy":
             backend_healthy = True # Already checked and healthy
        else:
             # If already checked and not healthy, show error again
             st.error(f"🚨 API connection issue. Status: '{st.session_state.backend_status}'. Please check the backend service.")


        # If backend isn't healthy after check, stop rendering further elements
        if not backend_healthy:
            st.warning("Backend service is unavailable. Cannot load drawings or perform analysis.")
            st.stop() # Stop script execution here

    except Exception as e:
        st.error(f"🚨 Failed to connect to API during initial check: {e}")
        logger.error(f"API connection failed during health check/init: {e}", exc_info=True)
        st.session_state.backend_status = "error" # Mark as error
        st.session_state.drawing_to_delete = None # Clear on connection error
        st.stop() # Stop script execution


    # --- Sidebar for Upload ---
    with st.sidebar:
        try:
            upload_completed = upload_drawing_component()

            if upload_completed:
                refresh_drawings() # Use helper function
                st.session_state.selected_drawings = [] # Clear selection after upload
                st.session_state.drawing_to_delete = None # Clear pending delete action
                st.rerun()
        except Exception as e:
             logger.error(f"Error in sidebar upload component: {e}", exc_info=True)
             st.sidebar.error(f"Error during upload setup: {e}")


    # --- Main Layout (Two Columns) ---
    col1, col2 = st.columns([1, 2]) # Adjust ratio as needed

    # --- Left Column: Drawing Selection & Deletion ---
    with col1:
        st.subheader("Select Drawings")

        # --- Deletion Confirmation UI ---
        # Put this *before* the list rendering so it appears above
        if st.session_state.drawing_to_delete:
            st.warning(f"**Confirm Deletion:** Are you sure you want to permanently delete `{st.session_state.drawing_to_delete}`?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Yes, Delete", type="primary", key="confirm_delete_button", use_container_width=True):
                    try:
                        target_drawing = st.session_state.drawing_to_delete
                        logger.info(f"Attempting to delete drawing: {target_drawing}")
                        response = delete_drawing(target_drawing) # Call API

                        # --- REVISED ERROR HANDLING FOR 404 ---
                        is_successful_delete = False
                        is_already_gone = False # Flag for 404 errors
                        error_message = "Unknown error during deletion." # Default error

                        if isinstance(response, dict):
                            if response.get("success"):
                                is_successful_delete = True
                            else:
                                error_message = response.get("error", error_message)
                                # Check if the specific error indicates "Not Found" (404)
                                # Check for both text and potential status code if included
                                if "not found" in str(error_message).lower() or "404" in str(error_message):
                                    is_already_gone = True
                                    logger.warning(f"Deletion attempt for '{target_drawing}' returned 'Not Found (404)'. Treating as already removed.")
                                else:
                                    # Log other backend errors
                                    logger.error(f"API error deleting {target_drawing}: {error_message} | Response: {response}")
                        else:
                            error_message = "Invalid response from server."
                            logger.error(f"Invalid response type deleting {target_drawing}: {type(response)} | Response: {response}")


                        if is_successful_delete:
                            st.success(f"Drawing `{target_drawing}` deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")
                        elif is_already_gone:
                            # If it's already gone, show info message instead of success/error
                            st.info(f"Drawing `{target_drawing}` was already removed or could not be found.")
                        else:
                            # Show the specific error from the backend if it wasn't success or 404
                            st.error(f"Failed to delete drawing `{target_drawing}`: {error_message}")

                        # If the delete was successful OR it was already gone (404), refresh the UI state
                        if is_successful_delete or is_already_gone:
                             # Ensure selected_drawings is a list before trying to remove
                            if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)

                            # Clear the pending delete state FIRST
                            st.session_state.drawing_to_delete = None
                            # Refresh the list from backend (this should now exclude the deleted/non-existent item)
                            refresh_drawings()
                            # Rerun to reflect changes
                            st.rerun()
                        # Else (if it was a real error other than 404), do nothing more here, error is already shown. User needs to press Cancel.

                    except Exception as e:
                        # Handle exceptions during the API call itself
                        st.error(f"Error during deletion call for `{st.session_state.drawing_to_delete}`: {e}")
                        logger.error(f"Exception during delete_drawing API call: {e}", exc_info=True)
                        # Clear pending delete on exception and rerun
                        st.session_state.drawing_to_delete = None
                        st.rerun()
                # --- END REVISED ERROR HANDLING ---

            with cancel_col:
                 if st.button("Cancel", key="cancel_delete_button", use_container_width=True):
                    logger.info(f"Deletion cancelled for: {st.session_state.drawing_to_delete}")
                    st.session_state.drawing_to_delete = None # Clear pending delete state
                    st.rerun()
            st.divider()


        # --- Drawing List Rendering ---
        with st.container(border=True):
            # Ensure available_drawings is a list before proceeding
            available_drawings_list = st.session_state.get('available_drawings', [])
            if not isinstance(available_drawings_list, list):
                logger.warning("available_drawings in session state is not a list. Resetting.")
                available_drawings_list = []
                st.session_state.available_drawings = [] # Fix state

            # Ensure selected_drawings is a list
            selected_drawings_list = st.session_state.get('selected_drawings', [])
            if not isinstance(selected_drawings_list, list):
                 logger.warning("selected_drawings in session state is not a list. Resetting.")
                 selected_drawings_list = []
                 st.session_state.selected_drawings = [] # Fix state


            if not available_drawings_list:
                st.info("No drawings processed yet. Upload a PDF via the sidebar.")
            else:
                # Disable list interactions if confirmation is active
                disable_list = bool(st.session_state.drawing_to_delete)

                if disable_list:
                    st.caption("Confirm or cancel deletion above before selecting drawings.")

                # --- Select All Checkbox ---
                select_all_key = "select_all_main_checkbox"
                # Determine the desired state based on current selection
                all_selected_calculated = False
                if available_drawings_list: # Avoid division by zero or errors if list is empty
                    # Ensure both are sets for comparison
                    all_selected_calculated = set(selected_drawings_list) == set(available_drawings_list)

                # Use a separate state variable to track the checkbox widget's value to detect changes
                current_widget_state = st.session_state.get('select_all_checkbox_state', all_selected_calculated)

                new_widget_state = st.checkbox(
                    "Select All Drawings",
                    value=all_selected_calculated, # The visual state depends on calculation
                    key=select_all_key,
                    disabled=disable_list,
                )

                # Logic to handle the change after the widget interaction
                if not disable_list and new_widget_state != all_selected_calculated:
                    if new_widget_state: # User clicked to select all
                         logger.debug("Select All checkbox clicked - selecting all.")
                         st.session_state.selected_drawings = list(available_drawings_list)
                    else: # User clicked to deselect all
                         logger.debug("Select All checkbox clicked - deselecting all.")
                         st.session_state.selected_drawings = []
                    # Update the tracking state AFTER processing the change
                    st.session_state.select_all_checkbox_state = new_widget_state
                    st.rerun()


                st.divider()

                # --- Individual Drawing Rows ---
                try:
                    sorted_drawings = sorted(available_drawings_list)
                except TypeError:
                    logger.error(f"Could not sort available_drawings_list: {available_drawings_list}. Displaying unsorted.")
                    st.warning("Could not sort drawing names.")
                    sorted_drawings = available_drawings_list

                for drawing_name in sorted_drawings:
                    if not isinstance(drawing_name, str):
                         logger.warning(f"Skipping non-string item in drawing list: {drawing_name}")
                         continue

                    list_col1, list_col2 = st.columns([0.9, 0.1])
                    with list_col1:
                        is_selected = drawing_name in selected_drawings_list
                        new_state = st.checkbox(
                            drawing_name,
                            value=is_selected,
                            key=f"select_{drawing_name}",
                            disabled=disable_list
                        )
                        if not disable_list and new_state != is_selected:
                            if new_state:
                                if drawing_name not in selected_drawings_list:
                                    logger.debug(f"Checkbox checked for {drawing_name}, adding to selection.")
                                    st.session_state.selected_drawings.append(drawing_name)
                            else:
                                if drawing_name in selected_drawings_list:
                                    logger.debug(f"Checkbox unchecked for {drawing_name}, removing from selection.")
                                    st.session_state.selected_drawings.remove(drawing_name)
                            # Update the select all tracking state as well
                            st.session_state.select_all_checkbox_state = (set(st.session_state.selected_drawings) == set(available_drawings_list)) if available_drawings_list else False
                            st.rerun()

                    with list_col2:
                         if st.button("🗑️", key=f"delete_{drawing_name}", help=f"Delete {drawing_name}", disabled=disable_list):
                             st.session_state.drawing_to_delete = drawing_name
                             logger.debug(f"Delete button clicked for {drawing_name}, setting state.")
                             st.rerun()

                # Display selection count
                st.caption(f"{len(st.session_state.get('selected_drawings', []))} selected.")


    # --- Right Column: Query, Controls, Progress, Results ---
    try:
        with col2:
            disable_analysis = bool(st.session_state.drawing_to_delete)

            st.subheader("Analyze Selected Drawings")

            with st.container(border=True):
                 query = query_box(disabled=disable_analysis)
                 st.divider()
                 force_new, analyze_clicked, stop_clicked = control_row(disabled=disable_analysis)


            # --- Handle Analysis Request ---
            if analyze_clicked and not disable_analysis:
                selected_list = st.session_state.get('selected_drawings', [])
                if not isinstance(selected_list, list):
                    selected_list = []

                if not selected_list:
                    st.warning("👈 Please select one or more drawings from the list first.")
                elif not query:
                    st.warning("❓ Please enter a query or question above.")
                else:
                    st.session_state.analysis_result = None
                    st.session_state.analysis_running = False
                    st.session_state.analysis_job_id = None

                    st.success(f"🚀 Starting analysis for '{query[:30]}...' on {len(selected_list)} drawing(s)...")
                    logger.info(f"User requested analysis. Query: '{query}', Drawings: {selected_list}, ForceNew: {force_new}")
                    try:
                        resp = start_analysis(query, selected_list, use_cache=not force_new)
                        job_id = resp.get("job_id") if isinstance(resp, dict) else None
                        if job_id:
                            st.session_state.analysis_job_id = job_id
                            st.session_state.analysis_running = True
                            logger.info(f"Analysis job started: {job_id}")
                            st.rerun()
                        else:
                            error_msg = resp.get('error', 'Unknown API error') if isinstance(resp, dict) else "Invalid response from start_analysis"
                            st.error(f"Failed to start analysis: {error_msg}")
                    except Exception as e:
                         st.error(f"API Error: Could not start analysis. {e}")
                         logger.error(f"API call start_analysis failed: {e}", exc_info=True)

            # --- Display Analysis Progress ---
            st.divider()
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
                         st.rerun()
                    else:
                         error_msg = final_job_status.get("error", "Analysis failed with unknown error.")
                         logger.error(f"Analysis job {analysis_job_id} failed or polling error: {error_msg}")
                         st.session_state.analysis_result = f"Error during analysis: {error_msg}"
                         st.rerun()

            # --- Display Analysis Results ---
            if not st.session_state.get('analysis_running', False) and st.session_state.get('analysis_result') and not disable_analysis:
                 st.subheader("Analysis Results")
                 with st.container(border=True):
                    results_pane(st.session_state.analysis_result)


            # Handle the Stop button
            if stop_clicked and not disable_analysis:
                job_id_to_stop = st.session_state.get('analysis_job_id')
                if st.session_state.get('analysis_running') and job_id_to_stop:
                    st.warning(f"Stopping analysis job {job_id_to_stop}… (Backend functionality pending)")
                    logger.warning(f"Stop requested for job {job_id_to_stop} - functionality pending.")
                    st.session_state.analysis_running = False
                    st.session_state.analysis_job_id = None
                    st.session_state.analysis_result = "Analysis stopped by user (Stop functionality pending backend)."
                    time.sleep(1)
                    st.rerun()
                else:
                     st.info("No analysis job is currently running.")

    except Exception as e:
         logger.error(f"Error rendering right column (Analyze Drawings): {e}", exc_info=True)
         st.error(f"An error occurred while rendering the analysis section: {e}")


# --- Run the App ---
if __name__ == "__main__":
    try:
        initialize_session_state()
        main()
    except Exception as e:
         logger.critical(f"A critical error occurred in the main UI thread: {e}", exc_info=True)
         st.error(f"A critical application error occurred. Please check the logs or contact support.")
