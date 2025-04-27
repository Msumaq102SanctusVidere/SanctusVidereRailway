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
    # --- Middle Column: Query, Analysis Control & Status ---
    with col2:
        st.subheader("Query & Status")
    
        # Query input
        query_text = st.text_area("Type your question here...", st.session_state.query)
        st.session_state.query = query_text  # Make sure query value is always updated
        use_cache = st.checkbox("Use cache", value=st.session_state.use_cache)
        st.session_state.use_cache = use_cache  # Update cache value
        
        # Buttons side by side 
        col2a, col2b = st.columns(2)
        
        # Analyze button - Simplify logic to ensure it works
        can_run = (st.session_state.backend_healthy 
                   and len(st.session_state.selected_drawings) > 0
                   and len(st.session_state.query.strip()) > 0)
        
        with col2a:
            if st.button("Analyze Drawings", disabled=not can_run, key="analyze_button"):
                # Basic logging to debug
                st.write(f"Selected drawings: {st.session_state.selected_drawings}")
                st.write(f"Query: {st.session_state.query}")
                
                # Simple try/except
                try:
                    # Call the API directly
                    resp = start_analysis(
                        st.session_state.query,
                        st.session_state.selected_drawings,
                        st.session_state.use_cache
                    )
                    
                    # Check response
                    if resp and 'job_id' in resp:
                        jid = resp['job_id']
                        st.session_state.current_job_id = jid
                        st.session_state.analysis_results = None
                        st.session_state.job_status = None
                        st.success(f"Analysis started! Job ID: {jid}")
                        st.rerun()
                    else:
                        st.error(f"Failed to start analysis: {resp}")
                except Exception as e:
                    st.error(f"Analysis request failed: {str(e)}")

    # --- Right Column: Analysis Results ---
    # --- Right Column: Analysis Results ---
    with col3:
        st.subheader("Analysis Results")
        if st.session_state.analysis_results is not None:
            results_pane(st.session_state.analysis_results)
        else:
            st.info("Results will appear here after analysis completes.")

if __name__ == "__main__":
    main()
