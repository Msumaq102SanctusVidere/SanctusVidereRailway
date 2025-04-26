# --- Filename: ui/components/log_console.py (Enhanced Log Console Component) ---

import streamlit as st
import logging
import re
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

def parse_log_message(message: str) -> Dict[str, Any]:
    """
    Parse a log message into its components.
    
    Expected format: "TIMESTAMP - MESSAGE"
    
    Returns a dict with:
    - timestamp: The timestamp string
    - message: The message text
    - level: The log level (INFO, WARNING, ERROR, etc.)
    - icon: An emoji representing the log level
    - is_tile_processing: Whether this message is about tile processing
    - tile_name: The name of the tile being processed (if applicable)
    - api_info: Information about API calls (if applicable)
    """
    try:
        # Split timestamp and message
        parts = message.split(" - ", 1)
        timestamp = parts[0] if len(parts) > 1 else ""
        content = parts[1] if len(parts) > 1 else message
        
        # Determine log level based on content
        level = "INFO"
        icon = "ℹ️"
        
        if "❌" in content or "FAILED" in content or "failed" in content or "error" in content or "Error" in content:
            level = "ERROR"
            icon = "❌"
        elif "⚠️" in content or "WARNING" in content or "warning" in content or "Warning" in content:
            level = "WARNING"
            icon = "⚠️"
        elif "✅" in content or "SUCCESS" in content or "success" in content or "complete" in content or "Generated" in content:
            level = "SUCCESS"
            icon = "✅"
        
        # Check if this is about tile processing
        is_tile_processing = False
        tile_name = ""
        if "Analyzing" in content and "tile" in content:
            is_tile_processing = True
            # Try to extract tile name
            match = re.search(r"Analyzing (?:content|legend) tile ([^\s]+)", content)
            if match:
                tile_name = match.group(1)
        
        # Check if this contains API information
        api_info = None
        if "HTTP/1.1 200 OK" in content or "API" in content:
            api_info = {
                "success": "HTTP/1.1 200 OK" in content,
                "message": content
            }
        
        return {
            "timestamp": timestamp,
            "message": content,
            "level": level,
            "icon": icon,
            "is_tile_processing": is_tile_processing,
            "tile_name": tile_name,
            "api_info": api_info
        }
    except Exception as e:
        logger.error(f"Error parsing log message: {e}")
        return {
            "timestamp": "",
            "message": message,
            "level": "INFO",
            "icon": "ℹ️",
            "is_tile_processing": False,
            "tile_name": "",
            "api_info": None
        }

def highlight_tile_numbers(message: str) -> str:
    """Highlight tile numbers and processing information in messages."""
    # Highlight "tile X of Y" patterns
    highlighted = re.sub(
        r'(tile\s+\d+\s+of\s+\d+)', 
        r'<span style="color: #FFD700; font-weight: bold;">\1</span>', 
        message
    )
    
    # Highlight specific tile names
    highlighted = re.sub(
        r'(tile_\d+\.png|tile_\w+\.png)', 
        r'<span style="color: #00BFFF; font-weight: bold;">\1</span>', 
        highlighted
    )
    
    # Highlight API response codes
    highlighted = re.sub(
        r'(HTTP/1\.1\s+200\s+OK)', 
        r'<span style="color: #00FF00;">\1</span>', 
        highlighted
    )
    
    # Highlight API errors
    highlighted = re.sub(
        r'(API\s+error|Rate\s+limited|Timeout)', 
        r'<span style="color: #FF6B6B; font-weight: bold;">\1</span>', 
        highlighted
    )
    
    return highlighted

def log_console(messages: List[str], max_height: int = 400, auto_scroll: bool = True, highlight_tiles: bool = True):
    """
    Display a terminal-like console for log messages with enhanced tile processing visualization.
    
    Args:
        messages: List of log messages to display
        max_height: Maximum height of the console in pixels
        auto_scroll: Whether to automatically scroll to the latest messages
        highlight_tiles: Whether to highlight tile-related information
    """
    if not messages:
        st.info("No log messages available.")
        return
    
    # Create a container with fixed height and scrollbar
    log_container = st.container(border=True)
    
    # Set CSS for console-like appearance
    css = f"""
    <style>
        .log-console {{
            background-color: #0E1117;
            color: #E0E0E0;
            font-family: 'Courier New', monospace;
            padding: 10px;
            border-radius: 5px;
            overflow-y: auto;
            max-height: {max_height}px;
        }}
        .log-entry {{
            margin: 0;
            padding: 2px 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .log-timestamp {{
            color: #888888;
            margin-right: 8px;
        }}
        .log-info {{
            color: #E0E0E0;
        }}
        .log-warning {{
            color: #FFA500;
        }}
        .log-error {{
            color: #FF6B6B;
        }}
        .log-success {{
            color: #4CAF50;
        }}
        .log-tile {{
            color: #00BFFF;
            font-weight: bold;
        }}
        .log-api-success {{
            color: #4CAF50;
        }}
        .log-api-error {{
            color: #FF6B6B;
        }}
    </style>
    """
    
    # Start building HTML content
    html_content = f"{css}<div class='log-console'>"
    
    # Count of tile processing entries
    tile_processing_count = 0
    api_call_count = 0
    api_error_count = 0
    
    # Process messages
    for message in messages:
        parsed = parse_log_message(message)
        
        # Format the log entry
        css_class = f"log-{parsed['level'].lower()}"
        if css_class == "log-success":
            # For compatibility - success isn't a standard level
            css_class = "log-success"
        
        # Highlight tile information if enabled
        display_message = parsed['message']
        if highlight_tiles:
            display_message = highlight_tile_numbers(display_message)
        
        # Track tile processing
        if parsed['is_tile_processing']:
            tile_processing_count += 1
        
        # Track API calls
        if parsed['api_info']:
            if parsed['api_info']['success']:
                api_call_count += 1
            else:
                api_error_count += 1
        
        html_content += f"""
        <div class='log-entry {css_class}'>
            <span class='log-timestamp'>{parsed['timestamp']}</span>
            <span class='{css_class}'>{parsed['icon']} {display_message}</span>
        </div>
        """
    
    # Close the container
    html_content += "</div>"
    
    # Add JavaScript for auto-scrolling if enabled
    if auto_scroll and messages:
        html_content += """
        <script>
            // Auto-scroll to bottom
            (function() {
                const logConsole = document.querySelector('.log-console');
                if (logConsole) {
                    logConsole.scrollTop = logConsole.scrollHeight;
                }
            })();
        </script>
        """
    
    # Display the HTML
    with log_container:
        st.markdown(html_content, unsafe_allow_html=True)
        
        # Add control bar below the console
        cols = st.columns([1, 1, 1])
        
        with cols[0]:
            if st.button("Copy Logs", key="copy_logs_button"):
                # Use streamlit.markdown to create the copy to clipboard functionality
                # Join all messages with newlines
                text_to_copy = "\n".join(messages)
                st.markdown(
                    f"""
                    <textarea id="copy-text" style="opacity:0;position:absolute;z-index:-1;">{text_to_copy}</textarea>
                    <script>
                        // Copy text to clipboard
                        const copyText = document.getElementById('copy-text');
                        copyText.select();
                        document.execCommand('copy');
                        // Show success using toast notification
                        window.parent.postMessage({{
                            type: 'streamlit:showToast',
                            message: 'Logs copied to clipboard!',
                            kind: 'success'
                        }}, '*');
                    </script>
                    """,
                    unsafe_allow_html=True
                )
        
        with cols[1]:
            # Show tile processing statistics if available
            if tile_processing_count > 0:
                st.caption(f"Tile processing entries: {tile_processing_count}")
        
        with cols[2]:
            # Show API call statistics if available
            if api_call_count > 0 or api_error_count > 0:
                api_text = f"API calls: {api_call_count}"
                if api_error_count > 0:
                    api_text += f" (Errors: {api_error_count})"
                st.caption(api_text)
            else:
                st.caption(f"Total: {len(messages)} log entries")

def extract_user_friendly_logs(messages: List[str]) -> List[str]:
    """
    Extract user-friendly log messages from technical logs.
    Focus on tile processing and major phase transitions.
    """
    user_friendly = []
    seen_phases = set()
    tile_count = 0
    total_tiles = 0
    
    for message in messages:
        parsed = parse_log_message(message)
        content = parsed['message']
        
        # Major phase transitions
        if "PHASE" in content or "Phase" in content:
            phase_match = re.search(r"(?:PHASE|Phase)(?::|:?\s+)(.+)", content)
            if phase_match:
                phase = phase_match.group(1).strip()
                if phase not in seen_phases:
                    seen_phases.add(phase)
                    user_friendly.append(f"📋 Starting phase: {phase}")
        
        # Tile generation
        elif "Generated" in content and "tiles" in content:
            match = re.search(r"Generated (\d+) tiles", content)
            if match:
                total_tiles = int(match.group(1))
                user_friendly.append(f"🖼️ Generated {total_tiles} tiles for processing")
        
        # Tile processing
        elif parsed['is_tile_processing']:
            tile_count += 1
            # Only report every 5th tile to avoid flooding
            if tile_count % 5 == 0 or tile_count == total_tiles:
                progress = f"{tile_count}/{total_tiles}" if total_tiles > 0 else f"{tile_count}"
                user_friendly.append(f"🔍 Processing tile {progress} ({parsed['tile_name']})")
        
        # API errors
        elif "API error" in content or "Rate limited" in content:
            user_friendly.append(f"⚠️ API issue detected (automatic retry in progress)")
        
        # Completion
        elif "completed successfully" in content or "Processing complete" in content:
            user_friendly.append(f"✅ Processing completed successfully")
        
        # Failures
        elif "failed" in content.lower() or "error" in content.lower():
            user_friendly.append(f"❌ Processing issue: {content}")
    
    return user_friendly

# Example usage:
if __name__ == "__main__":
    # This code runs when the component is run directly for testing
    st.title("Log Console Test")
    
    # Sample log messages
    sample_logs = [
        "2023-06-15T14:30:25.123Z - 🚀 Starting processing",
        "2023-06-15T14:30:26.234Z - 📄 Converting PDF to image",
        "2023-06-15T14:30:30.456Z - ⚠️ Warning: Large file detected",
        "2023-06-15T14:30:35.789Z - 🖼️ Created 25 tiles successfully",
        "2023-06-15T14:30:40.123Z - Analyzing content tile tmpj9sx01n0_tile_015.png",
        "2023-06-15T14:30:40.456Z - HTTP/1.1 200 OK",
        "2023-06-15T14:30:45.456Z - Analyzing content tile tmpj9sx01n0_tile_016.png (5 of 25)",
        "2023-06-15T14:30:50.789Z - ❌ Error: API error during analysis",
        "2023-06-15T14:30:55.123Z - Retrying API call in 2.5s",
        "2023-06-15T14:31:00.456Z - ✅ Processing completed successfully",
    ]
    
    # Demo controls
    st.subheader("Demo Controls")
    auto_scroll = st.checkbox("Auto-scroll", value=True)
    highlight = st.checkbox("Highlight Tile Information", value=True)
    max_height = st.slider("Console Height", min_value=100, max_value=800, value=400, step=50)
    
    tab1, tab2 = st.tabs(["Technical Logs", "User-Friendly Logs"])
    
    with tab1:
        st.subheader("Technical Log Console")
        log_console(sample_logs, max_height=max_height, auto_scroll=auto_scroll, highlight_tiles=highlight)
    
    with tab2:
        st.subheader("User-Friendly Logs")
        user_logs = extract_user_friendly_logs(sample_logs)
        for log in user_logs:
            st.info(log)
