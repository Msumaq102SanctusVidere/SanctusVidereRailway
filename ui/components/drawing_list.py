# --- Filename: components/drawing_list.py ---

import streamlit as st
import sqlite3
import os
import json
import logging
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

def get_completed_drawings():
    """
    Get a list of successfully processed drawing names by checking the job database.
    This ensures we only show drawings that have been fully processed.
    
    Returns:
        list: List of drawing names that have been successfully processed
    """
    processed_drawings = []
    
    try:
        # Get the database path from environment or use default
        db_path = os.environ.get('DATABASE_PATH', '/app/database/jobs.db')
        
        # Check if database exists
        if not os.path.exists(db_path):
            logger.warning(f"Database not found at {db_path}")
            return []
        
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query for all completed conversion jobs
        cursor.execute("""
            SELECT id, result FROM jobs 
            WHERE status = 'completed' AND type = 'conversion'
        """)
        
        jobs = cursor.fetchall()
        
        # Extract drawing names from results
        for job in jobs:
            try:
                if job['result']:
                    result = json.loads(job['result']) if isinstance(job['result'], str) else job['result']
                    if isinstance(result, dict) and 'drawing_name' in result:
                        processed_drawings.append(result['drawing_name'])
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error parsing result for job {job['id']}: {e}")
        
        conn.close()
        logger.info(f"Found {len(processed_drawings)} successfully processed drawings from job database")
        
    except Exception as e:
        logger.error(f"Error retrieving completed drawings from database: {e}")
    
    return processed_drawings

def drawing_list(drawings):
    """
    Render a 'Select All' toggle and a checkbox per drawing.
    Only displays drawings that have been fully processed according to job database.
    Returns the list of selected drawing names.
    """
    st.subheader("Available Drawings")
    
    # Get the list of drawings that have been successfully processed
    processed_drawing_names = get_completed_drawings()
    
    # Filter the input drawings list to show only processed ones
    # If we can't determine processed drawings, show all of them
    if processed_drawing_names:
        filtered_drawings = [d for d in drawings if d in processed_drawing_names]
    else:
        # Fallback - show all drawings if we can't determine processed ones
        logger.warning("Could not determine processed drawings, showing all")
        filtered_drawings = drawings
    
    # No drawings after filtering
    if not filtered_drawings:
        st.info("No processed drawings available. Upload a drawing to get started.")
        return []
    
    # Selection logic for filtered drawings
    select_all = st.checkbox("Select All Drawings", key="select_all")
    selected = []
    
    if select_all:
        # Show all checked and disabled so user can't uncheck individually
        for drawing in filtered_drawings:
            st.checkbox(drawing, value=True, key=f"cb_{drawing}", disabled=True)
        selected = filtered_drawings.copy()
    else:
        for drawing in filtered_drawings:
            if st.checkbox(drawing, key=f"cb_{drawing}"):
                selected.append(drawing)
    
    # Display count of available drawings
    st.caption(f"Showing {len(filtered_drawings)} processed drawing(s)")
    
    # Instructions if needed
    if not selected:
        st.caption("Select drawings to analyze or delete")
    
    return selected
