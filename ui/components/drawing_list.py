# --- Filename: components/drawing_list.py ---

import streamlit as st
import re
import os
import json
from pathlib import Path
import logging

# Set up logging
logger = logging.getLogger(__name__)

def verify_drawing_is_processed(drawing_name, drawings_dir):
    """
    Verify that a drawing has been completely processed by checking for required files.
    
    Args:
        drawing_name: Name of the drawing to verify
        drawings_dir: Path to the drawings directory
        
    Returns:
        tuple: (is_processed, display_name)
            - is_processed: Boolean indicating if drawing is fully processed
            - display_name: A user-friendly display name for the drawing
    """
    try:
        # Build path to drawing directory
        drawing_dir = Path(drawings_dir) / drawing_name
        if not drawing_dir.is_dir():
            return False, drawing_name
        
        # Check for essential files
        required_files = [
            f"{drawing_name}_tile_metadata.json",
            f"{drawing_name}_tile_analysis.json",
            f"{drawing_name}_legend_knowledge.json"
        ]
        
        # At least one of these specialized analysis files should exist
        optional_files = [
            f"{drawing_name}_general_notes_analysis.json",
            f"{drawing_name}_elevation_analysis.json",
            f"{drawing_name}_detail_analysis.json"
        ]
        
        # Check required files
        for req_file in required_files:
            if not (drawing_dir / req_file).exists():
                return False, drawing_name
        
        # Check that at least one optional file exists
        has_optional = any((drawing_dir / opt_file).exists() for opt_file in optional_files)
        if not has_optional:
            return False, drawing_name
        
        # Get a better display name from metadata if possible
        display_name = get_display_name_from_metadata(drawing_dir, drawing_name)
        
        return True, display_name
    except Exception as e:
        logger.error(f"Error verifying drawing {drawing_name}: {e}")
        return False, drawing_name

def get_display_name_from_metadata(drawing_dir, drawing_name):
    """
    Extract a user-friendly display name from the drawing metadata.
    
    Args:
        drawing_dir: Path to the drawing directory
        drawing_name: Current drawing name (fallback)
        
    Returns:
        str: A user-friendly display name
    """
    try:
        # Try to get metadata file
        metadata_file = drawing_dir / f"{drawing_name}_tile_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                
                # Check if drawing_info with title exists
                if "drawing_info" in metadata and "title" in metadata["drawing_info"]:
                    return metadata["drawing_info"]["title"]
                
                # Look for original_filename in metadata
                if "original_filename" in metadata:
                    orig = metadata["original_filename"]
                    # Remove extension
                    orig = re.sub(r'\.pdf$', '', orig, flags=re.IGNORECASE)
                    return orig
        
        # Format the tmp filename if no metadata is available
        if re.match(r'^tmp[a-zA-Z0-9]+$', drawing_name):
            return f"Drawing {drawing_name[-5:]}"  # Last 5 chars for uniqueness
            
        # Format existing name if it looks like a descriptive filename
        if "_" in drawing_name:
            # Replace underscores with spaces and capitalize words
            return " ".join(word.capitalize() for word in drawing_name.split("_"))
            
        return drawing_name
    except Exception as e:
        logger.error(f"Error getting display name for {drawing_name}: {e}")
        return drawing_name

def drawing_list(drawings, drawings_dir=None):
    """
    Render a 'Select All' toggle and a checkbox per drawing.
    Only displays fully processed drawings with improved display names.
    
    Args:
        drawings: List of drawing names/IDs
        drawings_dir: Path to the drawings directory (optional)
        
    Returns:
        list: Names of selected drawings
    """
    # Check if drawings_dir is provided, otherwise try to determine it
    if not drawings_dir:
        # Try to get it from environment or use a default
        drawings_dir = os.environ.get("DRAWINGS_DIR", "/app/tiles_output")
    
    st.subheader("Available Drawings")
    
    # Filter and get display names for processed drawings
    processed_drawings = []
    display_names = {}
    original_names = {}  # Keep mapping of display names back to original names
    
    for drawing in drawings:
        is_processed, display_name = verify_drawing_is_processed(drawing, drawings_dir)
        if is_processed:
            processed_drawings.append(drawing)
            display_names[drawing] = display_name
            original_names[display_name] = drawing
    
    # Show message if no processed drawings
    if not processed_drawings:
        st.info("No processed drawings available. Upload a drawing to get started.")
        return []
    
    # Checkboxes for drawing selection
    select_all = st.checkbox("Select All Drawings", key="select_all")
    selected = []
    
    if select_all:
        # Show all checked and disabled so user can't uncheck individually
        for drawing in processed_drawings:
            st.checkbox(display_names[drawing], value=True, 
                        key=f"cb_{drawing}", disabled=True)
        selected = processed_drawings.copy()
    else:
        for drawing in processed_drawings:
            if st.checkbox(display_names[drawing], key=f"cb_{drawing}"):
                selected.append(drawing)
    
    # Display count of available drawings
    st.caption(f"Showing {len(processed_drawings)} processed drawing(s)")
    
    # Instructions if needed
    if not selected:
        st.caption("Select drawings to analyze or delete")
    
    return selected

# For testing
if __name__ == "__main__":
    st.title("Drawing List Test")
    
    # Sample drawings
    test_drawings = [
        "tmpj9sx01n0",
        "A2.3.2_OVERALL_THIRD_FLOOR_FINISH_PLAN_Rev.3",
        "tmpg9hpgyms"
    ]
    
    # Call the function
    selected = drawing_list(test_drawings)
    
    # Show result
    st.write("Selected drawings:", selected)
