# --- Filename: home.py (Frontend Streamlit Home Page) ---

import streamlit as st
import time
import logging
import sys
import os
import re
import json
import datetime

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - HOME - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- Session State Initialization ---
def init_state():
    defaults = {
        'authenticated': False,
        'username': None,
        'show_login': False,
        'last_visit': None,
        'visit_count': 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# --- Main Application ---
def main():
    st.set_page_config(page_title="Sanctus Videre 1.0", layout="wide")
    
    # Add custom CSS to make the title more prominent and maintain theme consistency
    st.markdown("""
    <style>
    .big-title {
        font-size: 3rem !important;
        margin-top: -1.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    .subtitle {
        font-size: 1.2rem !important;
        margin-top: -0.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    .stButton button {
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    /* Make action buttons more distinct */
    .action-btn {
        background-color: #4CAF50 !important;
        color: white !important;
    }
    /* Custom panel styling */
    .info-panel {
        background-color: #1E1E1E;
        color: white;
        padding: 20px;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .feature-card {
        background-color: #2C2C2C;
        border-radius: 5px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .feature-card h3 {
        color: #4CAF50;
        margin-top: 0;
    }
    /* Custom styling for video container */
    .video-container {
        position: relative;
        padding-bottom: 56.25%;
        height: 0;
        overflow: hidden;
        max-width: 100%;
        margin-bottom: 20px;
        border-radius: 10px;
    }
    .video-container iframe {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Debugging indicator to verify version
    st.sidebar.text("Version: 1.0.2")
    
    # Add title with custom styling
    st.markdown('<h1 class="big-title">Sanctus Videre 1.0</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle"><i>Bridging Human Creativity and Computational Insight</i></p>', unsafe_allow_html=True)
    
    # --- Three-Column Layout ---
    col1, col2, col3 = st.columns([1, 1, 1])
    
    # --- Left Column: Welcome Video and Description ---
    with col1:
        st.subheader("Welcome to Sanctus Videre")
        
        # Video container with responsive design
        st.markdown('<div class="video-container">', unsafe_allow_html=True)
        # Replace 'YOUR_VIDEO_ID' with actual YouTube video ID
        st.video("https://www.youtube.com/watch?v=YOUR_VIDEO_ID")
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("""
        Sanctus Videre is an advanced AI-powered construction drawing analysis system that helps construction professionals extract valuable insights from their drawings instantly.
        
        Leveraging state-of-the-art large language models, our system can understand complex construction drawings and answer detailed questions about specifications, layouts, materials, and more.
        """)
    
    # --- Middle Column: Features Highlight ---
    with col2:
        st.subheader("Key Capabilities")
        
        # Feature cards with custom styling
        st.markdown('<div class="feature-card">', unsafe_allow_html=True)
        st.markdown("""
        ### Multi-Drawing Analysis
        Analyze relationships across multiple drawings simultaneously to identify cross-references and dependencies. Select multiple drawings for comprehensive integrated analysis.
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="feature-card">', unsafe_allow_html=True)
        st.markdown("""
        ### Advanced Context Understanding
        Extract information that may not be explicitly stated in the drawings. Our system provides valuable construction insights by leveraging industry knowledge.
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="feature-card">', unsafe_allow_html=True)
        st.markdown("""
        ### Intelligent Memory System
        The system builds a knowledge base as you interact with it, becoming more efficient over time. Initial analyses set the foundation for faster subsequent queries.
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # --- Right Column: Get Started & Login ---
    with col3:
        st.subheader("Get Started")
        
        # Login/Authentication section
        with st.container(border=True):
            if not st.session_state.authenticated:
                st.markdown("### Login to Your Account")
                
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                
                col_login1, col_login2 = st.columns([1, 1])
                
                with col_login1:
                    if st.button("Sign In", use_container_width=True):
                        # This is a placeholder for actual authentication
                        # In production, you'd validate against a user database
                        if username and password:
                            st.session_state.authenticated = True
                            st.session_state.username = username
                            st.session_state.last_visit = datetime.datetime.now()
                            st.session_state.visit_count += 1
                            st.rerun()
                        else:
                            st.error("Please enter credentials")
                
                with col_login2:
                    if st.button("Register", use_container_width=True):
                        st.info("Registration functionality coming soon.")
            else:
                st.markdown(f"### Welcome Back, {st.session_state.username}!")
                st.markdown(f"Last visit: {st.session_state.last_visit.strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"Visit count: {st.session_state.visit_count}")
                
                if st.button("Sign Out", use_container_width=True):
                    st.session_state.authenticated = False
                    st.session_state.username = None
                    st.rerun()
        
        # Navigation buttons
        st.markdown("### Navigation")
        
        # Administrator backdoor - allows direct access to dashboard without login
        admin_mode = False
        if username == "admin" and password == "sanctus2025":
            admin_mode = True
            
        if st.button("Go to Dashboard", type="primary", use_container_width=True):
            # Add debugging info first to see what's happening
            st.info("Attempting to navigate to dashboard...")
            # Use the direct path format that matches the error message exactly
            try:
                st.switch_page("01_dashboard.py")
            except Exception as e:
                st.error(f"Navigation error: {str(e)}")
                logger.error(f"Navigation error: {str(e)}")
                # Fallback approach
                try:
                    st.switch_page("ui/pages/01_dashboard.py")
                except Exception as e2:
                    st.error(f"Fallback navigation error: {str(e2)}")
                    logger.error(f"Fallback navigation error: {str(e2)}")
        
        if st.button("View Analysis History", use_container_width=True):
            # Match the same pattern for consistency
            try:
                st.switch_page("02_review.py")
            except Exception as e:
                st.error(f"Navigation error: {str(e)}")
                logger.error(f"Navigation error: {str(e)}")
                # Fallback approach
                try:
                    st.switch_page("ui/pages/02_review.py")
                except Exception as e2:
                    st.error(f"Fallback navigation error: {str(e2)}")
                    logger.error(f"Fallback navigation error: {str(e2)}")
        
        # Recent activity or system status
        st.markdown("### System Status")
        st.markdown("✅ All systems operational")
        st.markdown("🔄 Last update: Today")
    
    # --- Footer ---
    st.markdown("---")
    
    footer_col1, footer_col2, footer_col3 = st.columns([1, 1, 1])
    
    with footer_col1:
        st.markdown("**Sanctus Videre 1.0**")
        st.markdown("© 2025 All Rights Reserved")
    
    with footer_col2:
        st.markdown("**Contact**")
        st.markdown("support@sanctusvidere.com")
        st.markdown("1-800-SANCTUS")
    
    with footer_col3:
        st.markdown("**Resources**")
        st.markdown("[Documentation](#)")
        st.markdown("[Privacy Policy](#)")

if __name__ == "__main__":
    main()
