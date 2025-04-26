# --- Filename: components/query_box.py (Revised) ---
import streamlit as st
def query_box(disabled=False):
    """
    Render a professional query input box that doesn't require Control+Enter.
    
    Parameters:
        disabled (bool): Whether the text area should be disabled
    
    Returns:
        str: The query text
    """
    # Use a container for styling
    with st.container():
        # Form for query submission
        with st.form(key="query_form", clear_on_submit=False):
            # Get existing query from session state
            current_query = st.session_state.get("query", "")
            
            # Text area for query
            query = st.text_area(
                "Type your question here...",
                value=current_query,
                height=120,
                disabled=disabled,
                placeholder="Example: What are the finishes specified for the private offices?",
                key="query_input"
            )
            
            # Submit button
            submit = st.form_submit_button(
                "Analyze Drawings", 
                type="primary",
                use_container_width=True,
                disabled=disabled
            )
            
            # Store in session state regardless of submission
            st.session_state.query = query
            
            # Return query if submitted, otherwise return existing query
            if submit:
                return query
            else:
                return current_query
