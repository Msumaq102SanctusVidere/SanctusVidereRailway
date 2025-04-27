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
            if 'analysis' in result_obj:
                analysis_text = result_obj['analysis']
                
                # Display in a clean, bordered container
                with st.container(border=True):
                    st.markdown(analysis_text)
                    
                    # Add a copy button
                    if st.button("Copy Results", key="copy_results_main"):
                        # Using JavaScript to try to copy to clipboard
                        js = f"""
                        <script>
                        const text = `{analysis_text.replace('`', '\`')}`;
                        navigator.clipboard.writeText(text)
                            .then(() => console.log('Text copied to clipboard'))
                            .catch(err => console.error('Failed to copy: ', err));
                        </script>
                        """
                        st.components.v1.html(js, height=0)
                        st.success("Results copied to clipboard!")
                
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
                                # Using JavaScript to try to copy to clipboard
                                js = f"""
                                <script>
                                const text = `{analysis_text.replace('`', '\`')}`;
                                navigator.clipboard.writeText(text)
                                    .then(() => console.log('Text copied to clipboard'))
                                    .catch(err => console.error('Failed to copy: ', err));
                                </script>
                                """
                                st.components.v1.html(js, height=0)
                                st.success("Results copied to clipboard!")
                        
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
