import os
import sys
import json
from pathlib import Path
import logging
from pdf2image import convert_from_path
from PIL import Image

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the current directory to Python path to find the modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Import modules
try:
    from modules.tile_generator_wow import ensure_dir, save_tiles_with_metadata, ensure_landscape
    from modules.construction_drawing_analyzer_rev2_wow_rev6 import DrawingManager, Config, ConstructionAnalyzer
    from modules.extract_tile_entities_wow_rev4 import analyze_all_tiles
    logger.info("Successfully imported all modules")
except ImportError as e:
    logger.error(f"Error importing modules: {e}")
    logger.error("Make sure all scripts are in the correct locations")
    sys.exit(1)

class IntegratedWorkflow:
    """Manages the integrated workflow across all modules"""
    
    def __init__(self, base_dir=None):
        """Initialize the workflow with paths"""
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path(os.getcwd())
        
        # Set up directories
        self.tiles_output = self.base_dir / "tiles_output"
        self.memory_store = self.base_dir / "memory_store"
        
        # Ensure directories exist
        ensure_dir(self.tiles_output)
        ensure_dir(self.memory_store)
        
        # Configure paths
        Config.configure(base_dir=self.base_dir)
        
        # Initialize components
        self.drawing_manager = DrawingManager(self.tiles_output)
        logger.info(f"Initialized workflow with base directory: {self.base_dir}")
    
    def process_pdf(self, pdf_path, dpi=300, tile_size=2048, overlap_ratio=0.35):
        """Process a PDF through the complete workflow:
           1. Generate tiles
           2. Extract information
           3. Analyze the tiles"""
        try:
            pdf_path = Path(pdf_path)
            sheet_name = pdf_path.stem.replace(" ", "_").replace("-", "_")
            sheet_output_dir = self.tiles_output / sheet_name
            ensure_dir(sheet_output_dir)
            
            logger.info(f"📄 Converting {pdf_path.name} to image...")
            images = convert_from_path(str(pdf_path), dpi=dpi)
            full_image = images[0]  # Only first page
            
            # Ensure the image is in landscape orientation
            full_image = ensure_landscape(full_image)
            
            full_image_path = sheet_output_dir / f"{sheet_name}.png"
            full_image.save(full_image_path)
            logger.info(f"🖼️ Saved full image to {full_image_path}")
            
            logger.info(f"🔳 Creating tiles for {sheet_name}...")
            save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name, 
                                    tile_size=tile_size, overlap_ratio=overlap_ratio)
            
            # Step 2 & 3: Analyze tiles
            logger.info(f"📊 Analyzing tiles for {sheet_name}...")
            analyze_all_tiles(sheet_output_dir, sheet_name)
            
            logger.info(f"✅ Successfully processed {pdf_path.name}")
            return sheet_name, sheet_output_dir
            
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            raise
    
    def run_query(self, query, use_cache=True):
        """Run a query against the analyzed drawings"""
        analyzer = ConstructionAnalyzer()
        return analyzer.analyze_query(query, use_cache=use_cache)

# Simple CLI for testing the integration
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Integrated Drawing Processing and Analysis")
    parser.add_argument("--pdf", help="Path to PDF to process")
    parser.add_argument("--query", help="Query to run against processed drawings")
    parser.add_argument("--force", action="store_true", help="Force new analysis (ignore cache)")
    
    args = parser.parse_args()
    
    workflow = IntegratedWorkflow()
    
    if args.pdf:
        print(f"Processing PDF: {args.pdf}")
        workflow.process_pdf(args.pdf)
    
    if args.query:
        print(f"Running query: {args.query}")
        result = workflow.run_query(args.query, use_cache=not args.force)
        print("\nRESULT:\n")
        print(result)