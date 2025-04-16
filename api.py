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
    from modules.construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config, DrawingManager
    logger.info("Successfully imported analyzer modules")
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    sys.exit(1)

app = Flask(__name__)

# Create required directories
os.makedirs(Config.DRAWINGS_DIR, exist_ok=True)
os.makedirs(Config.MEMORY_STORE, exist_ok=True)

# Create global instances
try:
    analyzer = ConstructionAnalyzer()
    drawing_manager = DrawingManager(Config.DRAWINGS_DIR)
    logger.info("Successfully created analyzer and drawing_manager instances")
except Exception as e:
    logger.error(f"ERROR INITIALIZING: {str(e)}", exc_info=True)
    analyzer = None
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

@app.route('/analyze', methods=['POST'])
def analyze_query():
    """Analyze a query against selected drawings"""
    try:
        if analyzer is None:
            return jsonify({"error": "Analyzer not initialized"}), 500
            
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        query = data.get('query')
        selected_drawings = data.get('drawings', [])
        use_cache = data.get('use_cache', True)
        
        if not query:
            return jsonify({"error": "No query provided"}), 400
        if not selected_drawings:
            return jsonify({"error": "No drawings selected"}), 400
            
        logger.info(f"Processing query: {query}")
        logger.info(f"Selected drawings: {selected_drawings}")
        
        # Format the query with drawing selection
        modified_query = f"[DRAWINGS:{','.join(selected_drawings)}] {query}"
        
        # Run the analysis
        response = analyzer.analyze_query(modified_query, use_cache=use_cache)
        
        return jsonify({
            "result": response,
            "query": query,
            "drawings": selected_drawings
        })
    except Exception as e:
        logger.error(f"Error analyzing query: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
