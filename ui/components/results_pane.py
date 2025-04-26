import streamlit as st

def results_pane(result_text):
    """
    Render the analysis results in a clean, professional scrollable text area.
    
    Parameters:
        result_text (str): The JSON-formatted result from the analysis job
    """
    try:
        # Try to parse JSON
        import json
        result_obj = json.loads(result_text)
        
        # Check for analysis field in the result object
        if isinstance(result_obj, dict):
            if 'analysis' in result_obj:
                # Direct analysis field
                analysis_text = result_obj['analysis']
                st.text_area(
                    label="",
                    value=analysis_text,
                    height=400,
                    key="results_text_area"
                )
            elif 'batches' in result_obj and isinstance(result_obj['batches'], list):
                # Handle batch structure - extract from last batch
                batches = result_obj['batches']
                if batches and 'result' in batches[-1] and 'analysis' in batches[-1]['result']:
                    analysis_text = batches[-1]['result']['analysis']
                    st.text_area(
                        label="",
                        value=analysis_text,
                        height=400,
                        key="results_text_area"
                    )
                else:
                    # No analysis found in batch structure
                    st.info("No analysis content found in job results.")
                    st.json(result_obj)
            else:
                # No analysis field found, show the raw result
                st.info("No structured analysis data found. Showing raw job results.")
                st.json(result_obj)
        else:
            # Not a dict, so just show as-is
            st.text_area(
                label="",
                value=result_text,
                height=400,
                key="results_text_area"
            )
    except (json.JSONDecodeError, TypeError):
        # If not valid JSON, just display as-is
        st.text_area(
            label="",
            value=result_text,
            height=400,
            key="results_text_area"
        )
