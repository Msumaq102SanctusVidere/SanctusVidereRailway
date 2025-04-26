import streamlit as st
def results_pane(result_text):
    """
    Render the analysis results in a clean, professional dedicated window.
    
    Parameters:
        result_text (str): The JSON-formatted result from the analysis job
    """
    try:
        # Try to parse JSON
        import json
        result_obj = json.loads(result_text)
        
        # Extract analysis text
        if isinstance(result_obj, dict):
            if 'analysis' in result_obj:
                analysis_text = result_obj['analysis']
                
                # Display in a clean, bordered container
                with st.container(border=True):
                    st.markdown(analysis_text)
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_results"):
                        # This doesn't actually copy to clipboard (Streamlit limitation)
                        # but indicates to user they should copy the text
                        st.success("Results ready to copy!")
                
                # Technical information in an expandable section 
                # that's collapsed by default
                with st.expander("Technical Information", expanded=False):
                    st.json(result_obj)
                
                return
            
            # Handle batch structure if no direct analysis field
            if 'batches' in result_obj and isinstance(result_obj['batches'], list):
                for batch in result_obj['batches']:
                    if isinstance(batch, dict) and 'result' in batch and 'analysis' in batch['result']:
                        analysis_text = batch['result']['analysis']
                        
                        # Display in a clean, bordered container
                        with st.container(border=True):
                            st.markdown(analysis_text)
                            
                            # Add a copy button
                            if st.button("Copy Results", key="copy_results"):
                                st.success("Results ready to copy!")
                        
                        # Technical information in a collapsed expandable section
                        with st.expander("Technical Information", expanded=False):
                            st.json(result_obj)
                        
                        return
        
        # Fallback to showing the raw result
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
