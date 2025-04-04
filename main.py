import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import json
import os
import subprocess
import logging
from pathlib import Path
import threading
import queue
import time
import openai
import deepl
import pptx
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR, MSO_COLOR_TYPE

# --- Constants ---
SUPPORTED_LANGUAGES_FILE = "supported_languages.json"
ELEVENLABS_CONFIG_FILE = "elevenlabs_config.json"
API_KEYS_FILE = "api_keys.json"

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ConfigManager:
    """Manages configuration files for the application."""

    def __init__(self, languages_file=SUPPORTED_LANGUAGES_FILE,
                 elevenlabs_file=ELEVENLABS_CONFIG_FILE, api_keys_file=API_KEYS_FILE):
        self.languages_file = Path(languages_file)
        self.elevenlabs_file = Path(elevenlabs_file)
        self.api_keys_file = Path(api_keys_file)

        self.languages = self.load_json(self.languages_file)
        self.elevenlabs_config = self.load_json(self.elevenlabs_file)
        self.api_keys = self.load_json(self.api_keys_file)

    def load_json(self, file_path: Path):
        """Loads JSON data from a file."""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.warning(f"Config file not found: {file_path}. Creating a default.")
            return {}
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {file_path}. Please check the file for errors.")
            return {}

    def save_json(self, data, file_path: Path):
        """Saves JSON data to a file."""
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving to {file_path}: {e}")

    def get_languages(self):
        return self.languages

    def get_elevenlabs_config(self):
        return self.elevenlabs_config

    def get_api_keys(self):
        return self.api_keys

    def save_languages(self):
        self.save_json(self.languages, self.languages_file)
    
    def save_elevenlabs_config(self):
        self.save_json(self.elevenlabs_config, self.elevenlabs_file)

    def save_api_keys(self):
        """Saves the current API keys to the configuration file."""
        try:
            self.save_json(self.api_keys, self.api_keys_file)
            logging.info("API keys saved successfully")
        except Exception as e:
            logging.error(f"Error saving API keys: {e}")
class ToolBase:
    """Base class for all tools in the application."""
    
    def __init__(self, master, config_manager, progress_queue):
        """Initialize the tool base class."""
        self.master = master
        self.config_manager = config_manager
        self.progress_queue = progress_queue
        self.input_paths = []
        self.output_path = None
        self.supported_languages = self.config_manager.get_languages()
        
        # Add selection mode variable
        self.selection_mode = tk.StringVar(value="file")  # "file" or "folder"
        
        # Define supported extensions for the tool (to be overridden by child classes)
        self.supported_extensions = set()
        
        # Initialize display attributes
        self.input_paths_display = None
        self.output_path_display = None

        self.stop_flag = threading.Event()
        self.processing_thread = None

    def stop_processing(self):
        """Signals the processing to stop."""
        if self.stop_flag:
            self.stop_flag.set()
            self.send_progress_update("Stopping processing... Please wait.")
            logging.info("Stop processing requested")

    def create_selection_mode_controls(self, parent_frame):
        """Creates radio buttons for selection mode."""
        mode_frame = ttk.LabelFrame(parent_frame, text="Selection Mode")
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Single File", 
                       variable=self.selection_mode, 
                       value="file").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Folder (Recursive)", 
                       variable=self.selection_mode, 
                       value="folder").pack(side=tk.LEFT, padx=10)

    def select_input_paths(self):
        """Opens a dialog to select input files or directory based on mode."""
        if self.selection_mode.get() == "folder":
            path = filedialog.askdirectory(title="Select Input Directory")
            if path:
                self.input_paths = [Path(path)]
                self.update_input_display()
                return True
        else:
            paths = filedialog.askopenfilenames(
                title="Select Input Files",
                filetypes=[("Supported Files", 
                          [f"*{ext}" for ext in self.supported_extensions])]
            )
            if paths:
                self.input_paths = [Path(p) for p in paths]
                self.update_input_display()
                return True
        return False

    def select_output_path(self):
        """Opens a dialog to select an output directory."""
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_path = Path(path)
            logging.info(f"Output path selected: {self.output_path}")
            self.update_output_display()
            return True
        return False

    def set_same_as_input(self):
        """Sets the output path to be the same as the input path."""
        if self.input_paths:
            if self.selection_mode.get() == "folder":
                self.output_path = self.input_paths[0]
            else:
                self.output_path = self.input_paths[0].parent
            logging.info(f"Output path set to same as input: {self.output_path}")
            self.update_output_display()
            return True
        else:
            messagebox.showwarning("Warning", "Please select input paths first.")
            return False

    def update_input_display(self):
        """Updates the input paths display."""
        if hasattr(self, 'input_paths_display'):
            self.input_paths_display.configure(state='normal')
            self.input_paths_display.delete(1.0, tk.END)
            for path in self.input_paths:
                self.input_paths_display.insert(tk.END, f"{path}\n")
            self.input_paths_display.configure(state='disabled')

    def update_output_display(self):
        """Updates the output path display."""
        if hasattr(self, 'output_path_display'):
            self.output_path_display.configure(state='normal')
            self.output_path_display.delete(1.0, tk.END)
            if self.output_path:
                self.output_path_display.insert(tk.END, str(self.output_path))
            self.output_path_display.configure(state='disabled')

    def get_all_files_recursive(self, directory: Path) -> list:
        """Recursively gets all supported files from directory."""
        files = []
        try:
            for item in directory.rglob("*"):
                if item.is_file() and item.suffix.lower() in self.supported_extensions:
                    files.append(item)
        except Exception as e:
            self.send_progress_update(f"Error scanning directory {directory}: {e}")
        return sorted(files)  # Sort files for consistent processing order

    def process_paths(self):
        """Enhanced process_paths method with stop functionality."""
        if not self.input_paths:
            messagebox.showerror("Error", "No input paths selected.")
            return

        if self.output_path is None:
            result = messagebox.askyesno(
                "Question", 
                "No output path selected. Output to same directory as input?"
            )
            if result:
                if not self.set_same_as_input():
                    return
            else:
                messagebox.showinfo("Info", "Processing cancelled.")
                return

        # Reset stop flag before starting new processing
        self.stop_flag.clear()
        
        # Store thread reference for stopping
        self.processing_thread = threading.Thread(
            target=self._process_paths_threaded, 
            daemon=True
        )
        self.processing_thread.start()

    def _process_paths_threaded(self):
        """Enhanced threaded processing with stop functionality."""
        try:
            self.before_processing()
            
            files_to_process = []
            if self.selection_mode.get() == "folder":
                for input_path in self.input_paths:
                    files_to_process.extend(self.get_all_files_recursive(input_path))
            else:
                files_to_process = self.input_paths

            total_files = len(files_to_process)
            self.send_progress_update(f"Found {total_files} files to process")

            for index, file_path in enumerate(files_to_process, 1):
                # Check if processing should stop
                if self.stop_flag.is_set():
                    self.send_progress_update("Processing stopped by user")
                    return

                try:
                    if self.selection_mode.get() == "folder":
                        relative_path = file_path.parent.relative_to(self.input_paths[0])
                        output_dir = self.output_path / relative_path
                    else:
                        output_dir = self.output_path

                    output_dir.mkdir(parents=True, exist_ok=True)

                    self.send_progress_update(
                        f"Processing file {index}/{total_files}: {file_path.name}"
                    )
                    self.process_file(file_path, output_dir)

                except Exception as e:
                    self.send_progress_update(
                        f"Error processing {file_path.name}: {str(e)}"
                    )
                    logging.exception(f"Error processing {file_path}")

            self.after_processing()

        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.send_progress_update(error_msg)
            logging.exception(error_msg)
        finally:
            self.stop_flag.clear()
            self.processing_thread = None
            self.send_progress_update("Processing complete")


    def send_progress_update(self, message: str):
        """Sends a progress update message to the GUI."""
        self.progress_queue.put(message)

    def before_processing(self):
        """Hook for pre-processing setup."""
        pass

    def after_processing(self):
        """Hook for post-processing cleanup."""
        pass

    def process_file(self, input_file: Path, output_dir: Path):
        """Abstract method for processing a single file."""
        raise NotImplementedError("Subclasses must implement process_file()")

    def handle_drop(self, event):
        """Handles drag and drop events."""
        files = event.data.split()
        
        # Filter files based on selection mode and supported extensions
        if self.selection_mode.get() == "folder":
            self.input_paths = [Path(f) for f in files if Path(f).is_dir()]
        else:
            self.input_paths = [
                Path(f) for f in files 
                if Path(f).is_file() and Path(f).suffix.lower() in self.supported_extensions
            ]
        
        if self.input_paths:
            logging.info(f"Files dropped: {self.input_paths}")
            self.update_input_display()
        else:
            messagebox.showwarning(
                "Warning", 
                "No valid input paths found. Please check selection mode and file types."
            )

class LanguageSelectionMixin:
    """Mixin class for language selection functionality."""
    
    def create_language_selection(self):
        """Creates the language selection UI elements."""
        # Language selection frame
        self.lang_frame = ttk.LabelFrame(self.master, text="Language Selection")
        self.lang_frame.pack(fill='x', padx=5, pady=5)

        # Source language
        source_frame = ttk.Frame(self.lang_frame)
        source_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(source_frame, text="Source Language:").pack(side=tk.LEFT, padx=5)
        self.source_lang_combo = ttk.Combobox(
            source_frame, 
            textvariable=self.source_lang,
            values=list(self.supported_languages.get("source_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.source_lang_combo.pack(side=tk.LEFT, padx=5)

        # Target language
        target_frame = ttk.Frame(self.lang_frame)
        target_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Target Language:").pack(side=tk.LEFT, padx=5)
        self.target_lang_combo = ttk.Combobox(
            target_frame, 
            textvariable=self.target_lang,
            values=list(self.supported_languages.get("target_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.target_lang_combo.pack(side=tk.LEFT, padx=5)

        # Add language info tooltips
        self.add_language_tooltips()

    def add_language_tooltips(self):
        """Adds tooltips to show full language names on hover."""
        def create_tooltip(widget, text):
            def show_tooltip(event):
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                
                label = ttk.Label(tooltip, text=text, background="#ffffe0", 
                                relief='solid', borderwidth=1)
                label.pack()
                
                def hide_tooltip():
                    tooltip.destroy()
                
                widget.tooltip = tooltip
                widget.after(2000, hide_tooltip)
            
            def hide_tooltip(event):
                if hasattr(widget, 'tooltip'):
                    widget.tooltip.destroy()
            
            widget.bind('<Enter>', show_tooltip)
            widget.bind('<Leave>', hide_tooltip)

        # Add tooltips for source languages
        source_languages = self.supported_languages.get("source_languages", {})
        source_tooltip_text = "Available source languages:\n" + \
                            "\n".join(f"{code}: {name}" for code, name in source_languages.items())
        create_tooltip(self.source_lang_combo, source_tooltip_text)

        # Add tooltips for target languages
        target_languages = self.supported_languages.get("target_languages", {})
        target_tooltip_text = "Available target languages:\n" + \
                            "\n".join(f"{code}: {name}" for code, name in target_languages.items())
        create_tooltip(self.target_lang_combo, target_tooltip_text)


class PPTXTranslationTool(ToolBase, LanguageSelectionMixin):
    """Translates PPTX files from one language to another."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx'}
        
        # Language selection variables
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")
        
        self.api_key = self.config_manager.get_api_keys().get("deepl")
        if not self.api_key:
            logging.warning("DeepL API key not configured")

    def create_language_selection(self):
        """Creates the language selection UI elements."""
        # Language selection frame
        self.lang_frame = ttk.LabelFrame(self.master, text="Language Selection")
        self.lang_frame.pack(fill='x', padx=5, pady=5)

        # Source language
        source_frame = ttk.Frame(self.lang_frame)
        source_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(source_frame, text="Source Language:").pack(side=tk.LEFT, padx=5)
        self.source_lang_combo = ttk.Combobox(
            source_frame, 
            textvariable=self.source_lang,
            values=list(self.supported_languages.get("source_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.source_lang_combo.pack(side=tk.LEFT, padx=5)

        # Target language
        target_frame = ttk.Frame(self.lang_frame)
        target_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Target Language:").pack(side=tk.LEFT, padx=5)
        self.target_lang_combo = ttk.Combobox(
            target_frame, 
            textvariable=self.target_lang,
            values=list(self.supported_languages.get("target_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.target_lang_combo.pack(side=tk.LEFT, padx=5)

        # Add language info tooltips
        self.add_language_tooltips()

    def add_language_tooltips(self):
        """Adds tooltips to show full language names on hover."""
        def create_tooltip(widget, text):
            def show_tooltip(event):
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                
                label = ttk.Label(tooltip, text=text, background="#ffffe0", relief='solid', borderwidth=1)
                label.pack()
                
                def hide_tooltip():
                    tooltip.destroy()
                
                widget.tooltip = tooltip
                widget.after(2000, hide_tooltip)
            
            def hide_tooltip(event):
                if hasattr(widget, 'tooltip'):
                    widget.tooltip.destroy()
            
            widget.bind('<Enter>', show_tooltip)
            widget.bind('<Leave>', hide_tooltip)

        # Add tooltips for source languages
        source_languages = self.supported_languages.get("source_languages", {})
        source_tooltip_text = "Available source languages:\n" + \
                            "\n".join(f"{code}: {name}" for code, name in source_languages.items())
        create_tooltip(self.source_lang_combo, source_tooltip_text)

        # Add tooltips for target languages
        target_languages = self.supported_languages.get("target_languages", {})
        target_tooltip_text = "Available target languages:\n" + \
                            "\n".join(f"{code}: {name}" for code, name in target_languages.items())
        create_tooltip(self.target_lang_combo, target_tooltip_text)



    def process_file(self, input_file: Path, output_dir: Path = None):
        """Processes a single PPTX file."""
        if input_file.suffix.lower() != ".pptx":
            self.send_progress_update(f"Skipping non-PPTX file: {input_file}")
            return

        try:
            self.send_progress_update(f"Translating {input_file.name}...")
            output_file = self.translate_pptx(input_file, self.source_lang.get(), 
                                            self.target_lang.get(), output_dir)
            self.send_progress_update(f"Successfully translated: {output_file.name}")

        except Exception as e:
            error_message = f"Error translating {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)


    def translate_pptx(self, input_file: Path, source_lang: str, target_lang: str, output_dir: Path) -> Path:
        """Translates a PPTX file using DeepL API."""
        try:

            # Get and validate API key
            api_key = self.config_manager.get_api_keys().get("deepl")
            if not api_key:
                raise ValueError("DeepL API key not configured. Please add your API key in the Configuration menu.")

            # Validate API key format
            if not isinstance(api_key, str) or len(api_key.strip()) < 10:
                raise ValueError("Invalid DeepL API key format. Please check your API key.")

            translator = deepl.Translator(api_key.strip())

            # Test API connection
            try:
                translator.get_usage()
            except deepl.exceptions.AuthorizationException:
                raise ValueError("Invalid DeepL API key. Please check your API key.")
            except Exception as e:
                raise ValueError(f"Error connecting to DeepL API: {str(e)}")

            # Load the presentation
            prs = Presentation(input_file)

            # Track translation progress
            total_shapes = sum(len(slide.shapes) for slide in prs.slides)
            processed_shapes = 0

            # Translate each shape with text
            for slide_idx, slide in enumerate(prs.slides):
                if self.stop_flag.is_set():
                    raise InterruptedError("Processing stopped by user")
                self.send_progress_update(f"Processing Slide {slide_idx + 1}/{len(prs.slides)}")
                for shape_idx, shape in enumerate(slide.shapes):
                    if self.stop_flag.is_set():
                        raise InterruptedError("Processing stopped by user")

                    # Check if shape has a text frame and text
                    if not shape.has_text_frame or not shape.text_frame.text.strip():
                        processed_shapes += 1
                        continue # Skip shapes without text

                    try:
                        text_frame = shape.text_frame
                        original_paras_data = []

                        # --- Store original formatting (Modified) ---
                        for para in text_frame.paragraphs:
                            para_data = {
                                'text': para.text, # Store original text for reference if needed
                                'alignment': para.alignment,
                                'level': para.level,
                                'line_spacing': para.line_spacing,
                                'space_before': para.space_before,
                                'space_after': para.space_after,
                                'runs': []
                            }

                            for run in para.runs:
                                font = run.font
                                color_info = None
                                # --- Correctly handle color types ---
                                if font.color and hasattr(font.color, 'type'): # Check if color exists and has type
                                    if font.color.type == MSO_COLOR_TYPE.RGB:
                                        color_info = ('rgb', font.color.rgb)
                                    elif font.color.type == MSO_COLOR_TYPE.SCHEME:
                                        # Store theme color enum and brightness
                                        color_info = ('scheme', font.color.theme_color, getattr(font.color, 'brightness', 0.0))
                                    # Add elif for other MSO_COLOR_TYPE if needed (e.g., PRESET)
                                # --- End color handling ---

                                run_data = {
                                    'text': run.text, # Store original run text
                                    'font_name': font.name,
                                    'size': font.size,
                                    'bold': font.bold,
                                    'italic': font.italic,
                                    'underline': font.underline,
                                    'color_info': color_info, # Store the structured color info
                                    'language': getattr(font, 'language_id', None) # Use getattr for safety
                                }
                                para_data['runs'].append(run_data)
                            original_paras_data.append(para_data)

                        # --- Translate the text ---
                        original_full_text = text_frame.text # Get the full text once
                        if not original_full_text.strip():
                             processed_shapes += 1
                             continue # Skip if effectively empty after stripping

                        translated_text_obj = translator.translate_text(
                            original_full_text,
                            source_lang=source_lang,
                            target_lang=target_lang
                        )
                        translated_full_text = translated_text_obj.text

                        # --- Restore formatting (Modified) ---
                        text_frame.clear() # Clear existing content

                        # Heuristic: Try to map translated text back to original structure.
                        # This is complex. A simpler approach is often to apply paragraph/first run formatting.
                        # Let's try a basic approach: apply formatting paragraph by paragraph,
                        # and run by run within the paragraph, distributing the translated text.

                        translated_paras = translated_full_text.split('\n')
                        num_orig_paras = len(original_paras_data)
                        num_trans_paras = len(translated_paras)

                        for i, trans_para_text in enumerate(translated_paras):
                            # Determine which original paragraph's style to mimic
                            orig_para_idx = min(i, num_orig_paras - 1)
                            orig_para_data = original_paras_data[orig_para_idx]

                            # Add paragraph (first one exists, add subsequent ones)
                            if i == 0:
                                p = text_frame.paragraphs[0]
                                p.text = '' # Clear any default text in the first paragraph
                            else:
                                p = text_frame.add_paragraph()

                            # Apply paragraph formatting
                            p.alignment = orig_para_data['alignment']
                            p.level = orig_para_data['level']
                            if orig_para_data['line_spacing']: p.line_spacing = orig_para_data['line_spacing']
                            if orig_para_data['space_before']: p.space_before = orig_para_data['space_before']
                            if orig_para_data['space_after']: p.space_after = orig_para_data['space_after']

                            # Apply run formatting - Distribute text and styles
                            orig_runs_data = orig_para_data['runs']
                            num_orig_runs = len(orig_runs_data)

                            if not orig_runs_data: # If original paragraph had no runs (e.g., empty)
                                p.text = trans_para_text # Just add the text
                                continue

                            # Simple distribution: Apply styles run-by-run, splitting translated text
                            words = trans_para_text.split()
                            total_words = len(words)
                            start_idx = 0

                            for j, run_data in enumerate(orig_runs_data):
                                # Calculate approx words for this run based on original run length proportion (or just divide equally)
                                # Equal division is simpler here:
                                words_for_this_run = total_words // num_orig_runs
                                if j < total_words % num_orig_runs:
                                    words_for_this_run += 1

                                end_idx = start_idx + words_for_this_run
                                run_text = ' '.join(words[start_idx:end_idx])
                                start_idx = end_idx

                                if not run_text and j < num_orig_runs -1 : # Avoid adding empty runs unless it's the last one potentially
                                    continue

                                run = p.add_run()
                                run.text = run_text + (' ' if j < num_orig_runs - 1 and run_text else '') # Add space between runs

                                # Apply run formatting
                                font = run.font
                                if run_data['font_name']: font.name = run_data['font_name']
                                if run_data['size']: font.size = run_data['size']
                                # Explicitly set False if stored as False
                                font.bold = run_data['bold'] if run_data['bold'] is not None else None
                                font.italic = run_data['italic'] if run_data['italic'] is not None else None
                                font.underline = run_data['underline'] if run_data['underline'] is not None else None # Check underline type if needed

                                # --- Restore color correctly ---
                                stored_color_info = run_data['color_info']
                                if stored_color_info:
                                    color_type, value1, *rest = stored_color_info
                                    if color_type == 'rgb':
                                        try:
                                            font.color.rgb = RGBColor(*value1) # Pass tuple elements to RGBColor
                                        except Exception as color_e:
                                            self.send_progress_update(f"Warn: Failed to set RGB color {value1}: {color_e}")
                                    elif color_type == 'scheme':
                                        try:
                                            font.color.theme_color = value1
                                            if rest: # Brightness was stored
                                                font.color.brightness = rest[0]
                                        except Exception as color_e:
                                             self.send_progress_update(f"Warn: Failed to set theme color {value1}: {color_e}")
                                # --- End color restoration ---

                                if run_data['language']: font.language_id = run_data['language']


                    except InterruptedError:
                        raise # Propagate stop request
                    except Exception as e:
                        self.send_progress_update(f"Error translating shape {shape_idx+1} on slide {slide_idx+1}: {e}")
                        logging.warning(f"Error translating shape {shape_idx+1} on slide {slide_idx+1} in {input_file.name}: {e}", exc_info=True) # Log with traceback for debugging

                    processed_shapes += 1
                    if total_shapes > 0 and processed_shapes % 5 == 0: # Update progress more frequently
                        progress = (processed_shapes / total_shapes) * 100
                        self.send_progress_update(f"Translation progress: {progress:.1f}% ({processed_shapes}/{total_shapes} shapes)")


            # Create output filename
            output_file = output_dir / f"{input_file.stem}_{target_lang}{input_file.suffix}"

            # Save the translated presentation
            prs.save(output_file)
            return output_file

        except ImportError:
            raise ImportError("Required libraries not installed. Please install python-pptx and deepl")
        except InterruptedError:
             self.send_progress_update(f"Translation stopped for {input_file.name}")
             raise # Re-raise to stop processing loop
        except Exception as e:
            # Ensure specific error types from DeepL/pptx are caught if needed
            raise Exception(f"Translation failed for {input_file.name}: {str(e)}")




class AudioTranscriptionTool(ToolBase):
    """Transcribes audio files using OpenAI's Whisper API."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        # Define supported extensions
        self.supported_extensions = {'.wav', '.mp3', '.m4a', '.webm', 
                                   '.mp4', '.mpga', '.mpeg'}
        
        self.MAX_SUPPORTED_AUDIO_SIZE_MB = 20

        # Get OpenAI API key from config
        self.api_key = self.config_manager.get_api_keys().get("openai")
        if not self.api_key:
            logging.warning("OpenAI API key not configured")

    def process_file(self, input_file: Path, output_dir: Path):
        """Processes a single audio file."""
        try:
            self.send_progress_update(f"Transcribing {input_file.name}...")
            transcript = self.transcribe_audio(input_file, output_dir)
            self.save_transcript(transcript, input_file, output_dir)
            self.send_progress_update(f"Successfully transcribed: {input_file.name}")

        except Exception as e:
            error_message = f"Error transcribing {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def transcribe_audio(self, input_file: Path, output_dir: Path, max_retries=10, retry_delay=5):
        """Transcribes an audio file using OpenAI's Whisper API."""
        if not self.api_key:
            raise ValueError("OpenAI API key not configured. Please add your API key in the Configuration menu.")

        # Check file size and split if necessary
        audio_files = self.prepare_audio_files(input_file, output_dir)
        transcript_texts = []

        for audio_file in audio_files:
            for attempt in range(max_retries):
                try:
                    # Check if processing should stop
                    if self.stop_flag.is_set():
                        raise InterruptedError("Processing stopped by user")

                    with open(audio_file, "rb") as f:
                        client = openai.OpenAI(api_key=self.api_key)
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f
                        )
                        transcript_texts.append(transcript.text)
                        break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise Exception(f"Transcription failed after {max_retries} attempts: {str(e)}")
                    self.send_progress_update(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
                    time.sleep(retry_delay)

            # Clean up temporary files if they were created
            if audio_file != input_file:
                audio_file.unlink()

        return " ".join(transcript_texts)

    def prepare_audio_files(self, input_file: Path, output_dir: Path) -> list:
        """Prepares audio files for transcription, splitting if necessary."""
        audio_size_mb = input_file.stat().st_size / (1024 * 1024)
        
        if audio_size_mb <= self.MAX_SUPPORTED_AUDIO_SIZE_MB:
            return [input_file]

        # Split audio file if it's too large
        audio = AudioSegment.from_file(str(input_file))
        chunk_size_ms = int((self.MAX_SUPPORTED_AUDIO_SIZE_MB * 1024 * 1024 * 8) / 1000)
        duration_ms = len(audio)
        
        chunks = []
        for i in range(0, duration_ms, chunk_size_ms):
            chunk = audio[i:i + chunk_size_ms]
            chunk_file = output_dir / f"{input_file.stem}_chunk_{i//chunk_size_ms}{input_file.suffix}"
            chunk.export(str(chunk_file), format=input_file.suffix.lstrip('.'))
            chunks.append(chunk_file)
            
        return chunks

    def save_transcript(self, transcript: str, input_file: Path, output_dir: Path):
        """Saves the transcript to a text file."""
        output_file = output_dir / f"{input_file.stem}_transcript.txt"
        output_file.write_text(transcript, encoding='utf-8')

class TextTranslationTool(ToolBase, LanguageSelectionMixin):
    """Translates text files using DeepL API."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        
        # Define supported extensions
        self.supported_extensions = {'.txt'}
        
        # Language selection variables
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")
        
        # Get API key
        self.api_key = self.config_manager.get_api_keys().get("deepl")
        if not self.api_key:
            logging.warning("DeepL API key not configured")

    def create_language_selection(self):
        """Creates the language selection UI elements."""
        # Language selection frame
        self.lang_frame = ttk.LabelFrame(self.master, text="Language Selection")
        self.lang_frame.pack(fill='x', padx=5, pady=5)

        # Source language
        source_frame = ttk.Frame(self.lang_frame)
        source_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(source_frame, text="Source Language:").pack(side=tk.LEFT, padx=5)
        self.source_lang_combo = ttk.Combobox(
            source_frame, 
            textvariable=self.source_lang,
            values=list(self.supported_languages.get("source_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.source_lang_combo.pack(side=tk.LEFT, padx=5)

        # Target language
        target_frame = ttk.Frame(self.lang_frame)
        target_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Target Language:").pack(side=tk.LEFT, padx=5)
        self.target_lang_combo = ttk.Combobox(
            target_frame, 
            textvariable=self.target_lang,
            values=list(self.supported_languages.get("target_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.target_lang_combo.pack(side=tk.LEFT, padx=5)

    def process_file(self, input_file: Path, output_dir: Path):
        """Processes a single text file."""
        try:
            self.send_progress_update(f"Translating {input_file.name}...")
            
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")

            # Create output file path
            output_file = output_dir / f"{input_file.stem}_{self.target_lang.get()}{input_file.suffix}"

            # Read source file
            with open(input_file, 'r', encoding='utf-8') as f:
                source_text = f.read()

            # Translate text
            translated_text = self.translate_text(
                source_text,
                self.source_lang.get(),
                self.target_lang.get()
            )

            # Save translated text
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(translated_text)

            self.send_progress_update(f"Successfully translated: {input_file.name}")

        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error translating {input_file.name}: {str(e)}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def translate_text(self, text: str, source_lang: str, target_lang: str, max_retries=3, retry_delay=5) -> str:
        """Translates text using DeepL API with retry mechanism."""
        if not self.api_key:
            raise ValueError("DeepL API key not configured. Please add your API key in the Configuration menu.")

        if not text.strip():
            return text

        # Get language mappings from supported_languages.json
        source_languages = self.supported_languages.get("source_languages", {})
        target_languages = self.supported_languages.get("target_languages", {})

        # Validate languages
        if source_lang not in source_languages:
            raise ValueError(f"Unsupported source language: {source_lang}")
        if target_lang not in target_languages:
            raise ValueError(f"Unsupported target language: {target_lang}")

        translator = deepl.Translator(self.api_key.strip())

        for attempt in range(max_retries):
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")

            try:
                # Test API connection on first attempt
                if attempt == 0:
                    try:
                        translator.get_usage()
                    except deepl.exceptions.AuthorizationException:
                        raise ValueError("Invalid DeepL API key. Please check your API key.")
                    except Exception as e:
                        raise ValueError(f"Error connecting to DeepL API: {str(e)}")

                # Perform translation
                result = translator.translate_text(
                    text,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                return result.text

            except InterruptedError:
                raise
            except Exception as e:
                if attempt < max_retries - 1:
                    self.send_progress_update(
                        f"Translation attempt {attempt + 1} failed: {str(e)}. Retrying in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    raise Exception(f"Translation failed after {max_retries} attempts: {str(e)}")

    def before_processing(self):
        """Pre-processing setup."""
        if not self.api_key:
            raise ValueError("DeepL API key not configured. Please add your API key in the Configuration menu.")

    def after_processing(self):
        """Post-processing cleanup."""
        pass


class MainApp(TkinterDnD.Tk):
    """Main application class."""

    def __init__(self):
        super().__init__()

        self.title("Course Video Tools")
        self.geometry("800x600")

        # Initialize components
        self.config_manager = ConfigManager()
        self.progress_queue = queue.Queue()

        # Create UI
        self.create_widgets()
        self.process_progress_queue()

    def create_widgets(self):
        """Creates the main UI elements."""
        # Menu
        self.menu_bar = tk.Menu(self)
        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.config_menu.add_command(label="API Keys", command=self.open_api_key_config)
        self.menu_bar.add_cascade(label="Configuration", menu=self.config_menu)
        self.config(menu=self.menu_bar)

        # Notebook (Tab Control)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # Tool Frames
        self.pptx_translation_tool = self.create_tool_tab("PPTX Translation", PPTXTranslationTool)
        self.audio_transcription_tool = self.create_tool_tab("Audio Transcription", AudioTranscriptionTool)
        self.text_translation_tool = self.create_tool_tab("Text Translation", TextTranslationTool)


        # Progress Text Area
        self.progress_label = tk.Label(self, text="Progress:")
        self.progress_label.pack(pady=(0, 5))

        self.progress_text = tk.Text(self, height=10, width=80, state="disabled")
        self.progress_text.pack(expand=False, fill="x", padx=10, pady=(0, 10))

        self.sb = tk.Scrollbar(self, command=self.progress_text.yview)
        self.sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.progress_text['yscrollcommand'] = self.sb.set

    def create_tool_tab(self, tab_name, tool_class):
        """Creates a tab with the specified tool."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=tab_name)
        
        tool = tool_class(
            master=frame,
            config_manager=self.config_manager,
            progress_queue=self.progress_queue
        )
        
        self.create_tool_ui(frame, tool)
        return tool


    def create_tool_ui(self, frame, tool):
        """Creates the UI elements for a specific tool."""
        
        tool.create_selection_mode_controls(frame)

        # If the tool has language selection capability, create the UI
        if isinstance(tool, LanguageSelectionMixin):
            tool.create_language_selection()
        
        # Input Path Selection
        input_frame = ttk.Frame(frame)
        input_frame.pack(pady=5, fill='x', padx=5)


        input_label = ttk.Label(input_frame, text="Input Path(s):")
        input_label.pack(side=tk.LEFT, padx=5)

        input_button = ttk.Button(input_frame, text="Select Input", command=tool.select_input_paths)
        input_button.pack(side=tk.LEFT, padx=5)

        tool.input_paths_display = tk.Text(input_frame, height=3, width=50, wrap=tk.WORD)
        tool.input_paths_display.pack(side=tk.LEFT, padx=5, fill='x', expand=True)


        
        input_scrollbar = ttk.Scrollbar(input_frame, orient="vertical", 
                                      command=tool.input_paths_display.yview)
        input_scrollbar.pack(side=tk.RIGHT, fill='y')
        tool.input_paths_display.configure(yscrollcommand=input_scrollbar.set)
        tool.input_paths_display.configure(state='disabled')
        
        # Output Path Selection
        output_frame = ttk.Frame(frame)
        output_frame.pack(pady=5, fill='x', padx=5)

        output_label = ttk.Label(output_frame, text="Output Path:")
        output_label.pack(side=tk.LEFT, padx=5)

        output_button = ttk.Button(output_frame, text="Select Output", 
                                 command=tool.select_output_path)
        output_button.pack(side=tk.LEFT, padx=5)

        same_as_input_button = ttk.Button(output_frame, text="Same as Input", 
                                        command=tool.set_same_as_input)
        same_as_input_button.pack(side=tk.LEFT, padx=5)

        tool.output_path_display = tk.Text(output_frame, height=1, width=50)
        tool.output_path_display.pack(side=tk.LEFT, padx=5, fill='x', expand=True)
        tool.output_path_display.configure(state='disabled')

        # Button Frame
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)

        # Process Button
        tool.process_button = ttk.Button(
            button_frame, 
            text="Process", 
            command=lambda: self.start_processing(tool)
        )
        tool.process_button.pack(side=tk.LEFT, padx=5)

        # Stop Button
        tool.stop_button = ttk.Button(
            button_frame, 
            text="Stop", 
            command=lambda: self.stop_processing(tool),
            state=tk.DISABLED
        )
        tool.stop_button.pack(side=tk.LEFT, padx=5)

        # Drag and Drop
        input_frame.drop_target_register(DND_FILES)
        input_frame.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, tool))

    def start_processing(self, tool):
        """Starts processing and updates button states."""
        tool.process_button.configure(state=tk.DISABLED)
        tool.stop_button.configure(state=tk.NORMAL)
        tool.process_paths()
        
        # Start checking if processing is complete
        self.check_processing_complete(tool)

    def stop_processing(self, tool):
        """Stops processing and updates button states."""
        tool.stop_processing()
        tool.stop_button.configure(state=tk.DISABLED)
        
        # Wait for processing to actually stop
        if tool.processing_thread:
            tool.processing_thread.join(timeout=1.0)
        
        tool.process_button.configure(state=tk.NORMAL)

    def check_processing_complete(self, tool):
        """Checks if processing is complete and updates button states."""
        if not tool.processing_thread or not tool.processing_thread.is_alive():
            tool.process_button.configure(state=tk.NORMAL)
            tool.stop_button.configure(state=tk.DISABLED)
        else:
            # Check again in 100ms
            self.after(100, lambda: self.check_processing_complete(tool))

    def process_progress_queue(self):
        """Processes messages from the progress queue."""
        try:
            while True:
                message = self.progress_queue.get_nowait()
                self.update_progress_text(message)
                
                # Enable process button if processing is complete
                if message == "Processing complete" or message == "Processing stopped by user":
                    for tool in [self.pptx_translation_tool, self.audio_transcription_tool]:
                        tool.process_button.configure(state=tk.NORMAL)
                        tool.stop_button.configure(state=tk.DISABLED)
                
        except queue.Empty:
            pass
        
        self.after(100, self.process_progress_queue)

    def on_drop(self, event, tool):
        """Handles drag and drop events."""
        files = event.data.split()
        tool.input_paths = [Path(f) for f in files]
        logging.info(f"Files dropped: {tool.input_paths}")
        tool.update_input_display()

    def open_api_key_config(self):
        """Opens a dialog to configure API keys."""
        api_config_window = tk.Toplevel(self)
        api_config_window.title("API Key Configuration")
        api_config_window.geometry("500x300")

        # Load current API keys
        api_keys = self.config_manager.get_api_keys()

        # Create a dictionary to store the entry widgets
        api_entries = {}

        # Create entries for each API key
        for api_name in ["openai", "anthropic", "deepl", "adobe", "elevenlabs", "google"]:
            frame = ttk.Frame(api_config_window)
            frame.pack(pady=5, padx=10, fill="x")

            label = ttk.Label(frame, text=f"{api_name.capitalize()} API Key:")
            label.pack(side=tk.LEFT, padx=5)

            entry = ttk.Entry(frame, width=40)
            entry.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

            if api_name in api_keys:
                entry.insert(0, api_keys[api_name])

            api_entries[api_name] = entry

        # Save Button
        save_button = ttk.Button(api_config_window, text="Save", 
                               command=lambda: self.save_api_keys(api_entries, api_config_window))
        save_button.pack(pady=10)

    def save_api_keys(self, api_entries, window):
        """Saves the API keys from the configuration dialog."""
        try:
            api_keys = {name: entry.get().strip() 
                       for name, entry in api_entries.items() 
                       if entry.get().strip()}

            self.config_manager.api_keys = api_keys
            self.config_manager.save_api_keys()
            
            window.destroy()
            messagebox.showinfo("Success", "API keys saved successfully.")
            logging.info(f"Saved API keys for services: {list(api_keys.keys())}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save API keys: {str(e)}")
            logging.error(f"Error saving API keys: {e}")

    def process_progress_queue(self):
        """Processes messages from the progress queue."""
        try:
            while True:
                message = self.progress_queue.get_nowait()
                self.update_progress_text(message)
        except queue.Empty:
            pass

        self.after(100, self.process_progress_queue)

    def update_progress_text(self, message):
        """Updates the progress text area with a new message."""
        self.progress_text.config(state="normal")
        self.progress_text.insert(tk.END, message + "\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state="disabled")

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()

