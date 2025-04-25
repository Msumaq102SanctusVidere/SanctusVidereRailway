# --- Filename: ui/app.py (Frontend Streamlit UI - Simplified Delete Handling) ---

import streamlit as st
import time
import logging
import sys
import os

# --- Path Setup ---
try: # Keep imports
except ImportError as e: # Keep error handling
# --- Import UI Components ---
try: # Keep imports
except ImportError as e: # Keep error handling
except Exception as e: # Keep error handling

# --- Helper Function for Refreshing Drawings ---
def refresh_drawings(): # Keep implementation

# --- Initialize Session State ---
def initialize_session_state(): # Keep implementation

initialize_session_state()

# --- Main Application Logic ---
def main():
    # --- Page Configuration ---
    st.set_page_config( page_title="Sanctus Videre 1.0", layout="wide", page_icon="🏗️", initial_sidebar_state="expanded")
    # --- Title Area ---
    st.title("🏗️ Sanctus Videre 1.0"); st.caption("Visionary Construction Insights"); st.divider()
    # --- Backend Health Check & Initial Drawing Fetch ---
    backend_healthy = False
    try: # Keep health check logic
    except Exception as e: # Keep error handling

    # --- Sidebar for Upload ---
    with st.sidebar: # Keep implementation
    # --- Main Layout (Two Columns) ---
    col1, col2 = st.columns([1, 2])

    # --- Left Column: Drawing Selection & Deletion ---
    with col1:
        st.subheader("Select Drawings")

        # --- Deletion Confirmation UI ---
        if st.session_state.drawing_to_delete:
            st.warning(f"**Confirm Deletion:** Are you sure you want to permanently delete `{st.session_state.drawing_to_delete}`?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Yes, Delete", type="primary", key="confirm_delete_button", use_container_width=True):
                    try:
                        target_drawing = st.session_state.drawing_to_delete
                        logger.info(f"Attempting to delete drawing: {target_drawing}")
                        response = delete_drawing(target_drawing) # Call API

                        # --- SIMPLIFIED ERROR HANDLING ---
                        # Trust only the "success" boolean from the backend
                        if isinstance(response, dict) and response.get("success") is True:
                            st.success(f"Drawing `{target_drawing}` deleted successfully.")
                            logger.info(f"Successfully deleted drawing: {target_drawing}")

                            # Refresh UI only on explicit success from backend
                            if isinstance(st.session_state.selected_drawings, list) and target_drawing in st.session_state.selected_drawings:
                                st.session_state.selected_drawings.remove(target_drawing)
                            st.session_state.drawing_to_delete = None
                            refresh_drawings()
                            st.rerun()
                        else:
                            # If not success==True, show the error from the backend
                            default_error = f"Failed to delete '{target_drawing}'. Unknown error."
                            error_message = response.get("error", default_error) if isinstance(response, dict) else default_error
                            st.error(error_message) # Display the error received
                            logger.error(f"API call delete_drawing failed for '{target_drawing}'. Response: {response}")
                            # Do NOT clear drawing_to_delete or rerun here - let user Cancel
                        # --- END SIMPLIFIED HANDLING ---

                    except Exception as e:
                        # Handle exceptions during the API call itself (e.g., network error)
                        st.error(f"Error communicating with server during deletion: {e}")
                        logger.error(f"Exception during delete_drawing API call: {e}", exc_info=True)
                        # Clear pending delete on communication exception and rerun
                        st.session_state.drawing_to_delete = None
                        st.rerun()

            with cancel_col:
                 if st.button("Cancel", key="cancel_delete_button", use_container_width=True):
                    logger.info(f"Deletion cancelled for: {st.session_state.drawing_to_delete}")
                    st.session_state.drawing_to_delete = None # Clear pending delete state
                    st.rerun()
            st.divider()

        # --- Drawing List Rendering ---
        # (Keep the robust version from previous step)
        with st.container(border=True): # Keep full list rendering logic

    # --- Right Column: Query, Controls, Progress, Results ---
    try:
        with col2: # Keep full implementation
    except Exception as e: # Keep error handling


# --- Run the App ---
if __name__ == "__main__": # Keep implementation
