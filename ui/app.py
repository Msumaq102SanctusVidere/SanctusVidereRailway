# --- Filename: ui/app.py (Frontend Streamlit UI - Enhanced Progress Tracking) ---

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
    if "drawing_to_delete" not in st.session_state:
        st.session_state.drawing_to_delete = None
    if "upload_job_id" not in st.session_state:
        st.session_state.upload_job_id = None
    if "show_advanced_logs" not in st.session_state:
        st.session_state.show_advanced_logs = False
    if "log_level_filter" not in st.session_state:
        st.session_state.log_level_filter = "INFO"
    logger.info("Session state initialized")

initialize_session_state()

# --- Toggle Advanced Logs ---
def toggle_advanced_logs():
    st.session_state.show_advanced_logs = not st.session_state.show_advanced_logs
    logger.info(f"Advanced logs toggled to: {st.session_state.show_advanced_logs}")

# --- Set Log Level Filter ---
def set_log_level_filter(level):
    st.session_state.log_level_filter = level
    logger.info(f"Log level filter set to: {level}")

# --- Main Application Logic ---
def main():
    # --- Page Configuration ---
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")
    # --- Title Area ---
    st.title("🏗️ Sanctus Videre 1.0"); st.caption("Visionary Construction Insights"); st.divider()
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
            st.error("⚠️ Backend service unhealthy. Please check server status.")
            logger.error(f"Backend unhealthy: {health_status}")
    except Exception as e:
        st.session_state.backend_healthy = False
        st.error(f"⚠️ Unable to connect to backend service: {e}")
        logger.error(f"Backend connection error: {e}", exc_info=True)

    # --- Sidebar for Upload ---
    with st.sidebar:
        upload_success = upload_drawing_component()
        if upload_success:
            # Refresh drawings if upload was successful
            refresh_drawings()
            st.rerun()

    # --- Main Layout (Two Columns) ---
    col1, col2 = st.columns([1, 2])

    # --- Left Column: Drawing Selection & Deletion ---
    with col1:
        st.subheader("Select Drawings")

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

                        # --- SIMPLIFIED ERROR HANDLING ---
                        # Trust only the "success" boolean from the backend
                        if isinstance(response, dict) and response.get("success") is True:
                            st.success(f"Drawing `{target_drawing}` deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")

                            # Refresh UI only on explicit success from backend
                            if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)
                            st.session_state.drawing_to_delete = None
                            refresh_drawings()
                            st.rerun()
                        else:
                            # If not success==True, show the error from the backend
                            default_error = f"Failed to delete '{target_drawing}'. Unknown error."
                            error_message = response.get("error", default_error) if isinstance(response, dict) else default_error
                            st.error(error_message) # Display the error received
                            logger.error(f"API call delete_drawing failed for '{target_drawing}'. Response: {response}")
                            # Do NOT clear drawing_to_delete or rerun here - let user Cancel
                        # --- END SIMPLIFIED HANDLING ---

                    except Exception as e:
                        # Handle exceptions during the API call itself (e.g., network error)
                        st.error(f"Error communicating with server during deletion: {e}")
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
                if st.button("🔄 Refresh", key="refresh_drawings", use_container_width=True):
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
                        if st.button(f"🗑️ Delete '{drawing}'", key=f"delete_{drawing}"):
                            st.session_state.drawing_to_delete = drawing
                            st.rerun()
                else:
                    st.caption("Select drawings to analyze or delete")

    # --- Right Column: Query, Controls, Progress, Results ---
    try:
        with col2:
            # Use the query_box component
            query = query_box(disabled=not st.session_state.backend_healthy)
            st.session_state.query = query
            
            # Use the control_row component
            disabled = not (st.session_state.backend_healthy and 
                          st.session_state.selected_drawings and 
                          st.session_state.query.strip())
            force_new, analyze_clicked, stop_clicked = control_row(disabled=disabled)
            
            # Handle analyze button click
            if analyze_clicked and st.session_state.selected_drawings and st.session_state.query.strip():
                with st.spinner("Starting analysis..."):
                    try:
                        response = analyze_drawings(
                            st.session_state.query,
                            st.session_state.selected_drawings,
                            use_cache=not force_new
                        )
                        
                        if response and "job_id" in response:
                            st.session_state.current_job_id = response["job_id"]
                            st.session_state.job_status = None
                            st.session_state.analysis_results = None
                            logger.info(f"Started analysis job: {st.session_state.current_job_id}")
                            st.rerun()
                        else:
                            st.error(f"Failed to start analysis: {response}")
                            logger.error(f"Failed to start analysis: {response}")
                    except Exception as e:
                        st.error(f"Error starting analysis: {e}")
                        logger.error(f"Error starting analysis: {e}", exc_info=True)
            
            # Handle stop button click
            if stop_clicked and st.session_state.current_job_id:
                st.session_state.current_job_id = None
                st.success("Analysis stopped.")
                st.rerun()
            
            # --- Enhanced Progress Display ---
            if st.session_state.current_job_id:
                # Get detailed job status and logs
                job_status, job_logs = get_detailed_job_status(st.session_state.current_job_id)
                
                if job_status:
                    # Store job status in session
                    st.session_state.job_status = job_status
                    
                    # Progress container with phases
                    with st.container(border=True):
                        # Get phase status for visualization
                        phase_status = get_phase_status(job_status)
                        
                        # Header with time estimation
                        st.subheader(f"Processing Status - {job_status.get('progress', 0)}% Complete")
                        
                        # Time estimation
                        time_remaining = estimate_time_remaining(job_status)
                        st.write(f"⏱️ Estimated time remaining: {time_remaining}")
                        
                        # Main progress bar
                        st.progress(job_status.get("progress", 0) / 100)
                        
                        # Phase visualization
                        phase_cols = st.columns(len(phase_status["phases"]))
                        for i, phase in enumerate(phase_status["phases"]):
                            with phase_cols[i]:
                                if phase["status"] == "complete":
                                    st.markdown(f"### {phase['emoji']} ✓")
                                elif phase["status"] == "active":
                                    st.markdown(f"### {phase['emoji']} ⟳")
                                elif phase["status"] == "failed":
                                    st.markdown(f"### {phase['emoji']} ❌")
                                else:
                                    st.markdown(f"### {phase['emoji']} ○")
                                st.caption(phase["name"])
                        
                        # Current phase description
                        current_phase = job_status.get("current_phase", "")
                        st.write(f"**Current Phase:** {current_phase}")
                        
                        # Tile Processing Information
                        tile_info = job_status.get("tile_info", {})
                        if tile_info and tile_info.get("total_tiles", 0) > 0:
                            total_tiles = tile_info.get("total_tiles", 0)
                            processed_tiles = tile_info.get("processed_tiles", 0)
                            current_tile = tile_info.get("current_tile", "")
                            
                            # Create progress meter for tiles
                            if total_tiles > 0:
                                tile_progress = min(processed_tiles / total_tiles, 1.0)
                                st.write(f"**Tile Processing:** {processed_tiles} of {total_tiles} tiles processed ({int(tile_progress * 100)}%)")
                                
                                # Tile progress bar
                                st.progress(tile_progress)
                                
                                # Current tile information
                                if current_tile:
                                    st.caption(f"Currently processing: {current_tile}")
                        
                        # API Connection Status
                        api_status = job_status.get("api_status", {})
                        api_status_value = api_status.get("status", "unknown")
                        api_success_count = api_status.get("success_count", 0)
                        api_error_count = api_status.get("error_count", 0)
                        
                        # API Status indicator
                        st.write("**Foundation Model Connection:**")
                        status_cols = st.columns([1, 3])
                        with status_cols[0]:
                            if api_status_value == "good":
                                st.success("✓ Good")
                            elif api_status_value == "warning":
                                st.warning("⚠️ Issues Detected")
                            elif api_status_value == "error":
                                st.error("❌ Connection Problems")
                            else:
                                st.info("ℹ️ Unknown")
                        
                        with status_cols[1]:
                            if api_success_count > 0:
                                st.write(f"✓ {api_success_count} successful API calls")
                            if api_error_count > 0:
                                st.write(f"⚠️ {api_error_count} errors (with automatic retry)")
                        
                        # Latest progress message
                        if "progress_messages" in job_status and job_status["progress_messages"]:
                            latest_message = job_status["progress_messages"][-1]
                            # Extract just the message part without timestamp
                            if " - " in latest_message:
                                latest_message = latest_message.split(" - ", 1)[1]
                            st.write(f"**Latest Update:** {latest_message}")
                        
                        # Controls for advanced logs
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            if st.button(
                                "🔍 " + ("Hide" if st.session_state.show_advanced_logs else "Show") + " Technical Logs", 
                                key="toggle_logs_button"
                            ):
                                toggle_advanced_logs()
                                st.rerun()
                        
                        with col2:
                            if st.session_state.show_advanced_logs:
                                log_level = st.selectbox(
                                    "Log Level",
                                    options=["ALL", "INFO", "WARNING", "ERROR"],
                                    index=["ALL", "INFO", "WARNING", "ERROR"].index(st.session_state.log_level_filter),
                                    key="log_level_selector"
                                )
                                if log_level != st.session_state.log_level_filter:
                                    set_log_level_filter(log_level)
                                    st.rerun()
                        
                        # Advanced logs display
                        if st.session_state.show_advanced_logs:
                            # Display progress messages as a log console
                            messages = []
                            if "progress_messages" in job_status:
                                messages = job_status["progress_messages"]
                            
                            # Filter messages by log level if needed
                            if st.session_state.log_level_filter != "ALL":
                                filtered_messages = []
                                for msg in messages:
                                    if st.session_state.log_level_filter == "ERROR" and ("❌" in msg or "error" in msg.lower() or "failed" in msg.lower()):
                                        filtered_messages.append(msg)
                                    elif st.session_state.log_level_filter == "WARNING" and ("⚠️" in msg or "warning" in msg.lower() or "❌" in msg or "error" in msg.lower() or "failed" in msg.lower()):
                                        filtered_messages.append(msg)
                                    elif st.session_state.log_level_filter == "INFO":
                                        filtered_messages.append(msg)
                                messages = filtered_messages
                            
                            # Use the log console component
                            log_console(messages, max_height=300)
                    
                    # Check if job is complete or failed
                    if job_status.get("status") == "completed":
                        st.session_state.analysis_results = job_status.get("result", {})
                        st.session_state.current_job_id = None
                        st.success("Analysis completed successfully!")
                        st.rerun()
                    elif job_status.get("status") == "failed":
                        error_msg = job_status.get("error", "Unknown error")
                        st.error(f"Analysis failed: {error_msg}")
                        st.session_state.current_job_id = None
                else:
                    # Fallback to standard progress indicator if detailed status not available
                    result = progress_indicator(st.session_state.current_job_id)
                    
                    if result and result.get("status") in ["completed", "failed"]:
                        st.session_state.current_job_id = None
                        if result.get("status") == "completed":
                            st.session_state.analysis_results = result.get("result", {})
                            st.success("Analysis completed successfully!")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            st.error(f"Analysis failed: {error_msg}")
            
            # Show stored results if available
            if st.session_state.analysis_results:
                st.header("Analysis Results")
                results_text = json.dumps(st.session_state.analysis_results, indent=2)
                results_pane(results_text)
                
                # Clear results button
                if st.button("Clear Results", key="clear_results"):
                    st.session_state.analysis_results = None
                    st.rerun()
    except Exception as e:
        st.error(f"An error occurred in the UI: {e}")
        logger.error(f"Unhandled UI exception: {e}", exc_info=True)


# --- Run the App ---
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}", exc_info=True)
