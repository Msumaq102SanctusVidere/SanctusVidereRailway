# --- Filename: components/control_row.py (Revised) ---
import streamlit as st

def control_row(disabled=False): # <-- Add disabled parameter with default False
    """
    Render:
      - A 'Force new analysis' checkbox
      - An 'Analyze Drawings' button
      - A 'Stop Analysis' button
    Accepts a 'disabled' flag to disable all controls.

    Returns:
      force_new (bool), analyze_clicked (bool), stop_clicked (bool)
    """
    # Subheader can remain enabled
    st.subheader("Controls")

    # Checkbox to ignore cache if checked
    force_new = st.checkbox(
        "Force new analysis (ignore cache)",
        key="force_new",
        disabled=disabled # <-- Pass disabled state to checkbox
    )

    # Place buttons side by side
    col_analysis, col_stop = st.columns(2)
    with col_analysis:
        analyze_clicked = st.button(
            "Analyze Drawings",
            key="analyze",
            disabled=disabled # <-- Pass disabled state to button
        )
    with col_stop:
        stop_clicked = st.button(
            "Stop Analysis",
            key="stop",
            disabled=disabled # <-- Pass disabled state to button
        )

    return force_new, analyze_clicked, stop_clicked
