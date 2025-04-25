# --- Filename: components/query_box.py (Revised) ---
import streamlit as st

def query_box(disabled=False): # <-- Add disabled parameter with default False
    """
    Render a multi-line text input for the user’s question.
    Accepts a 'disabled' flag to disable the input.
    Returns the entered query string.
    """
    # Subheader can remain enabled
    st.subheader("Query")

    query = st.text_area(
        label="Type your question here…",
        height=100,
        placeholder="e.g. What are the finishes specified for room 101?",
        disabled=disabled # <-- Pass the disabled state to the text_area
    )
    return query.strip()
