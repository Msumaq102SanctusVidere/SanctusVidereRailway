import os
import json
import base64
import re
from pathlib import Path
from anthropic import Anthropic
import time

# --- Configuration ---
API_KEY = "sk-ant-api03-KeyRemoved"
MODEL = "claude-3-7-sonnet-20250219"
# Will be set via parameters in analyze_all_tiles()
TILES_DIR = None

client = Anthropic(api_key=API_KEY)

def analyze_all_tiles(sheet_folder: Path, sheet_name: str):
    """Two-phase analysis: first legends, then content"""
    print(f"📄 Analyzing {sheet_name} using two-phase approach...")
    
    # Load metadata
    metadata_file = sheet_folder / f"{sheet_name}_tile_metadata.json"
    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"❌ Could not load metadata for {sheet_name}: {e}")
        return
    
    # Load drawing goals for context
    drawing_goals = load_drawing_goals(sheet_folder, sheet_name)
    drawing_type = determine_drawing_type(sheet_name, drawing_goals)
    print(f"🏛️ Identified as '{drawing_type}' drawing")
    
    # Handle general notes differently if detected
    if drawing_type == "general_notes":
        print("📝 Detected General Notes drawing, analyzing with specialized approach...")
        analyze_general_notes(sheet_folder, sheet_name, metadata, drawing_goals)
        return
        
    # Call specialized functions for elevation or detail drawings
    if drawing_type == "elevation":
        print(f"📐 Detected Elevation drawing, analyzing with specialized approach...")
        analyze_all_elevation_detail_tiles(sheet_folder, sheet_name, "elevation")
        return
    elif drawing_type == "detail":
        print(f"📏 Detected Detail drawing, analyzing with specialized approach...")
        analyze_all_elevation_detail_tiles(sheet_folder, sheet_name, "detail")
        return
        
    # Continue with standard two-phase analysis for plans, schedules, and other types
    print(f"📊 Proceeding with standard two-phase analysis for {drawing_type} drawing...")
    
    # PHASE 1: Analyze right-side tiles first for legends
    print("🔍 PHASE 1: Analyzing right-side tiles for legends...")
    
    if "tiles" not in metadata:
        print("❌ No tiles found in metadata")
        return
    
    sorted_tiles = sorted(metadata["tiles"], key=lambda t: t["x"], reverse=True)
    
    if sorted_tiles:
        max_x = sorted_tiles[0]["x"]
        drawing_width = max(t["x"] + t["width"] for t in metadata["tiles"])
        width_threshold = drawing_width * 0.75
        
        legend_tiles = [t for t in sorted_tiles if t["x"] >= width_threshold]
        print(f"📊 Identified {len(legend_tiles)} potential legend tiles")
    else:
        print("❌ No tiles found to analyze")
        return
    
    legend_results = []
    for tile in legend_tiles:
        filename = tile["filename"]
        print(f"📊 Analyzing legend tile {filename}")
        result = analyze_tile(sheet_folder, tile, drawing_goals, drawing_type, is_legend=True)
        legend_results.append(result)
    
    legend_knowledge = extract_legend_knowledge(legend_results)
    
    legend_file = sheet_folder / f"{sheet_name}_legend_knowledge.json"
    with open(legend_file, "w") as f:
        json.dump(legend_knowledge, f, indent=2)
    print(f"📚 Saved legend knowledge to {legend_file}")
    
    # PHASE 2: Analyze all remaining tiles
    print("🧩 PHASE 2: Analyzing all tiles with legend knowledge...")
    print(f"🎯 Drawing type entering Phase 2: {drawing_type}")
    all_results = []
    
    for result in legend_results:
        all_results.append(result)
    
    for tile in metadata["tiles"]:
        filename = tile["filename"]
        if any(r.get("filename") == filename for r in legend_results):
            continue
        
        print(f"🧩 Analyzing content tile {filename}")
        result = analyze_tile(sheet_folder, tile, drawing_goals, drawing_type, is_legend=False, legend_knowledge=legend_knowledge)
        all_results.append(result)
    
    # Save all results
    out_path = sheet_folder / f"{sheet_name}_tile_analysis.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"✅ Saved tile analysis to {out_path}")
    
def analyze_general_notes(sheet_folder: Path, sheet_name: str, metadata, drawing_goals):
    """Specialized analysis for general notes pages"""
    print("📝 Analyzing General Notes page...")
    
    if "tiles" not in metadata:
        print("❌ No tiles found in metadata")
        return
    
    # Sort tiles by y-coordinate (top to bottom) and then x-coordinate (left to right)
    # This helps process the notes in a logical reading order
    sorted_tiles = sorted(metadata["tiles"], key=lambda t: (t["y"], t["x"]))
    
    all_results = []
    for tile in sorted_tiles:
        filename = tile["filename"]
        print(f"📝 Analyzing general notes tile {filename}")
        result = analyze_general_notes_tile(sheet_folder, tile, drawing_goals)
        all_results.append(result)
    
    # Save all results
    out_path = sheet_folder / f"{sheet_name}_general_notes_analysis.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Extract and save knowledge from general notes
    notes_knowledge = extract_general_notes_knowledge(all_results)
    knowledge_path = sheet_folder / f"{sheet_name}_general_notes_knowledge.json"
    with open(knowledge_path, "w") as f:
        json.dump(notes_knowledge, f, indent=2)
    
    print(f"✅ Saved general notes analysis to {out_path}")
    print(f"📚 Saved general notes knowledge to {knowledge_path}\n")

def analyze_general_notes_tile(sheet_folder, tile, drawing_goals):
    """Analyze a single tile from a general notes page"""
    filename = tile["filename"]
    image_path = sheet_folder / filename
    
    try:
        with open(image_path, "rb") as img_file:
            image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
        
        # Build prompt for general notes analysis
        prompt = build_general_notes_prompt(filename, drawing_goals)
        system_message = "You are an experienced construction manager analyzing general notes. Return ONLY valid JSON."

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            temperature=0,
            system=system_message,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                    ]
                }
            ]
        )

        claude_response = response.content[0].text.strip()
        validated_json = validate_json(claude_response)
        
        return {
            "filename": filename,
            "tile_position": {
                "x": tile["x"],
                "y": tile["y"],
                "width": tile["width"],
                "height": tile["height"]
            },
            "tile_type": "general_notes",
            "claude_response": validated_json
        }

    except Exception as e:
        print(f"❌ Error on {filename}: {e}")
        return {"filename": filename, "error": str(e)}

def build_general_notes_prompt(tile_name, drawing_goals):
    """Build prompt for analyzing general notes pages"""
    context_text = extract_basic_context(drawing_goals)
    
    return f"""
You are analyzing a GENERAL NOTES section of a construction drawing. Extract structured information according to the EXACT format specified below.

DRAWING CONTEXT:
{context_text}

You MUST return a JSON array of entities with the EXACT fields specified below:

REQUIRED JSON STRUCTURE - NO EXCEPTIONS:
[
  {{
    "type": "notes_header",
    "text": "GENERAL REQUIREMENTS",
    "bbox": [10, 20, 200, 30],
    "id": "H1"
  }},
  {{
    "type": "notes_paragraph",
    "text": "All work shall comply with applicable building codes and standards.",
    "bbox": [10, 60, 400, 80],
    "parent_id": "H1"
  }},
  {{
    "type": "critical_requirement",
    "text": "Special inspection required for all structural connections.",
    "bbox": [10, 100, 400, 120],
    "parent_id": "H1",
    "requirement_type": "inspection"
  }}
]

Please identify and create a hierarchical structure of:

1. SECTION HEADERS:
   - Identify all section headers (e.g., "GENERAL REQUIREMENTS", "CONCRETE", "STRUCTURAL STEEL", "FINISHES")
   - Create a "notes_header" entity for each distinct section header
   - Assign a unique ID to each header for reference by child entities
   - Note the order/sequence of headers to maintain document organization

2. NOTE PARAGRAPHS:
   - Create a "notes_paragraph" entity for each paragraph of text under a header
   - Connect each paragraph to its parent header through parent_id
   - If a paragraph contains multiple distinct requirements, split it into separate entities
   - Capture the complete text of each paragraph

3. CRITICAL REQUIREMENTS:
   - Pay special attention to inspection requirements, testing protocols, and compliance standards
   - Create a "critical_requirement" entity for any paragraph that contains:
     * Required inspections or tests
     * Safety protocols
     * Quality control measures
     * Submittals and approvals
     * Code compliance specifications
   - Link these to their parent header through parent_id
   - Add a "requirement_type" field indicating the nature of the requirement (inspection, testing, etc.)

4. REFERENCES:
   - Identify references to other sheets, specifications, or standards
   - Create a "reference" entity for each specific reference
   - Include what is being referenced (spec section, drawing number, industry standard)
   - Connect to the relevant paragraph or header through parent_id

5. ABBREVIATIONS AND DEFINITIONS:
   - If there is a list of abbreviations or definitions, capture each as an "abbreviation" entity
   - Include both the abbreviation and its full definition

CRITICAL - DO NOT:
- Change the field names
- Add extra fields
- Use different JSON structure
- Skip any headers or paragraphs

The filename of the tile is: {tile_name}
"""

def extract_general_notes_knowledge(notes_results):
    """Extract structured knowledge from general notes analysis"""
    knowledge = {
        "headers": {},           # Header text and section types
        "critical_requirements": [],  # List of all critical requirements
        "inspections": [],       # List of inspection requirements
        "testing": [],           # List of testing requirements
        "submittals": [],        # List of submittal requirements
        "references": {},        # References to other documents/standards
        "abbreviations": {},     # Abbreviation definitions
    }
    
    # Process all notes results
    all_notes_entities = []
    for result in notes_results:
        if "claude_response" in result:
            try:
                entities = json.loads(result["claude_response"])
                all_notes_entities.extend(entities)
            except Exception as e:
                print(f"⚠️ Error parsing general notes result: {e}")
    
    # Extract headers
    headers = [e for e in all_notes_entities if e.get("type") == "notes_header"]
    for header in headers:
        header_id = header.get("id", "")
        header_text = header.get("text", "")
        if header_id and header_text:
            knowledge["headers"][header_id] = header_text
    
    # Extract critical requirements
    critical_reqs = [e for e in all_notes_entities if e.get("type") == "critical_requirement"]
    for req in critical_reqs:
        req_type = req.get("requirement_type", "")
        req_text = req.get("text", "")
        parent_id = req.get("parent_id", "")
        
        # Add to general critical requirements
        knowledge["critical_requirements"].append({
            "text": req_text,
            "type": req_type,
            "section": knowledge["headers"].get(parent_id, "Unknown Section")
        })
        
        # Add to specific requirement type lists
        if req_type == "inspection":
            knowledge["inspections"].append({
                "text": req_text,
                "section": knowledge["headers"].get(parent_id, "Unknown Section")
            })
        elif req_type == "testing":
            knowledge["testing"].append({
                "text": req_text,
                "section": knowledge["headers"].get(parent_id, "Unknown Section")
            })
        elif req_type == "submittal":
            knowledge["submittals"].append({
                "text": req_text,
                "section": knowledge["headers"].get(parent_id, "Unknown Section")
            })
    
    # Extract references
    references = [e for e in all_notes_entities if e.get("type") == "reference"]
    for ref in references:
        ref_to = ref.get("reference_to", "")
        ref_text = ref.get("text", "")
        if ref_to:
            knowledge["references"][ref_to] = ref_text
    
    # Extract abbreviations
    abbreviations = [e for e in all_notes_entities if e.get("type") == "abbreviation"]
    for abbr in abbreviations:
        abbr_text = abbr.get("text", "")
        # Try to split into abbreviation and definition
        if ":" in abbr_text:
            parts = abbr_text.split(":", 1)
            abbr_key = parts[0].strip()
            abbr_def = parts[1].strip()
            knowledge["abbreviations"][abbr_key] = abbr_def
        elif "=" in abbr_text:
            parts = abbr_text.split("=", 1)
            abbr_key = parts[0].strip()
            abbr_def = parts[1].strip()
            knowledge["abbreviations"][abbr_key] = abbr_def
    
    print(f"📚 Extracted {len(knowledge['headers'])} section headers")
    print(f"📚 Extracted {len(knowledge['critical_requirements'])} critical requirements")
    print(f"📚 Extracted {len(knowledge['inspections'])} inspection requirements")
    print(f"📚 Extracted {len(knowledge['testing'])} testing requirements")
    print(f"📚 Extracted {len(knowledge['submittals'])} submittal requirements")
    print(f"📚 Extracted {len(knowledge['references'])} references")
    print(f"📚 Extracted {len(knowledge['abbreviations'])} abbreviations")
    
    return knowledge

def build_legend_prompt(tile_name, drawing_goals, drawing_type):
    """Build prompt for legend analysis focused on construction knowledge, including graphical symbols"""
    context_text = extract_basic_context(drawing_goals)

    return f"""
You are analyzing a LEGEND SECTION of a construction drawing. Extract legend information according to the EXACT format specified below, using your construction expertise to describe visual elements.

DRAWING CONTEXT:
{context_text}

You MUST return a JSON array with entities using the EXACT fields specified:

REQUIRED JSON STRUCTURE - NO EXCEPTIONS:
[
  {{
    "type": "specific_legend",
    "text": "P-1: PAINT - SEMI-GLOSS FINISH",
    "bbox": [10, 20, 200, 30],
    "finish_type": "wall",
    "notes": "Standard paint finish for interior walls",
    "description": "Text 'P-1' with a solid line leader pointing right, no graphical symbols present"
  }},
  {{
    "type": "specific_legend",
    "text": "CPT-2: CARPET - LOOP PILE",
    "bbox": [10, 60, 200, 30],
    "finish_type": "floor",
    "notes": "Used in main office areas",
    "description": "Text 'CPT-2' accompanied by a small square symbol representing carpet texture"
  }},
  {{
    "type": "keynote",
    "text": "1: PROVIDE 5/8\" GYPSUM BOARD",
    "bbox": [10, 100, 200, 30],
    "description": "Number '1' in a circle with a dashed leader line pointing up"
  }}
]

Your task is to extract:

1. SPECIFIC LEGEND ITEMS:
   - Create a "specific_legend" entity for EACH tag/code and its description
   - Include the "text" exactly as shown, preserving the code and description
   - Classify the "finish_type" as "floor", "wall", "ceiling", or "base" if applicable
   - Add any relevant observations in the "notes" field
   - Include a "description" field describing what you see, including any graphical symbols (e.g., lines, arrows, circles) and their meaning based on construction knowledge

2. KEYNOTES:
   - Create a "keynote" entity for each numbered reference and its explanation
   - Preserve the exact text without interpretation
   - Include a "description" field describing the visual representation, including any symbols or leader lines

3. MASTER LEGENDS:
   - Create a "master_legend" entity for any diagrams explaining tag structures
   - Note tag conventions and their meanings in "notes"
   - Include a "description" field for the diagram's visual elements

CRITICAL - DO NOT:
- Change the field names
- Add extra fields beyond those specified
- Use different JSON structure
- Interpret or modify tag text unless describing it in the "description" field
- Rearrange or reformat tag information

The filename of the tile is: {tile_name}
"""
def build_schedule_prompt(tile_name, drawing_goals, legend_knowledge):
    """Build simplified prompt for schedule extraction with focus on completeness"""
    context_text = extract_basic_context(drawing_goals)
    
    return f"""
Analyze this construction schedule drawing and extract ALL visible rows.

Context: {context_text}

TASK: Extract EVERY SINGLE row visible in this schedule. 

Step 1: COUNT how many rows you can see in total.
Step 2: Extract ALL rows, starting from the top, one by one.
Step 3: Make sure your JSON array has exactly the same number of entries as rows you counted.

JSON format:
[
  {{
    "row_id": "row_{tile_name}_1",
    "text": "All text in this row exactly as written",
    "partial": false
  }},
  {{
    "row_id": "row_{tile_name}_2",
    "text": "All text in this row exactly as written",
    "partial": true,
    "cut_edge": ["right"]
  }}
]

REMEMBER: Extract EVERY row (including headers). If you see 20 rows, I need 20 JSON entries.

Filename: {tile_name}
"""

def build_content_prompt(tile_name, drawing_goals, drawing_type, legend_knowledge):
    """Build prompt for analyzing content tiles, including visual descriptions with construction expertise"""
    context_text = extract_basic_context(drawing_goals)

    specific_tags_text = ""
    if legend_knowledge is not None:
        specific_tags = legend_knowledge.get("specific_tags", {})
        if specific_tags:
            specific_tags_text = "SPECIFIC TAG DEFINITIONS:\n"
            for tag, info in specific_tags.items():
                tag_type = info.get("type", "unknown")
                description = info.get("description", "")
                specific_tags_text += f"- {tag}: {description} ({tag_type} type)\n"

    return f"""
You are analyzing a section of a {drawing_type.upper()} drawing. Extract information according to the EXACT format below, using your construction knowledge to describe visual elements.

DRAWING CONTEXT:
{context_text}

{specific_tags_text}

You MUST return a JSON array of entities with the EXACT fields specified below but note that the "text" entries for each "type" will vary depending on what is exactly shown in the drawings:

REQUIRED JSON STRUCTURE - NO EXCEPTIONS:
[
  {{
    "type": "room_label",
    "text": "OFFICE 101",
    "bbox": [100, 200, 50, 20],
    "description": "Text 'OFFICE 101' in a rectangular box, no symbols"
  }},
  {{
    "type": "tag",
    "text": "A34",
    "bbox": [150, 250, 20, 10],
    "tag_type": "partition",
    "description": "Tag 'A34' with a solid leader line pointing left to a wall outline"
  }},
  {{
    "type": "tag",
    "text": "E1",
    "bbox": [180, 270, 10, 10],
    "tag_type": "electrical",
    "description": "Tag 'E1' in a diamond shape with a dashed leader pointing to an electrical fixture"
  }},
  {{
    "type": "keynote_reference",
    "text": "3",
    "bbox": [200, 290, 10, 10],
    "description": "Number '3' in a circle with a dashed leader pointing to a structural element"
  }},
  {{
    "type": "room_area",
    "bbox": [50, 150, 200, 180],
    "extends_beyond": ["right", "bottom"],
    "description": "Shaded area with no symbols, extends beyond tile edges"
  }}
]

Please identify:

1. Room entities (labels, numbers, identifiers)
   - Type: "room_label"
   - Include a "description" field for visual elements (e.g., symbols, lines)

2. Tags:
   - Type: "tag"
   - ALWAYS PRESERVE THE TAGS EXACTLY AS THEY APPEAR in the image
   - Do NOT reword, reinterpret, or expand tag values
   - Specify "tag_type" based on context or legend knowledge (e.g., "partition", "electrical", "finish", "structural", "plumbing", "mechanical", or "unknown" if unclear)
   - Include a "description" field for visual elements (e.g., leader lines, symbols)

3. Keynotes and references:
   - Type: "keynote_reference"
   - Extract exactly as shown
   - Include a "description" field for visual elements (e.g., circles, arrows)

4. Room areas:
   - Type: "room_area"
   - Note which edges the room extends beyond (if any)
   - Include a "description" field for visual elements

5. Schedule rows in mini-schedules:
   - Type: "schedule_row"
   - Preserve all text exactly as shown
   - Include a "description" field for visual elements

For the "description" field in all entities:
- Describe what you see in the tile, including any graphical symbols (e.g., electrical fixtures, plumbing icons, arrows) and their likely meaning based on your construction expertise
- Mention leader lines, their direction, and any associated symbols

CRITICAL - DO NOT:
- Modify any tag text (e.g., "A34" must remain "A34", not "Partition A34")
- Add fields not shown in the examples
- Change the field names
- Use different JSON structure

The filename of the tile is: {tile_name}
"""

def extract_legend_knowledge(legend_results):
    """Extract structured knowledge from legend tile analyses using construction expertise"""
    knowledge = {
        "specific_tags": {},
        "keynotes": {},
        "industry_standards": {},
    }

    all_legend_entities = []
    for result in legend_results:
        if "claude_response" in result:
            try:
                entities = json.loads(result["claude_response"])
                all_legend_entities.extend(entities)
            except Exception as e:
                print(f"⚠️ Error parsing legend result: {e}")

    for entity in all_legend_entities:
        if entity.get("type") == "specific_legend":
            tag_text = entity.get("text", "")
            finish_type = entity.get("finish_type", "unknown")
            notes = entity.get("notes", "")

            if "-" in tag_text:
                parts = tag_text.split("-", 1)
                if len(parts) == 2:
                    tag = parts[0].strip()
                    description = parts[1].strip()
            elif ":" in tag_text:
                parts = tag_text.split(":", 1)
                if len(parts) == 2:
                    tag = parts[0].strip()
                    description = parts[1].strip()
            else:
                words = tag_text.split()
                if words and any(char.isdigit() for char in words[0]):
                    tag = words[ 0]
                    description = " ".join(words[1:])
                else:
                    continue

            knowledge["specific_tags"][tag] = {
                "description": description,
                "type": finish_type,
                "notes": notes
            }

    knowledge["industry_standards"] = {
        "ACT": "ceiling",
        "C": "floor",
        "CPT": "floor",
        "P": "wall",
        "RB": "base",
        "VCT": "floor",
        "CT": "floor",
        "PT": "floor",
        "WD": "floor",
        "LVT": "floor",
        "RF": "floor",
        "SS": "wall",
        "PL": "wall",
        "WC": "wall",
        "MT": "wall",
        "GL": "wall",
        "CN": "floor",
        "TS": "wall",
        "MB": "wall"
    }

    for entity in all_legend_entities:
        if "keynote" in entity.get("type", "").lower():
            keynote_text = entity.get("text", "")
            if ":" in keynote_text:
                number, description = keynote_text.split(":", 1)
                number = number.strip()
                description = description.strip()
                knowledge["keynotes"][number] = description

    print(f"📚 Extracted {len(knowledge['specific_tags'])} specific tags")
    print(f"📚 Extracted {len(knowledge['keynotes'])} keynotes")
    print(f"📚 Added {len(knowledge['industry_standards'])} industry standard abbreviations")

    return knowledge



def calculate_global_bbox(results):
    """
    Calculate the global bounding box that encompasses all tiles
    
    Args:
        results: List of tile analysis results
        
    Returns:
        Dictionary with global position information
    """
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')
    
    for result in results:
        tile_pos = result.get("tile_position", {})
        x = tile_pos.get("x", 0)
        y = tile_pos.get("y", 0)
        width = tile_pos.get("width", 0)
        height = tile_pos.get("height", 0)
        
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + width)
        max_y = max(max_y, y + height)
    
    return {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x,
        "height": max_y - min_y
    }

def extract_basic_context(drawing_goals):
    """Extract basic context from drawing goals"""
    drawing_info = drawing_goals.get("drawing_info", {})
    scale = drawing_goals.get("scale", "")
    
    return f"""
Title: {drawing_info.get('title', 'Unknown')}
Number: {drawing_info.get('number', 'Unknown')}
Scale: {scale}
"""

def analyze_tile(sheet_folder, tile, drawing_goals, drawing_type, is_legend=False, legend_knowledge=None):
    """Analyze a single tile, either as a legend tile or a content tile"""
    filename = tile["filename"]
    image_path = sheet_folder / filename
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with open(image_path, "rb") as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
            
            if is_legend:
                prompt = build_legend_prompt(filename, drawing_goals, drawing_type)
                system_message = "You are an expert construction manager analyzing construction drawing legends. Return ONLY valid JSON."
            elif drawing_type == "schedule":
                prompt = build_schedule_prompt(filename, drawing_goals, legend_knowledge)
                system_message = "You are an experienced construction manager analyzing a schedule. Return ONLY valid JSON."
            else:
                prompt = build_content_prompt(filename, drawing_goals, drawing_type, legend_knowledge)
                system_message = f"You are an experienced construction manager analyzing a {drawing_type} drawing. Return ONLY valid JSON."

            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                temperature=0,
                system=system_message,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                        ]
                    }
                ]
            )

            claude_response = response.content[0].text.strip()
            validated_json = validate_json(claude_response)
            
            return {
                "filename": filename,
                "tile_position": {
                    "x": tile["x"],
                    "y": tile["y"],
                    "width": tile["width"],
                    "height": tile["height"]
                },
                "tile_type": "legend" if is_legend else "content",
                "claude_response": validated_json,
                "status": "success"
            }
        except Exception as e:
            if "529" in str(e) and attempt < max_retries - 1:
                print(f"⚠️ Overloaded on {filename}, retrying in 5s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(5)
                continue
            print(f"❌ Error on {filename}: {e}")
            return {
                "filename": filename,
                "error": str(e),
                "status": "failed"
            }

def analyze_elevation_detail_tile(sheet_folder, tile, drawing_goals, drawing_type):
    """Simplified analysis of a single tile for detail/elevation mini-drawings"""
    filename = tile["filename"]
    image_path = sheet_folder / filename
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(image_path, "rb") as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
            
            # Build simplified prompt
            prompt = build_elevation_detail_prompt(filename, drawing_goals, drawing_type)
            system_message = f"You are an expert construction manager analyzing {drawing_type} drawings. Return ONLY valid JSON."

            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                temperature=0,
                system=system_message,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                        ]
                    }
                ]
            )

            claude_response = response.content[0].text.strip()
            validated_json = validate_json(claude_response)
            
            # Parse the result and check if it's empty
            detected_components = json.loads(validated_json)
            if not detected_components:
                print(f"⚠️ No components detected in {filename}. Retrying with adjusted prompt...")
                if attempt < max_retries - 1:
                    # Add a stronger emphasis in the retry
                    prompt += "\n\nIMPORTANT: MAKE SURE TO EXTRACT ALL TEXT AND COMPONENTS VISIBLE IN THE IMAGE, INCLUDING ANY PARTIAL DETAILS OR TITLES."
                    continue
            
            return {
                "filename": filename,
                "tile_position": {
                    "x": tile["x"],
                    "y": tile["y"],
                    "width": tile["width"],
                    "height": tile["height"]
                },
                "tile_type": drawing_type,
                "detected_components": detected_components
            }

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Error on {filename}: {e}, retrying in 3s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(3)
                continue
            print(f"❌ Error on {filename}: {e}")
            return {"filename": filename, "error": str(e)}

def build_elevation_detail_prompt(tile_name, drawing_goals, drawing_type):
    """Build simplified prompt for detail/elevation analysis"""
    context_text = extract_basic_context(drawing_goals)
    
    return f"""
You are analyzing a tile from a {drawing_type.upper()} drawing that contains multiple mini-drawings. 
Identify each separate mini-drawing visible in the tile.

DRAWING CONTEXT:
{context_text}

IMPORTANT DRAWING CONVENTIONS:
- In elevation and detail drawings, the title and identification tag are typically located BELOW the drawing they refer to
- Titles may span across multiple tiles - look for partial titles that might continue in adjacent tiles
- Pay special attention to text near the bottom of details that appears to be a title or label
- Revision clouds (wavy red lines) often indicate changes or important information
- Scale notations are typically near titles

CRITICAL EXTRACTION REQUIREMENTS:
- EXTRACT ALL TEXT VISIBLE IN THE TILE EXACTLY AS IT APPEARS
- Capture ALL component titles completely, especially those at the bottom of details
- Extract ALL text even if it has revision clouds or marks around it (this is often critical information)
- Include ALL annotations, dimensions, material callouts, and notes
- When text appears to continue beyond the tile edge, note this in "extends_beyond"
- Do not omit any text, numbers, or symbols visible in the drawing

For EACH distinct {drawing_type} mini-drawing visible in this tile, create a JSON object with these fields:

REQUIRED JSON STRUCTURE:
[
  {{
    "component_id": "D3",  // The callout/tag identifier (e.g., "A1", "D3", etc.). Use "unknown" if not visible.
    "title": "PARTITION TYPE A",  // The title of the component. Use empty string if not visible.
    "bbox": [10, 20, 200, 150],  // Bounding box coordinates of this mini-drawing [x, y, width, height]
    "is_partial": true,  // Boolean indicating if this component appears to be cut off in this tile
    "extends_beyond": ["right", "bottom"],  // Directions where the component extends beyond the tile
    "materials": ["GYPSUM BOARD", "METAL STUD"],  // Any material tags visible in this component
    "description": "This {drawing_type} shows a metal stud partition with 5/8\\" gypsum board on both sides."  // Brief description
  }}
]

CRITICAL INSTRUCTIONS:
1. Focus ONLY on identifying separate mini-drawings - one JSON object per distinct {drawing_type}.
2. If a mini-drawing is cut off, set "is_partial" to true and specify in "extends_beyond" which edges it extends beyond.
3. If a mini-drawing has distinctive materials/components visible, list them in "materials".
4. Keep the "description" brief but informative about what this particular mini-drawing shows.
5. Pay special attention to identifying the correct "component_id" (callout/reference number) for each mini-drawing.
6. Look for titles at the bottom of details and capture them completely, even if they appear to be part of a longer title.
7. Extract text EXACTLY as shown without elaboration or modification.
8. Text with revision clouds or red markings is especially important - always include it.
9. Return an empty array [] if no mini-drawings are visible in this tile.

The filename of the tile is: {tile_name}
"""

def extract_drawing_number(drawing_goals):
    """Extract drawing number from goals data"""
    if drawing_goals and "drawing_info" in drawing_goals:
        return drawing_goals["drawing_info"].get("number", "unknown")
    return "unknown"

def generate_unique_suffix():
    """Generate a unique suffix for undefined IDs"""
    import datetime
    import random
    timestamp = datetime.datetime.now().strftime("%m%d%H%M")
    random_num = random.randint(1000, 9999)
    return f"{timestamp}-{random_num}"


def analyze_all_elevation_detail_tiles(sheet_folder, sheet_name, drawing_type):
    """Streamlined analysis for elevation/detail drawings with clear, focused steps"""
    print(f"📊 Analyzing {sheet_name} as {drawing_type} drawing...")
    
    # Load metadata and drawing goals
    metadata_file = sheet_folder / f"{sheet_name}_tile_metadata.json"
    try:
        with open(metadata_file) as f:
            metadata = json.load(f)
    except Exception as e:
        print(f"❌ Could not load metadata for {sheet_name}: {e}")
        return
    
    drawing_goals = load_drawing_goals(sheet_folder, sheet_name)
    
    # Sort tiles in reading order (top-to-bottom, left-to-right)
    sorted_tiles = sorted(metadata.get("tiles", []), key=lambda t: (t["y"], t["x"]))
    if not sorted_tiles:
        print(f"❌ No tiles found in metadata for {sheet_name}")
        return
    
    # STEP 1: Identify component boundaries across all tiles
    print(f"🔍 STEP 1: Identifying {drawing_type} component boundaries...")
    boundary_results = []
    
    for tile in sorted_tiles:
        filename = tile["filename"]
        print(f"  → Scanning tile {filename}")
        result = identify_component_boundaries(sheet_folder, tile, drawing_goals, drawing_type)
        boundary_results.append(result)
    
    # STEP 2: Group components that span multiple tiles
    print(f"🔗 STEP 2: Grouping related {drawing_type} components...")
    component_groups = group_components_across_tiles(boundary_results)
    
    # STEP 3: Detailed analysis of each grouped component
    print(f"🔬 STEP 3: Analyzing {len(component_groups)} {drawing_type} components in detail...")
    final_components = []
    
    for i, group in enumerate(component_groups):
        comp_id = group.get("component_id", f"COMP_{i+1}")
        print(f"  → Analyzing {drawing_type} component {comp_id}")
        
        # For each component, analyze all related tiles together
        detailed_result = analyze_component_detail(
            sheet_folder, 
            group["tiles"], 
            group["bbox"], 
            drawing_goals, 
            drawing_type
        )
        
        final_components.append(detailed_result)
    
    # Save both intermediate and final results
    print(f"💾 Saving analysis results...")
    
    # Save boundary detection results for debugging
    boundary_path = sheet_folder / f"{sheet_name}_{drawing_type}_boundaries.json"
    with open(boundary_path, "w") as f:
        json.dump(boundary_results, f, indent=2)
    
    # Save final component analysis
    final_path = sheet_folder / f"{sheet_name}_{drawing_type}_analysis.json"
    with open(final_path, "w") as f:
        json.dump(final_components, f, indent=2)
    
    print(f"✅ Analysis complete. Found {len(final_components)} {drawing_type} components.")
    return final_components

def identify_component_boundaries(sheet_folder, tile, drawing_goals, drawing_type):
    """Identify component boundaries with a simple, focused prompt"""
    filename = tile["filename"]
    image_path = sheet_folder / filename
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with open(image_path, "rb") as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode("utf-8")
            
            # Simple prompt focusing only on boundaries and IDs
            prompt = f"""
Look at this tile from a construction {drawing_type.upper()} drawing. Your only task is to identify the boundaries of distinct components.

For each separate {drawing_type} component visible in this image:
1. Find its boundaries
2. Look for any ID tag (like "A1", "D3", etc.)
3. Identify its title (usually below the component)

Return a JSON array with these fields for each component:
[
  {{
    "component_id": "D3",  // The identifier tag. Use "unknown" if not visible.
    "title": "PARTITION TYPE A",  // Component title. Use empty string if not visible.
    "bbox": [10, 20, 200, 150],  // Estimated bounding box [x, y, width, height]
    "is_partial": true,  // Is this component cut off at the tile edge?
    "cut_edges": ["right", "bottom"]  // Which edges is it cut off at?
  }}
]

Return an empty array [] if no components are visible.
The filename of the tile is: {filename}
"""
            system_message = f"You are an expert construction drawing analyst focusing on {drawing_type} drawings. Return ONLY valid JSON."

            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                temperature=0,
                system=system_message,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                        ]
                    }
                ]
            )

            claude_response = response.content[0].text.strip()
            validated_json = validate_json(claude_response)
            
            # Add tile position information
            return {
                "filename": filename,
                "tile_position": {
                    "x": tile["x"],
                    "y": tile["y"],
                    "width": tile["width"],
                    "height": tile["height"]
                },
                "components": validated_json,
                "status": "success"
            }
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ Error on {filename}: {e}, retrying in 3s...")
                time.sleep(3)
                continue
            print(f"❌ Error on {filename}: {e}")
            return {
                "filename": filename,
                "tile_position": {
                    "x": tile["x"],
                    "y": tile["y"],
                    "width": tile["width"],
                    "height": tile["height"]
                },
                "components": "[]",
                "status": "failed",
                "error": str(e)
            }

def group_components_across_tiles(boundary_results):
    """Group components that span multiple tiles using simple geometric logic"""
    all_components = []
    
    # Extract all components from all tiles
    for result in boundary_results:
        tile_pos = result.get("tile_position", {})
        filename = result.get("filename", "")
        
        try:
            components = json.loads(result.get("components", "[]"))
            for component in components:
                # Convert bounding box to global coordinates
                bbox = component.get("bbox", [0, 0, 0, 0])
                global_bbox = {
                    "x": tile_pos.get("x", 0) + bbox[0],
                    "y": tile_pos.get("y", 0) + bbox[1],
                    "width": bbox[2],
                    "height": bbox[3]
                }
                
                # Create component entry with tile info
                all_components.append({
                    "component_id": component.get("component_id", "unknown"),
                    "title": component.get("title", ""),
                    "global_bbox": global_bbox,
                    "is_partial": component.get("is_partial", False),
                    "cut_edges": component.get("cut_edges", []),
                    "source_tile": filename,
                    "tile_position": tile_pos,
                    "local_bbox": bbox
                })
        except:
            continue
    
    # Group components based on ID first, then spatial proximity
    grouped_components = []
    processed = set()
    
    # First group by ID (most reliable)
    id_groups = {}
    for i, comp in enumerate(all_components):
        comp_id = comp["component_id"]
        if comp_id != "unknown":
            if comp_id not in id_groups:
                id_groups[comp_id] = []
            id_groups[comp_id].append((i, comp))
    
    # Create component groups from ID matches
    for comp_id, members in id_groups.items():
        indices, comps = zip(*members)
        processed.update(indices)
        
        # Combine all tiles from this component group
        tiles = []
        for comp in comps:
            tiles.append({
                "filename": comp["source_tile"],
                "position": comp["tile_position"],
                "local_bbox": comp["local_bbox"]
            })
        
        # Calculate encompassing bounding box
        min_x = min(c["global_bbox"]["x"] for c in comps)
        min_y = min(c["global_bbox"]["y"] for c in comps)
        max_x = max(c["global_bbox"]["x"] + c["global_bbox"]["width"] for c in comps)
        max_y = max(c["global_bbox"]["y"] + c["global_bbox"]["height"] for c in comps)
        
        global_bbox = {
            "x": min_x,
            "y": min_y,
            "width": max_x - min_x,
            "height": max_y - min_y
        }
        
        # Get the most complete title
        title = max((c["title"] for c in comps if c["title"]), key=len, default="")
        
        grouped_components.append({
            "component_id": comp_id,
            "title": title,
            "bbox": global_bbox,
            "tiles": tiles,
            "is_partial": any(c["is_partial"] for c in comps),
            "num_tiles": len(tiles)
        })
    
    # Next, group components that are adjacent and have matching cut edges
    for i, comp_a in enumerate(all_components):
        if i in processed:
            continue
            
        current_group = [comp_a]
        processed.add(i)
        
        # Find adjacent components that match this one's cut edges
        for j, comp_b in enumerate(all_components):
            if j in processed or i == j:
                continue
                
            # Check if these components might be continuations
            if is_likely_continuation(comp_a, comp_b):
                current_group.append(comp_b)
                processed.add(j)
        
        # If we found a group, create a grouped component
        if len(current_group) > 1:
            tiles = []
            for comp in current_group:
                tiles.append({
                    "filename": comp["source_tile"],
                    "position": comp["tile_position"],
                    "local_bbox": comp["local_bbox"]
                })
            
            # Calculate encompassing bounding box
            min_x = min(c["global_bbox"]["x"] for c in current_group)
            min_y = min(c["global_bbox"]["y"] for c in current_group)
            max_x = max(c["global_bbox"]["x"] + c["global_bbox"]["width"] for c in current_group)
            max_y = max(c["global_bbox"]["y"] + c["global_bbox"]["height"] for c in current_group)
            
            global_bbox = {
                "x": min_x,
                "y": min_y,
                "width": max_x - min_x,
                "height": max_y - min_y
            }
            
            # Get the most complete title
            title = max((c["title"] for c in current_group if c["title"]), key=len, default="")
            
            # Use the most specific component ID
            comp_id = next((c["component_id"] for c in current_group if c["component_id"] != "unknown"), f"COMP_{len(grouped_components)+1}")
            
            grouped_components.append({
                "component_id": comp_id,
                "title": title,
                "bbox": global_bbox,
                "tiles": tiles,
                "is_partial": any(c["is_partial"] for c in current_group),
                "num_tiles": len(tiles)
            })
    
    # Finally, add any remaining components as individual items
    for i, comp in enumerate(all_components):
        if i in processed:
            continue
            
        grouped_components.append({
            "component_id": comp["component_id"],
            "title": comp["title"],
            "bbox": comp["global_bbox"],
            "tiles": [{
                "filename": comp["source_tile"],
                "position": comp["tile_position"],
                "local_bbox": comp["local_bbox"]
            }],
            "is_partial": comp["is_partial"],
            "num_tiles": 1
        })
    
    return grouped_components

def is_likely_continuation(comp_a, comp_b):
    """Determine if two components are likely continuations of each other"""
    # If both have IDs and they're different, they're not the same component
    if (comp_a["component_id"] != "unknown" and 
        comp_b["component_id"] != "unknown" and
        comp_a["component_id"] != comp_b["component_id"]):
        return False
    
    bbox_a = comp_a["global_bbox"]
    bbox_b = comp_b["global_bbox"]
    
    # Check if one component extends to an edge and the other starts at that edge
    tolerance = 50  # Pixel tolerance for alignment
    
    # Component A extends right, B continues from left
    if "right" in comp_a.get("cut_edges", []) and "left" in comp_b.get("cut_edges", []):
        if (abs(bbox_a["x"] + bbox_a["width"] - bbox_b["x"]) < tolerance and
            overlap_percent(bbox_a["y"], bbox_a["height"], bbox_b["y"], bbox_b["height"]) > 0.3):
            return True
    
    # Component A extends left, B continues from right
    if "left" in comp_a.get("cut_edges", []) and "right" in comp_b.get("cut_edges", []):
        if (abs(bbox_b["x"] + bbox_b["width"] - bbox_a["x"]) < tolerance and
            overlap_percent(bbox_a["y"], bbox_a["height"], bbox_b["y"], bbox_b["height"]) > 0.3):
            return True
            
    # Component A extends bottom, B continues from top
    if "bottom" in comp_a.get("cut_edges", []) and "top" in comp_b.get("cut_edges", []):
        if (abs(bbox_a["y"] + bbox_a["height"] - bbox_b["y"]) < tolerance and
            overlap_percent(bbox_a["x"], bbox_a["width"], bbox_b["x"], bbox_b["width"]) > 0.3):
            return True
    
    # Component A extends top, B continues from bottom
    if "top" in comp_a.get("cut_edges", []) and "bottom" in comp_b.get("cut_edges", []):
        if (abs(bbox_b["y"] + bbox_b["height"] - bbox_a["y"]) < tolerance and
            overlap_percent(bbox_a["x"], bbox_a["width"], bbox_b["x"], bbox_b["width"]) > 0.3):
            return True
    
    return False

def overlap_percent(pos1, size1, pos2, size2):
    """Calculate percentage of overlap between two line segments"""
    # Find overlapping segment
    overlap_start = max(pos1, pos2)
    overlap_end = min(pos1 + size1, pos2 + size2)
    
    if overlap_start >= overlap_end:
        return 0.0  # No overlap
    
    overlap_length = overlap_end - overlap_start
    min_size = min(size1, size2)
    
    if min_size == 0:
        return 0.0
        
    return overlap_length / min_size

def analyze_component_detail(sheet_folder, tiles, bbox, drawing_goals, drawing_type):
    """Simplified component analysis with very robust error handling"""
    # Construct a basic result in case of errors
    result = {
        "component_id": "unknown",
        "title": "",
        "materials": [],
        "annotations": [],
        "description": f"{drawing_type} component",
        "bbox": bbox,
        "tile_filenames": [],
        "num_tiles": 0
    }
    
    # Check if tiles is valid and not empty
    if not tiles:
        result["error"] = "No tiles provided"
        return result
    
    # Get first tile safely
    if not isinstance(tiles, list) or len(tiles) == 0:
        result["error"] = "Invalid tiles data structure"
        return result
    
    # Get tile filenames regardless of success
    for t in tiles:
        if isinstance(t, dict) and "filename" in t and t["filename"]:
            result["tile_filenames"].append(t["filename"])
    result["num_tiles"] = len(result["tile_filenames"])
    
    try:
        # Get first tile with more careful checking
        primary_tile = tiles[0] if isinstance(tiles, list) and len(tiles) > 0 else None
        if not primary_tile or not isinstance(primary_tile, dict):
            result["error"] = "Invalid primary tile structure"
            return result
        
        # Get filename safely
        primary_filename = primary_tile.get("filename", "")
        if not primary_filename:
            result["error"] = "No filename in primary tile"
            return result
        
        # Load image with careful error handling
        try:
            image_path = sheet_folder / primary_filename
            if not os.path.exists(image_path):
                result["error"] = f"Image file not found: {primary_filename}"
                return result
                
            with open(image_path, "rb") as img_file:
                image_data = base64.b64encode(img_file.read()).decode("utf-8")
        except Exception as img_err:
            result["error"] = f"Image loading error: {str(img_err)}"
            return result
        
        # Simpler prompt with minimal structure requirements
        prompt = f"""
Analyze this {drawing_type.upper()} drawing component and describe what you see.

Focus on identifying:
1. Component ID (if any)
2. Component title
3. Key materials
4. Important annotations

Filename: {primary_filename}
"""
        system_message = "You are analyzing an architectural drawing. Respond with a brief description."
        
        # Make API call with careful error handling
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                temperature=0,
                system=system_message,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                        ]
                    }
                ]
            )
        except Exception as api_err:
            result["error"] = f"API error: {str(api_err)}"
            return result
            
        # Process response carefully
        try:
            if not hasattr(response, 'content') or not response.content or len(response.content) == 0:
                result["error"] = "Empty API response"
                return result
                
            text_response = response.content[0].text.strip()
            
            # Try to extract structured data from the response
            if text_response.startswith("{") and text_response.endswith("}"):
                # Looks like JSON, try to parse it
                try:
                    extracted = json.loads(text_response)
                    if isinstance(extracted, dict):
                        # Update result with any valid fields from the extracted data
                        for key in ["component_id", "title", "materials", "annotations", "description"]:
                            if key in extracted and extracted[key]:
                                result[key] = extracted[key]
                except:
                    # If JSON parsing fails, use text as description
                    result["description"] = text_response
            else:
                # Not JSON, use the whole response as description
                result["description"] = text_response
                
                # Try to extract key information using regex
                id_match = re.search(r'(ID|identifier|number)[:\s]+([A-Z0-9]+)', text_response, re.IGNORECASE)
                if id_match:
                    result["component_id"] = id_match.group(2).strip()
                    
                title_match = re.search(r'(title|named|called)[:\s]+"?([^"\n.]+)"?', text_response, re.IGNORECASE)
                if title_match:
                    result["title"] = title_match.group(2).strip()
        except Exception as parse_err:
            result["error"] = f"Response parsing error: {str(parse_err)}"
            # Still return what we have rather than failing completely
            return result
            
        return result
            
    except Exception as e:
        # Catch-all error handler
        result["error"] = f"Unexpected error: {str(e)}"
        return result

def check_tile_adjacency(pos_a, pos_b):
    """
    Determine if and how two tiles are adjacent.
    
    Returns:
        str: "horizontal_right" if B is to the right of A
             "horizontal_left" if B is to the left of A
             "vertical_below" if B is below A
             "vertical_above" if B is above A
             "none" if tiles are not adjacent
    """
    # Extract coordinates
    a_x = pos_a.get("x", 0)
    a_y = pos_a.get("y", 0)
    a_width = pos_a.get("width", 0)
    a_height = pos_a.get("height", 0)
    
    b_x = pos_b.get("x", 0)
    b_y = pos_b.get("y", 0)
    b_width = pos_b.get("width", 0)
    b_height = pos_b.get("height", 0)
    
    # Check horizontal adjacency
    horizontal_overlap = (
        (a_y <= b_y + b_height) and (a_y + a_height >= b_y)
    )
    
    if horizontal_overlap:
        # B is to the right of A
        if abs(a_x + a_width - b_x) < 20:
            return "horizontal_right"
        # B is to the left of A
        if abs(b_x + b_width - a_x) < 20:
            return "horizontal_left"
    
    # Check vertical adjacency
    vertical_overlap = (
        (a_x <= b_x + b_width) and (a_x + a_width >= b_x)
    )
    
    if vertical_overlap:
        # B is below A
        if abs(a_y + a_height - b_y) < 20:
            return "vertical_below"
        # B is above A
        if abs(b_y + b_height - a_y) < 20:
            return "vertical_above"
    
    return "none"



def extract_basic_context(drawing_goals):
    """Extract basic context from drawing goals"""
    drawing_info = drawing_goals.get("drawing_info", {})
    scale = drawing_goals.get("scale", "")
    
    return f"""
Title: {drawing_info.get('title', 'Unknown')}
Number: {drawing_info.get('number', 'Unknown')}
Scale: {scale}
"""

def load_drawing_goals(sheet_folder, sheet_name):
    """Load drawing goals data if available"""
    goals_file = sheet_folder / f"{sheet_name}_drawing_goals.json"
    if goals_file.exists():
        try:
            with open(goals_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading goals data: {e}")
            return {}
    else:
        print(f"⚠️ No goals data found for {sheet_name}")
        return {}

def determine_drawing_type(sheet_name, goals_data):
    """Determine the drawing type based on filename and goals data"""
    # Check filename first
    sheet_name_lower = sheet_name.lower()
    if "general note" in sheet_name_lower or "gen note" in sheet_name_lower:
        return "general_notes"
    elif "schedule" in sheet_name_lower:
        return "schedule"
    elif "plan" in sheet_name_lower:
        return "plan"
    # More specific matching for detail variations
    elif "detail" in sheet_name_lower or "details" in sheet_name_lower or "partition" in sheet_name_lower:
        return "detail"
    elif "elevation" in sheet_name_lower or "elevations" in sheet_name_lower:
        return "elevation"
    
    # Check drawing info if available
    if goals_data and "drawing_info" in goals_data:
        drawing_info = goals_data["drawing_info"]
        title = drawing_info.get("title", "").lower()
        
        if "general note" in title or "gen note" in title:
            return "general_notes"
        elif "schedule" in title:
            return "schedule"
        elif "plan" in title:
            return "plan"
        # More specific matching for detail variations
        elif "detail" in title or "details" in title or "partition" in title:
            return "detail"
        elif "elevation" in title or "elevations" in title or "section" in title:
            return "elevation"
    
    # Default to generic if we can't determine
    return "generic"

def validate_json(json_str):
    """Validate and fix JSON formatting issues"""
    # Remove any markdown formatting if present
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()
    
    # Remove any non-JSON leading or trailing text
    json_str = json_str.strip()
    if json_str.startswith("[") and json_str.endswith("]"):
        # Good, it's already an array
        pass
    elif json_str.startswith("{") and json_str.endswith("}"):
        # It's an object, wrap in array
        json_str = f"[{json_str}]"
    else:
        # Try to find JSON array
        match = re.search(r'\[\s*\{.*\}\s*\]', json_str, re.DOTALL)
        if match:
            json_str = match.group(0)
        else:
            # Try to find JSON object
            match = re.search(r'\{\s*".*"\s*:.*\}', json_str, re.DOTALL)
            if match:
                json_str = f"[{match.group(0)}]"
            else:
                # Return empty array if no valid JSON found
                return "[]"
    
    # Try to parse the JSON
    try:
        parsed = json.loads(json_str)
        # Return the re-serialized JSON to ensure it's correctly formatted
        return json.dumps(parsed)
    except json.JSONDecodeError:
        # If parsing fails, return an empty array
        return "[]"

def check_tile_adjacency(pos_a, pos_b):
    """
    Determine if and how two tiles are adjacent.
    
    Returns:
        str: "horizontal_right" if B is to the right of A
             "horizontal_left" if B is to the left of A
             "vertical_below" if B is below A
             "vertical_above" if B is above A
             "none" if tiles are not adjacent
    """
    # Extract coordinates
    a_x = pos_a.get("x", 0)
    a_y = pos_a.get("y", 0)
    a_width = pos_a.get("width", 0)
    a_height = pos_a.get("height", 0)
    
    b_x = pos_b.get("x", 0)
    b_y = pos_b.get("y", 0)
    b_width = pos_b.get("width", 0)
    b_height = pos_b.get("height", 0)
    
    # Check horizontal adjacency
    horizontal_overlap = (
        (a_y <= b_y + b_height) and (a_y + a_height >= b_y)
    )
    
    if horizontal_overlap:
        # B is to the right of A
        if abs(a_x + a_width - b_x) < 20:
            return "horizontal_right"
        # B is to the left of A
        if abs(b_x + b_width - a_x) < 20:
            return "horizontal_left"
    
    # Check vertical adjacency
    vertical_overlap = (
        (a_x <= b_x + b_width) and (a_x + a_width >= b_x)
    )
    
    if vertical_overlap:
        # B is below A
        if abs(a_y + a_height - b_y) < 20:
            return "vertical_below"
        # B is above A
        if abs(b_y + b_height - a_y) < 20:
            return "vertical_above"
    
    return "none"

# --- Run All Sheets ---
if __name__ == "__main__":
    for sheet_dir in TILES_DIR.iterdir():
        if sheet_dir.is_dir():
            sheet_name = sheet_dir.name
            analyze_all_tiles(sheet_dir, sheet_name)