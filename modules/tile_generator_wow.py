import os
import json
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image

# --- Default Configuration ---
TILE_SIZE = 2048
OVERLAP_RATIO = 0.35
DPI = 300

# --- Utilities ---
def ensure_dir(path):
    """Ensure directory exists"""
    path.mkdir(parents=True, exist_ok=True)

def ensure_landscape(image):
    """Ensure the image is in landscape orientation (width > height)"""
    width, height = image.size
    if height > width:
        return image.transpose(Image.ROTATE_90)
    return image

def save_tiles_with_metadata(image, out_folder, sheet_name, tile_size=2048, overlap_ratio=0.35):
    """Generate tiles from image with metadata"""
    metadata = {
        "image_size": image.size,
        "tiles": []
    }
    width, height = image.size
    step = int(tile_size * (1 - overlap_ratio))
    
    tile_id = 0
    for top in range(0, height, step):
        for left in range(0, width, step):
            right = min(left + tile_size, width)
            bottom = min(top + tile_size, height)
            
            # Adjust left/top if we're at the edge to preserve tile_size
            if right - left < tile_size and left != 0:
                left = max(0, right - tile_size)
            if bottom - top < tile_size and top != 0:
                top = max(0, bottom - tile_size)
            
            tile = image.crop((left, top, right, bottom))
            tile_filename = f"{sheet_name}_tile_{tile_id:03}.png"
            tile.save(out_folder / tile_filename)
            
            metadata["tiles"].append({
                "filename": tile_filename,
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top
            })
            
            tile_id += 1
    
    with open(out_folder / f"{sheet_name}_tile_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Generated {tile_id} tiles for {sheet_name}")
    return metadata

# Only run this if script is executed directly (not imported)
if __name__ == "__main__":
    # Default paths when run directly
    PDF_PATHS = [
        "/home/msumaq102/Sanctus Videre/A4.3.1A-THIRD-FLOOR---ZONE-1-CONSTRUCTION-PLAN-Rev.3.pdf",
        "/home/msumaq102/Sanctus Videre/A9.1.1-INTERIOR-PARTITION-DETAILS-Rev.4.pdf"
    ]
    OUTPUT_DIR = Path("/home/msumaq102/Sanctus Videre/tiles_output")
    
    for pdf_path in PDF_PATHS:
        pdf_path = Path(pdf_path)
        sheet_name = pdf_path.stem.replace(" ", "_").replace("-", "_")
        sheet_output_dir = OUTPUT_DIR / sheet_name
        ensure_dir(sheet_output_dir)
        
        print(f"📄 Converting {pdf_path.name} to image...")
        images = convert_from_path(str(pdf_path), dpi=DPI)
        full_image = images[0]  # Only first page
        
        # Ensure the image is in landscape orientation
        full_image = ensure_landscape(full_image)
        
        full_image_path = sheet_output_dir / f"{sheet_name}.png"
        full_image.save(full_image_path)
        print(f"🖼️ Saved full image to {full_image_path}")
        
        print(f"🔳 Creating tiles for {sheet_name}...")
        save_tiles_with_metadata(full_image, sheet_output_dir, sheet_name)
    
    print("✅ All sheets processed.")