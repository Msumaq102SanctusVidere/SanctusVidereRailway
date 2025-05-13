# --- Filename: ui/app.py (Frontend Streamlit UI - Fixed User Workspace Initialization) ---
# REVISED: Fixed workspace initialization to only happen once per user
# REVISED: Ensured drawings are always fetched on initial load

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
    upload_drawing,
    clear_cache
)

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - UI - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- Check for user_id parameter from Auth0 ---
def check_user_parameter():
    """
    Check if URL contains a user_id parameter to identify the user
    This is passed from Auth0 after authentication
    FIXED: Only initialize workspace once per user, not on every rerun
    """
    try:
        # Get query parameters from URL
        query_params = st.query_params
        
        # Get user_id parameter (sent by Auth0)
        user_id = query_params.get("user_id", "")
        
        # Get current user_id from session state (if any)
        current_user_id = st.session_state.get("user_id")
        
        # Only initialize if user_id is present AND different from current user_id
        # This prevents reinitialization on every interaction
        if user_id and user_id != current_user_id:
            logger.info(f"New user detected. Initializing workspace for user_id: {user_id}")
            
            # Store the user_id in session state for later use in API calls
            st.session_state["user_id"] = user_id
            
            # We still want to set a flag to skip the next refresh
            # This ensures a clean start with the correct user context
            st.session_state["skip_next_refresh"] = True
            st.session_state["skip_flag_timestamp"] = time.time()
            
            # Clear old data if we're initializing a user workspace
            if 'drawings' in st.session_state:
                st.session_state.drawings = []
                logger.info(f"Cleared drawings for user workspace: {user_id}")
            if 'selected_drawings' in st.session_state:
                st.session_state.selected_drawings = []
                logger.info(f"Cleared selected drawings for user workspace: {user_id}")
            if 'analysis_results' in st.session_state:
                st.session_state.analysis_results = None
                logger.info(f"Cleared analysis results for user workspace: {user_id}")
            
            return True
        elif user_id and user_id == current_user_id:
            logger.debug(f"Same user continued session: {user_id}")
            return False
        return False
    except Exception as e:
        logger.error(f"Error checking user parameter: {e}")
        return False

# --- Simple function to clear cache ---
def user_clear_cache():
    """Call the API to clear the memory cache for the current user"""
    try:
        # Get the user_id from session state
        user_id = st.session_state.get("user_id")
        
        # Call the clear_cache function with user_id
        response = clear_cache(user_id)
        
        if response and response.get('success'):
            logger.info(f"Cache cleared successfully for user: {user_id}")
            return {"success": True, "message": "Cache cleared successfully"}
        else:
            error_msg = response.get('error', 'Unknown error')
            logger.error(f"Failed to clear cache for user {user_id}: {error_msg}")
            return {"success": False, "error": error_msg}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return {"success": False, "error": str(e)}

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
        'show_directions': False,  # Track directions visibility
        'user_id': None,  # Store the Auth0 user ID
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# --- System Directions Content ---
def get_directions_content():
    """Return the directions content for the system"""
    return """
    # Sanctus Videre 1.0 - System Guide
    
    ## Overview
    Sanctus Videre utilizes advanced Large Language Model technology through API integration. The system will continue to improve as AI technology advances - this Version 1.0 represents just the beginning of its capabilities.
    
    ## Key Capabilities
    
    • **Beyond Drawing Information**: The system can provide valuable construction insights that may not be explicitly stated in the drawings. It leverages advanced AI to offer context, implications, and related knowledge that construction managers would find useful.
    
    • **Integrated Multi-Drawing Analysis**: One of the system's most powerful features is its ability to analyze multiple drawings simultaneously. When you select more than one drawing, the system will integrate information across all selected drawings, providing comprehensive insights that reflect the entire selected set. Note that processing time increases with each additional drawing selected.
    
    ## Important Guidelines
    
    • **Original Drawing Size**: Upload drawings in their native size without reduction or shrinking for optimal results.
    
    • **Processing Time**: Depending on drawing size and complexity, processing can take 5-7 minutes per drawing. Network capacity may affect processing speed.
    
    • **One Drawing Per Upload Session**: For best performance, upload only one drawing at a time during the processing phase.
    
    • **Memory Building**: The system builds a knowledge base as you interact with it:
      - When first analyzing a drawing, uncheck "Use cache" to build comprehensive memory
      - Similar questions will be answered faster over time as the system learns
      - Initial analyses with "Use cache" unchecked may take 5-7 minutes
      - Once memory is built, similar queries with "Use cache" checked can be answered in 2 minutes or less
    
    • **Project Management**:
      - Use "Clear Cache" to delete the memory bank for the current project
      - Use "Delete Selected Drawings" to remove drawings
      - This flexibility allows you to start fresh with new projects
    
    ## Best Practices
    1. Start with asking questions using one drawing only
    2. Ask detailed questions about a specific topic such as doors and finishes with "Use cache" unchecked
    3. Keep "Use cache" unchecked while asking different questions to build memory bank
    4. When switching projects, clear the cache and delete unwanted drawings
    """

# --- Helper to Refresh Drawings ---
def refresh_drawings():
    try:
        # Check if we should skip this refresh operation (one-time flag for fresh workspace)
        if st.session_state.get("skip_next_refresh", False):
            logger.info("Skipping refresh_drawings call for fresh workspace (one-time skip)")
            # Reset the skip flag immediately to ensure future refreshes work normally
            st.session_state["skip_next_refresh"] = False
            return True
            
        # Safety check: if the skip flag is somehow stuck for more than 5 minutes, reset it
        skip_timestamp = st.session_state.get("skip_flag_timestamp", 0)
        if skip_timestamp and (time.time() - skip_timestamp > 300):  # 5 minutes
            logger.warning("Skip refresh flag was stuck - resetting it")
            st.session_state["skip_next_refresh"] = False
        
        # Get user_id from session state
        user_id = st.session_state.get("user_id")
        
        # Normal operation - fetch drawings from API with user_id
        st.session_state.drawings = get_drawings(user_id)
        st.session_state.drawings_last_updated = time.time()
        
        if user_id:
            logger.info(f"Refreshed drawings list for user {user_id}: {len(st.session_state.drawings)} items")
        else:
            logger.info(f"Refreshed drawings list (global workspace): {len(st.session_state.drawings)} items")
            
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
                    
                    # Get user_id from session state
                    user_id = st.session_state.get("user_id")
                    
                    # Upload to API with user_id
                    resp = upload_drawing(file_bytes, uploaded_file.name, user_id)
                    job_id = resp.get("job_id")
                    
                    if job_id:
                        # Update status and track job
                        st.session_state.upload_status[file_key]['job_id'] = job_id
                        st.session_state.upload_status[file_key]['status'] = 'processing'
                        # The button click will naturally trigger a rerun
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
                current_phase = job.get("phase", "")
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
                    st.info("The drawing is now available for analysis.")
                    
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
                    st.rerun()  # This rerun is needed for the polling loop
        
        # Show status for completed uploads
        elif status_info['status'] == 'completed':
            st.success(f"✅ Drawing {uploaded_file.name} already processed")
            st.info("This drawing is available in the drawing list.")
        
        # Show status for failed uploads
        elif status_info['status'] == 'failed':
            st.error(f"❌ Previous upload of {uploaded_file.name} failed")
            if st.button("Try Again"):
                st.session_state.upload_status[file_key]['status'] = 'new'
                # The button click will naturally trigger a rerun
    
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

# --- Helper function to convert markdown to HTML ---
def markdown_to_html(markdown_text):
    """
    Basic conversion of markdown to HTML
    For a more robust solution, consider using a library like markdown2 or python-markdown
    """
    # Create HTML header
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Analysis Results</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; }
        h1 { color: #333; }
        h2 { color: #444; }
        h3 { color: #555; }
        ul, ol { margin-left: 20px; }
        li { margin-bottom: 5px; }
        code { background-color: #f4f4f4; padding: 2px 4px; border-radius: 4px; }
    </style>
</head>
<body>
"""
    
    # Basic markdown conversion
    # Headers
    markdown_text = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', markdown_text, flags=re.MULTILINE)
    markdown_text = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', markdown_text, flags=re.MULTILINE)
    markdown_text = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', markdown_text, flags=re.MULTILINE)
    
    # Lists
    markdown_text = re.sub(r'^- (.*?)$', r'<li>\1</li>', markdown_text, flags=re.MULTILINE)
    markdown_text = re.sub(r'^(\d+)\. (.*?)$', r'<li>\2</li>', markdown_text, flags=re.MULTILINE)
    
    # Bold
    markdown_text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', markdown_text)
    
    # Italic
    markdown_text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', markdown_text)
    
    # Wrap lists in ul/ol tags
    markdown_text = re.sub(r'(<li>.*?</li>)\n\n', r'<ul>\1</ul>\n\n', markdown_text, flags=re.DOTALL)
    
    # Paragraphs
    markdown_text = re.sub(r'(?<!\n)\n(?!\n)', r'<br/>', markdown_text)
    markdown_text = re.sub(r'\n\n', r'</p>\n\n<p>', markdown_text)
    
    # Wrap in paragraphs
    html += f"<p>{markdown_text}</p>"
    
    # Close HTML
    html += """
</body>
</html>
"""
    
    return html

# --- Integrated Results Pane Component - FIXED VERSION ---
def integrated_results_pane(result_text):
    """Improved results display with better formatting and error handling"""
    try:
        # Don't show raw error message for valid results
        if isinstance(result_text, dict) or (isinstance(result_text, str) and len(result_text.strip()) > 0):
            # Display in a clean, bordered container
            with st.container(border=True):
                # Handle if result_text is already a dictionary
                if isinstance(result_text, dict):
                    result_obj = result_text
                    
                    # Extract analysis text
                    if 'analysis' in result_obj:
                        analysis_text = result_obj['analysis']
                        
                        # Display formatted analysis
                        st.markdown(analysis_text)
                        
                        # Add a download button instead of copy+code block
                        filename = "analysis_results.html"
                        html_content = markdown_to_html(analysis_text)
                        
                        st.download_button(
                            label="Copy Results",
                            data=html_content,
                            file_name=filename,
                            mime="text/html",
                            key="download_results_main"
                        )
                        
                        # Technical information in an expandable section
                        with st.expander("Technical Information", expanded=False):
                            st.json(result_obj)
                        
                        return
                    
                    # If no analysis field but it's still a dict, just display content
                    st.subheader("Analysis Results")
                    st.json(result_obj)
                    
                    # Add a download button for JSON results
                    json_str = json.dumps(result_obj, indent=2)
                    st.download_button(
                        label="Copy Results",
                        data=json_str,
                        file_name="analysis_results.json",
                        mime="application/json",
                        key="download_results_json"
                    )
                    
                    return
                    
                # If it's a string, try to display as markdown
                elif isinstance(result_text, str):
                    try:
                        # Try to parse as JSON first
                        result_obj = json.loads(result_text)
                        if isinstance(result_obj, dict) and 'analysis' in result_obj:
                            analysis_text = result_obj['analysis']
                            st.markdown(analysis_text)
                            
                            # Add a download button for analysis text
                            html_content = markdown_to_html(analysis_text)
                            st.download_button(
                                label="Copy Results",
                                data=html_content,
                                file_name="analysis_results.html",
                                mime="text/html",
                                key="download_results_json_str"
                            )
                        else:
                            st.markdown(result_text)
                            
                            # Add a download button for general text
                            html_content = markdown_to_html(result_text)
                            st.download_button(
                                label="Copy Results",
                                data=html_content,
                                file_name="analysis_results.html",
                                mime="text/html",
                                key="download_results_parsed"
                            )
                    except:
                        # If not valid JSON, just show as markdown
                        st.markdown(result_text)
                        
                        # Add a download button for plain text
                        html_content = markdown_to_html(result_text)
                        st.download_button(
                            label="Copy Results",
                            data=html_content,
                            file_name="analysis_results.html",
                            mime="text/html",
                            key="download_results_plain"
                        )
        else:
            # Empty or null result
            st.info("Results will appear here after analysis completes.")
            
    except Exception as e:
        # Only show fallback for real exceptions, not empty results
        st.info("Results will appear here after analysis completes.")

# --- Main Application ---
def main():
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide")
    
    # FIXED: Only check and initialize user workspace once
    check_user_parameter()
    
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
    .stButton button {
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    /* Make the Analyze button more distinct */
    [data-testid="stHorizontalBlock"] > div:first-child .stButton button {
        background-color: #4CAF50;
        color: white;
    }
    /* Style the status container for better appearance */
    [data-testid="stVerticalBlock"] > div > [data-testid="stContainer"] {
        padding: 1rem;
    }
    /* Custom styling for directions panel */
    .directions-panel {
        background-color: #1E1E1E;
        color: white;
        padding: 20px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .directions-panel h1, .directions-panel h2, .directions-panel h3 {
        color: white;
    }
    /* Show user ID indicator in top right */
    .user-indicator {
        position: absolute;
        top: 5px;
        right: 15px;
        font-size: 0.8rem;
        color: #888;
        padding: 2px 8px;
        border-radius: 3px;
        background-color: #f0f0f0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add title with custom styling
    st.markdown('<h1 class="big-title">Sanctus Videre 1.0</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle"><i>Bridging Human Creativity and Computational Insight</i></p>', unsafe_allow_html=True)
    
    # Display user ID indicator at the top (only if a user_id exists)
    if st.session_state.get("user_id"):
        user_id_display = st.session_state.get("user_id")
        # If user ID is long, truncate it for display
        if len(user_id_display) > 20:
            user_id_display = user_id_display[:10] + '...' + user_id_display[-10:]
        st.markdown(f'<div class="user-indicator">User: {user_id_display}</div>', unsafe_allow_html=True)
    
    # --- Health Check & Initial Drawings Fetch ---
    try:
        status = health_check().get('status')
        if status == 'ok':
            st.session_state.backend_healthy = True
            
            # FIXED: Make sure drawings are always fetched on initial load
            if not st.session_state.drawings:
                logger.info("Drawings list empty, doing initial fetch")
                # Turn off skip flag to ensure drawings are fetched
                st.session_state["skip_next_refresh"] = False
                # Fetch drawings
                refresh_drawings()
            else:
                logger.info(f"Using existing drawings list with {len(st.session_state.drawings)} items")
        else:
            st.error("⚠️ Backend service unavailable.")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Health check failed: {e}")

    # --- Sidebar: Upload with Directions Button ---
    with st.sidebar:
        # Directions Button - toggles direction visibility
        if st.button("📋 Directions", use_container_width=True):
            st.session_state.show_directions = not st.session_state.show_directions
            # The button click will naturally trigger a rerun
            
        # Show directions panel if enabled
        if st.session_state.show_directions:
            st.markdown('<div class="directions-panel">', unsafe_allow_html=True)
            st.markdown(get_directions_content())
            if st.button("Close Directions", use_container_width=True):
                st.session_state.show_directions = False
                # The button click will naturally trigger a rerun
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Upload Drawing component
        upload_ok = integrated_upload_drawing()
        if upload_ok:
            # After upload completes, refresh the list
            refresh_drawings()

    # --- Three-Column Layout ---
    col1, col2, col3 = st.columns([1, 1, 2])

    # --- Left Column: Drawing Selection ---
    with col1:
        st.subheader("Select Drawings")
    
        # Add manual refresh button (new addition to solve the missing drawings issue)
        if st.button("Refresh Drawings List"):
            st.session_state["skip_next_refresh"] = False  # Ensure skip flag is off
            refresh_drawings()
            st.success("✅ Drawings list refreshed!")
    
        # Special notification if upload just completed
        if st.session_state.get("refresh_drawings_needed", False):
            st.success("✨ New drawing has been uploaded!")
    
        # Drawing list component (integrated version)
        selected = integrated_drawing_list(st.session_state.drawings)
        if selected is not None:
            st.session_state.selected_drawings = selected

        # Single delete button for all selected drawings
        if st.session_state.selected_drawings:
            if st.button("Delete Selected Drawings"):
                delete_count = 0
                error_count = 0
                
                # Save a copy of selected drawings to process
                drawings_to_delete = list(st.session_state.selected_drawings)
                
                # Clear the selected drawings list immediately to avoid UI state issues
                # This is the key fix: clearing selection before processing deletions
                st.session_state.selected_drawings = []
                
                # Get user_id for deletion
                user_id = st.session_state.get("user_id")
                
                # Process each drawing from our saved copy
                for drawing in drawings_to_delete:
                    try:
                        # Log before deletion attempt
                        logger.info(f"Attempting to delete drawing: {drawing} for user: {user_id}")
                        
                        # Call delete API with user_id and capture response
                        response = delete_drawing(drawing, user_id)
                        logger.info(f"Delete API response: {response}")
                        
                        # Consider 404 errors as success for UI purposes
                        if response and response.get('success'):
                            delete_count += 1
                            logger.info(f"Successfully deleted drawing: {drawing}")
                        else:
                            error_msg = response.get('error', 'Unknown error')
                            logger.error(f"API reported error deleting {drawing}: {error_msg}")
                            
                            # Check if it's a 404 error (drawing not found)
                            if "404" in str(error_msg) or "not found" in str(error_msg).lower():
                                # Treat "not found" as success for UI purposes
                                logger.info(f"Drawing {drawing} not found, treating as already deleted")
                                delete_count += 1
                            else:
                                st.error(f"Failed to delete {drawing}: {error_msg}")
                                error_count += 1
                    except Exception as e:
                        logger.error(f"Exception when deleting {drawing}: {e}")
                        st.error(f"Failed to delete {drawing}: {e}")
                        error_count += 1
                
                # REVISED: Follow the automatic refresh pattern instead of forcing a rerun
                # Refresh the drawings list to show current state
                refresh_drawings()
                
                # Set the flag that indicates drawings need to be refreshed
                # This follows the pattern from automatic refresh
                st.session_state["refresh_drawings_needed"] = True
                
                # Show summary message
                if delete_count > 0:
                    st.success(f"Successfully processed {delete_count} drawings.")

    # --- Middle Column: Query, Analysis Control & Status ---
    with col2:
        st.subheader("Query & Status")
    
        # Query input (simplified from query_box component)
        st.session_state.query = st.text_area(
            "Type your question here...", 
            st.session_state.query, 
            placeholder="Example: What are the finishes specified for the private offices?"
        )
        
        # Cache controls - added Clear Cache button next to Use Cache checkbox
        col_cache1, col_cache2 = st.columns([1, 1])
        with col_cache1:
            st.session_state.use_cache = st.checkbox("Use cache", value=st.session_state.use_cache)
        with col_cache2:
            if st.button("Clear Cache"):
                # Call the clear_cache function with the current user_id
                response = user_clear_cache()
                if response and response.get('success'):
                    st.success("Cache cleared successfully!")
                else:
                    error_msg = response.get('error', 'Unknown error')
                    st.error(f"Failed to clear cache: {error_msg}")
    
        # Buttons side by side with new Clear Results button
        col2a, col2b, col2c = st.columns(3)
        
        # Analyze button
        with col2a:
            analyze_disabled = not st.session_state.query.strip() or not st.session_state.selected_drawings
            if st.button("Analyze Drawings", disabled=analyze_disabled):
                try:
                    # Get user_id for analysis
                    user_id = st.session_state.get("user_id")
                    
                    # Start analysis with user_id
                    resp = start_analysis(
                        st.session_state.query,
                        st.session_state.selected_drawings,
                        st.session_state.use_cache,
                        user_id
                    )
                    if resp and 'job_id' in resp:
                        st.session_state.current_job_id = resp['job_id']
                        st.session_state.job_status = None
                        
                        # The button click will naturally trigger a rerun
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
                        
                        # The button click will naturally trigger a rerun
                    else:
                        st.warning("Results not ready yet. Please wait for analysis to complete.")
                except Exception as e:
                    st.error(f"Error retrieving results: {str(e)}")
        
        # Clear Results button
        with col2c:
            if st.button("Clear Results"):
                # Simply clear the results
                st.session_state.analysis_results = None
                
                # The button click will naturally trigger a rerun
    
        # Job status display - styled with border for better appearance
        if st.session_state.current_job_id:
            try:
                # Poll job status
                job = get_job_status(st.session_state.current_job_id)
                st.session_state.job_status = job
        
                phase = job.get('phase', '')
                prog = job.get('progress', 0)
                
                # Status display in a bordered container with better spacing
                with st.container(border=True):
                    # Status indicator
                    st.markdown(f"**Status:**")
                    st.markdown(f"### {phase}")
                    
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
                    st.rerun()  # This rerun is needed for the polling loop
            except Exception as e:
                st.error(f"Error updating job status: {str(e)}")

    # --- Right Column: Analysis Results ---
    with col3:
        st.subheader("Analysis Results")
        
        # Show appropriate content based on analysis state
        if st.session_state.current_job_id:
            # Show "analyzing" message while job is running
            st.info("Analysis in progress. Results will appear here when complete.")
        elif st.session_state.analysis_results is not None:
            # Show results using improved display function
            integrated_results_pane(st.session_state.analysis_results)
        else:
            # Default state
            st.info("Results will appear here after analysis completes.")

if __name__ == "__main__":
    main()
