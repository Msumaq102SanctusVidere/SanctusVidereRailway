from flask import Flask, request, jsonify
import os
import sys
import logging
from pathlib import Path

# Rebuild trigger - April 15, 2025
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

# Create a global analyzer instance
analyzer = ConstructionAnalyzer()
drawing_manager = DrawingManager(Config.DRAWINGS_DIR)

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/drawings', methods=['GET'])
def get_drawings():
    """Get list of available drawings"""
    try:
        available_drawings = drawing_manager.get_available_drawings()
        return jsonify({"drawings": available_drawings})
    except Exception as e:
        logger.error(f"Error retrieving drawings: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/analyze', methods=['POST'])
def analyze_query():
    """Analyze a query against selected drawings"""
    try:
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
