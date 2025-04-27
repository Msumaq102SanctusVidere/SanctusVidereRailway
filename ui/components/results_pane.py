import streamlit as st
import json

def results_pane(result_text):
    """
    Render the analysis results in a clean, professional dedicated window.
    
    Parameters:
        result_text (str): The JSON-formatted result from the analysis job
    """
    # Handle None or empty results
    if result_text is None or result_text == "":
        st.warning("No results data available. Try clicking 'Show Results' again.")
        return
        
    try:
        # Try to parse JSON
        result_obj = json.loads(result_text)
        
        # Debug info
        st.markdown("---")
        st.markdown("### Analysis Results")
        
        # Extract analysis text
        if isinstance(result_obj, dict):
            if 'analysis' in result_obj:
                analysis_text = result_obj['analysis']
                
                # Display in a clean, bordered container
                with st.container(border=True):
                    st.markdown(analysis_text)
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_results_main"):
                        # We'll use st.code for better clipboard support
                        st.code(analysis_text, language=None)
                        st.success("Results ready to copy! Use the copy button in the top-right of the code block above.")
                
                # Technical information in an expandable section 
                # that's collapsed by default
                with st.expander("Technical Information", expanded=False):
                    st.json(result_obj)
                
                return
            
            # Handle batch structure if no direct analysis field
            if 'batches' in result_obj and isinstance(result_obj['batches'], list):
                for i, batch in enumerate(result_obj['batches']):
                    if isinstance(batch, dict) and 'result' in batch and 'analysis' in batch['result']:
                        analysis_text = batch['result']['analysis']
                        
                        # Display in a clean, bordered container
                        with st.container(border=True):
                            st.markdown(analysis_text)
                            
                            # Add a copy button with unique key
                            if st.button("Copy Results", key=f"copy_results_batch_{i}"):
                                # We'll use st.code for better clipboard support
                                st.code(analysis_text, language=None)
                                st.success("Results ready to copy! Use the copy button in the top-right of the code block above.")
                        
                        # Technical information in a collapsed expandable section
                        with st.expander("Technical Information", expanded=False):
                            st.json(batch)
                        
                        return
                
                # If we didn't find analysis in batches
                st.warning("Results format not recognized. Displaying raw data.")
        
        # Fallback to showing the raw result
        st.text_area(
            label="Raw Results Data",
            value=result_text,
            height=400,
            key="results_text_area"
        )
        
    except (json.JSONDecodeError, TypeError) as e:
        # If not valid JSON, just display as-is with error
        st.error(f"Could not parse results as JSON: {str(e)}")
        st.text_area(
            label="Raw Results Data",
            value=result_text,
            height=400,
            key="results_text_area"
        )
