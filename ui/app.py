# --- Filename: ui/app.py (Frontend Streamlit UI - Three-Column Layout) ---

import streamlit as st
import time
import logging
import sys
import os
import re
import json
from api_client import (
    health_check,
    get_drawings,
    delete_drawing,
    start_analysis,
    get_job_status,
    upload_drawing
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - UI - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- Session State Initialization ---
def init_state():
    defaults = {
        'backend_healthy': False,
        'drawings': [],
        'drawings_last_updated': 0,
        'selected_drawings': [],
        'query': '',
        'use_cache': True,
        'current_job_id': None,
        'job_status': None,
        'analysis_results': None,
        'last_status_check': 0,
        'upload_status': {},  # Track upload status
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# --- Helper to Refresh Drawings List ---
def refresh_drawings():
    try:
        # Force a clean fetch from API (no caching)
        st.session_state.drawings = get_drawings()
        st.session_state.drawings_last_updated = time.time()
        logger.info(f"Refreshed drawings list: {len(st.session_state.drawings)} items")
        return True
    except Exception as e:
        logger.error(f"Failed to refresh drawings: {e}")
        return False

# --- Integrated Upload Drawing Component ---
def integrated_upload_drawing():
    """Simplified file uploader integrated directly into app.py"""
    st.header("Upload Drawing")
    uploaded_file = st.file_uploader(
        label="Select a PDF drawing to upload and process",
        type=["pdf"],
        key="pdf_uploader",
        help="Upload a construction drawing in PDF format. Processing will start automatically."
    )

    if uploaded_file is not None:
        # Track this specific file
        file_key = f"upload_{uploaded_file.name}"
        
        # Initialize status if this is a new file
        if file_key not in st.session_state.upload_status:
            st.session_state.upload_status[file_key] = {'status': 'new', 'job_id': None}
        
        status_info = st.session_state.upload_status[file_key]
        
        # Handle new uploads
        if status_info['status'] == 'new':
            if st.button("Process Drawing"):
                try:
                    # Get file bytes directly
                    file_bytes = uploaded_file.getbuffer()
                    
                    # Upload to API
                    resp = upload_drawing(file_bytes, uploaded_file.name)
                    job_id = resp.get("job_id")
                    
                    if job_id:
                        # Update status and track job
                        st.session_state.upload_status[file_key]['job_id'] = job_id
                        st.session_state.upload_status[file_key]['status'] = 'processing'
                        st.rerun()
                    else:
                        st.error(f"Upload failed: {resp.get('error', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Error during upload: {e}")
        
        # Handle processing uploads
        if status_info['status'] == 'processing' and status_info['job_id']:
            job_id = status_info['job_id']
            
            # Show status indicator
            with st.status(f"Processing {uploaded_file.name}...", expanded=True) as status:
                # Get job status
                job = get_job_status(job_id)
                
                if not job:
                    st.error("Could not retrieve job status")
                    return False
                
                # Extract status information
                percent = job.get("progress", 0)
                backend_status = job.get("status", "unknown")
                current_phase = job.get("current_phase", "")
                messages = job.get("progress_messages", [])
                
                # Show status details
                status.write(f"**Phase:** {current_phase}")
                st.progress(int(percent), text=f"Progress: {percent}%")
                
                # Show recent messages
                if messages:
                    st.write("Recent updates:")
                    for msg in messages[-3:]:
                        if " - " in msg:
                            msg = msg.split(" - ", 1)[1]  # Remove timestamp
                        st.info(msg)
                
                # Check for completion
                if backend_status == "completed":
                    result_info = job.get("result", {})
                    drawing_name = result_info.get('drawing_name', uploaded_file.name)
                    
                    # Update status
                    st.session_state.upload_status[file_key]['status'] = 'completed'
                    
                    # Critical fix: Force drawings refresh on completion
                    refresh_drawings()
                    st.session_state["refresh_drawings_needed"] = True
                    
                    # Show completion message
                    status.update(label="✅ Processing Complete", state="complete")
                    st.success(f"✅ UPLOAD COMPLETE: {drawing_name} has been successfully processed!")
                    st.info("The drawing is now available for analysis. Click 'Refresh Drawings' to update the list.")
                    
                    return True
                
                elif backend_status == "failed":
                    # Handle failure
                    error_msg = job.get("error", "Unknown error")
                    st.session_state.upload_status[file_key]['status'] = 'failed'
                    status.update(label="❌ Processing Failed", state="error")
                    st.error(f"Error: {error_msg}")
                    return False
                
                # Auto-refresh for ongoing uploads
                if percent < 100 and backend_status != "completed" and backend_status != "failed":
                    time.sleep(2)  # Brief pause
                    st.rerun()
        
        # Show status for completed uploads
        elif status_info['status'] == 'completed':
            st.success(f"✅ Drawing {uploaded_file.name} already processed")
            st.info("This drawing is available in the drawing list.")
        
        # Show status for failed uploads
        elif status_info['status'] == 'failed':
            st.error(f"❌ Previous upload of {uploaded_file.name} failed")
            if st.button("Try Again"):
                st.session_state.upload_status[file_key]['status'] = 'new'
                st.rerun()
    
    return False

# --- Integrated Drawing List Component ---
def integrated_drawing_list(drawings):
    """Simplified drawing list integrated directly into app.py"""
    st.subheader("Available Drawings")
    
    # No drawings case
    if not drawings:
        st.info("No drawings available. Upload a drawing to get started.")
        return []
    
    # Select All option
    select_all = st.checkbox("Select All Drawings", key="select_all")
    selected = []
    
    # Show drawings with selection
    if select_all:
        for drawing in drawings:
            st.checkbox(drawing, value=True, key=f"cb_{drawing}", disabled=True)
        selected = drawings.copy()
    else:
        for drawing in drawings:
            if st.checkbox(drawing, key=f"cb_{drawing}"):
                selected.append(drawing)
    
    # Display count
    st.caption(f"Showing {len(drawings)} drawing(s)")
    
    # Instructions if none selected
    if not selected:
        st.caption("Select drawings to analyze or delete")
    
    return selected

# --- Integrated Results Pane Component ---
def integrated_results_pane(result_text):
    """Simplified results display integrated directly into app.py"""
    try:
        # Handle if result_text is already a dictionary
        if isinstance(result_text, dict):
            result_obj = result_text
        else:
            # Try to parse as JSON
            result_obj = json.loads(result_text)
        
        # Extract analysis text
        if isinstance(result_obj, dict):
            if 'analysis' in result_obj:
                analysis_text = result_obj['analysis']
                
                # Display in a clean, bordered container
                with st.container(border=True):
                    st.markdown(analysis_text)
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_results_main"):
                        st.code(analysis_text, language=None)
                        st.success("Results ready to copy! Use the copy button in the top-right of the code block above.")
                
                # Technical information in an expandable section
                with st.expander("Technical Information", expanded=False):
                    st.json(result_obj)
                
                return
            
            # Handle other result structures
            for key in result_obj.keys():
                if isinstance(result_obj[key], str) and len(result_obj[key]) > 100:
                    analysis_text = result_obj[key]
                    
                    # Display in a bordered container
                    with st.container(border=True):
                        st.markdown(analysis_text)
                        
                        # Add a copy button
                        if st.button("Copy Results", key="copy_text"):
                            st.code(analysis_text, language=None)
                            st.success("Results ready to copy!")
                    
                    return
        
        # Fallback to raw display
        st.warning("Displaying raw results:")
        if isinstance(result_text, dict):
            with st.container(border=True):
                st.json(result_text)
        else:
            with st.container(border=True):
                st.text_area("Raw Results", value=str(result_text), height=400)
    
    except Exception as e:
        st.warning(f"Could not parse results as expected: {str(e)}")
        with st.container(border=True):
            st.text_area("Raw Results", value=str(result_text), height=400)

# --- Main Application ---
def main():
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide")
    
    # Add custom CSS to make the title more prominent
    st.markdown("""
    <style>
    .big-title {
        font-size: 3rem !important;
        margin-top: -1.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    .subtitle {
        font-size: 1.2rem !important;
        margin-top: -0.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add title with custom styling
    st.markdown('<h1 class="big-title">Sanctus Videre 1.0</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle"><i>Architectural Drawing Analysis Tool</i></p>', unsafe_allow_html=True)
    
    # --- Health Check & Initial Drawings Fetch ---
    try:
        status = health_check().get('status')
        if status == 'ok':
            st.session_state.backend_healthy = True
            # Critical fix: Always refresh on load for consistent state
            refresh_drawings()  
        else:
            st.error("⚠️ Backend service unavailable.")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Health check failed: {e}")

    # --- Sidebar: Upload ---
    with st.sidebar:
        upload_ok = integrated_upload_drawing()
        if upload_ok:
            # After upload completes, refresh the list
            refresh_drawings()

    # --- Three-Column Layout ---
    col1, col2, col3 = st.columns([1, 1, 2])

    # --- Left Column: Drawing Selection ---
    with col1:
        st.subheader("Select Drawings")
    
        # Special notification if upload just completed
        if st.session_state.get("refresh_drawings_needed", False):
            st.success("✨ New drawing has been uploaded!")
    
        # Refresh button
        if st.button("Refresh Drawings", key="refresh_btn"):  
            if refresh_drawings():
                st.success("Drawings list updated.")
                # Clear the flag after successful refresh
                if "refresh_drawings_needed" in st.session_state:
                    del st.session_state["refresh_drawings_needed"]
            else:
                st.error("Failed to refresh drawings.")
            st.rerun()

        # Drawing list component (integrated version)
        selected = integrated_drawing_list(st.session_state.drawings)
        if selected is not None:
            st.session_state.selected_drawings = selected

        # Single delete button for all selected drawings
        if st.session_state.selected_drawings:
            if st.button("Delete Selected Drawings"):
                delete_count = 0
                error_count = 0
                
                # Process each selected drawing
                for drawing in list(st.session_state.selected_drawings):
                    try:
                        # Log before deletion attempt
                        logger.info(f"Attempting to delete drawing: {drawing}")
                        
                        # Call delete API and capture response
                        response = delete_drawing(drawing)
                        logger.info(f"Delete API response: {response}")
                        
                        # Check if deletion was successful
                        if response and response.get('success'):
                            st.session_state.selected_drawings.remove(drawing)
                            delete_count += 1
                        else:
                            error_msg = response.get('error', 'Unknown error')
                            logger.error(f"API reported error deleting {drawing}: {error_msg}")
                            st.error(f"Failed to delete {drawing}: {error_msg}")
                            error_count += 1
                    except Exception as e:
                        logger.error(f"Exception when deleting {drawing}: {e}")
                        st.error(f"Failed to delete {drawing}: {e}")
                        error_count += 1
                
                # Refresh the drawings list
                refresh_drawings()
                
                # Show summary message
                if delete_count > 0:
                    st.success(f"Successfully deleted {delete_count} drawings.")
                
                # Force UI refresh
                st.rerun()

    # --- Middle Column: Query, Analysis Control & Status ---
    with col2:
        st.subheader("Query & Status")
    
        # Query input (simplified from query_box component)
        st.session_state.query = st.text_area(
            "Type your question here...", 
            st.session_state.query, 
            placeholder="Example: What are the finishes specified for the private offices?"
        )
        st.session_state.use_cache = st.checkbox("Use cache", value=st.session_state.use_cache)
    
        # Buttons side by side 
        col2a, col2b = st.columns(2)
        
        # Analyze button - simple implementation that works
        with col2a:
            analyze_disabled = not st.session_state.query.strip() or not st.session_state.selected_drawings
            if st.button("Analyze Drawings", disabled=analyze_disabled):
                try:
                    resp = start_analysis(
                        st.session_state.query,
                        st.session_state.selected_drawings,
                        st.session_state.use_cache
                    )
                    if resp and 'job_id' in resp:
                        st.session_state.current_job_id = resp['job_id']
                        st.session_state.analysis_results = None
                        st.session_state.job_status = None
                        st.rerun()
                    else:
                        st.error(f"Failed to start analysis: {resp}")
                except Exception as e:
                    st.error(f"Error starting analysis: {str(e)}")
        
        # Show Results button
        with col2b:
            show_results_disabled = not st.session_state.current_job_id
            if st.button("Show Results", disabled=show_results_disabled):
                try:
                    job = get_job_status(st.session_state.current_job_id)
                    result = job.get('result')
                    if result:
                        st.session_state.analysis_results = result
                        st.session_state.current_job_id = None
                        st.rerun()
                    else:
                        st.warning("Results not ready yet. Please wait for analysis to complete.")
                except Exception as e:
                    st.error(f"Error retrieving results: {str(e)}")
    
        # Stop analysis button
        if st.session_state.current_job_id:
            if st.button("Stop Analysis"):  
                st.session_state.current_job_id = None
                st.info("Analysis stopped.")
                st.rerun()
    
        # Job status display (simplified from progress_bar component)
        if st.session_state.current_job_id:
            try:
                # Poll job status
                job = get_job_status(st.session_state.current_job_id)
                st.session_state.job_status = job
        
                phase = job.get('current_phase', '')
                prog = job.get('progress', 0)
                
                # Status display in a bordered container
                with st.container(border=True):
                    # Status indicator
                    st.markdown(f"**Status:** {phase}")
                    
                    # Progress indicator
                    st.progress(prog / 100, text=f"Progress: {prog}%")
                    
                    # Progress complete indicator
                    if prog >= 100 or 'complete' in phase.lower():
                        st.success("✅ Analysis complete! Click 'Show Results' to view.")
                
                    # Recent Updates section
                    st.markdown("**Recent Updates:**")
                    logs = job.get('progress_messages', [])
                    if logs:
                        for log in logs[-3:]:
                            # Remove HTML tags and timestamps if present
                            if " - " in log:
                                log = log.split(" - ", 1)[1]  # Remove timestamp
                            clean_log = re.sub(r'<[^>]+>', '', log)
                            st.info(clean_log)
                
                # Auto-refresh while analysis is running
                if prog < 100 and 'complete' not in phase.lower():
                    time.sleep(2)  # Brief pause to avoid hammering the API
                    st.rerun()
            except Exception as e:
                st.error(f"Error updating job status: {str(e)}")

    # --- Right Column: Analysis Results ---
    with col3:
        st.subheader("Analysis Results")
        if st.session_state.analysis_results is not None:
            try:
                integrated_results_pane(st.session_state.analysis_results)
            except Exception as e:
                st.error(f"Error displaying results: {str(e)}")
                
                # Fallback display
                st.warning("Could not parse results in standard format. Displaying raw data:")
                if isinstance(st.session_state.analysis_results, dict):
                    # If it's a dict, display as JSON
                    st.json(st.session_state.analysis_results)
                else:
                    # Otherwise display as text
                    st.text_area("Raw Results:", value=str(st.session_state.analysis_results), height=400)
        else:
            st.info("Results will appear here after analysis completes.")

if __name__ == "__main__":
    main()
