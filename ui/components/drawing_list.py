# --- Filename: components/drawing_list.py ---

import streamlit as st
import re

def drawing_list(drawings):
    """
    Render a 'Select All' toggle and a checkbox per drawing.
    Returns the list of selected drawing names.
    """
    st.subheader("Available Drawings")
    select_all = st.checkbox("Select All Drawings", key="select_all")
    selected = []
    if select_all:
        # Show all checked and disabled so user can't uncheck individually
        for drawing in drawings:
            st.checkbox(drawing, value=True, key=f"cb_{drawing}", disabled=True)
        selected = drawings.copy()
    else:
        for drawing in drawings:
            if st.checkbox(drawing, key=f"cb_{drawing}"):
                selected.append(drawing)
    
    # Display count of available drawings
    st.caption(f"Showing {len(drawings)} processed drawing(s)")
    
    # Instructions if needed
    if not selected:
        st.caption("Select drawings to analyze or delete")
    
    return selected
