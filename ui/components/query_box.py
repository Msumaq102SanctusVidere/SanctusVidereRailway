import streamlit as st

def query_box():
    """
    Render a multi-line text input for the user’s question.
    Returns the entered query string.
    """
    st.subheader("Query")
    query = st.text_area(
        label="Type your question here…",
        height=100,
        placeholder="e.g. What are the finishes specified for room 101?"
    )
    return query.strip()
