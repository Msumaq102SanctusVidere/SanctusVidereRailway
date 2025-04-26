# --- Filename: components/query_box.py (Revised) ---
import streamlit as st
def query_box(disabled=False):
    """
    Render a text area for entering a query with automatic submission.
    
    Parameters:
        disabled (bool): Whether the text area should be disabled
    
    Returns:
        str: The query text
    """
    # Use a form to make submission easier
    with st.form(key="query_form"):
        query = st.text_area(
            "Type your question here...",
            value=st.session_state.get("query", ""),
            height=120,
            disabled=disabled,
            placeholder="Example: What are the finishes specified for the private offices?"
        )
        
        # Add a submit button inside the form
        submit_button = st.form_submit_button(
            "Submit Query", 
            type="primary",
            use_container_width=True,
            disabled=disabled
        )
    
    # Update session state
    if query != st.session_state.get("query", ""):
        st.session_state.query = query
    
    return query

