import streamlit as st
import time # Import time for potential use in polling if needed here

# --- Import API Client Functions ---
# Make sure api_client.py is accessible (it's in the parent directory,
# Python might find it, but explicit sys.path modification might be safer if issues arise)
try:
    # Assuming api_client.py is one level up from the ui directory's parent
    # This path handling might need adjustment based on how you run streamlit
    import sys
    import os
    # Add the root directory ('main' in your github structure) to the path
    # This assumes you run streamlit from the 'main' directory
    current_dir = os.path.dirname(os.path.abspath(__file__)) # ui/
    parent_dir = os.path.dirname(current_dir) # main/
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)

    from api_client import health_check, get_drawings, start_analysis, get_job_status # Ensure get_job_status is imported if needed here
    logger = logging.getLogger(__name__) # Use logging if needed
    logger.info("Successfully imported api_client functions.")

except ImportError as e:
    st.error(f"Failed to import api_client: {e}. Ensure api_client.py is in the correct path.")
    st.stop()
except NameError: # If logging wasn't set up here, handle it
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.warning("Logging re-initialized in ui/app.py")
    from api_client import health_check, get_drawings, start_analysis, get_job_status

# --- Import UI Components ---
# Ensure components are found relative to this file (ui/app.py)
try:
    from components.upload_drawing import upload_drawing_component
    from components.drawing_list import drawing_list
    from components.query_box import query_box
    from components.control_row import control_row
    from components.progress_bar import progress_indicator # Assumes this handles polling for analysis
    from components.results_pane import results_pane
    logger.info("Successfully imported UI components.")
except ImportError as e:
    st.error(f"Failed to import UI components: {e}. Check paths in ui/components/.")
    st.stop()


# --- Main Application Logic ---
def main():
    # Page setup
    st.set_page_config(
        page_title="Sanctus Videre 1.0",
        layout="wide",
        page_icon="🏗️"
    )

    # Title and subheading
    st.markdown(
        """
        <h1 style='font-family:Orbitron; color:#00ffcc;'>Sanctus Videre 1.0</h1>
        <h4 style='font-family:Orbitron; color:#00ffcc;'>Visionary Construction Insights</h4>
        """,
        unsafe_allow_html=True
    )

    # --- State Initialization (Good practice) ---
    if 'available_drawings' not in st.session_state:
        st.session_state.available_drawings = []
    if 'analysis_job_id' not in st.session_state:
        st.session_state.analysis_job_id = None
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False

    # --- Backend Health Check ---
    try:
        health_info = health_check()
        status = health_info.get("status", "error")
        if status != "healthy":
            st.error(f"🚨 API is not responding or unhealthy. Please check the backend service. Status: {status}")
            st.stop() # Stop execution if backend is down
        else:
            logger.info("Backend health check successful.")
            # Initial fetch or refresh drawings if state is empty
            if not st.session_state.available_drawings:
                 st.session_state.available_drawings = get_drawings()
                 logger.info(f"Fetched initial drawings: {len(st.session_state.available_drawings)}")

    except Exception as e:
        st.error(f"🚨 Failed to connect to API for health check: {e}")
        logger.error(f"API connection failed: {e}", exc_info=True)
        st.stop()


    # --- Sidebar for Upload ---
    with st.sidebar:
        st.header("Upload Drawing")
        # This component now needs to handle the async upload internally
        # It should ideally return True or trigger st.rerun *after*
        # the background job (polled via get_job_status) completes successfully.
        upload_completed = upload_drawing_component() # Keep calling the component

        if upload_completed:
            st.success("Drawing processed successfully! Refreshing list.")
            # Clear cache and refresh drawings from API
            st.session_state.available_drawings = get_drawings()
            st.rerun() # Force a rerun to update the drawing list display


    # --- Main Layout ---
    col1, col2 = st.columns([1, 3])

    with col1:
        st.header("Available Drawings")
        if not st.session_state.available_drawings:
            st.info("No processed drawings found. Upload a PDF using the sidebar.")
        else:
            # Pass the current list from session state
            selected_drawings = drawing_list(st.session_state.available_drawings)

    with col2:
        st.header("Analyze Drawings")
        # Query input
        query = query_box()

        # Controls row
        force_new, analyze_clicked, stop_clicked = control_row()

        # Handle the Analyze button click
        if analyze_clicked:
            if 'selected_drawings' not in locals() or not selected_drawings:
                st.warning("Please select at least one drawing from the list on the left.")
            elif not query:
                st.warning("Please enter a query before analyzing.")
            else:
                st.info(f"🚀 Starting analysis for query '{query}' on {len(selected_drawings)} drawing(s)...")
                try:
                    resp = start_analysis(query, selected_drawings, use_cache=not force_new)
                    job_id = resp.get("job_id")
                    if job_id:
                        st.session_state.analysis_job_id = job_id
                        st.session_state.analysis_result = None # Clear previous results
                        st.session_state.analysis_running = True
                        logger.info(f"Analysis job started: {job_id}")
                        st.rerun() # Rerun to start showing progress
                    else:
                        st.error(f"Failed to start analysis: {resp.get('error', 'Unknown error')}")
                        st.session_state.analysis_job_id = None
                        st.session_state.analysis_running = False
                except Exception as e:
                     st.error(f"Error calling start_analysis API: {e}")
                     logger.error(f"API call start_analysis failed: {e}", exc_info=True)
                     st.session_state.analysis_job_id = None
                     st.session_state.analysis_running = False


        # --- Display Analysis Progress and Results ---
        if st.session_state.analysis_running and st.session_state.analysis_job_id:
            job_id = st.session_state.analysis_job_id
            # Use the progress component (assuming it handles polling)
            # It should return the final job details when done, or None while running
            final_job_status = progress_indicator(job_id)

            if final_job_status: # If progress_indicator signals completion/failure
                st.session_state.analysis_running = False # Stop polling
                if final_job_status.get("status") == "completed":
                     st.session_state.analysis_result = final_job_status.get("result", "No result returned.")
                     logger.info(f"Analysis job {job_id} completed.")
                     st.rerun() # Rerun one last time to display results cleanly
                else:
                     error_msg = final_job_status.get("error", "Analysis failed with unknown error.")
                     st.error(f"Analysis failed: {error_msg}")
                     logger.error(f"Analysis job {job_id} failed: {error_msg}")
                     st.session_state.analysis_result = f"Error: {error_msg}" # Display error in results area

        # Display results if available (and analysis is not running)
        if not st.session_state.analysis_running and st.session_state.analysis_result:
             results_pane(st.session_state.analysis_result)

        # Handle the Stop button (placeholder - needs implementation)
        if stop_clicked:
            st.warning("Stopping analysis… (Stop functionality not yet implemented)")
            # TODO: Need an API endpoint to stop/cancel a job
            # If implemented: call API to stop job_id, set analysis_running = False

# --- Run the App ---
if __name__ == "__main__":
    # Add path modification here as well if needed, especially if running `python ui/app.py` directly
    try:
        main()
    except Exception as e:
         # Catch potential top-level errors during development
         logger.error(f"An error occurred in the main UI thread: {e}", exc_info=True)
         st.error(f"A critical error occurred: {e}")
