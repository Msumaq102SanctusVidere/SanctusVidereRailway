# --- Filename: ui/components/progress_bar.py (Enhanced Progress Indicator) ---

import streamlit as st
import time
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

# Set up logging
logger = logging.getLogger(__name__)

def extract_tile_info(progress_messages: List[str]) -> Dict[str, Any]:
    """
    Extract information about tile processing from progress messages.
    
    Returns a dict with:
    - total_tiles: Total number of tiles detected
    - processed_tiles: Number of tiles processed so far
    - current_tile: Name of the current tile being processed
    """
    tile_info = {
        "total_tiles": 0,
        "processed_tiles": 0,
        "current_tile": ""
    }
    
    try:
        if not progress_messages:
            return tile_info
        
        # Try to find total tile count
        for message in progress_messages:
            if "Generated" in message and "tiles" in message:
                match = re.search(r"Generated (\d+) tiles", message)
                if match:
                    tile_info["total_tiles"] = int(match.group(1))
                    break
        
        # Process messages to find current tile and count processed tiles
        processed_tiles_set = set()
        current_tile = ""
        
        for message in progress_messages:
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
        logger.error(f"Error extracting tile info: {e}")
        return tile_info

def check_api_status(progress_messages: List[str]) -> Dict[str, Any]:
    """
    Check API connection status from progress messages.
    
    Returns a dict with:
    - status: "good", "warning", or "error"
    - success_count: Number of successful API calls
    - error_count: Number of API errors
    """
    api_status = {
        "status": "unknown",
        "success_count": 0,
        "error_count": 0,
        "retry_count": 0,
        "last_response_time": None,
        "last_error": ""
    }
    
    try:
        # Process all messages
        for message in progress_messages:
            # Count successful API calls
            if "HTTP/1.1 200 OK" in message:
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
        logger.error(f"Error checking API status: {e}")
        return api_status

def get_current_operation(progress_messages: List[str]) -> str:
    """
    Determine the current operation from progress messages.
    Returns a user-friendly description of what's happening now.
    """
    if not progress_messages:
        return "Starting..."
    
    # Get the most recent message
    latest_message = progress_messages[-1]
    
    # Remove timestamp if present
    if " - " in latest_message:
        latest_message = latest_message.split(" - ", 1)[1]
    
    # Look for specific operations
    if "Converting" in latest_message:
        return "Converting PDF to image"
    elif "orientation" in latest_message:
        return "Adjusting image orientation"
    elif "Creating tiles" in latest_message:
        return "Dividing image into tiles"
    elif "Generated" in latest_message and "tiles" in latest_message:
        return "Tile generation complete"
    elif "Analyzing legend" in latest_message:
        return "Analyzing drawing legends"
    elif "Analyzing content tile" in latest_message:
        # Extract tile information
        match = re.search(r"Analyzing content tile ([^\s]+)", latest_message)
        if match:
            return f"Analyzing content in {match.group(1)}"
    elif "Analysis completed" in latest_message:
        return "Analysis complete"
    elif "Processing failed" in latest_message:
        return "Processing failed"
    
    # Default case
    return latest_message

def progress_indicator(job_id: str, poll_interval: float = 1.0) -> Dict[str, Any]:
    """Enhanced progress indicator with detailed information.
    
    Args:
        job_id: ID of the job to track
        poll_interval: How often to poll for updates (seconds)
        
    Returns:
        The job status data from the API
    """
    from api_client import get_job_status
    
    try:
        # Initial status request
        job_status = get_job_status(job_id)
        
        if not job_status or not isinstance(job_status, dict):
            st.error(f"Error getting job status: {job_status}")
            return None
        
        # Extract key information
        status = job_status.get("status", "")
        progress = job_status.get("progress", 0)
        current_phase = job_status.get("current_phase", "")
        progress_messages = job_status.get("progress_messages", [])
        
        # Create enhanced progress bar
        progress_container = st.container(border=True)
        
        with progress_container:
            # Show progress header
            if status == "completed":
                st.success(f"✅ Processing Complete (100%)")
            elif status == "failed":
                st.error(f"❌ Processing Failed")
                error_msg = job_status.get("error", "Unknown error")
                st.error(f"Error: {error_msg}")
            else:
                st.subheader(f"Processing: {progress}% Complete")
            
            # Show main progress bar
            st.progress(progress / 100)
            
            # Show current phase
            st.write(f"**Phase:** {current_phase}")
            
            # Extract tile information
            tile_info = extract_tile_info(progress_messages)
            total_tiles = tile_info.get("total_tiles", 0)
            processed_tiles = tile_info.get("processed_tiles", 0)
            current_tile = tile_info.get("current_tile", "")
            
            # Show tile information if available
            if total_tiles > 0:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Show tile progress
                    st.metric("Tiles Processed", f"{processed_tiles} / {total_tiles}")
                    
                    # Show tile progress bar if meaningful
                    if processed_tiles > 0 and total_tiles > 0:
                        st.progress(min(processed_tiles / total_tiles, 1.0))
                
                with col2:
                    # Current tile
                    if current_tile:
                        st.write(f"**Current Tile:** {current_tile}")
                    
                    # Current operation
                    current_op = get_current_operation(progress_messages)
                    st.write(f"**Current Operation:** {current_op}")
            
            # Check API status
            api_status = check_api_status(progress_messages)
            api_status_value = api_status.get("status", "unknown")
            api_success_count = api_status.get("success_count", 0)
            api_error_count = api_status.get("error_count", 0)
            
            # Show API status if we have meaningful information
            if api_success_count > 0 or api_error_count > 0:
                st.write("**Foundation Model Connection:**")
                status_cols = st.columns([1, 3])
                
                with status_cols[0]:
                    if api_status_value == "good":
                        st.success("✓ Good")
                    elif api_status_value == "warning":
                        st.warning("⚠️ Issues")
                    elif api_status_value == "error":
                        st.error("❌ Problems")
                    else:
                        st.info("ℹ️ Unknown")
                
                with status_cols[1]:
                    if api_success_count > 0:
                        st.write(f"✓ {api_success_count} successful API calls")
                    if api_error_count > 0:
                        st.write(f"⚠️ {api_error_count} errors (with automatic retry)")
            
            # Recent updates section
            st.write("--- Recent Updates ---")
            
            # Display last 5 progress messages (reversed so newest are first)
            if progress_messages:
                latest_messages = progress_messages[-5:]
                latest_messages.reverse()
                
                for message in latest_messages:
                    # Extract message without timestamp
                    if " - " in message:
                        timestamp, content = message.split(" - ", 1)
                    else:
                        content = message
                    
                    # Display with appropriate styling
                    if "❌" in content or "error" in content.lower() or "failed" in content.lower():
                        st.error(content)
                    elif "⚠️" in content or "warning" in content.lower():
                        st.warning(content)
                    elif "✅" in content or "Generated" in content or "complete" in content:
                        st.success(content)
                    else:
                        st.info(content)
        
        # Return the job status
        return job_status
    
    except Exception as e:
        logger.error(f"Error in progress_indicator: {e}")
        st.error(f"Error tracking progress: {e}")
        return None

# Example usage if run directly
if __name__ == "__main__":
    st.title("Progress Indicator Test")
    
    # Example job ID
    job_id = st.text_input("Enter Job ID")
    
    if job_id:
        progress_indicator(job_id)
