# --- Filename: components/drawing_list.py ---

import streamlit as st
import os
import logging
from pathlib import Path
import urllib.parse

# Set up logging
logger = logging.getLogger(__name__)

def is_fully_processed(drawing_name, drawings_dir):
    """
    Check if a drawing is fully processed by verifying its file structure.
    
    Args:
        drawing_name: Name of the drawing to check
        drawings_dir: Directory containing drawing folders
        
    Returns:
        bool: True if drawing is fully processed, False otherwise
    """
    try:
        # Build path to drawing directory
        drawing_dir = Path(drawings_dir) / drawing_name
        
        # Check if directory exists
        if not drawing_dir.is_dir():
            logger.info(f"Drawing directory not found: {drawing_dir}")
            return False
        
        # Check for essential files
        required_files = [
            f"{drawing_name}_tile_metadata.json",
            f"{drawing_name}_tile_analysis.json",
            f"{drawing_name}_legend_knowledge.json"
        ]
        
        for req_file in required_files:
            if not (drawing_dir / req_file).exists():
                logger.info(f"Missing required file for {drawing_name}: {req_file}")
                return False
        
        # If all required files exist, consider it fully processed
        return True
        
    except Exception as e:
        logger.error(f"Error checking if drawing {drawing_name} is processed: {e}")
        return False

def drawing_list(drawings):
    """
    Render a 'Select All' toggle and a checkbox per drawing.
    Only displays fully processed drawings by checking file structure.
    Returns the list of selected drawing names.
    """
    st.subheader("Available Drawings")
    
    # Get the directory where drawing files are stored
    # Try environment variable first, then fallback to default
    drawings_dir = os.environ.get('DRAWINGS_DIR', '/app/tiles_output')
    
    # Filter out drawings that are not fully processed
    processed_drawings = []
    for drawing in drawings:
        if is_fully_processed(drawing, drawings_dir):
            processed_drawings.append(drawing)
        else:
            logger.info(f"Drawing {drawing} filtered out - not fully processed")
    
    # No drawings after filtering
    if not processed_drawings:
        st.info("No processed drawings available. Upload a drawing to get started.")
        return []
    
    # Selection logic for filtered drawings
    select_all = st.checkbox("Select All Drawings", key="select_all")
    selected = []
    
    if select_all:
        # Show all checked and disabled so user can't uncheck individually
        for drawing in processed_drawings:
            st.checkbox(drawing, value=True, key=f"cb_{drawing}", disabled=True)
        selected = processed_drawings.copy()
    else:
        for drawing in processed_drawings:
            if st.checkbox(drawing, key=f"cb_{drawing}"):
                selected.append(drawing)
    
    # Display count of available drawings
    st.caption(f"Showing {len(processed_drawings)} processed drawing(s)")
    
    # Add delete buttons for each selected drawing
    if selected:
        st.divider()
        for drawing in selected:
            # URL encode the drawing name to handle special characters
            # This fixes the 404 error when deleting drawings with special characters
            encoded_drawing = urllib.parse.quote(drawing)
            
            if st.button(f"🗑️ Delete '{drawing}'", key=f"delete_{drawing}"):
                # Store the encoded version in session state for the delete operation
                st.session_state.drawing_to_delete = drawing
                st.rerun()
    else:
        st.caption("Select drawings to analyze or delete")
    
    return selected
