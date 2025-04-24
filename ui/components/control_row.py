import streamlit as st

def control_row():
    """
    Render:
      - A 'Force new analysis' checkbox
      - An 'Analyze Drawings' button
      - A 'Stop Analysis' button

    Returns:
      force_new (bool), analyze_clicked (bool), stop_clicked (bool)
    """
    st.subheader("Controls")

    # Checkbox to ignore cache if checked
    force_new = st.checkbox(
        "Force new analysis (ignore cache)",
        key="force_new"
    )

    # Place buttons side by side
    col_analysis, col_stop = st.columns(2)
    with col_analysis:
        analyze_clicked = st.button(
            "Analyze Drawings",
            key="analyze"
        )
    with col_stop:
        stop_clicked = st.button(
            "Stop Analysis",
            key="stop"
        )

    return force_new, analyze_clicked, stop_clicked
