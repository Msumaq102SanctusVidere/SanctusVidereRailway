# --- Filename: components/drawing_list.py ---

import streamlit as st
import re

def drawing_list(drawings):
    """
    Render a 'Select All' toggle and a checkbox per drawing.
    Returns the list of selected drawing names.
    """
    st.subheader("Available Drawings")
    
    # Option to show/hide temporary files
    show_temp_files = st.checkbox("Show Temporary Files", value=False, key="show_temp_files")
    
    # Filter out temporary files if not showing them
    if not show_temp_files:
        # Filter out drawings that start with "tmp"
        filtered_drawings = [d for d in drawings if not d.startswith("tmp")]
    else:
        filtered_drawings = drawings
    
    # No drawings after filtering
    if not filtered_drawings:
        st.info("No drawings available. Upload a drawing to get started.")
        return []
    
    # Selection logic
    select_all = st.checkbox("Select All Drawings", key="select_all")
    selected = []
    
    if select_all:
        # Show all checked and disabled so user can't uncheck individually
        for drawing in filtered_drawings:
            st.checkbox(drawing, value=True, key=f"cb_{drawing}", disabled=True)
        selected = filtered_drawings.copy()
    else:
        for drawing in filtered_drawings:
            if st.checkbox(drawing, key=f"cb_{drawing}"):
                selected.append(drawing)
    
    # Display count of available drawings
    total_count = len(drawings)
    filtered_count = len(filtered_drawings)
    
    if total_count != filtered_count and not show_temp_files:
        st.caption(f"Showing {filtered_count} of {total_count} drawings (filtering temporary files)")
    else:
        st.caption(f"Showing {filtered_count} drawing(s)")
    
    # Instructions if needed
    if not selected:
        st.caption("Select drawings to analyze or delete")
    
    return selected
