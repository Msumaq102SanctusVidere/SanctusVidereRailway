# --- Filename: components/query_box.py ---

import streamlit as st

def query_box(empty_disabled=False, remove_analyze_button=False):
    """
    Renders a text area for entering queries about drawings.
    
    Args:
        empty_disabled (bool): If True, disables the analyze button when query is empty
        remove_analyze_button (bool): If True, doesn't render the Analyze button
        
    Returns:
        str: The query text entered by the user
    """
    # Get current query from session state, defaulting to empty string
    current_query = st.session_state.get('query', '')
    
    # Create text area for query input
    query = st.text_area(
        "Type your question here...",
        value=current_query,
        height=150,
        placeholder="Example: What are the finishes specified for the private offices?"
    )
    
    # Only render the Analyze button if not specifically asked to remove it
    if not remove_analyze_button:
        # Determine if the button should be disabled
        disabled = empty_disabled and not query.strip()
        
        # Create the analyze button
        if st.button("Analyze Drawings", disabled=disabled, key="query_analyze_btn"):
            pass  # The main app handles the button click
    
    return query
