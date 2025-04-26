# --- Filename: ui/components/log_console.py (Log Console Component) ---

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
        elif "✅" in content or "SUCCESS" in content or "success" in content or "complete" in content:
            level = "SUCCESS"
            icon = "✅"
            
        return {
            "timestamp": timestamp,
            "message": content,
            "level": level,
            "icon": icon
        }
    except Exception as e:
        logger.error(f"Error parsing log message: {e}")
        return {
            "timestamp": "",
            "message": message,
            "level": "INFO",
            "icon": "ℹ️"
        }

def log_console(messages: List[str], max_height: int = 400, auto_scroll: bool = True):
    """
    Display a terminal-like console for log messages.
    
    Args:
        messages: List of log messages to display
        max_height: Maximum height of the console in pixels
        auto_scroll: Whether to automatically scroll to the latest messages
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
    </style>
    """
    
    # Start building HTML content
    html_content = f"{css}<div class='log-console'>"
    
    # Process messages
    for message in messages:
        parsed = parse_log_message(message)
        
        # Format the log entry
        css_class = f"log-{parsed['level'].lower()}"
        if css_class == "log-success":
            # For compatibility - success isn't a standard level
            css_class = "log-success"
            
        html_content += f"""
        <div class='log-entry {css_class}'>
            <span class='log-timestamp'>{parsed['timestamp']}</span>
            <span class='{css_class}'>{parsed['icon']} {parsed['message']}</span>
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
        
        # Add controls below the console
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
        
        with cols[2]:
            st.caption(f"Total: {len(messages)} log entries")

def format_log_entry(message: str) -> str:
    """Format a log entry for better readability."""
    # This can be expanded to add colors, formatting, etc.
    return message

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
        "2023-06-15T14:30:40.123Z - ❌ Error: Failed to analyze tile 15",
        "2023-06-15T14:30:45.456Z - 🔍 Analyzing content (25%)",
        "2023-06-15T14:30:50.789Z - 🔍 Analyzing content (50%)",
        "2023-06-15T14:30:55.123Z - 🔍 Analyzing content (75%)",
        "2023-06-15T14:31:00.456Z - ✅ Processing completed successfully",
    ]
    
    # Demo controls
    st.subheader("Demo Controls")
    auto_scroll = st.checkbox("Auto-scroll", value=True)
    max_height = st.slider("Console Height", min_value=100, max_value=800, value=400, step=50)
    
    # Display the log console
    st.subheader("Log Console")
    log_console(sample_logs, max_height=max_height, auto_scroll=auto_scroll)
