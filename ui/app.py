# --- Filename: ui/app.py (Frontend Streamlit UI - Further Robustness Fixes) ---

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

                        # Check response carefully
                        if isinstance(response, dict) and response.get("success"):
                            st.success(f"Drawing `{target_drawing}` deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")
                            # Remove from selection list if present
                            if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)

                            # Clear the pending delete state FIRST
                            st.session_state.drawing_to_delete = None
                            # Refresh the list from backend
                            refresh_drawings()
                            # Rerun to reflect changes
                            st.rerun()
                        else:
                            error_msg = response.get("error", "Unknown error during deletion.") if isinstance(response, dict) else "Invalid response from server."
                            st.error(f"Failed to delete drawing `{target_drawing}`: {error_msg}")
                            logger.error(f"API error deleting {target_drawing}: {error_msg} | Response: {response}")
                            # Keep drawing_to_delete state so user can cancel or retry? Or clear? Clear seems safer.
                            # st.session_state.drawing_to_delete = None
                            # st.rerun()
                    except Exception as e:
                        st.error(f"Error during deletion call for `{st.session_state.drawing_to_delete}`: {e}")
                        logger.error(f"Exception during delete_drawing API call: {e}", exc_info=True)
                        # Clear pending delete on exception
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
                    all_selected_calculated = set(selected_drawings_list) == set(available_drawings_list)

                # Use a separate state variable to track the checkbox widget's value to detect changes
                # This avoids infinite loops if not done carefully
                current_widget_state = st.session_state.get('select_all_checkbox_state', all_selected_calculated)

                new_widget_state = st.checkbox(
                    "Select All Drawings",
                    value=all_selected_calculated, # The visual state depends on calculation
                    key=select_all_key,
                    disabled=disable_list,
                    # Use on_change callback for cleaner state management
                    # on_change=handle_select_all_change # Define this function if preferred
                )

                # Logic to handle the change after the widget interaction
                # Check if the *visual state* changed compared to *calculated state* (means user clicked it)
                if not disable_list and new_widget_state != all_selected_calculated:
                    if new_widget_state: # User clicked to select all
                         logger.debug("Select All checkbox clicked - selecting all.")
                         st.session_state.selected_drawings = list(available_drawings_list)
                    else: # User clicked to deselect all
                         logger.debug("Select All checkbox clicked - deselecting all.")
                         st.session_state.selected_drawings = []
                    # Update the tracking state AFTER processing the change
                    st.session_state.select_all_checkbox_state = new_widget_state
                    st.rerun() # Rerun is needed to update individual checkboxes visually


                st.divider()

                # --- Individual Drawing Rows ---
                try:
                    sorted_drawings = sorted(available_drawings_list)
                except TypeError:
                    logger.error(f"Could not sort available_drawings_list: {available_drawings_list}. Displaying unsorted.")
                    st.warning("Could not sort drawing names.")
                    sorted_drawings = available_drawings_list # Display unsorted if sort fails

                for drawing_name in sorted_drawings:
                    # Basic check if drawing_name is string-like, skip if not
                    if not isinstance(drawing_name, str):
                         logger.warning(f"Skipping non-string item in drawing list: {drawing_name}")
                         continue

                    list_col1, list_col2 = st.columns([0.9, 0.1]) # Name | Delete Button
                    with list_col1:
                        is_selected = drawing_name in selected_drawings_list # Check against the safe list
                        new_state = st.checkbox(
                            drawing_name,
                            value=is_selected,
                            key=f"select_{drawing_name}", # Ensure keys are unique
                            disabled=disable_list
                        )
                        # Update selection list based ONLY on individual checkbox interaction
                        if not disable_list and new_state != is_selected:
                            if new_state: # Checked
                                if drawing_name not in selected_drawings_list:
                                    logger.debug(f"Checkbox checked for {drawing_name}, adding to selection.")
                                    # Modify the list directly (Streamlit manages state)
                                    st.session_state.selected_drawings.append(drawing_name)
                            else: # Unchecked
                                if drawing_name in selected_drawings_list:
                                    logger.debug(f"Checkbox unchecked for {drawing_name}, removing from selection.")
                                    st.session_state.selected_drawings.remove(drawing_name)
                            # Update the select all tracking state as well
                            st.session_state.select_all_checkbox_state = (set(st.session_state.selected_drawings) == set(available_drawings_list)) if available_drawings_list else False
                            st.rerun() # Rerun needed to update counts and potentially Select All checkbox

                    with list_col2:
                         # Delete button
                         if st.button("🗑️", key=f"delete_{drawing_name}", help=f"Delete {drawing_name}", disabled=disable_list):
                             st.session_state.drawing_to_delete = drawing_name
                             logger.debug(f"Delete button clicked for {drawing_name}, setting state.")
                             st.rerun() # Rerun to show confirmation dialog

                # Display selection count
                st.caption(f"{len(st.session_state.get('selected_drawings', []))} selected.")


    # --- Right Column: Query, Controls, Progress, Results ---
    # Wrap this section in a try-except as well, in case of component errors
    try:
        with col2:
            # Disable analysis if deletion confirmation is active
            disable_analysis = bool(st.session_state.drawing_to_delete)

            st.subheader("Analyze Selected Drawings")

            with st.container(border=True):
                 query = query_box(disabled=disable_analysis) # Pass disabled state
                 st.divider()
                 force_new, analyze_clicked, stop_clicked = control_row(disabled=disable_analysis) # Pass disabled state


            # --- Handle Analysis Request ---
            if analyze_clicked and not disable_analysis:
                # Use .get for safety
                selected_list = st.session_state.get('selected_drawings', [])
                if not isinstance(selected_list, list): # Double check type
                    selected_list = []

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
                        job_id = resp.get("job_id") if isinstance(resp, dict) else None
                        if job_id:
                            st.session_state.analysis_job_id = job_id
                            st.session_state.analysis_running = True
                            logger.info(f"Analysis job started: {job_id}")
                            st.rerun() # Rerun to show progress indicator
                        else:
                            error_msg = resp.get('error', 'Unknown API error') if isinstance(resp, dict) else "Invalid response from start_analysis"
                            st.error(f"Failed to start analysis: {error_msg}")
                    except Exception as e:
                         st.error(f"API Error: Could not start analysis. {e}")
                         logger.error(f"API call start_analysis failed: {e}", exc_info=True)

            # --- Display Analysis Progress ---
            st.divider()
            analysis_job_id = st.session_state.get('analysis_job_id')
            # Add check for disable_analysis here too
            if st.session_state.get('analysis_running') and analysis_job_id and not disable_analysis:
                st.subheader("Analysis Progress")
                final_job_status = progress_indicator(analysis_job_id) # Assume this component handles its own errors

                if final_job_status: # If progress_indicator returns a final status
                    st.session_state.analysis_running = False # Stop polling
                    job_status = final_job_status.get("status")
                    if job_status == "completed":
                         st.session_state.analysis_result = final_job_status.get("result", "Analysis complete, but no result returned.")
                         logger.info(f"Analysis job {analysis_job_id} completed.")
                         st.rerun() # Rerun to display results immediately
                    else: # Job failed or polling failed
                         error_msg = final_job_status.get("error", "Analysis failed with unknown error.")
                         logger.error(f"Analysis job {analysis_job_id} failed or polling error: {error_msg}")
                         st.session_state.analysis_result = f"Error during analysis: {error_msg}"
                         st.rerun() # Rerun to display error in results area

            # --- Display Analysis Results ---
            # Use .get with defaults for safety
            if not st.session_state.get('analysis_running', False) and st.session_state.get('analysis_result') and not disable_analysis:
                 st.subheader("Analysis Results")
                 with st.container(border=True):
                    results_pane(st.session_state.analysis_result) # Assume this handles display


            # Handle the Stop button
            if stop_clicked and not disable_analysis:
                job_id_to_stop = st.session_state.get('analysis_job_id')
                if st.session_state.get('analysis_running') and job_id_to_stop:
                    st.warning(f"Stopping analysis job {job_id_to_stop}… (Backend functionality pending)")
                    logger.warning(f"Stop requested for job {job_id_to_stop} - functionality pending.")
                    # TODO: Implement stop job functionality in backend and api_client
                    st.session_state.analysis_running = False # Temporarily set to false
                    st.session_state.analysis_job_id = None
                    st.session_state.analysis_result = "Analysis stopped by user (Stop functionality pending backend)."
                    time.sleep(1) # Give user feedback time
                    st.rerun()
                else:
                     st.info("No analysis job is currently running.")

    except Exception as e:
         logger.error(f"Error rendering right column (Analyze Drawings): {e}", exc_info=True)
         st.error(f"An error occurred while rendering the analysis section: {e}")


# --- Run the App ---
if __name__ == "__main__":
    try:
        # Ensure state is initialized before main runs fully
        initialize_session_state()
        main()
    except Exception as e:
         # This is the final catch-all. Log the detailed error.
         logger.critical(f"A critical error occurred in the main UI thread: {e}", exc_info=True)
         # Display the generic error message in the UI.
         # Avoid showing the raw exception 'e' directly to the user for security/friendliness.
         st.error(f"A critical application error occurred. Please check the logs or contact support.")
