import streamlit as st

def results_pane(result_text):
    """
    Render the analysis results in a scrollable text area.
    
    Parameters:
        result_text (str): The JSON-formatted result from the analysis job
    """
    try:
        # Try to parse JSON
        import json
        result_obj = json.loads(result_text)
        
        # If the result contains the 'analysis' field, use that
        if isinstance(result_obj, dict) and 'analysis' in result_obj:
            analysis_text = result_obj['analysis']
            st.text_area(
                label="",
                value=analysis_text,
                height=400,
                placeholder="Results will appear here after analysis completes...",
                disabled=False  # Allow copying text
            )
        else:
            # Fallback to showing full result object
            st.text_area(
                label="",
                value=result_text,
                height=400,
                placeholder="Results will appear here after analysis completes...",
                disabled=False  # Allow copying text
            )
            st.caption("Note: No structured analysis data found. Showing raw response.")
    except (json.JSONDecodeError, TypeError):
        # If it's not valid JSON, just display as-is
        st.text_area(
            label="",
            value=result_text,
            height=400,
            placeholder="Results will appear here after analysis completes...",
            disabled=False  # Allow copying text
        )
