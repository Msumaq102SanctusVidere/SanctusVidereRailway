# --- Filename: ui/app.py (Frontend Streamlit UI - Three-Column Layout) ---

import streamlit as st
import time
import logging
import sys
import os
import re
from api_client import (
    health_check,
    get_drawings,
    delete_drawing,
    start_analysis,
    get_job_status
)
from components.drawing_list import drawing_list
from components.upload_drawing import upload_drawing_component
from components.query_box import query_box
from components.progress_bar import progress_indicator
from components.results_pane import results_pane
from components.log_console import log_console

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
        'analysis_complete': False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# --- Helper to Refresh Drawings List ---
def refresh_drawings():
    try:
        st.session_state.drawings = get_drawings()
        st.session_state.drawings_last_updated = time.time()
        logger.info(f"Refreshed drawings list: {len(st.session_state.drawings)} items")
        return True
    except Exception as e:
        logger.error(f"Failed to refresh drawings: {e}")
        return False

# --- Main Application ---
def main():
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide")
    
    # Add main title to the page
    st.title("Sanctus Videre 1.0")
    st.markdown("*Architectural Drawing Analysis Tool*")

    # --- Health Check & Initial Drawings Fetch ---
    try:
        status = health_check().get('status')
        if status == 'ok':
            st.session_state.backend_healthy = True
            if not st.session_state.drawings or time.time() - st.session_state.drawings_last_updated > 30:
                refresh_drawings()
        else:
            st.error("⚠️ Backend service unavailable.")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Health check failed: {e}")

    # --- Sidebar: Upload ---
    with st.sidebar:
        st.header("Upload Drawing")
        upload_ok = upload_drawing_component()
        if upload_ok:
            # After upload completes, refresh the list
            refresh_drawings()
            st.rerun()

    # --- Three-Column Layout ---
    col1, col2, col3 = st.columns([1, 1, 2])

    
    # --- Left Column: Drawing Selection ---
    with col1:
        st.subheader("Select Drawings")
    
        # Special notification if upload just completed
        if st.session_state.get("refresh_drawings_needed", False):
            st.info("✨ New drawing has been uploaded. Click 'Refresh Drawings' to see it.")
    
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

        # Drawing list component
        selected = drawing_list(st.session_state.drawings)
        if selected is not None:
            st.session_state.selected_drawings = selected

        # Delete buttons for selected
        for d in st.session_state.selected_drawings:
            if st.button(f"Delete '{d}'", key=f"del_{d}"):
                delete_drawing(d)
                refresh_drawings()
                st.rerun()

    # --- Middle Column: Query, Analysis Control & Status ---
    with col2:
        st.subheader("Query & Status")

        # Query input - Modified to pass empty_disabled=True to prevent automatic analyze button
        st.session_state.query = query_box(empty_disabled=True, remove_analyze_button=True)
        st.session_state.use_cache = st.checkbox("Use cache", value=st.session_state.use_cache)

        # Analyze and Show Results buttons in a horizontally aligned container
        button_cols = st.columns([1, 1])
        
        # Analyze button
        can_run = (st.session_state.backend_healthy 
                   and st.session_state.selected_drawings 
                   and st.session_state.query.strip())
        with button_cols[0]:
            if st.button("Analyze Drawings", disabled=not can_run, key="main_analyze_btn"):
                resp = start_analysis(
                    st.session_state.query,
                    st.session_state.selected_drawings,
                    st.session_state.use_cache
                )
                jid = resp.get('job_id')
                if jid:
                    st.session_state.current_job_id = jid
                    st.session_state.analysis_results = None
                    st.session_state.job_status = None
                    st.session_state.analysis_complete = False
                else:
                    st.error(f"Failed to start analysis: {resp}")
                st.rerun()
        
        # Show Results button - placed next to Analyze button
        with button_cols[1]:
            # Force enable Show Results button if job is complete
            force_enable = False
            if st.session_state.current_job_id:
                job = st.session_state.job_status
                if job and (job.get('progress', 0) >= 100 or 
                           (job.get('current_phase', '').lower() == 'complete') or
                           (job.get('status', '').lower() == 'completed')):
                    force_enable = True
                    st.session_state.analysis_complete = True
            
            show_results_button = st.button(
                "Show Results", 
                disabled=not (st.session_state.analysis_complete or force_enable),
                key="show_results_btn"
            )
            if show_results_button:
                job = st.session_state.job_status
                if job:
                    result = job.get('result')
                    st.session_state.analysis_results = result
                    st.session_state.current_job_id = None
                    st.rerun()

        # Stop analysis
        if st.session_state.current_job_id:
            if st.button("Stop Analysis"):  
                st.session_state.current_job_id = None
                st.info("Analysis stopped.")
                st.rerun()

        # Job status display
        jid = st.session_state.current_job_id
        if jid:
            # Poll job status
            job = get_job_status(jid)
            st.session_state.job_status = job

            phase = job.get('current_phase', '')
            prog = job.get('progress', 0)
            
            # Status indicator with clearer phase information
            st.markdown(f"**Status:** {phase}")
            
            # Progress bar
            if prog is not None:
                progress_indicator(prog)
                
                # Set analysis complete flag when progress is 100%
                if prog >= 100 or 'complete' in phase.lower():
                    st.session_state.analysis_complete = True
                    st.success("✅ Analysis complete! Click 'Show Results' to view.")

            # Latest log message
            logs = job.get('progress_messages', [])
            if logs:
                st.markdown("**Recent Updates:**")
                
                # Clean any HTML tags from logs
                clean_logs = []
                for log in logs:
                    # Use regex to remove HTML tags if present
                    clean_log = re.sub(r'<[^>]+>', '', log)
                    clean_logs.append(clean_log)
                
                log_console(clean_logs)
        
        # Add a separate section for Recent Updates
        if st.session_state.current_job_id:
            st.markdown("---")
            st.markdown("#### Recent Updates")
            
            # Display the most recent log message in a more prominent way
            if st.session_state.job_status and 'progress_messages' in st.session_state.job_status:
                recent_logs = st.session_state.job_status.get('progress_messages', [])
                if recent_logs:
                    # Clean any HTML tags from logs
                    clean_logs = []
                    for log in recent_logs:
                        # Use regex to remove HTML tags if present
                        clean_log = re.sub(r'<[^>]+>', '', log)
                        clean_logs.append(clean_log)
                    
                    # Display the latest log in a more formatted way
                    for log in clean_logs[-3:]:  # Show last 3 logs
                        st.info(log)

    # --- Right Column: Analysis Results ---
    with col3:
        st.subheader("Analysis Results")
        if st.session_state.analysis_results is not None:
            results_pane(st.session_state.analysis_results)
        else:
            st.info("Results will appear here after analysis completes.")

if __name__ == "__main__":
    main()
