# --- Filename: ui/app.py (Frontend Streamlit UI - Three-Column Layout) ---

import streamlit as st
import time
import logging
import sys
import os
import json
import re
from pathlib import Path
import datetime
from typing import List, Dict, Any, Tuple, Optional

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
        get_job_status,
        get_job_logs  # New function to get detailed logs
    )
    
    # Import components from components folder
    from components.control_row import control_row
    from components.drawing_list import drawing_list
    from components.progress_bar import progress_indicator
    from components.query_box import query_box
    from components.results_pane import results_pane
    from components.upload_drawing import upload_drawing_component
    from components.log_console import log_console  # Component for log display
    
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

# --- Enhanced Job Status Tracking ---
def get_detailed_job_status(job_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Gets both job status and detailed logs for better progress tracking.
    
    Returns:
        Tuple containing (job_status, job_logs)
    """
    try:
        # Get basic job status
        job_status = get_job_status(job_id)
        
        # Get detailed logs
        try:
            # Get last 50 logs or logs since the last one we saw
            last_log_id = st.session_state.get(f"last_log_id_{job_id}", None)
            logs_response = get_job_logs(job_id, limit=50, since_id=last_log_id)
            logs = logs_response.get("logs", [])
            
            # Update the last seen log ID if we have logs
            if logs and len(logs) > 0:
                st.session_state[f"last_log_id_{job_id}"] = logs[0].get("id")
        except Exception as log_e:
            logger.warning(f"Could not fetch detailed logs: {log_e}")
            logs = []
        
        # Extract tile processing information
        tile_info = extract_tile_info(job_status, logs)
        if tile_info:
            # Update session state with tile information
            st.session_state[f"tile_info_{job_id}"] = tile_info
        else:
            # Use cached tile info if available
            tile_info = st.session_state.get(f"tile_info_{job_id}", {})
        
        # Add tile info to job status
        job_status["tile_info"] = tile_info
        
        # Extract API connection status
        api_status = extract_api_status(logs)
        job_status["api_status"] = api_status
        
        return job_status, logs
    except Exception as e:
        logger.error(f"Error getting detailed job status: {e}", exc_info=True)
        return None, []

def extract_tile_info(job_status: Dict[str, Any], logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract information about tile processing from logs and job status.
    
    Returns a dict with:
    - total_tiles: Total number of tiles detected
    - processed_tiles: Number of tiles processed so far
    - current_tile: Name of the current tile being processed
    - phase: Current processing phase
    """
    tile_info = {
        "total_tiles": 0,
        "processed_tiles": 0,
        "current_tile": "",
        "phase": ""
    }
    
    try:
        # Check job status and progress messages
        if not job_status or not isinstance(job_status, dict):
            return tile_info
        
        # Get progress messages
        messages = job_status.get("progress_messages", [])
        
        # Try to find total tile count
        for message in messages:
            if "Generated" in message and "tiles" in message:
                match = re.search(r"Generated (\d+) tiles", message)
                if match:
                    tile_info["total_tiles"] = int(match.group(1))
                    break
        
        # Get current phase
        tile_info["phase"] = job_status.get("current_phase", "")
        
        # Process logs to find current tile and count processed tiles
        processed_tiles_set = set()
        current_tile = ""
        
        # Convert logs to messages if needed
        log_messages = []
        if isinstance(logs, list):
            for log in logs:
                if isinstance(log, dict) and "message" in log:
                    log_messages.append(log["message"])
                elif isinstance(log, str):
                    log_messages.append(log)
        
        # Add progress messages
        log_messages.extend(messages)
        
        # Process all messages
        for message in log_messages:
            # Look for tile processing messages
            if "Analyzing content tile" in message or "Analyzing legend tile" in message:
                match = re.search(r"Analyzing (?:content|legend) tile ([^\s]+)", message)
                if match:
                    tile_name = match.group(1)
                    processed_tiles_set.add(tile_name)
                    current_tile = tile_name
        
        # Update tile info
        tile_info["processed_tiles"] = len(processed_tiles_set)
        tile_info["current_tile"] = current_tile
        
        return tile_info
    except Exception as e:
        logger.error(f"Error extracting tile info: {e}", exc_info=True)
        return tile_info

def extract_api_status(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract API connection status information from logs.
    
    Returns a dict with:
    - status: "good", "warning", or "error"
    - success_count: Number of successful API calls
    - error_count: Number of API errors
    - retry_count: Number of retries
    - last_error: Last error message
    """
    api_status = {
        "status": "unknown",
        "success_count": 0,
        "error_count": 0,
        "retry_count": 0,
        "last_error": ""
    }
    
    try:
        # Convert logs to messages if needed
        log_messages = []
        if isinstance(logs, list):
            for log in logs:
                if isinstance(log, dict) and "message" in log:
                    log_messages.append(log["message"])
                elif isinstance(log, str):
                    log_messages.append(log)
        
        # Process all messages
        for message in log_messages:
            # Count successful API calls
            if "HTTP Request: POST" in message and "HTTP/1.1 200 OK" in message:
                api_status["success_count"] += 1
            
            # Count errors and retries
            if "API error" in message:
                api_status["error_count"] += 1
                api_status["last_error"] = message
            
            if "Retrying" in message:
                api_status["retry_count"] += 1
        
        # Determine overall status
        if api_status["error_count"] == 0 and api_status["success_count"] > 0:
            api_status["status"] = "good"
        elif api_status["error_count"] > 0 and api_status["success_count"] > 0:
            api_status["status"] = "warning"
        elif api_status["error_count"] > 0 and api_status["success_count"] == 0:
            api_status["status"] = "error"
        
        return api_status
    except Exception as e:
        logger.error(f"Error extracting API status: {e}", exc_info=True)
        return api_status

# --- Job Progress Visualization Functions ---
def get_phase_status(job_status: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze job status and return phase information for visualization.
    """
    phases = [
        {"id": "init", "name": "Initialization", "emoji": "🚀"},
        {"id": "convert", "name": "PDF Conversion", "emoji": "📄"},
        {"id": "tile", "name": "Image Tiling", "emoji": "🖼️"},
        {"id": "analyze", "name": "Content Analysis", "emoji": "🔍"},
        {"id": "complete", "name": "Completion", "emoji": "✨"}
    ]
    
    current_phase = job_status.get("current_phase", "")
    progress = job_status.get("progress", 0)
    status = job_status.get("status", "")
    
    # Map backend phase to frontend phase
    phase_mapping = {
        "🚀 INITIALIZATION": "init",
        "⏳ QUEUED": "init",
        "📄 CONVERTING": "convert",
        "🖼️ TILING": "tile",
        "🔍 ANALYZING LEGENDS": "analyze",
        "🧩 ANALYZING CONTENT": "analyze",
        "✨ COMPLETE": "complete",
        "❌ FAILED": ""
    }
    
    # Check logs for more accurate phase detection
    tile_info = job_status.get("tile_info", {})
    if tile_info:
        # Override phase based on tile processing information
        if "Analyzing content" in str(tile_info.get("current_tile", "")):
            current_phase = "🧩 ANALYZING CONTENT"
    
    current_phase_id = phase_mapping.get(current_phase, "")
    
    # Determine the status of each phase
    phase_statuses = []
    found_current = False
    
    for phase in phases:
        if status == "failed":
            # If job failed, mark the current phase as failed and earlier phases as complete
            if phase["id"] == current_phase_id:
                phase_status = "failed"
            elif found_current:
                phase_status = "pending"
            else:
                phase_status = "complete"
        elif phase["id"] == current_phase_id:
            phase_status = "active"
            found_current = True
        elif found_current:
            phase_status = "pending"
        else:
            phase_status = "complete"
        
        phase_statuses.append({
            "id": phase["id"],
            "name": phase["name"],
            "emoji": phase["emoji"],
            "status": phase_status
        })
    
    return {
        "phases": phase_statuses,
        "current_phase_id": current_phase_id,
        "progress": progress,
        "status": status
    }

def format_time_elapsed(seconds: float) -> str:
    """Format seconds into a human-readable time string."""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"

def estimate_time_remaining(job_status: Dict[str, Any]) -> str:
    """Estimate remaining time based on progress and time elapsed."""
    try:
        progress = job_status.get("progress", 0)
        if progress <= 0:
            return "Calculating..."
        
        created_at = job_status.get("created_at", "")
        if not created_at:
            return "Unknown"
        
        # Parse ISO timestamp
        created_datetime = datetime.datetime.fromisoformat(created_at.rstrip('Z'))
        if created_datetime.tzinfo is None:
            created_datetime = created_datetime.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Calculate elapsed time
        elapsed_seconds = (now - created_datetime).total_seconds()
        
        # Estimate total time based on progress percentage
        if progress < 5:  # Too early for accurate estimation
            return "Calculating..."
        
        total_estimated_seconds = elapsed_seconds * 100 / progress
        remaining_seconds = total_estimated_seconds - elapsed_seconds
        
        # Format remaining time
        if remaining_seconds < 0:
            return "Almost done..."
        
        return format_time_elapsed(remaining_seconds)
    except Exception as e:
        logger.error(f"Error estimating time: {e}")
        return "Calculating..."

# --- Process Completed Job ---
def process_completed_job(job_status):
    """Process a completed job and extract results for display."""
    try:
        # Get the result object
        result = job_status.get("result", {})
        
        # Store the complete result object for potential debugging
        st.session_state.raw_job_result = result
        
        # If result is a string, try to parse it
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                # If not valid JSON, store as-is
                st.session_state.analysis_results = result
                return
        
        # Extract analysis text from result structure
        if isinstance(result, dict):
            # Direct analysis field
            if "analysis" in result:
                st.session_state.analysis_results = result
                return
                
            # Check for batch structure
            if "batches" in result and isinstance(result["batches"], list) and result["batches"]:
                for batch in result["batches"]:
                    if isinstance(batch, dict) and "result" in batch:
                        batch_result = batch["result"]
                        if isinstance(batch_result, dict) and "analysis" in batch_result:
                            # Store the entire result structure for access to both 
                            # analysis text and technical details
                            st.session_state.analysis_results = result
                            return
        
        # Fallback: store the whole result
        st.session_state.analysis_results = result
        
    except Exception as e:
        logger.error(f"Error processing completed job: {e}", exc_info=True)
        st.session_state.analysis_results = f"Error processing results: {str(e)}"

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
    if "raw_job_result" not in st.session_state:
        st.session_state.raw_job_result = None
    if "drawing_to_delete" not in st.session_state:
        st.session_state.drawing_to_delete = None
    if "upload_job_id" not in st.session_state:
        st.session_state.upload_job_id = None
    if "show_logs" not in st.session_state:
        st.session_state.show_logs = False
    if "log_level_filter" not in st.session_state:
        st.session_state.log_level_filter = "INFO"
    if "upload_success" not in st.session_state:
        st.session_state.upload_success = False
    if "last_poll_time" not in st.session_state:
        st.session_state.last_poll_time = 0
    if "left_column_expanded" not in st.session_state:
        st.session_state.left_column_expanded = True
    if "middle_column_expanded" not in st.session_state:
        st.session_state.middle_column_expanded = True
    if "all_job_logs" not in st.session_state:
        st.session_state.all_job_logs = []
    logger.info("Session state initialized")

initialize_session_state()

# --- Toggle Logs Display ---
def toggle_logs_display():
    st.session_state.show_logs = not st.session_state.show_logs
    logger.info(f"Logs display toggled to: {st.session_state.show_logs}")

# --- Toggle Left Column Expansion ---
def toggle_left_column():
    st.session_state.left_column_expanded = not st.session_state.left_column_expanded
    logger.info(f"Left column expanded: {st.session_state.left_column_expanded}")

# --- Toggle Middle Column Expansion ---
def toggle_middle_column():
    st.session_state.middle_column_expanded = not st.session_state.middle_column_expanded
    logger.info(f"Middle column expanded: {st.session_state.middle_column_expanded}")

# --- Set Log Level Filter ---
def set_log_level_filter(level):
    st.session_state.log_level_filter = level
    logger.info(f"Log level filter set to: {level}")

# --- Check for Completion in Logs ---
def check_for_completion(logs):
    """Check logs for completion indicators"""
    completion_indicators = [
        "Analysis completed",
        "Analysis complete",
        "COMPLETE",
        "Completed batch",
        "completed successfully"
    ]
    
    if logs:
        for message in logs:
            for indicator in completion_indicators:
                if indicator in message:
                    logger.info(f"Job completion detected in logs: {message}")
                    return True
    return False

# --- Main Application Logic ---
def main():
    # --- Page Configuration ---
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")
    
    # --- Title Area ---
    st.title("Sanctus Videre 1.0")
    st.caption("Construction Drawing Analysis Platform")
    st.divider()
    
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
            st.error("⚠️ Backend service unavailable. Please check server status.")
            logger.error(f"Backend unhealthy: {health_status}")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Unable to connect to backend service: {e}")
        logger.error(f"Backend connection error: {e}", exc_info=True)

    # --- Sidebar for Upload ---
    with st.sidebar:
        st.header("Upload Drawing")
        upload_success = upload_drawing_component()
        if upload_success:
            # Mark successful upload for refreshing drawings
            st.session_state.upload_success = True
            # Refresh drawings if upload was successful
            refresh_drawings()
            st.rerun()
    
    # --- Three-column layout ---
    # Create three columns with flexible widths
    # Determine column widths based on expansion state
    left_width = 1 if st.session_state.left_column_expanded else 0.5
    middle_width = 1 if st.session_state.middle_column_expanded else 0.5
    right_width = 2  # Right column always gets more space
    
    col1, col2, col3 = st.columns([left_width, middle_width, right_width])
    
    # --- Left Column: Drawing Selection (Collapsible) ---
    with col1:
        # Collapsible header
        left_col_header = st.container()
        with left_col_header:
            col1a, col1b = st.columns([5, 1])
            with col1a:
                st.subheader("Select Drawings")
            with col1b:
                # Toggle button for left column
                if st.button("↔️", key="toggle_left_col", help="Expand/Collapse"):
                    toggle_left_column()
                    st.rerun()
        
        # If expanded, show full content, otherwise show minimal content
        if st.session_state.left_column_expanded:
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

                            # Trust only the "success" boolean from the backend
                            if isinstance(response, dict) and response.get("success") is True:
                                st.success(f"Drawing deleted successfully.")
                                logger.info(f"Successfully deleted drawing: {target_drawing}")

                                # Refresh UI only on explicit success from backend
                                if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                    st.session_state.selected_drawings.remove(target_drawing)
                                st.session_state.drawing_to_delete = None
                                refresh_drawings()
                                st.rerun()
                            else:
                                # If not success==True, show the error from the backend
                                default_error = f"Failed to delete drawing. Unknown error."
                                error_message = response.get("error", default_error) if isinstance(response, dict) else default_error
                                st.error(error_message) # Display the error received
                                logger.error(f"API call delete_drawing failed for '{target_drawing}'. Response: {response}")
                        except Exception as e:
                            # Handle exceptions during the API call itself (e.g., network error)
                            st.error(f"Error communicating with server: {e}")
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
                    if st.button("Refresh Drawings", key="refresh_drawings", use_container_width=True):
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
                            if st.button(f"Delete '{drawing}'", key=f"delete_{drawing}"):
                                st.session_state.drawing_to_delete = drawing
                                st.rerun()
                    else:
                        st.caption("Select one or more drawings to analyze")
        else:
            # Show minimal view when collapsed
            st.info(f"Selected: {len(st.session_state.selected_drawings)} drawing(s)")
    
    # --- Middle Column: Query Input & Status (Collapsible) ---
    with col2:
        # Collapsible header
        middle_col_header = st.container()
        with middle_col_header:
            col2a, col2b = st.columns([5, 1])
            with col2a:
                st.subheader("Query & Status")
            with col2b:
                # Toggle button for middle column
                if st.button("↔️", key="toggle_middle_col", help="Expand/Collapse"):
                    toggle_middle_column()
                    st.rerun()
        
        # If expanded, show full content, otherwise show minimal content
        if st.session_state.middle_column_expanded:
            # --- Query Input ---
            query = st.text_area(
                "Type your question here...",
                value=st.session_state.get("query", ""),
                height=120,
                disabled=not st.session_state.backend_healthy,
                placeholder="Example: What are the finishes specified for the private offices?"
            )

            # Store the query in session state
            st.session_state.query = query

            # Force new analysis checkbox
            force_new = st.checkbox("Force new analysis (ignore cache)", value=False)

            # Submit button
            disabled = not (st.session_state.backend_healthy and 
                        st.session_state.selected_drawings and 
                        query.strip())
                        
            if st.button(
                "Analyze Drawings",
                type="primary",
                disabled=disabled,
                use_container_width=True,
                key="analyze_button"
            ):
                with st.spinner("Starting analysis..."):
                    try:
                        response = analyze_drawings(
                            query,
                            st.session_state.selected_drawings,
                            use_cache=not force_new
                        )
                        
                        if response and "job_id" in response:
                            st.session_state.current_job_id = response["job_id"]
                            st.session_state.job_status = None
                            st.session_state.analysis_results = None
                            st.session_state.raw_job_result = None
                            # Reset logs for new job
                            st.session_state.all_job_logs = []
                            logger.info(f"Started analysis job: {st.session_state.current_job_id}")
                            st.rerun()
                        else:
                            st.error(f"Failed to start analysis: {response}")
                            logger.error(f"Failed to start analysis: {response}")
                    except Exception as e:
                        st.error(f"Error starting analysis: {e}")
                        logger.error(f"Error starting analysis: {e}", exc_info=True)
            
            # Stop analysis button
            if st.session_state.current_job_id:
                if st.button("Stop Analysis", key="stop_analysis", use_container_width=True):
                    st.session_state.current_job_id = None
                    st.info("Analysis stopped.")
                    st.rerun()
            
            # --- Job Status & Technical Logs ---
            if st.session_state.current_job_id:
                # Get job status AND detailed logs
                job_status, job_logs = get_detailed_job_status(st.session_state.current_job_id)
                
                # Extract log messages from job_logs
                log_messages = []
                if job_logs:
                    for log in job_logs:
                        if isinstance(log, dict) and "message" in log:
                            log_messages.append(log["message"])
                
                # Add progress messages from job status
                progress_messages = []
                if job_status and "progress_messages" in job_status:
                    progress_messages = job_status.get("progress_messages", [])
                
                # Update the cumulative logs in session state
                if log_messages or progress_messages:
                    # Get existing logs
                    all_logs = st.session_state.all_job_logs.copy()
                    
                    # Add new log messages
                    for message in log_messages + progress_messages:
                        if message not in all_logs:
                            all_logs.append(message)
                    
                    # Store updated logs
                    st.session_state.all_job_logs = all_logs
                
                if job_status:
                    # Get status information
                    status = job_status.get("status", "")
                    current_phase = job_status.get("current_phase", "")
                    
                    # Display status info
                    with st.container(border=True):
                        # Clean up phase name (remove emojis)
                        if current_phase:
                            clean_phase = re.sub(r'[^\w\s]', '', current_phase).strip()
                            st.info(f"Status: Processing - {clean_phase}")
                        
                        # Latest progress message
                        if progress_messages:
                            latest_message = progress_messages[-1]
                            # Extract just the message part without timestamp
                            if " - " in latest_message:
                                latest_message = latest_message.split(" - ", 1)[1]
                            # Remove emojis for cleaner display
                            clean_message = re.sub(r'[^\w\s,.\-;:()/]', '', latest_message).strip()
                            st.caption(f"Latest Update: {clean_message}")
                        
                        # Technical logs button
                        if st.button("Show Technical Logs", key="show_tech_logs"):
                            toggle_logs_display()
                            st.rerun()
                    
                    # Show technical logs if toggled
                    if st.session_state.show_logs:
                        with st.expander("Technical Logs", expanded=True):
                            # Display all collected logs
                            for message in st.session_state.all_job_logs:
                                st.text(message)
                            
                            # Button to hide logs
                            if st.button("Hide Technical Logs", key="hide_tech_logs"):
                                toggle_logs_display()
                                st.rerun()
                    
                    # Check for job completion
                    job_completed = False
                    
                    # Check official status
                    if status == "completed":
                        job_completed = True
                    
                    # Check logs for completion indicators
                    if not job_completed:
                        job_completed = check_for_completion(st.session_state.all_job_logs)
                        
                    # If job is completed, process results
                    if job_completed:
                        logger.info("Job completion detected - processing results")
                        process_completed_job(job_status)
                        st.session_state.current_job_id = None
                        st.success("Analysis completed successfully!")
                        st.rerun()
                    elif status == "failed":
                        error_msg = job_status.get("error", "Unknown error")
                        st.error(f"Analysis failed: {error_msg}")
                        st.session_state.current_job_id = None
                else:
                    # Fallback for when job status cannot be retrieved
                    st.warning("Unable to retrieve job status. Retrying...")
                    time.sleep(0.5)
                    st.rerun()
        else:
            # Show minimal view when collapsed
            if st.session_state.current_job_id:
                st.info("Analysis in progress...")
            elif st.session_state.analysis_results:
                st.info("Analysis complete")
            else:
                st.info("Ready for query")
    
    # --- Right Column: Analysis Results (Always Expanded) ---
    with col3:
        st.subheader("Analysis Results")
        
        # Create a scrollable container for the results
        results_container = st.container(border=True, height=600)
        
        with results_container:
            # Display results if available
            if st.session_state.analysis_results:
                # Format the results for display
                if isinstance(st.session_state.analysis_results, dict):
                    results_text = json.dumps(st.session_state.analysis_results, indent=2)
                else:
                    results_text = str(st.session_state.analysis_results)
                
                # Use the results_pane component
                results_pane(results_text)
                
                # Add a copy button
                if st.button("Copy Results", key="copy_results", help="Copy results to clipboard"):
                    st.success("Results copied to clipboard!")
            else:
                # Show placeholder when no results are available
                st.info("Results will appear here after analysis is complete.")
        
        # Clear results button
        if st.session_state.analysis_results:
            if st.button("Clear Results", key="clear_results"):
                st.session_state.analysis_results = None
                st.session_state.raw_job_result = None
                st.rerun()


# --- Run the App ---
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}", exc_info=True)
