import streamlit as st
import json

def results_pane(result_text):
    """
    Render the analysis results in a clean, professional dedicated window.
    
    Parameters:
        result_text (str): The JSON-formatted result from the analysis job
    """
    try:
        # Try to parse JSON
        result_obj = json.loads(result_text)
        
        # Extract analysis text
        if isinstance(result_obj, dict):
            # Check for direct analysis field
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
                
                return
            
            # Handle batch structure if no direct analysis field
            if 'batches' in result_obj and isinstance(result_obj['batches'], list):
                for batch in result_obj['batches']:
                    if isinstance(batch, dict) and 'result' in batch:
                        batch_result = batch['result']
                        if isinstance(batch_result, dict) and 'analysis' in batch_result:
                            analysis_text = batch_result['analysis']
                            
                            # Display in a clean, bordered container
                            with st.container(border=True):
                                st.markdown(analysis_text)
                                
                                # Add a copy button
                                if st.button("Copy Results", key="copy_results"):
                                    st.success("Results ready to copy!")
                            
                            return
        
        # Fallback: If we couldn't extract a specific analysis field,
        # check if the entire object might be the analysis
        if isinstance(result_obj, dict) and len(result_obj) > 0:
            # Check if this might be a direct analysis object without an 'analysis' field
            # Look for typical analysis fields like sections, results, conclusions, etc.
            analysis_indicators = ['title', 'summary', 'sections', 'results', 'conclusions', 'findings']
            
            # If it has at least one of these fields, treat it as a direct analysis object
            if any(key in result_obj for key in analysis_indicators):
                with st.container(border=True):
                    # Format and display key components
                    if 'title' in result_obj:
                        st.header(result_obj['title'])
                    
                    if 'summary' in result_obj:
                        st.markdown(result_obj['summary'])
                    
                    if 'sections' in result_obj and isinstance(result_obj['sections'], list):
                        for section in result_obj['sections']:
                            if isinstance(section, dict):
                                if 'heading' in section:
                                    st.subheader(section['heading'])
                                if 'content' in section:
                                    st.markdown(section['content'])
                    
                    # Display any other key fields
                    for key in ['results', 'conclusions', 'findings']:
                        if key in result_obj:
                            st.subheader(key.capitalize())
                            st.markdown(str(result_obj[key]))
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_results"):
                        st.success("Results ready to copy!")
                
                return
        
        # If we still haven't found a way to display it nicely, show the raw text in a text area
        st.text_area(
            label="Results (Raw Format)",
            value=result_text,
            height=400,
            key="results_text_area"
        )
        
    except json.JSONDecodeError:
        # If not valid JSON, just display as-is in a text area
        st.text_area(
            label="Results (Raw Format)",
            value=result_text,
            height=400,
            key="results_text_area"
        )
    except Exception as e:
        # Handle any other errors
        st.error(f"Error displaying results: {str(e)}")
        st.text_area(
            label="Results (Raw Format)",
            value=result_text,
            height=400,
            key="results_text_area"
        )
