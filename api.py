from flask import Flask, request, jsonify
import os
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the current directory to Python path to find the modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import modules
try:
    from modules.construction_drawing_analyzer_rev2_wow_rev6 import Config, DrawingManager
    logger.info("Successfully imported DrawingManager")
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    sys.exit(1)

app = Flask(__name__)

# Create a drawing manager instance
try:
    drawing_manager = DrawingManager(Config.DRAWINGS_DIR)
    logger.info("Successfully created drawing_manager instance")
except Exception as e:
    logger.error(f"ERROR INITIALIZING DRAWING MANAGER: {str(e)}", exc_info=True)
    drawing_manager = None

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    logger.info("Health check endpoint called")
    return jsonify({"status": "healthy"})

@app.route('/drawings', methods=['GET'])
def get_drawings():
    """Get list of available drawings"""
    try:
        if drawing_manager is None:
            return jsonify({"drawings": [], "error": "Drawing manager not initialized"}), 500
            
        available_drawings = drawing_manager.get_available_drawings()
        return jsonify({"drawings": available_drawings})
    except Exception as e:
        logger.error(f"Error retrieving drawings: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
