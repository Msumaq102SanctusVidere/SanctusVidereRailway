from transformers import pipeline
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
from pathlib import Path
import json
import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import your ConstructionAnalyzer class
try:
    from modules.construction_drawing_analyzer_rev2_wow_rev6 import ConstructionAnalyzer, Config
except ImportError:
    logger.error("modules/construction_drawing_analyzer_rev2_wow_rev6.py not found. Make sure you're in the right directory.")
    sys.exit(1)

class ConstructionAnalyzerGUI:
    def __init__(self, root):
        """Initialize the GUI with transformer for smart filtering"""
        self.root = root
        self.root.title("Construction Drawing Analyzer 1.0 by Sanctus Videre")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.configure(bg="#1a0033")  # Deep purple-black cyberpunk base
        
        # Initialize analyzer with error handling
        try:
            self.analyzer = ConstructionAnalyzer()
            self.available_drawings = self.analyzer.drawing_manager.get_available_drawings()
            logger.info(f"Initialized analyzer with {len(self.available_drawings)} drawings")
        except Exception as e:
            logger.error(f"Error initializing analyzer: {str(e)}")
            messagebox.showerror("Initialization Error", f"Error initializing analyzer: {str(e)}")
            self.available_drawings = []
        
        # Initialize lightweight transformer (DistilBERT) with GPU support
        try:
            import torch
            device = 0 if torch.cuda.is_available() else -1  # Use GPU if available, else CPU
            self.intent_classifier = pipeline("text-classification", 
                                            model="distilbert-base-uncased", 
                                            device=device, 
                                            top_k=None)
            logger.info(f"Loaded DistilBERT for intent filtering on {'GPU' if device == 0 else 'CPU'}")
        except Exception as e:
            logger.warning(f"Failed to load transformer: {e}. Using basic filtering.")
            self.intent_classifier = None
        
        # Create and set up the main frame with a resizable PanedWindow
        self.main_frame = ttk.Frame(root, style="Cyber.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure cyberpunk style
        style = ttk.Style()
        style.configure("Cyber.TFrame", background="#1a0033")
        style.configure("Cyber.TLabel", background="#1a0033", foreground="#00ffcc", font=("Orbitron", 16, "bold"))
        style.configure("Cyber.TButton", background="#00ffcc", foreground="#1a0033")
        style.configure("Cyber.TCheckbutton", background="#1a0033", foreground="#66ffcc")
        style.configure("Cyber.Horizontal.TProgressbar", troughcolor="#1a0033", background="#ff007f")
        style.configure("Cyber.TLabelframe.Label", background="#00ffcc", foreground="#1a0033", font=("Orbitron", 10, "bold"), padding=3)
        
        # Create a PanedWindow for resizable boundary
        paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Create left panel for drawings
        left_frame = ttk.Frame(paned_window, style="Cyber.TFrame", width=250)
        paned_window.add(left_frame, weight=1)  # Weight allows resizing
        
        # Create right panel for query, controls, and results
        right_frame = ttk.Frame(paned_window, style="Cyber.TFrame")
        paned_window.add(right_frame, weight=3)  # Give more initial weight to right frame
        
        # Create header in right frame
        header_frame = ttk.Frame(right_frame, style="Cyber.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Construction Drawing Analyzer 1.0 by Sanctus Videre", 
                style="Cyber.TLabel").pack(side=tk.LEFT)
        
        # Create drawings list frame with scrollbar in left panel
        drawings_frame = ttk.LabelFrame(left_frame, text="Available Drawings", style="Cyber.TFrame")
        drawings_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(drawings_frame, bg="#1a0033", highlightthickness=0)
        scrollbar = ttk.Scrollbar(drawings_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.drawings_list_frame = ttk.Frame(canvas, style="Cyber.TFrame")
        
        self.drawings_list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.create_window((0, 0), window=self.drawings_list_frame, anchor="nw")
        
        # Create checkboxes for each drawing
        self.drawing_vars = {}
        self.populate_drawings_list()
        
        # Query input in right frame
        query_frame = ttk.LabelFrame(right_frame, text="Query", style="Cyber.TFrame")
        query_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.query_text = scrolledtext.ScrolledText(query_frame, height=4, wrap=tk.WORD, bg="#1b3a4b", fg="#ffffff", insertbackground="#ff007f")
        self.query_text.pack(fill=tk.X, padx=5, pady=5)
    
        # Controls frame in right frame
        self.controls_frame = ttk.Frame(right_frame, style="Cyber.TFrame")
        self.controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.force_new_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.controls_frame, text="Force new analysis (ignore cache)", 
                        variable=self.force_new_var, style="Cyber.TCheckbutton").pack(side=tk.LEFT, padx=(0, 10))
        
        self.select_all_var = tk.BooleanVar(value=False)
        self.select_all_checkbox = ttk.Checkbutton(self.controls_frame, text="Select All Drawings", 
                                                variable=self.select_all_var, 
                                                command=self.toggle_select_all, style="Cyber.TCheckbutton")
        self.select_all_checkbox.pack(side=tk.LEFT, padx=(0, 10))
        
        self.analyze_button = ttk.Button(self.controls_frame, text="Analyze Drawings", 
                                        command=self.start_analysis, style="Cyber.TButton")
        self.analyze_button.pack(side=tk.RIGHT)
        
        self.stop_button = ttk.Button(self.controls_frame, text="Stop Analysis", 
                                    command=self.stop_analysis, state=tk.DISABLED, style="Cyber.TButton")
        self.stop_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(right_frame, variable=self.progress_var, 
                                        mode='indeterminate', style="Cyber.Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Results
        results_frame = ttk.LabelFrame(right_frame, text="Analysis Results", style="Cyber.TFrame")
        results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, bg="#1b3a4b", fg="#ffffff", insertbackground="#00ffcc")
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(right_frame, textvariable=self.status_var, 
                            relief=tk.SUNKEN, anchor=tk.W, background="#1a0033", foreground="#00ffcc")
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.is_running = False
        self.analysis_thread = None
        self.load_welcome_message()
        
        # Add a protocol handler for window closing to ensure threads are terminated
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_closing(self):
        """Handle window closing event to ensure threads are terminated"""
        if self.is_running:
            self.is_running = False
            # Wait briefly for threads to register the stop flag
            time.sleep(0.5)
        self.root.destroy()
        
    def smart_filter_query(self, query):
        """Use DistilBERT to refine vague queries"""
        if not self.intent_classifier:
            return query
        
        intent_map = {
            "POSITIVE": ["finish", "floor", "ceiling", "wall", "spec", "tile"],
            "NEUTRAL": ["area", "room", "space", "where"],
        }
        
        try:
            result = self.intent_classifier(query)[0]
            top_label = max(result, key=lambda x: x['score'])['label']
            query_lower = query.lower()
            
            areas = ["lab", "restroom", "office", "lobby", "conference"]
            area = next((a for a in areas if a in query_lower), "")
            
            if top_label in intent_map and area:
                intent_words = intent_map.get(top_label, [""])
                return f"{intent_words[0]} for {area} areas"
            return query
        except Exception as e:
            logger.error(f"Transformer error: {e}")
            return query

    def run_analysis(self, query, selected_drawings, use_cache):
        """Run the analysis with smart filtering"""
        try:
            start_time = time.time()
            
            # Monkey patch the analyzer's methods to check the stop flag
            self.patch_analyzer_methods()
            
            # Check if analysis has been stopped before starting
            if not self.is_running:
                self.root.after(0, self.show_error, "Analysis stopped by user.")
                return
            
            refined_query = self.smart_filter_query(query)
            modified_query = f"[DRAWINGS:{','.join(selected_drawings)}] {refined_query}"
            logger.info(f"Refined query: {modified_query}")
            
            # Process in smaller batches if multiple drawings selected
            if len(selected_drawings) > 3:
                response_parts = []
                batch_size = 3
                for i in range(0, len(selected_drawings), batch_size):
                    if not self.is_running:
                        self.root.after(0, self.show_error, "Analysis stopped by user.")
                        return
                    
                    batch = selected_drawings[i:i+batch_size]
                    batch_query = f"[DRAWINGS:{','.join(batch)}] {refined_query}"
                    logger.info(f"Processing batch {i//batch_size + 1}: {batch}")
                    
                    # Update status
                    self.root.after(0, self.update_status, f"Processing drawings {i+1}-{min(i+batch_size, len(selected_drawings))} of {len(selected_drawings)}...")
                    
                    batch_response = self.analyzer.analyze_query(batch_query, use_cache=use_cache)
                    response_parts.append(batch_response)
                
                # Combine responses
                response = "\n\n".join(response_parts)
            else:
                response = self.analyzer.analyze_query(modified_query, use_cache=use_cache)
            
            if not self.is_running:
                response = "Analysis stopped by user."
                
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"Analysis completed in {elapsed_time:.2f} seconds")
            
            self.root.after(0, self.update_results, response, elapsed_time)
        except Exception as e:
            logger.error(f"Error analyzing query: {str(e)}", exc_info=True)
            error_message = "Analysis failed due to an error. This could be due to API overload or connectivity issues. Please try again later."
            if not self.is_running:
                error_message = "Analysis stopped by user."
            self.root.after(0, self.show_error, error_message)

    def patch_analyzer_methods(self):
        """Monkey patch analyzer methods to respect the stop flag"""
        # Store original methods
        if not hasattr(self.analyzer, '_original_analyze_query'):
            self.analyzer._original_analyze_query = self.analyzer.analyze_query
            
            # Create patched method that checks the stop flag
            def patched_analyze_query(self_analyzer, query, use_cache=True):
                # Check if GUI wants to stop
                if not self.is_running:
                    logger.info("Analysis stopped by user, aborting analyze_query")
                    return "Analysis stopped by user."
                return self.analyzer._original_analyze_query(query, use_cache)
            
            # Replace the method
            self.analyzer.analyze_query = patched_analyze_query.__get__(self.analyzer, type(self.analyzer))
            
        # You may need to patch other methods that do long-running operations
        # like process_drawings, extract_information, etc. depending on your implementation

    def update_status(self, message):
        """Update the status bar message"""
        self.status_var.set(message)
        self.results_text.insert(tk.END, f"{message}\n")
        self.results_text.see(tk.END)

    def populate_drawings_list(self):
        """Populate the list of drawings with checkboxes vertically"""
        for widget in self.drawings_list_frame.winfo_children():
            widget.destroy()
        
        for i, drawing in enumerate(sorted(self.available_drawings)):
            row = i
            col = 0
            
            var = tk.BooleanVar(value=False)
            self.drawing_vars[drawing] = var
            
            frame = ttk.Frame(self.drawings_list_frame)
            frame.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            
            cb = ttk.Checkbutton(frame, text=drawing, variable=var)
            cb.pack(anchor=tk.W)
    
    def toggle_select_all(self):
        """Toggle all drawing checkboxes based on Select All state"""
        value = self.select_all_var.get()
        for var in self.drawing_vars.values():
            var.set(value)
    
    def load_welcome_message(self):
        """Load a welcome message in the results area"""
        welcome_message = """Welcome to the Construction Drawing Analyzer!

This tool helps you analyze construction drawings by asking natural language questions.

Instructions:
1. Select one or more drawings to analyze using the checkboxes
   - Note: Selecting more drawings will increase the analysis time, especially if the memory store is empty.
2. Type your question in the query box
3. Click "Analyze Drawings" to process your query
   - You can stop the analysis at any time by clicking "Stop Analysis" if it takes too long.
   - If results seem incomplete, use "Force new analysis" to reprocess all drawings.

Example queries:
- "What are the finishes specified for room 101?"
- "What type of doors are used in the lobby?"
- "What are the wall types shown in the drawings?"
- "What are the critical inspection requirements noted in the general notes?"

The analysis results will appear in this area.
"""
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, welcome_message)
    
    def get_selected_drawings(self):
        """Get a list of selected drawings"""
        return [drawing for drawing, var in self.drawing_vars.items() if var.get()]
    
    def start_analysis(self):
        """Start the analysis process in a separate thread"""
        query = self.query_text.get(1.0, tk.END).strip()
        if not query:
            messagebox.showwarning("Empty Query", "Please enter a query to analyze.")
            return
        
        selected_drawings = self.get_selected_drawings()
        if not selected_drawings:
            messagebox.showwarning("No Drawings Selected", "Please select at least one drawing to analyze.")
            return
        
        # If already running, stop first
        if self.is_running:
            self.stop_analysis()
            # Wait a moment for things to clean up
            time.sleep(0.5)
        
        self.analyze_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.query_text.config(state=tk.DISABLED)
        
        self.progress_var.set(0)
        self.progress_bar.start(10)
        self.status_var.set("Analyzing... Please wait.")
        
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Analyzing your query...\n\n")
        self.results_text.update()
        
        use_cache = not self.force_new_var.get()
        
        self.is_running = True
        
        # Terminate any existing thread before starting a new one
        if self.analysis_thread and self.analysis_thread.is_alive():
            logger.warning("Previous analysis thread still running, forcing stop...")
            self.is_running = False
            time.sleep(0.5)  # Give thread time to recognize stop flag
        
        self.is_running = True  # Reset the flag for the new analysis
        self.analysis_thread = threading.Thread(
            target=self.run_analysis,
            args=(query, selected_drawings, use_cache)
        )
        self.analysis_thread.daemon = True
        self.analysis_thread.start()
    
    def stop_analysis(self):
        """Stop the ongoing analysis"""
        if not self.is_running:
            return
            
        logger.info("Stopping analysis...")
        self.is_running = False
        self.status_var.set("Stopping analysis...")
        self.results_text.insert(tk.END, "Stopping analysis...\n\n")
        self.results_text.update()
        
        # Wait a bit to ensure threads have time to check the flag
        start_time = time.time()
        while self.analysis_thread and self.analysis_thread.is_alive() and time.time() - start_time < 3:
            # Update UI while waiting
            self.root.update()
            time.sleep(0.1)
        
        self.progress_bar.stop()
        self.analyze_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.query_text.config(state=tk.NORMAL)
        self.status_var.set("Analysis stopped.")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Analysis stopped by user.\n\n")
    
    def update_results(self, response, elapsed_time):
        """Update the results text area with the analysis results"""
        if not self.is_running:
            return
            
        self.progress_bar.stop()
        self.analyze_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.query_text.config(state=tk.NORMAL)
        
        self.status_var.set(f"Analysis completed in {elapsed_time:.2f} seconds")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, response)
        self.results_text.insert(tk.END, f"\n\n---\nAnalysis completed in {elapsed_time:.2f} seconds")
    
    def show_error(self, error_message):
        """Show an error message in the results area"""
        self.progress_bar.stop()
        self.analyze_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.query_text.config(state=tk.NORMAL)
        self.status_var.set("Analysis failed. See error message for details.")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, f"ERROR: {error_message}")

def patch_analyzer():
    """Monkey patch the ConstructionAnalyzer to respect selected drawings"""
    original_identify_relevant_drawings = ConstructionAnalyzer.identify_relevant_drawings
    
    def patched_identify_relevant_drawings(self, query):
        if query.startswith("[DRAWINGS:"):
            end_bracket = query.find("]")
            if end_bracket > 0:
                drawings_str = query[10:end_bracket]
                selected_drawings = [d.strip() for d in drawings_str.split(",")]
                self._original_query = query[end_bracket + 1:].strip()
                available_drawings = self.drawing_manager.get_available_drawings()
                return [d for d in selected_drawings if d in available_drawings]
        return original_identify_relevant_drawings(self, query)
    
    ConstructionAnalyzer.identify_relevant_drawings = patched_identify_relevant_drawings

def main():
    patch_analyzer()
    root = tk.Tk()
    try:
        root.iconbitmap("construction_icon.ico")
    except:
        logger.warning("No icon file found, using default icon")
    app = ConstructionAnalyzerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()