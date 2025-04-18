import os
import json
import glob
from pathlib import Path
import re
from typing import List, Dict, Any, Optional, Tuple
import logging
import hashlib
import time
from datetime import datetime
from anthropic import Anthropic

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
class Config:
    API_KEY = os.environ.get("API_KEY", "sk-ant-api03-KeyRemoved")
    MODEL = "claude-3-7-sonnet-20250219"
    BASE_DIR = Path("/app")
    DRAWINGS_DIR = BASE_DIR / "tiles_output"
    MEMORY_STORE = BASE_DIR / "memory_store"
    QUERY_INDEX = MEMORY_STORE / "query_index.json"
    MAX_TOKENS = 4096
    SIMILARITY_THRESHOLD = 0.8
    
    @classmethod
    def configure(cls, base_dir=None):
        """Configure paths with a custom base directory"""
        if base_dir:
            cls.BASE_DIR = Path(base_dir)
            cls.DRAWINGS_DIR = cls.BASE_DIR / "tiles_output"
            cls.MEMORY_STORE = cls.BASE_DIR / "memory_store"
            cls.QUERY_INDEX = cls.MEMORY_STORE / "query_index.json"
        
        # Ensure directories exist
        cls.MEMORY_STORE.mkdir(exist_ok=True, parents=True)
        cls.DRAWINGS_DIR.mkdir(exist_ok=True, parents=True)

# Initialize Anthropic client
client = Anthropic(api_key=Config.API_KEY)

# Ensure base directory and memory store exist
Config.BASE_DIR.mkdir(exist_ok=True)
Config.MEMORY_STORE.mkdir(exist_ok=True, parents=True)

class DrawingManager:
    """Manages access to drawing data and metadata"""
    def get_drawing_analysis(self, drawing_name: str) -> List[Dict]:
        """Get all analysis data for a drawing, combining standard and specialized formats"""
        drawing_type = self.get_drawing_type(drawing_name)
        result = []
        
        # Get standard tile analysis (always check this first)
        standard_file = self.drawings_dir / drawing_name / f"{drawing_name}_tile_analysis.json"
        if standard_file.exists():
            try:
                with open(standard_file, 'r') as f:
                    result = json.load(f)
                    logger.info(f"Loaded standard tile analysis for {drawing_name}")
            except Exception as e:
                logger.error(f"Error loading standard analysis for {drawing_name}: {e}")
        
        # Check for specialized analysis files based on drawing type
        specialized_file = None
        
        if drawing_type == "elevation":
            specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_elevation_analysis.json"
        elif drawing_type == "detail":
            specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_detail_analysis.json"
        elif drawing_type == "general_notes":
            specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_general_notes_analysis.json"
        
        # Load specialized file if it exists
        if specialized_file and specialized_file.exists():
            try:
                with open(specialized_file, 'r') as f:
                    specialized_data = json.load(f)
                    # Add a marker for specialized data
                    result.append({"_type": f"{drawing_type}_specialized", "data": specialized_data})
                    logger.info(f"Loaded specialized {drawing_type} analysis for {drawing_name}")
            except Exception as e:
                logger.error(f"Error loading specialized analysis for {drawing_name}: {e}")
        
        if not result:
            logger.warning(f"No analysis files found for drawing: {drawing_name}")
        
        return result

    def get_elevation_detail_components(self, drawing_name: str) -> List[Dict]:
        """Get components from elevation/detail specialized files"""
        drawing_type = self.get_drawing_type(drawing_name)
        if drawing_type not in ["elevation", "detail"]:
            return []
        
        specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_{drawing_type}_analysis.json"
        if not specialized_file.exists():
            return []
        
        try:
            with open(specialized_file, 'r') as f:
                components = json.load(f)
                logger.info(f"Loaded {len(components)} components from {drawing_name}_{drawing_type}_analysis.json")
                return components
        except Exception as e:
            logger.error(f"Error loading components for {drawing_name}: {e}")
            return []

    def extract_elevation_detail_information(self, drawing_name: str, query: str) -> List[Dict]:
        """Extract information related to the query from elevation/detail components"""
        drawing_type = self.get_drawing_type(drawing_name)
        if drawing_type not in ["elevation", "detail"]:
            return []
        
        components = self.get_elevation_detail_components(drawing_name)
        if not components:
            return []
        
        # Filter components relevant to the query
        query_terms = [term.lower() for term in query.split()]
        relevant_components = []
        
        for component in components:
            # Extract all text fields to check against query
            component_id = component.get("component_id", "unknown")
            title = component.get("title", "")
            description = component.get("description", "")
            materials = " ".join(component.get("materials", []))
            annotations = " ".join(component.get("annotations", []))
            
            combined_text = f"{component_id} {title} {description} {materials} {annotations}".lower()
            
            if any(term in combined_text for term in query_terms):
                relevant_components.append({
                    "component_id": component_id,
                    "title": title,
                    "description": description,
                    "materials": component.get("materials", []),
                    "annotations": component.get("annotations", []),
                    "drawing": drawing_name,
                    "drawing_type": drawing_type
                })
        
        logger.info(f"Found {len(relevant_components)} relevant components in {drawing_name}")
        return relevant_components

    def __init__(self, drawings_dir=None):
        """Initialize DrawingManager with optional custom drawings directory"""
        if drawings_dir:
            self.drawings_dir = Path(drawings_dir)
        else:
            self.drawings_dir = Config.DRAWINGS_DIR
        
        self.drawings_metadata = self._load_drawings_metadata()
        logger.info(f"DrawingManager initialized with drawings directory: {self.drawings_dir}")
        
    def _load_drawings_metadata(self) -> Dict[str, Dict]:
        metadata = {}
        for drawing_dir in self.drawings_dir.glob('*'):
            if drawing_dir.is_dir():
                drawing_name = drawing_dir.name
                metadata_file = drawing_dir / f"{drawing_name}_tile_metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata[drawing_name] = json.load(f)
                            logger.info(f"Loaded metadata for drawing: {drawing_name}")
                    except Exception as e:
                        logger.error(f"Error loading metadata for {drawing_name}: {e}")
        logger.info(f"Loaded metadata for {len(metadata)} drawings")
        return metadata
    
    def get_available_drawings(self) -> List[str]:
        return list(self.drawings_metadata.keys())
    
    def get_drawing_type(self, drawing_name: str) -> str:
        # First check if type-specific analysis files exist
        if (self.drawings_dir / drawing_name / f"{drawing_name}_elevation_analysis.json").exists():
            return "elevation"
        elif (self.drawings_dir / drawing_name / f"{drawing_name}_detail_analysis.json").exists():
            return "detail"
        elif (self.drawings_dir / drawing_name / f"{drawing_name}_general_notes_analysis.json").exists():
            return "general_notes"
        
        # Then check drawing name
        drawing_name_lower = drawing_name.lower()
        if "schedule" in drawing_name_lower:
            return "schedule"
        elif "general note" in drawing_name_lower or "gen note" in drawing_name_lower:
            return "general_notes"
        elif "plan" in drawing_name_lower:
            return "plan"
        elif "elevation" in drawing_name_lower:
            return "elevation"
        elif "section" in drawing_name_lower:
            return "section"
        elif "detail" in drawing_name_lower:
            return "detail"
        
        # Then check metadata
        if drawing_name in self.drawings_metadata:
            metadata = self.drawings_metadata[drawing_name]
            if "drawing_info" in metadata and "title" in metadata["drawing_info"]:
                title = metadata["drawing_info"]["title"].lower()
                if "schedule" in title:
                    return "schedule"
                elif "general note" in title or "gen note" in title:
                    return "general_notes"
                elif "plan" in title:
                    return "plan"
                elif "elevation" in title:
                    return "elevation"
                elif "section" in title:
                    return "section"
                elif "detail" in title:
                    return "detail"
        
        return "generic"
    
    def get_drawing_analysis(self, drawing_name: str) -> List[Dict]:
        drawing_type = self.get_drawing_type(drawing_name)
        
        # Check for specialized analysis files first
        if drawing_type == "elevation":
            specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_elevation_analysis.json"
            if specialized_file.exists():
                try:
                    with open(specialized_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error loading elevation analysis for {drawing_name}: {e}")
        
        elif drawing_type == "detail":
            specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_detail_analysis.json"
            if specialized_file.exists():
                try:
                    with open(specialized_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error loading detail analysis for {drawing_name}: {e}")
        
        elif drawing_type == "general_notes":
            specialized_file = self.drawings_dir / drawing_name / f"{drawing_name}_general_notes_analysis.json"
            if specialized_file.exists():
                try:
                    with open(specialized_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Error loading general notes analysis for {drawing_name}: {e}")
        
        # Fall back to the standard tile analysis file
        analysis_file = self.drawings_dir / drawing_name / f"{drawing_name}_tile_analysis.json"
        if analysis_file.exists():
            try:
                with open(analysis_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading analysis for {drawing_name}: {e}")
        
        logger.warning(f"No analysis file found for drawing: {drawing_name}")
        return []
    
    def get_drawing_goals(self, drawing_name: str) -> Dict:
        goals_file = self.drawings_dir / drawing_name / f"{drawing_name}_drawing_goals.json"
        if goals_file.exists():
            try:
                with open(goals_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading goals for {drawing_name}: {e}")
                return {}
        logger.warning(f"No goals file found for drawing: {drawing_name}")
        return {}
    
    def get_legend_knowledge(self, drawing_name: str) -> Dict:
        legend_file = self.drawings_dir / drawing_name / f"{drawing_name}_legend_knowledge.json"
        if legend_file.exists():
            try:
                with open(legend_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading legend knowledge for {drawing_name}: {e}")
                return {}
        logger.warning(f"No legend knowledge file found for drawing: {drawing_name}")
        return {}
    
    def get_general_notes_knowledge(self, drawing_name: str) -> Dict:
        notes_file = self.drawings_dir / drawing_name / f"{drawing_name}_general_notes_knowledge.json"
        if notes_file.exists():
            try:
                with open(notes_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading general notes knowledge for {drawing_name}: {e}")
                return {}
        logger.warning(f"No general notes knowledge file found for drawing: {drawing_name}")
        return {}
    
    def get_elevation_knowledge(self, drawing_name: str) -> Dict:
        """Get specialized knowledge for elevation drawings"""
        elevation_file = self.drawings_dir / drawing_name / f"{drawing_name}_elevation_knowledge.json"
        if elevation_file.exists():
            try:
                with open(elevation_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading elevation knowledge for {drawing_name}: {e}")
                return {}
        logger.warning(f"No elevation knowledge file found for drawing: {drawing_name}")
        return {}
    
    def get_detail_knowledge(self, drawing_name: str) -> Dict:
        """Get specialized knowledge for detail drawings"""
        detail_file = self.drawings_dir / drawing_name / f"{drawing_name}_detail_knowledge.json"
        if detail_file.exists():
            try:
                with open(detail_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading detail knowledge for {drawing_name}: {e}")
                return {}
        logger.warning(f"No detail knowledge file found for drawing: {drawing_name}")
        return {}
    
    def process_schedule_data(self, drawing_name: str, analysis: List[Dict]) -> Dict[str, List[Dict]]:
        """Process schedule data from tiles to extract tag information.
        Returns a dictionary mapping tags to a list of possible specifications.
        """
        tag_data = {}  # Will store all data for each tag

        try:
            # First pass - collect all tag mentions
            for tile_data in analysis:
                filename = tile_data.get("filename", "unknown")
                tile_position = tile_data.get("tile_position", {})
                tile_type = tile_data.get("tile_type", "content")
                claude_response = tile_data.get("claude_response", "[]")
                
                try:
                    # Extract all text that looks like tags
                    tile_analysis = json.loads(claude_response) if isinstance(claude_response, str) else claude_response
                    
                    for item in tile_analysis:
                        if item.get("type") == "schedule_row":
                            text = item.get("text", "").strip()
                            # Look for tag patterns at the beginning of schedule rows (e.g., "C2 ...")
                            tag_match = re.match(r'^([A-Z]\d+)\s+', text)
                            if tag_match:
                                tag = tag_match.group(1)
                                if tag not in tag_data:
                                    tag_data[tag] = []
                                
                                # Store the tile position and full text
                                tag_data[tag].append({
                                    "filename": filename,
                                    "position": tile_position,
                                    "text": text,
                                    "confidence": "high" if text.startswith(tag) else "medium"
                                })
                except Exception as e:
                    logger.error(f"Error processing schedule tile {filename}: {e}")
            
            # Second pass - look for specifications using Claude for free-form extraction
            for tile_data in analysis:
                filename = tile_data.get("filename", "unknown")
                tile_position = tile_data.get("tile_position", {})
                tile_type = tile_data.get("tile_type", "content")
                
                try:
                    claude_response = tile_data.get("claude_response", "[]")
                    tile_analysis = json.loads(claude_response) if isinstance(claude_response, str) else claude_response
                    
                    for item in tile_analysis:
                        if item.get("type") == "schedule_row":
                            text = item.get("text", "").strip()
                            
                            # Use Claude to extract any specification details without hard-coded limits.
                            prompt = (
                                f"Extract any construction specification details from the following schedule row text. "
                                f"These details might include manufacturer info, product models, dimensions, materials, finishes, "
                                f"tolerances, or any other relevant specifications. Return your findings as a JSON object. "
                                f"If no specifications are found, return an empty JSON object.\n"
                                f"Text: \"{text}\""
                            )
                            try:
                                response = client.messages.create(
                                    model=Config.MODEL,
                                    max_tokens=256,
                                    temperature=0,
                                    system="Extract specification details if available.",
                                    messages=[{"role": "user", "content": prompt}]
                                )
                                extracted = json.loads(response.content[0].text)
                            except Exception as e:
                                logger.error(f"Error extracting specifications from tile {filename}: {e}")
                                extracted = {}
                            
                            if extracted:
                                # Associate the extracted specifications with any tag entry that is on a similar vertical position.
                                for tag, entries in tag_data.items():
                                    for entry in entries:
                                        entry_y = entry.get("position", {}).get("y", 0)
                                        this_y = tile_position.get("y", 0)
                                        if abs(entry_y - this_y) < 50 or "specifications" not in entry:
                                            if "specifications" not in entry:
                                                entry["specifications"] = []
                                            entry["specifications"].append({
                                                "text": text,
                                                "specifications": extracted,
                                                "filename": filename,
                                                "position": tile_position,
                                                "confidence": "auto"
                                            })
                except Exception as e:
                    logger.error(f"Error processing specification data in tile {filename}: {e}")
            
            # Create a cleaned up version for the response.
            tag_specs = {}
            for tag, entries in tag_data.items():
                tag_specs[tag] = []
                
                # Collect all specifications with their confidence.
                for entry in entries:
                    if "specifications" in entry:
                        for spec in entry["specifications"]:
                            tag_specs[tag].append({
                                "full_text": spec["text"],
                                "specifications": spec["specifications"],
                                "confidence": spec.get("confidence", "auto"),
                                "source": spec.get("filename", "unknown")
                            })
                
                # If no specifications were found, record this.
                if not tag_specs[tag]:
                    tag_specs[tag].append({
                        "full_text": "No detailed specifications found",
                        "confidence": "low",
                        "source": "missing"
                    })
                
            logger.info(f"Processed schedule data for {drawing_name}, found {len(tag_specs)} tags with specifications")
            return tag_specs
                
        except Exception as e:
            logger.error(f"Error in overall schedule processing for {drawing_name}: {e}")
            return {}

class QueryMemory:
    """Manages the storage and retrieval of query information"""
    
    def __init__(self):
        # First ensure the base directory exists
        Config.BASE_DIR.mkdir(exist_ok=True)
        # Then ensure the memory store exists
        Config.MEMORY_STORE.mkdir(exist_ok=True, parents=True)
        self.query_index = self._load_query_index()
    
    def _load_query_index(self) -> Dict[str, Dict]:
        if Config.QUERY_INDEX.exists():
            try:
                with open(Config.QUERY_INDEX, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading query index: {e}")
                return {}
        return {}
    
    def _save_query_index(self):
        try:
            with open(Config.QUERY_INDEX, 'w') as f:
                json.dump(self.query_index, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving query index: {e}")
    
    def add_query(self, query_id: str, query: str, drawings: List[str]):
        self.query_index[query_id] = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "drawings": drawings
        }
        self._save_query_index()
    
    def find_similar_queries(self, query: str) -> List[Tuple[str, float]]:
        if not self.query_index:
            return []
        previous_queries = [{"id": qid, "text": data["query"]} for qid, data in self.query_index.items()]
        
        # Use string concatenation instead of f-string to avoid format specifier issues
        try:
            prompt = "New query: \"" + query + "\"\n"
            prompt += "Previous queries:\n"
            prompt += json.dumps(previous_queries, indent=2) + "\n"
            prompt += "For each previous query, determine similarity to the new query (0 to 1).\n"
            prompt += "Return JSON array: [{\"id\": \"query_id\", \"similarity\": 0.9}, ...]"
            logger.debug(f"Generated prompt for similarity check:\n{prompt}")
        except Exception as e:
            logger.error(f"Error constructing prompt: {str(e)}")
            return []
        
        try:
            response = client.messages.create(
                model=Config.MODEL,
                max_tokens=1024,
                temperature=0,
                system="Return only valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )
            similarity_data = json.loads(re.search(r'\[.*\]', response.content[0].text, re.DOTALL).group(0))
            return [(item["id"], item["similarity"]) for item in similarity_data]
        except Exception as e:
            logger.error(f"Error finding similar queries: {e}")
            return []
    
    def get_most_similar_query(self, query: str) -> Optional[str]:
        similar_queries = self.find_similar_queries(query)
        if not similar_queries:
            return None
        similar_queries.sort(key=lambda x: x[1], reverse=True)
        if similar_queries[0][1] >= Config.SIMILARITY_THRESHOLD:
            return similar_queries[0][0]
        return None
    
    def get_query_data(self, query_id: str) -> Dict:
        return self.query_index.get(query_id, {})

class ConstructionAnalyzer:
    """Main class for analyzing construction drawings"""
    def __init__(self):
        self.drawing_manager = DrawingManager(Config.DRAWINGS_DIR)
        self.query_memory = QueryMemory()
    
    def _generate_query_id(self, query: str) -> str:
        # Combine query with current timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Includes microseconds for extra uniqueness
        unique_string = f"{query}_{timestamp}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:10]
    
    def identify_relevant_drawings(self, query: str) -> List[str]:
        available_drawings = self.drawing_manager.get_available_drawings()
        if len(available_drawings) <= 5:
            return available_drawings
        prompt = f"""
        Available drawings:
        {json.dumps(available_drawings, indent=2)}
        User query: {query}
        Respond with JSON array of relevant drawing names: ["Drawing1", "Drawing2"]
        """
        try:
            response = client.messages.create(
                model=Config.MODEL,
                max_tokens=1024,
                temperature=0,
                system="Identify relevant drawings.",
                messages=[{"role": "user", "content": prompt}]
            )
            drawings_list = json.loads(re.search(r'\[.*\]', response.content[0].text, re.DOTALL).group(0))
            return [d for d in drawings_list if d in available_drawings]
        except Exception as e:
            logger.error(f"Error identifying relevant drawings: {e}")
            return available_drawings
    
    def analyze_query(self, query: str, use_cache: bool = True) -> str:
        if use_cache:
            similar_queries = self.query_memory.find_similar_queries(query)
            if similar_queries:
                similar_query_ids = [qid for qid, similarity in similar_queries if similarity >= Config.SIMILARITY_THRESHOLD]
                if similar_query_ids:
                    # Combine data from all similar queries for Claude to review
                    combined_extractions = []
                    combined_tag_specs = {}
                    for qid in similar_query_ids:
                        query_dir = Config.MEMORY_STORE / qid
                        try:
                            with open(query_dir / "all_tag_specs.json", 'r') as f:
                                tag_specs = json.load(f)
                                for tag, specs in tag_specs.items():
                                    if tag not in combined_tag_specs:
                                        combined_tag_specs[tag] = []
                                    combined_tag_specs[tag].extend(specs)
                        except Exception as e:
                            logger.error(f"Error loading tag specs for query {qid}: {e}")
                        
                        with open(query_dir / "relevant_drawings.json", 'r') as f:
                            drawings = json.load(f)
                        for drawing_name in drawings:
                            drawing_path = query_dir / drawing_name
                            if drawing_path.exists():
                                for extraction_file in drawing_path.glob("*_extraction.txt"):
                                    try:
                                        with open(extraction_file, 'r') as f:
                                            tile_name = extraction_file.stem.replace('_extraction', '')
                                            combined_extractions.append({"tile": tile_name, "drawing": drawing_name, "extraction": f.read()})
                                    except Exception as e:
                                        logger.error(f"Error loading extraction {extraction_file}: {e}")
                    
                    # Let Claude synthesize a response from all combined data
                    prompt = f"""
                    User Query: {query}
                    Below is all relevant data from previous similar queries. Review everything and provide a comprehensive response based on all available information, integrating data where some may be missing in one source but present in another, and prioritizing the most recent or complete data where applicable.

                    **TAG SPECIFICATIONS:**
                    {json.dumps(combined_tag_specs, indent=2)}

                    **EXTRACTED DATA:**
                    """
                    for extraction in combined_extractions:
                        prompt += f"\nFrom tile {extraction['tile']} (Drawing: {extraction['drawing']}):\n{extraction['extraction']}\n"
                    
                    try:
                        response = client.messages.create(
                            model=Config.MODEL,
                            max_tokens=Config.MAX_TOKENS,
                            temperature=0.2,
                            system="You are a senior construction manager with 25+ years of experience. Provide detailed, thorough analysis based on all provided data.",
                            messages=[{"role": "user", "content": prompt}]
                        )
                        return response.content[0].text
                    except Exception as e:
                        logger.error(f"Error synthesizing combined response: {e}")
                        return f"Error: {str(e)}"
        
        query_id = self._generate_query_id(query)
        query_memory = Config.MEMORY_STORE / query_id
        query_memory.mkdir(exist_ok=True, parents=True)
        
        with open(query_memory / "query.txt", 'w') as f:
            f.write(query)
        
        relevant_drawings = self.identify_relevant_drawings(query)
        logger.info(f"Identified relevant drawings: {relevant_drawings}")
        
        self.query_memory.add_query(query_id, query, relevant_drawings)
        with open(query_memory / "relevant_drawings.json", 'w') as f:
            json.dump(relevant_drawings, f)
        
        # Process schedule data differently - build more comprehensive relationships
        all_tag_specs = {}
        all_extractions = []
        BATCH_SIZE = 10
        
        for drawing_name in relevant_drawings:
            drawing_type = self.drawing_manager.get_drawing_type(drawing_name)
            analysis = self.drawing_manager.get_drawing_analysis(drawing_name)
            goals = self.drawing_manager.get_drawing_goals(drawing_name)
            legend_knowledge = self.drawing_manager.get_legend_knowledge(drawing_name)
            
            # Get specialized knowledge based on drawing type
            general_notes_knowledge = {} if drawing_type != "general_notes" else self.drawing_manager.get_general_notes_knowledge(drawing_name)
            elevation_knowledge = {} if drawing_type != "elevation" else self.drawing_manager.get_elevation_knowledge(drawing_name)
            detail_knowledge = {} if drawing_type != "detail" else self.drawing_manager.get_detail_knowledge(drawing_name)
            
            drawing_memory = query_memory / drawing_name
            drawing_memory.mkdir(exist_ok=True)
            
            drawing_context = {
                "name": drawing_name,
                "type": drawing_type,
                "goals": goals,
                "legend_knowledge": legend_knowledge,
                "general_notes_knowledge": general_notes_knowledge,
                "elevation_knowledge": elevation_knowledge,
                "detail_knowledge": detail_knowledge
            }
            with open(drawing_memory / "context.json", 'w') as f:
                json.dump(drawing_context, f, indent=2)
            
            # Handle schedules with the new processing method
            if drawing_type == "schedule":
                logger.info(f"Processing schedule drawing: {drawing_name}")
                tag_specs = self.drawing_manager.process_schedule_data(drawing_name, analysis)
                
                # Merge with existing tag specs
                for tag, specs in tag_specs.items():
                    if tag not in all_tag_specs:
                        all_tag_specs[tag] = []
                    all_tag_specs[tag].extend(specs)
                    
                # Save these for the drawing
                with open(drawing_memory / "tag_specs.json", 'w') as f:
                    json.dump(tag_specs, f, indent=2)
            
            # Batch process tiles for raw extraction data
            for batch_start in range(0, len(analysis), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(analysis))
                batch = analysis[batch_start:batch_end]
                logger.info(f"Processing batch {batch_start + 1}-{batch_end} of {len(analysis)} tiles from {drawing_name}")
                
                prompt = ""
                for tile_index, tile_data in enumerate(batch, start=batch_start):
                    filename = tile_data.get("filename", "unknown")
                    tile_position = tile_data.get("tile_position", {})
                    tile_type = tile_data.get("tile_type", "content")
                    claude_response = tile_data.get("claude_response", "[]")
                    try:
                        tile_analysis = json.loads(claude_response) if isinstance(claude_response, str) else claude_response
                        claude_response = json.dumps(tile_analysis, indent=2)
                    except:
                        pass
                    
                    position_info = f"x={tile_position.get('x', 0)}, y={tile_position.get('y', 0)}, width={tile_position.get('width', 0)}, height={tile_position.get('height', 0)}"
                    prompt += f"""
                    User Query: {query}
                    Drawing: {drawing_name} (Type: {drawing_type})
                    Tile: {filename} ({tile_index + 1}/{len(analysis)})
                    Position: {position_info}
                    Tile Type: {tile_type}
                    Tile Analysis Data:
                    {claude_response}
                    Extract relevant information:
                    RELEVANT INFORMATION:
                    [List relevant info]
                    RELATIONSHIPS TO OTHER TILES:
                    [Note extensions to other tiles]
                    \n---\n"""
                
                try:
                    response = client.messages.create(
                        model=Config.MODEL,
                        max_tokens=2048,
                        temperature=0,
                        system="Extract relevant information only.",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    extraction = response.content[0].text
                    tile_extractions = [e.strip() for e in extraction.split("---") if e.strip()]
                    for i, tile_extraction in enumerate(tile_extractions):
                        tile_data = batch[i]
                        filename = tile_data.get("filename", "unknown")
                        tile_filename_safe = re.sub(r'[^\w\-\.]', '_', filename)
                        with open(drawing_memory / f"{tile_filename_safe}_extraction.txt", 'w') as f:
                            f.write(tile_extraction)
                        logger.info(f"Processed tile {filename} from {drawing_name}")
                        all_extractions.append({"tile": filename, "drawing": drawing_name, "extraction": tile_extraction})
                except Exception as e:
                    logger.error(f"Error processing batch {batch_start + 1}-{batch_end} from {drawing_name}: {e}")
                    # Fallback to original single-tile processing for this batch
                    for tile_index, tile_data in enumerate(batch, start=batch_start):
                        filename = tile_data.get("filename", "unknown")
                        tile_position = tile_data.get("tile_position", {})
                        tile_type = tile_data.get("tile_type", "content")
                        claude_response = tile_data.get("claude_response", "[]")
                        try:
                            tile_analysis = json.loads(claude_response) if isinstance(claude_response, str) else claude_response
                            claude_response = json.dumps(tile_analysis, indent=2)
                        except:
                            pass
                        
                        position_info = f"x={tile_position.get('x', 0)}, y={tile_position.get('y', 0)}, width={tile_position.get('width', 0)}, height={tile_position.get('height', 0)}"
                        fallback_prompt = f"""
                        User Query: {query}
                        Drawing: {drawing_name} (Type: {drawing_type})
                        Tile: {filename} ({tile_index + 1}/{len(analysis)})
                        Position: {position_info}
                        Tile Type: {tile_type}
                        Tile Analysis Data:
                        {claude_response}
                        Extract relevant information:
                        RELEVANT INFORMATION:
                        [List relevant info]
                        RELATIONSHIPS TO OTHER TILES:
                        [Note extensions to other tiles]
                        """
                        try:
                            fallback_response = client.messages.create(
                                model=Config.MODEL,
                                max_tokens=2048,
                                temperature=0,
                                system="Extract relevant information only.",
                                messages=[{"role": "user", "content": fallback_prompt}]
                            )
                            extraction = fallback_response.content[0].text
                            tile_filename_safe = re.sub(r'[^\w\-\.]', '_', filename)
                            with open(drawing_memory / f"{tile_filename_safe}_extraction.txt", 'w') as f:
                                f.write(extraction)
                            logger.info(f"Fallback: Processed tile {filename} from {drawing_name}")
                            all_extractions.append({"tile": filename, "drawing": drawing_name, "extraction": extraction})
                        except Exception as e:
                            logger.error(f"Fallback error processing tile {filename}: {e}")
        
        # Save the comprehensive tag specifications to the memory store
        with open(query_memory / "all_tag_specs.json", 'w') as f:
            json.dump(all_tag_specs, f, indent=2)
        
        # Check if the processed data is sufficient for the query
        if all_tag_specs:
            query_lower = query.lower()
            tag_pattern = r'([A-Z]\d+)'
            tag_matches = re.findall(tag_pattern, query)
            
            if tag_matches:
                # The query is asking about specific tags
                queried_tag = tag_matches[0]
                if queried_tag in all_tag_specs and len(all_tag_specs[queried_tag]) > 0:
                    logger.info(f"Found specifications for queried tag {queried_tag}")
                    sufficiency = "SUFFICIENT"
                else:
                    logger.info(f"No specifications found for queried tag {queried_tag}")
                    sufficiency = "NOT SUFFICIENT"
            else:
                # General query, check if we have any good data
                general_tags = list(all_tag_specs.keys())
                if general_tags:
                    logger.info(f"Found {len(general_tags)} tag specifications for general query")
                    sufficiency = "SUFFICIENT"
                else:
                    logger.info("No tag specifications found for general query")
                    sufficiency = "NOT SUFFICIENT"
            
            with open(query_memory / "sufficiency.txt", 'w') as f:
                f.write(sufficiency)
        
        return self.synthesize_final_response(query, query_id)
    
    def synthesize_final_response(self, query: str, query_id: str) -> str:
        query_memory = Config.MEMORY_STORE / query_id
        
        try:
            with open(query_memory / "relevant_drawings.json", 'r') as f:
                relevant_drawings = json.load(f)
        except Exception as e:
            logger.error(f"Error loading relevant drawings: {e}")
            return f"Error: Could not load relevant drawings: {str(e)}"
        
        # Load comprehensive tag specifications
        try:
            with open(query_memory / "all_tag_specs.json", 'r') as f:
                all_tag_specs = json.load(f)
        except Exception as e:
            logger.error(f"Error loading tag specifications: {e}")
            all_tag_specs = {}
        
        drawing_contexts = []
        for drawing_name in relevant_drawings:
            context_file = query_memory / drawing_name / "context.json"
            if context_file.exists():
                try:
                    with open(context_file, 'r') as f:
                        drawing_contexts.append(json.load(f))
                except Exception as e:
                    logger.error(f"Error loading context for {drawing_name}: {e}")
        
        all_legend_knowledge = {c["name"]: c["legend_knowledge"] for c in drawing_contexts if c.get("legend_knowledge")}
        all_general_notes = {c["name"]: c["general_notes_knowledge"] for c in drawing_contexts if c.get("general_notes_knowledge")}
        
        # Extract elevation/detail information
        elevation_detail_components = []
        for drawing_name in relevant_drawings:
            drawing_type = self.drawing_manager.get_drawing_type(drawing_name)
            if drawing_type in ["elevation", "detail"]:
                components = self.drawing_manager.extract_elevation_detail_information(drawing_name, query)
                elevation_detail_components.extend(components)
        
        extraction_data = {}
        for drawing_name in relevant_drawings:
            drawing_path = query_memory / drawing_name
            if drawing_path.exists():
                extraction_data[drawing_name] = []
                for extraction_file in drawing_path.glob("*_extraction.txt"):
                    try:
                        with open(extraction_file, 'r') as f:
                            tile_name = extraction_file.stem.replace('_extraction', '')
                            extraction_data[drawing_name].append({"tile": tile_name, "extraction": f.read()})
                    except Exception as e:
                        logger.error(f"Error loading extraction {extraction_file}: {e}")
        
        prompt = f"""
        You are a senior construction manager with 25+ years of experience across all disciplines.
        Answer this query: {query}

        **INSTRUCTIONS:**
        - Explicitly connect keynote numbers (e.g., "1") found in drawing tiles to their definitions in legend data (e.g., "1: PROVIDE 5/8\" GYPSUM BOARD") when present, stating both the number and its meaning clearly.
        - Analyze ONLY data relevant to the query from the provided drawings.
        - Focus on all relevant elements from the drawings including tags, specifications, dimensions, annotations, and contextual information related to the query.
        - Use reasoning to connect data efficiently,and in your response be verbose and include extra information that may be of use for construction managers.
        - Provide thorough explanations including context, implications for construction, and relevant industry knowledge
        - If there appears to be any inconsistencies, and/or ambiguities when analyzing information to answer queries, be sure to note these in your responses and provide the reasons.
        - When discussing specifications, explain why they matter and how they affect installation or performance
        - For queries asking about specific schedule tags (e.g., "specifications for C2" for a finish schedule):
        - Below you will see extracted tag specifications in JSON format
        - For tags that have multiple possible specifications:
            1. Acknowledge this ambiguity in your response
            2. Present all possible variations clearly
            3. Assess which specification is most likely correct based on confidence scores and consistency
            4. Do not mention anything about "fragmented data," "tiles," or explain why there might be ambiguity
            5. Simply present the information in a professional manner
        
        - When you see a schedule tag (like 'C2' or 'H1'), use the tag exactly as it appears in the data
        - Provide a concise but comprehensive answer that acknowledges both what is known and any uncertainty

        **TAG SPECIFICATIONS:**
        {json.dumps(all_tag_specs, indent=2)}
        """
        
        # Only include elevation/detail components if they exist
        if elevation_detail_components:
            prompt += f"""
        **ELEVATION/DETAIL COMPONENTS:**
        {json.dumps(elevation_detail_components, indent=2)}
        """
        
        prompt += """
        Below is relevant data from the drawings:
        """
        
        # Add filtered extraction data
        for drawing_name in relevant_drawings:
            drawing_type = self.drawing_manager.get_drawing_type(drawing_name)
            prompt += f"\n\n--- DATA FROM {drawing_name} (TYPE: {drawing_type}) ---\n"
            
            # Add any relevant extracted information
            query_lower = query.lower()
            for extraction in extraction_data.get(drawing_name, []):
                text = extraction["extraction"].lower()
                if any(term in text for term in query_lower.split()):
                    prompt += f"\nFrom tile {extraction['tile']}:\n{extraction['extraction']}\n"
        
        if all_legend_knowledge:
            prompt += "\n\n--- LEGEND INFORMATION ---\n"
            query_lower = query.lower()
            for drawing_name, legend in all_legend_knowledge.items():
                if "specific_tags" in legend:
                    for tag, info in legend["specific_tags"].items():
                        desc = info.get("description", "").lower()
                        if any(term in desc for term in query_lower.split()):
                            prompt += f"- {tag}: {info.get('description', '')}\n"
        
        if all_general_notes:
            prompt += "\n\n--- GENERAL NOTES ---\n"
            query_lower = query.lower()
            for drawing_name, notes in all_general_notes.items():
                if "critical_requirements" in notes:
                    for req in notes["critical_requirements"]:
                        text = req.get("text", "").lower()
                        if any(term in text for term in query_lower.split()):
                            prompt += f"- {req.get('text', '')}\n"
        
        prompt += "\nProvide a concise answer based on the filtered data above."
        
        try:
            response = client.messages.create(
                model=Config.MODEL,
                max_tokens=Config.MAX_TOKENS,
                temperature=0.2,
                system="You are a senior construction manager with 25+ years of experience. Provide detailed, thorough analysis with examples and implications whenever possible. Explain technical terms in a way that adds value for both experts and non-experts.",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error synthesizing response: {e}")
            return f"Error: {str(e)}"

def simple_cli():
    analyzer = ConstructionAnalyzer()
    print("=== Construction Drawing Analyzer ===")
    print(f"Available drawings: {analyzer.drawing_manager.get_available_drawings()}")
    
    while True:
        query = input("\nEnter your question (or 'exit' to quit): ")
        if query.lower() == "exit":
            break
        use_cache = not query.lower().startswith("force:")
        if not use_cache:
            query = query[6:].strip()
            print("Forcing new analysis...")
        print("\nAnalyzing drawings...")
        start_time = time.time()
        response = analyzer.analyze_query(query, use_cache=use_cache)
        end_time = time.time()
        print(f"\n=== Analysis Result (took {end_time - start_time:.2f} seconds) ===")
        print(response)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response_path = Config.MEMORY_STORE / f"response_{timestamp}.txt"
        with open(response_path, 'w') as f:
            f.write(f"QUERY: {query}\n\n{response}")
        print(f"\nResponse saved to: {response_path}")

if __name__ == "__main__":
    simple_cli()
