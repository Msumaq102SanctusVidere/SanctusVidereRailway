# --- Filename: components/log_console.py ---

import streamlit as st
import re

def log_console(logs):
    """
    Renders a console-like display of log messages.
    
    Args:
        logs (list): List of log message strings
    """
    if not logs:
        st.text("No log messages available.")
        return
    
    # Clean any HTML tags from logs
    clean_logs = []
    for log in logs:
        # Use regex to remove HTML tags if present
        clean_log = re.sub(r'<[^>]+>', '', log)
        clean_logs.append(clean_log)
    
    # Display logs in a code block for a console-like appearance
    log_text = "\n".join(clean_logs[-5:])  # Show only the 5 most recent logs
    st.code(log_text, language="")
