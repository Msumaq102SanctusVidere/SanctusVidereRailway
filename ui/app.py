import streamlit as st

from api_client import health_check, get_drawings, start_analysis
from components.upload_drawing import upload_drawing_component
from components.drawing_list import drawing_list
from components.query_box import query_box
from components.control_row import control_row
from components.progress_bar import progress_indicator
from components.results_pane import results_pane

def main():
    # Page setup
    st.set_page_config(
        page_title="Sanctus Videre 1.0",
        layout="wide",
        page_icon="🏗️"
    )

    # Title and subheading
    st.markdown(
        """
        <h1 style='font-family:Orbitron; color:#00ffcc;'>Sanctus Videre 1.0</h1>
        <h4 style='font-family:Orbitron; color:#00ffcc;'>Visionary Construction Insights</h4>
        """,
        unsafe_allow_html=True
    )

    # Verify backend health
    status = health_check().get("status", "")
    if status != "healthy":
        st.error("🚨 API is not responding. Please check your backend.")
        st.stop()

    # Initial fetch of available drawings
    drawings = get_drawings()

    # Sidebar upload widget; refresh if a new drawing is added
    with st.sidebar:
        if upload_drawing_component():
            drawings = get_drawings()

    # Two-column layout: left for drawings, right for query/controls/results
    col1, col2 = st.columns([1, 3])

    with col1:
        selected_drawings = drawing_list(drawings)

    with col2:
        # Query input
        query = query_box()

        # Controls row
        force_new, analyze_clicked, stop_clicked = control_row()

        # Handle the Analyze button
        if analyze_clicked:
            if not selected_drawings:
                st.warning("Please select at least one drawing to analyze.")
            elif not query:
                st.warning("Please enter a query before analyzing.")
            else:
                st.info("🚀 Starting analysis...")
                resp = start_analysis(query, selected_drawings, use_cache=not force_new)
                job_id = resp.get("job_id")
                if job_id:
                    # Show live progress, then results
                    job = progress_indicator(job_id)
                    results_pane(job.get("result", "No result returned."))
                else:
                    st.error(f"Failed to start analysis: {resp.get('error', 'Unknown error')}")

        # Handle the Stop button (placeholder)
        if stop_clicked:
            st.warning("Stopping analysis…")

if __name__ == "__main__":
    main()
