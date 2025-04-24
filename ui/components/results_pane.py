import streamlit as st

def results_pane(result_text):
    """
    Render the analysis results in a scrollable text area.
    """
    st.subheader("Analysis Results")
    st.text_area(
        label="",
        value=result_text,
        height=400,
        placeholder="Results will appear here after analysis completes..."
    )
