import streamlit as st
import tempfile
import os
from api_client import upload_drawing

def upload_drawing_component():
    """
    Render a file uploader for PDFs and call the backend to process it.
    Returns True if a new drawing was successfully added (so you can refresh).
    """
    st.subheader("Upload New Drawing")
    uploaded_file = st.file_uploader(
        label="Select a PDF to upload",
        type=["pdf"]
    )
    if uploaded_file is not None:
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        # Call the API
        resp = upload_drawing(tmp_path)
        os.remove(tmp_path)  # clean up

        if resp.get("success"):
            st.success(f"✅ Processed drawing: {resp.get('drawing_name')}")
            return True
        else:
            st.error(f"❌ Upload failed: {resp.get('error')}")
    return False
