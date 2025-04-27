import streamlit as st
import json

def results_pane(result_text):
    """
    Render the analysis results in a clean, professional dedicated window.
    
    Parameters:
        result_text (str or dict): The result from the analysis job
    """
    try:
        # Handle if result_text is already a dictionary
        if isinstance(result_text, dict):
            result_obj = result_text
        else:
            # If it's a string, try to parse as JSON
            result_obj = json.loads(result_text)
        
        # Extract analysis text
        if isinstance(result_obj, dict):
            if 'analysis' in result_obj:
                analysis_text = result_obj['analysis']
                
                # Display in a clean, bordered container
                with st.container(border=True):
                    st.markdown(analysis_text)
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_results_main"):
                        # Use st.code for better clipboard support
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
                                # Use st.code for better clipboard support
                                st.code(analysis_text, language=None)
                                st.success("Results ready to copy! Use the copy button in the top-right of the code block above.")
                        
                        # Technical information in a collapsed expandable section
                        with st.expander("Technical Information", expanded=False):
                            st.json(batch)
                        
                        return
            
            # Handle direct text content
            if isinstance(result_obj, dict) and any(key for key in result_obj.keys() if isinstance(result_obj[key], str) and len(result_obj[key]) > 100):
                # Find the longest string value in the dict - likely the main content
                main_key = max(result_obj.keys(), key=lambda k: len(result_obj[k]) if isinstance(result_obj[k], str) else 0)
                analysis_text = result_obj[main_key]
                
                # Display in a clean, bordered container
                with st.container(border=True):
                    st.markdown(analysis_text)
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_main_text"):
                        # Use st.code for better clipboard support
                        st.code(analysis_text, language=None)
                        st.success("Results ready to copy! Use the copy button in the top-right of the code block above.")
                
                return
        
        # The result might be a simple string - check before showing raw data
        if isinstance(result_text, str) and result_text.startswith("{'analysis':"):
            # Try to extract analysis part directly
            try:
                # Simple string extraction for content between quotes
                import re
                match = re.search(r"'analysis':\s*'([^']*)'", result_text)
                if match:
                    analysis_text = match.group(1)
                    with st.container(border=True):
                        st.markdown(analysis_text)
                        return
            except:
                pass  # If regex fails, continue to fallback
        
        # If we've reached here, display the raw result in a nicer format
        st.warning("Displaying raw results:")
        if isinstance(result_text, dict):
            # If it's a dict, display as JSON in a container
            with st.container(border=True):
                st.json(result_text)
        else:
            # Otherwise display as text in a container
            with st.container(border=True):
                st.text_area("Raw Results Data", value=str(result_text), height=400)
        
    except (json.JSONDecodeError, TypeError) as e:
        # If not valid JSON, try to display the content directly
        st.warning(f"Could not parse results as JSON: {str(e)}")
        with st.container(border=True):
            # Try to display as markdown first
            try:
                if isinstance(result_text, str):
                    st.markdown(result_text)
                else:
                    st.text_area("Raw Results Data", value=str(result_text), height=400)
            except:
                # Fallback to simple text display
                st.text_area("Raw Results Data", value=str(result_text), height=400)
