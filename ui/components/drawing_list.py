# --- Filename: components/drawing_list.py ---

import streamlit as st
import re

def drawing_list(drawings):
    """
    Render a 'Select All' toggle and a checkbox per drawing.
    Only displays properly named drawings, hiding temporary files.
    Returns the list of selected drawing names.
    """
    st.subheader("Available Drawings")
    
    # Filter out temporary files
    filtered_drawings = [d for d in drawings if not re.match(r'^tmp[a-zA-Z0-9]+$', d)]
    
    # No drawings after filtering
    if not filtered_drawings:
        st.info("No processed drawings available. Upload a drawing to get started.")
        return []
    
    # Selection logic for filtered drawings
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
    st.caption(f"Showing {len(filtered_drawings)} processed drawing(s)")
    
    # Instructions if needed
    if not selected:
        st.caption("Select drawings to analyze or delete")
    
    return selected
