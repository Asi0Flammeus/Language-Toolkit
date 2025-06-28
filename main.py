import tkinter as tk
import convertapi
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import json
import requests
import time
import mimetypes
import os
import re
import subprocess
import logging
from pathlib import Path
import threading
import queue
import time
import openai
import deepl
import pptx
import fitz
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR, MSO_COLOR_TYPE
from PIL import Image
from core.tool_descriptions import get_short_description, get_tool_info, get_quick_tips


# --- Constants ---
SUPPORTED_LANGUAGES_FILE = "supported_languages.json"
API_KEYS_FILE = "api_keys.json"

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ConfigManager:
    """Manages configuration files for the application."""

    def __init__(self, languages_file=SUPPORTED_LANGUAGES_FILE, api_keys_file=API_KEYS_FILE):
        self.base_path = Path(__file__).resolve().parent
        self.languages_file = self.base_path / languages_file
        self.api_keys_file = self.base_path / api_keys_file

        self.languages = self.load_json(self.languages_file)
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


    def get_api_keys(self):
        return self.api_keys

    def save_languages(self):
        self.save_json(self.languages, self.languages_file)
    

    def save_api_keys(self, api_entries, window):
        """Saves the API keys entered in the configuration dialog."""
        api_keys = {}
        for name, entry in api_entries.items():
            api_keys[name] = entry.get().strip()
        
        # Update the config_manager with new keys
        self.config_manager.api_keys = api_keys
        self.config_manager.save_api_keys()
        
        # Update the API keys in existing tools
        if hasattr(self, 'text_to_speech_tool'):
            self.text_to_speech_tool.api_key = api_keys.get("elevenlabs")
        if hasattr(self, 'audio_transcription_tool'):
            self.audio_transcription_tool.api_key = api_keys.get("openai")
        if hasattr(self, 'text_translation_tool'):
            self.text_translation_tool.api_key = api_keys.get("deepl")
        if hasattr(self, 'pptx_translation_tool'):
            self.pptx_translation_tool.api_key = api_keys.get("deepl")
        
        window.destroy()
        messagebox.showinfo("Success", "API keys saved successfully")

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


class TextToSpeechTool(ToolBase):
    """
    Converts text files (.txt) to MP3 audio using the ElevenLabs API.
    Detects voice name anywhere in the filename using the predefined voice list.
    Voice name can be separated by underscore, hyphen, or space.
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.txt'}
        
        # Constants for ElevenLabs API
        self.ELEVENLABS_API_URL_BASE = "https://api.elevenlabs.io/v1"
        self.TTS_ENDPOINT_TEMPLATE = "/text-to-speech/{voice_id}/stream"
        self.VOICES_CONFIG_FILE = "elevenlabs_voices.json"
        self.DEFAULT_MODEL = "eleven_multilingual_v2"
        self.DEFAULT_VOICE_SETTINGS = {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.0,
            "use_speaker_boost": True
        }
        self.MAX_RETRIES = 3
        self.RETRY_DELAY = 3  # seconds
        
        # Load voices configuration
        self.voice_map = self._load_voices_config()
        
        # Get API key
        self.api_key = self.config_manager.get_api_keys().get("elevenlabs")
        if not self.api_key:
            logging.warning("ElevenLabs API key not configured")

    def _load_voices_config(self) -> dict:
        """Loads the voice name to voice ID mapping from JSON config file."""
        try:
            with open(self.VOICES_CONFIG_FILE, 'r', encoding='utf-8') as f:
                voices = json.load(f)
                logging.info(f"Loaded {len(voices)} voice mappings from {self.VOICES_CONFIG_FILE}")
                return voices
        except FileNotFoundError:
            logging.error(f"ElevenLabs voices config file not found at {self.VOICES_CONFIG_FILE}")
            self.send_progress_update(f"ERROR: Voices config file missing: {self.VOICES_CONFIG_FILE}")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {self.VOICES_CONFIG_FILE}: {e}")
            self.send_progress_update(f"ERROR: Invalid JSON in voices config: {self.VOICES_CONFIG_FILE}")
            return {}
        except Exception as e:
            logging.error(f"Unexpected error loading voices config: {e}", exc_info=True)
            self.send_progress_update(f"ERROR: Failed to load voices config: {self.VOICES_CONFIG_FILE}")
            return {}

    def _parse_voicename(self, filename_stem: str):
        """
        Extracts voice name from the filename stem by looking for any matching voice name
        from the voice_map regardless of its position in the filename.
        """
        if not self.voice_map:
            return None
            
        # Split the filename by common delimiters
        parts = re.split('[_\\- ]', filename_stem.lower())
        
        # Look for any part that matches a voice name (case-insensitive)
        voice_names = {name.lower(): name for name in self.voice_map.keys()}
        
        for part in parts:
            if part in voice_names:
                return voice_names[part]  # Return the original case of the voice name
                
        return None


    def before_processing(self):
        """Pre-processing setup."""
        if not self.api_key:
            raise ValueError("ElevenLabs API key not configured. Please add your API key in the Configuration menu.")
        
        if not self.voice_map:
            raise ValueError(f"Voice configuration missing or empty. Please check {self.VOICES_CONFIG_FILE}")

    def process_file(self, input_file: Path, output_dir: Path):
        """Processes a single text file for TTS conversion."""
        try:
            self.send_progress_update(f"Processing {input_file.name}...")
            
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")
            
            # Determine output path
            output_file = output_dir / f"{input_file.stem}.mp3"
            
            # Parse voice name
            voicename = self._parse_voicename(input_file.stem)
            if not voicename:
                error_msg = f"Could not parse voice name from filename '{input_file.name}'. Expected format: name_voicename.txt"
                self.send_progress_update(f"ERROR: {error_msg}")
                logging.error(error_msg)
                return
            
            # Look up voice ID
            voice_id = self.voice_map.get(voicename)
            if not voice_id:
                error_msg = (f"Could not find a valid voice name in filename '{input_file.name}'. "
                            f"Filename must include one of these voices: {', '.join(sorted(self.voice_map.keys()))}")
                self.send_progress_update(f"ERROR: {error_msg}")
                logging.error(error_msg)
                return
            
            self.send_progress_update(f"Using voice: {voicename} (ID: {voice_id[:6]}...)")
            
            # Read text content
            try:
                text_to_speak = input_file.read_text(encoding='utf-8')
                if not text_to_speak.strip():
                    self.send_progress_update(f"Skipping {input_file.name}: File is empty")
                    return
            except Exception as e:
                self.send_progress_update(f"ERROR: Failed to read {input_file.name}: {e}")
                logging.error(f"Failed to read {input_file.name}: {e}", exc_info=True)
                return
            
            # Generate audio
            self._generate_audio(text_to_speak, voice_id, output_file)
            
            self.send_progress_update(f"Successfully generated audio: {output_file.name}")
            
        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error generating audio for {input_file.name}: {str(e)}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def _generate_audio(self, text: str, voice_id: str, output_file: Path) -> None:
        """Generates audio using ElevenLabs API with retry mechanism."""
        tts_url = f"{self.ELEVENLABS_API_URL_BASE}{self.TTS_ENDPOINT_TEMPLATE.format(voice_id=voice_id)}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        payload = {
            "text": text,
            "model_id": self.DEFAULT_MODEL,
            "voice_settings": self.DEFAULT_VOICE_SETTINGS
        }
        
        for attempt in range(self.MAX_RETRIES):
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")
            
            try:
                self.send_progress_update(f"Requesting audio generation (attempt {attempt + 1}/{self.MAX_RETRIES})...")
                
                response = requests.post(tts_url, headers=headers, json=payload, stream=True, timeout=180)
                response.raise_for_status()
                
                # Save the audio stream
                bytes_written = 0
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.stop_flag.is_set():
                            f.close()
                            output_file.unlink(missing_ok=True)
                            raise InterruptedError("Download stopped by user")
                        
                        if chunk:
                            f.write(chunk)
                            bytes_written += len(chunk)
                
                if bytes_written == 0:
                    raise RuntimeError("Audio file was not saved correctly (0 bytes written)")
                
                return  # Success!
                
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                try:
                    error_details = e.response.json()
                    error_message = error_details.get("detail", {}).get("message", str(e))
                except:
                    error_message = e.response.text or str(e)
                
                if status_code == 401:
                    raise ValueError(f"Invalid ElevenLabs API key (Unauthorized): {error_message}")
                elif status_code == 422:
                    raise ValueError(f"Invalid request parameters: {error_message}")
                elif status_code >= 500:
                    self.send_progress_update(f"ElevenLabs server error: {error_message}. Retrying...")
                else:
                    raise ValueError(f"ElevenLabs API error ({status_code}): {error_message}")
            
            except (requests.exceptions.RequestException, RuntimeError) as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise RuntimeError(f"Failed to generate audio after {self.MAX_RETRIES} attempts: {e}")
                
                self.send_progress_update(f"Network error: {e}. Retrying in {self.RETRY_DELAY} seconds...")
                time.sleep(self.RETRY_DELAY)

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

                        for para in text_frame.paragraphs:
                            para_data = {
                                'text': para.text,
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
                                if font.color and hasattr(font.color, 'type'): 
                                    if font.color.type == MSO_COLOR_TYPE.RGB:
                                        color_info = ('rgb', font.color.rgb)
                                    elif font.color.type == MSO_COLOR_TYPE.SCHEME:
                                        color_info = ('scheme', font.color.theme_color, getattr(font.color, 'brightness', 0.0))

                                run_data = {
                                    'text': run.text, 
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

                        text_frame.clear() # Clear existing content


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


class PPTXtoPDFTool(ToolBase):
    """
    Converts PPTX files to PDF, PNG, or WEBP using ConvertAPI service.
    Supports PDF conversion, PNG conversion (one PNG per slide), and WEBP conversion (PNG to WEBP).
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx', '.ppt', '.potx', '.pps', '.ppsx'}
        self.output_format = tk.StringVar(value="pdf")  # Default to PDF

    def create_specific_controls(self, parent_frame):
        """Creates UI elements specific to this tool (output format selection)."""
        format_frame = ttk.LabelFrame(parent_frame, text="Output Format")
        format_frame.pack(fill='x', padx=5, pady=5)

        ttk.Radiobutton(format_frame, text="PDF",
                       variable=self.output_format,
                       value="pdf").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(format_frame, text="PNG (One per slide)",
                       variable=self.output_format,
                       value="png").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(format_frame, text="WEBP (One per slide)",
                       variable=self.output_format,
                       value="webp").pack(side=tk.LEFT, padx=10)

    def before_processing(self):
        """Load credentials before starting the batch."""
        api_keys = self.config_manager.get_api_keys()
        api_secret = api_keys.get("convertapi")
        
        if not api_secret:
            raise ValueError("Missing ConvertAPI secret in configuration. Please configure it via the menu.")
        
        convertapi.api_credentials = api_secret
        logging.info("ConvertAPI credentials loaded successfully.")


    def process_file(self, input_file: Path, output_dir: Path):
        """
        Processes a single PPTX file.
        Converts to PDF, PNG, or WEBP using ConvertAPI.
        For PNG/WEBP output, files are renamed to use sequential numbering (00, 01, 02, etc.)
        For WEBP output, first converts to PNG, then converts PNG to WEBP.
        """
        try:
            output_format = self.output_format.get()
            self.send_progress_update(f"Converting {input_file.name} to {output_format.upper()}...")

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # For WEBP, we need to convert to PNG first, then PNG to WEBP
            if output_format == 'webp':
                # Convert to PNG first
                result = convertapi.convert(
                    'png',
                    {
                        'File': str(input_file)
                    },
                    from_format='pptx'
                )
                
                # Save PNG files temporarily
                saved_files = result.save_files(str(output_dir))
                saved_paths = [Path(f) for f in saved_files]
                # Sort by creation time to maintain slide order
                sorted_files = sorted(saved_paths, key=lambda x: x.stat().st_ctime)
                
                # Convert each PNG to WEBP
                for idx, png_path in enumerate(sorted_files):
                    # Create new WEBP filename with sequential numbering
                    webp_name = f"{input_file.stem}_{idx:02d}.webp"
                    webp_path = png_path.parent / webp_name
                    
                    # Convert PNG to WEBP using PIL
                    self.send_progress_update(f"Converting slide {idx:02d} to WEBP...")
                    with Image.open(png_path) as img:
                        img.save(webp_path, 'WEBP', quality=85, method=6)
                    
                    # Remove the temporary PNG file
                    png_path.unlink()
                    
                    self.send_progress_update(f"Saved slide {idx:02d}: {webp_name}")
            else:
                # Convert the file using the original format
                result = convertapi.convert(
                    output_format,
                    {
                        'File': str(input_file)
                    },
                    from_format='pptx'
                )

                # Save the converted files
                saved_files = result.save_files(str(output_dir))
                
                # For PNG output, rename files with sequential numbering
                if output_format == 'png':
                    # Get list of files and sort them by creation time
                    saved_paths = [Path(f) for f in saved_files]
                    # Sort by creation time to maintain slide order
                    sorted_files = sorted(saved_paths, key=lambda x: x.stat().st_ctime)
                    
                    # Create new names with sequential numbering
                    for idx, old_path in enumerate(sorted_files):
                        new_name = f"{input_file.stem}_{idx:02d}.png"  # Use 02d for 2-digit padding
                        new_path = old_path.parent / new_name
                        
                        # Rename the file
                        old_path.rename(new_path)
                        self.send_progress_update(f"Saved slide {idx:02d}: {new_name}")
                else:
                    # For PDF, just log the saved file
                    for saved_file in saved_files:
                        self.send_progress_update(f"Successfully saved: {Path(saved_file).name}")

            return True

        except Exception as e:
            error_msg = f"Failed to convert {input_file.name}: {str(e)}"
            self.send_progress_update(f"ERROR: {error_msg}")
            logging.error(error_msg, exc_info=True)
            return False


    def after_processing(self):
        """Cleanup after processing batch."""
        convertapi.api_credentials = None
        self.send_progress_update("ConvertAPI conversion batch finished.")

class VideoMergeTool(ToolBase):
    """
    Merges MP3 audio files with PNG images to create MP4 videos.
    Uses ffmpeg directly instead of moviepy for better reliability.
    
    Matches files based on 2-digit number patterns in filenames,
    where digits are separated by underscore or hyphen.
    Adds a 0.5s silence between clips in the final video.
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        # We don't use self.supported_extensions in the usual way
        self.supported_extensions = {'.mp3', '.png'}
        
        # Force selection mode to folder only
        self.selection_mode = tk.StringVar(value="folder")
        # Toggle for recursive batch mode (process subfolders)
        self.recursive_mode = tk.BooleanVar(value=False)
        
        # Check dependencies
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if ffmpeg is installed and available."""
        self.dependencies_met = False
        try:
            # Check if ffmpeg is available in PATH
            result = subprocess.run(['ffmpeg', '-version'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            if result.returncode == 0:
                self.dependencies_met = True
                version_info = result.stdout.split('\n')[0]
                logging.info(f"Found ffmpeg: {version_info}")
            else:
                logging.error("ffmpeg command returned non-zero exit code")
                self.send_progress_update("ERROR: ffmpeg command failed")
        except FileNotFoundError:
            error_msg = "ffmpeg not found in PATH. Please install ffmpeg first."
            logging.error(error_msg)
            self.send_progress_update(f"ERROR: {error_msg}")
        except Exception as e:
            logging.error(f"Error checking ffmpeg: {str(e)}")
            self.send_progress_update(f"ERROR: Failed to check ffmpeg: {str(e)}")
            
    def create_selection_mode_controls(self, parent_frame):
        """Override to only show folder selection mode."""
        mode_frame = ttk.LabelFrame(parent_frame, text="Input Mode")
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(mode_frame, text="This tool accepts folders containing matching MP3 and PNG files").pack(padx=10, pady=5)
        note_frame = ttk.Frame(mode_frame)
        note_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(note_frame, text="Note: Files are matched by the same 2-digit number in their names").pack(side=tk.LEFT)
        # Recursive batch mode toggle: when enabled, each subfolder is processed separately
        ttk.Checkbutton(mode_frame,
                        text="Recursive batch mode (process subfolders)",
                        variable=self.recursive_mode).pack(anchor='w', padx=10, pady=5)
        
    def select_input_paths(self):
        """Override to only allow folder selection."""
        path = filedialog.askdirectory(title="Select Folder with MP3 and PNG Files")
        if path:
            self.input_paths = [Path(path)]
            self.update_input_display()
            return True
        return False
            
    def before_processing(self):
        """Pre-processing setup and validation."""
        if not self.dependencies_met:
            self._check_dependencies()  # Check again in case user installed ffmpeg
            if not self.dependencies_met:
                raise ImportError("ffmpeg not found. Please install ffmpeg and make sure it's in your PATH.")

    def process_file(self, input_file, output_dir):
        """Not used for this tool - we process directories instead."""
        pass

    def _process_paths_threaded(self):
        """Override to implement directory-based processing instead of file-based."""
        try:
            self.before_processing()
            
            if not self.input_paths:
                self.send_progress_update("No input directory selected.")
                return
                
            input_dir = self.input_paths[0]
            if not input_dir.is_dir():
                self.send_progress_update(f"Error: {input_dir} is not a directory.")
                return
                
            # Create output directory if it doesn't exist
            output_dir = self.output_path
            output_dir.mkdir(parents=True, exist_ok=True)
                
            # Process the directory
            self.process_directory(input_dir, output_dir)
                
            self.after_processing()
            
        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.send_progress_update(error_msg)
            logging.exception(error_msg)
        finally:
            self.stop_flag.clear()
            self.processing_thread = None
            self.send_progress_update("Processing complete")
            
    def process_directory(self, input_dir, output_dir):
        """Processes MP3/PNG pairs in either single-folder or recursive mode to create MP4 videos."""
        # Determine mode: flat (single folder) or recursive per subfolder
        if not getattr(self, 'recursive_mode', None) or not self.recursive_mode.get():
            self.send_progress_update(f"Processing single-folder mode: {input_dir}")
            # Collect MP3 and PNG files directly in the selected folder
            try:
                entries = os.listdir(input_dir)
            except Exception as e:
                self.send_progress_update(f"Error reading directory {input_dir}: {e}")
                return
            mp3_files = sorted([input_dir / f for f in entries if f.lower().endswith('.mp3')])
            png_files = sorted([input_dir / f for f in entries if f.lower().endswith('.png')])
            self.send_progress_update(f"Found {len(mp3_files)} MP3 and {len(png_files)} PNG in {input_dir}")
            # Match files by identifier
            file_pairs = self.match_file_pairs(mp3_files, png_files)
            if not file_pairs:
                self.send_progress_update(f"No matching MP3/PNG pairs found in {input_dir}")
                return
            self.send_progress_update(f"Found {len(file_pairs)} matching pairs in {input_dir}")
            # Sort file pairs by numeric ID
            file_pairs.sort(key=lambda x: x[0])
            # Generate output filename based on the first MP3 file (remove 2-digit identifier)
            _, first_mp3, _ = file_pairs[0]
            mp3_stem = first_mp3.stem
            identifier_pattern = r'[_-](\d{2})(?:[_-])'
            output_name = re.sub(identifier_pattern, '_', mp3_stem)
            end_pattern = r'[_-]\d{2}$'
            output_name = re.sub(end_pattern, '', output_name)
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{output_name}.mp4"
            self.send_progress_update(f"Output file will be: {output_file}")
            self.create_video_with_ffmpeg(file_pairs, output_file)
            return
        # Recursive mode: walk through all subdirectories
        self.send_progress_update(f"Scanning directory recursively: {input_dir}")
        for dirpath, dirnames, filenames in os.walk(input_dir):
            curr_dir = Path(dirpath)
            # Collect MP3 and PNG files in the current directory
            mp3_files = sorted([curr_dir / f for f in filenames if f.lower().endswith('.mp3')])
            png_files = sorted([curr_dir / f for f in filenames if f.lower().endswith('.png')])
            if not mp3_files or not png_files:
                continue
            self.send_progress_update(f"Found {len(mp3_files)} MP3 and {len(png_files)} PNG in {curr_dir}")
            # Match files by identifier
            file_pairs = self.match_file_pairs(mp3_files, png_files)
            if not file_pairs:
                self.send_progress_update(f"No matching MP3/PNG pairs found in {curr_dir}")
                continue
            self.send_progress_update(f"Found {len(file_pairs)} matching pairs in {curr_dir}")
            # Sort file pairs by numeric ID
            file_pairs.sort(key=lambda x: x[0])
            # Generate output filename based on the first MP3 file (remove 2-digit identifier)
            _, first_mp3, _ = file_pairs[0]
            mp3_stem = first_mp3.stem
            identifier_pattern = r'[_-](\d{2})(?:[_-])'
            output_name = re.sub(identifier_pattern, '_', mp3_stem)
            end_pattern = r'[_-]\d{2}$'
            output_name = re.sub(end_pattern, '', output_name)
            output_file = curr_dir / f"{output_name}.mp4"
            self.send_progress_update(f"Output file will be: {output_file}")
            # Create the output video
            self.create_video_with_ffmpeg(file_pairs, output_file)

        
    def match_file_pairs(self, mp3_files, png_files):
        """
        Match MP3 and PNG files based on a generic two-digit index in their filenames.
        The index is defined as exactly two digits not part of a larger digit sequence
        and can be surrounded by any non-digit character (e.g., '_01_', '-01-', '.01.').
        """
        file_pairs = []
        mp3_dict = {}
        png_dict = {}

        # Compile a regex to match exactly two digits not adjacent to other digits
        id_pattern = re.compile(r'(?<!\d)(\d{2})(?!\d)')

        # Extract indices for PNG files
        for png_file in png_files:
            match = id_pattern.search(png_file.name)
            if match:
                idx = match.group(1)
                self.send_progress_update(f"PNG found index {idx} in {png_file.name}")
                png_dict[idx] = png_file

        # Extract indices for MP3 files
        for mp3_file in mp3_files:
            match = id_pattern.search(mp3_file.name)
            if match:
                idx = match.group(1)
                self.send_progress_update(f"MP3 found index {idx} in {mp3_file.name}")
                mp3_dict[idx] = mp3_file

        # Match pairs by index
        for idx in sorted(mp3_dict.keys(), key=lambda x: int(x)):
            mp3_file = mp3_dict[idx]
            png_file = png_dict.get(idx)
            if png_file:
                self.send_progress_update(f"Matched index {idx}: {mp3_file.name} + {png_file.name}")
                file_pairs.append((idx, mp3_file, png_file))
            else:
                self.send_progress_update(f"No PNG match for MP3 index {idx}: {mp3_file.name}")

        # Return pairs sorted by numeric index
        return sorted(file_pairs, key=lambda x: int(x[0]))

    
    def create_video_with_ffmpeg(self, file_pairs, output_file):
        """
        Create a video from matched MP3/PNG pairs using ffmpeg directly.
        Handles adding silence between clips.
        """
        try:
            # Create a temporary directory for intermediate files
            temp_dir = output_file.parent / "temp_video_files"
            temp_dir.mkdir(exist_ok=True)
            
            # List to store paths to intermediate segment files
            segment_files = []
            
            # Process each pair and create individual video segments
            for idx, (numeric_id, mp3_file, png_file) in enumerate(file_pairs):
                if self.stop_flag.is_set():
                    self.send_progress_update("Processing stopped by user")
                    return
                
                self.send_progress_update(f"Processing pair {idx+1}/{len(file_pairs)}: {numeric_id}")
                
                # Create segment file path
                segment_file = temp_dir / f"segment_{idx:03d}.mp4"
                segment_files.append(segment_file)
                
                # Run ffmpeg to create a video segment from image and audio
                cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1',
                    '-i', str(png_file),
                    '-i', str(mp3_file),
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                    '-c:v', 'libx264',
                    '-tune', 'stillimage',
                    '-c:a', 'aac',
                    '-b:a', '192k',
                    '-pix_fmt', 'yuv420p',
                    '-shortest',
                    str(segment_file)
                ]
                
                self.send_progress_update(f"Creating segment for pair {idx+1}...")
                
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
                if result.returncode != 0:
                    self.send_progress_update(f"Error creating segment {idx+1}: {result.stderr}")
                    raise RuntimeError(f"ffmpeg error: {result.stderr}")
                
                # Add silence with the same image if not the last segment
                if idx < len(file_pairs) - 1:
                    silence_file = temp_dir / f"silence_{idx:03d}.mp4"
                    segment_files.append(silence_file)
                    
                    # Create 0.5 second silence with the same image
                    silence_cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1',
                        '-i', str(png_file),
                        '-f', 'lavfi', 
                        '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                        '-c:v', 'libx264',
                        '-t', '0.2',  # 0.5 seconds
                        '-c:a', 'aac',
                        '-pix_fmt', 'yuv420p',
                        str(silence_file)
                    ]
                    
                    self.send_progress_update(f"Adding silence after segment {idx+1}...")
                    
                    silence_result = subprocess.run(
                        silence_cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True
                    )
                    
                    if silence_result.returncode != 0:
                        self.send_progress_update(f"Error creating silence {idx+1}: {silence_result.stderr}")
                        raise RuntimeError(f"ffmpeg error: {silence_result.stderr}")
            
            # Create a file list for concatenation
            concat_file = temp_dir / "concat_list.txt"
            with open(concat_file, 'w') as f:
                for segment in segment_files:
                    f.write(f"file '{segment.absolute()}'\n")
            
            # Concatenate all segments into final video
            self.send_progress_update("Concatenating all segments...")
            
            concat_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(output_file)
            ]
            
            concat_result = subprocess.run(
                concat_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            if concat_result.returncode != 0:
                self.send_progress_update(f"Error concatenating: {concat_result.stderr}")
                raise RuntimeError(f"ffmpeg error: {concat_result.stderr}")
            
            self.send_progress_update(f"Successfully created video: {output_file}")
            
            # Clean up temporary files
            self.send_progress_update("Cleaning up temporary files...")
            for file in segment_files:
                file.unlink(missing_ok=True)
            concat_file.unlink(missing_ok=True)
            temp_dir.rmdir()
            
        except Exception as e:
            error_msg = f"Error creating video: {str(e)}"
            self.send_progress_update(error_msg)
            logging.exception(error_msg)



class SequentialProcessingTool(ToolBase, LanguageSelectionMixin):
    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx'}
        
        # Language selection variables
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")
        
        # Multiple target languages selection
        self.selected_target_langs = set()
        
        # Force selection mode to folder
        self.selection_mode = tk.StringVar(value="folder")
        
        # Initialize sub-tools
        self.pptx_translation_tool = PPTXTranslationTool(master, config_manager, progress_queue)
        self.pptx_export_tool = PPTXtoPDFTool(master, config_manager, progress_queue)
        self.text_translation_tool = TextTranslationTool(master, config_manager, progress_queue)
        self.text_to_speech_tool = TextToSpeechTool(master, config_manager, progress_queue)
        self.video_merge_tool = VideoMergeTool(master, config_manager, progress_queue)

    def create_language_selection(self):
        """Creates enhanced language selection UI with multiple target language support."""
        # Main language frame
        self.lang_frame = ttk.LabelFrame(self.master, text="Language Selection")
        self.lang_frame.pack(fill='x', padx=5, pady=5)

        # Source language frame
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

        # Target language selection button
        target_button = ttk.Button(
            self.lang_frame,
            text="Select Target Languages",
            command=self.open_target_language_selector
        )
        target_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Selected languages display
        self.selected_langs_display = tk.Text(
            self.lang_frame,
            height=2,
            width=30,
            wrap=tk.WORD,
            state='disabled'
        )
        self.selected_langs_display.pack(side=tk.LEFT, padx=5, pady=5, fill='x', expand=True)

    def open_target_language_selector(self):
        """Opens a dialog for selecting multiple target languages."""
        selector = tk.Toplevel(self.master)
        selector.title("Select Target Languages")
        selector.geometry("300x400")
        
        # Make dialog modal
        selector.transient(self.master)
        selector.grab_set()
        
        # Create scrollable frame
        main_frame = ttk.Frame(selector)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Variables to store checkbutton states
        checkbutton_vars = {}
        
        # Create checkbuttons for each target language
        target_languages = self.supported_languages.get("target_languages", {})
        for code, name in sorted(target_languages.items()):
            var = tk.BooleanVar(value=code in self.selected_target_langs)
            checkbutton_vars[code] = var
            ttk.Checkbutton(
                scrollable_frame,
                text=f"{code} - {name}",
                variable=var
            ).pack(anchor='w', padx=5, pady=2)

        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def save_selection():
            self.selected_target_langs = {
                code for code, var in checkbutton_vars.items() if var.get()
            }
            self.update_selected_languages_display()
            selector.destroy()

        # Add buttons
        button_frame = ttk.Frame(selector)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="Select All",
            command=lambda: [var.set(True) for var in checkbutton_vars.values()]
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Clear All",
            command=lambda: [var.set(False) for var in checkbutton_vars.values()]
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=save_selection
        ).pack(side=tk.RIGHT, padx=5)

    def update_selected_languages_display(self):
        """Updates the display of selected target languages."""
        self.selected_langs_display.config(state='normal')
        self.selected_langs_display.delete(1.0, tk.END)
        
        if self.selected_target_langs:
            langs_text = ", ".join(sorted(self.selected_target_langs))
            self.selected_langs_display.insert(tk.END, f"Selected: {langs_text}")
        else:
            self.selected_langs_display.insert(tk.END, "No target languages selected")
        
        self.selected_langs_display.config(state='disabled')

    def process_paths(self):
        """Override to process each target language sequentially."""
        if not self.input_paths:
            messagebox.showerror("Error", "No input paths selected.")
            return

        if not self.selected_target_langs:
            messagebox.showerror("Error", "No target languages selected.")
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
            target=self._process_multiple_languages, 
            daemon=True
        )
        self.processing_thread.start()

    def _process_multiple_languages(self):
        """Process all selected target languages sequentially."""
        try:
            self.before_processing()
            
            for target_lang in sorted(self.selected_target_langs):
                if self.stop_flag.is_set():
                    self.send_progress_update("Processing stopped by user")
                    return
                
                self.send_progress_update(f"\nProcessing target language: {target_lang}")
                self.target_lang.set(target_lang)
                
                # Create language-specific output directory
                lang_output_dir = self.output_path / target_lang
                lang_output_dir.mkdir(parents=True, exist_ok=True)
                
                # Process all files for this language
                if self.selection_mode.get() == "folder":
                    for input_path in self.input_paths:
                        files = self.get_all_files_recursive(input_path)
                        for file_path in files:
                            if self.stop_flag.is_set():
                                return
                            self.process_file(file_path, lang_output_dir)
                else:
                    for file_path in self.input_paths:
                        if self.stop_flag.is_set():
                            return
                        self.process_file(file_path, lang_output_dir)
            
            self.after_processing()
            
        except Exception as e:
            self.send_progress_update(f"Error during processing: {str(e)}")
            logging.exception("Error during multiple language processing")


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
        
        # Configuration menu
        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.config_menu.add_command(label="API Keys", command=self.open_api_key_config)
        self.menu_bar.add_cascade(label="Configuration", menu=self.config_menu)
        
        # Help menu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu.add_command(label="Tool Overview", command=self.show_tool_overview)
        self.help_menu.add_command(label="API Requirements", command=self.show_api_requirements)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="About", command=self.show_about)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        
        self.config(menu=self.menu_bar)

        # Notebook (Tab Control)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # Tool Frames
        self.pptx_translation_tool = self.create_tool_tab("PPTX Translation", PPTXTranslationTool)
        self.audio_transcription_tool = self.create_tool_tab("Audio Transcription", AudioTranscriptionTool)
        self.text_translation_tool = self.create_tool_tab("Text Translation", TextTranslationTool)
        self.pptx_to_pdf_tool = self.create_tool_tab("PPTX to PDF/PNG/WEBP", PPTXtoPDFTool)
        self.text_to_speech_tool = self.create_tool_tab("Text to Speech", TextToSpeechTool)  
        self.video_merge_tool = self.create_tool_tab("Video Merge", VideoMergeTool)
        self.sequential_tool = self.create_tool_tab("Sequential Processing", SequentialProcessingTool)




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
        
        # Map tool classes to description keys
        tool_description_map = {
            PPTXTranslationTool: "pptx_translation",
            AudioTranscriptionTool: "audio_transcription", 
            TextTranslationTool: "text_translation",
            PPTXtoPDFTool: "pptx_to_pdf_png",
            TextToSpeechTool: "text_to_speech",
            VideoMergeTool: "video_merge",
            SequentialProcessingTool: "sequential_processing"
        }
        
        # Get tool description key
        tool_key = tool_description_map.get(tool_class)
        
        # Add description at the top of the tab
        if tool_key:
            self.add_tool_description(frame, tool_key)
        
        tool = tool_class(
            master=frame,
            config_manager=self.config_manager,
            progress_queue=self.progress_queue
        )
        
        self.create_tool_ui(frame, tool)
        return tool

    def add_tool_description(self, frame, tool_key):
        """Add description and help information to the tool tab."""
        try:
            # Get tool information
            tool_info = get_tool_info(tool_key)
            if not tool_info:
                return
            
            desc = tool_info["description"]
            req = tool_info["requirements"]
            tips = tool_info["tips"]
            
            # Create description frame
            desc_frame = ttk.LabelFrame(frame, text=" Tool Information", padding=10)
            desc_frame.pack(fill="x", padx=5, pady=5)
            
            # Main description
            desc_label = tk.Label(desc_frame, text=desc["description"], 
                                font=("Arial", 10, "bold"), fg="navy", wraplength=700)
            desc_label.pack(anchor="w")
            
            # Detailed description
            detail_label = tk.Label(desc_frame, text=desc["details"], 
                                  font=("Arial", 9), fg="gray40", wraplength=700)
            detail_label.pack(anchor="w", pady=(2, 8))
            
            # API requirement info
            if req.get("api_required"):
                api_text = f"🔑 Requires: {req['api_required']} API key"
                if req["api_required"] == "Multiple":
                    api_text = "🔑 Requires: Multiple API keys (see Configuration menu)"
                api_label = tk.Label(desc_frame, text=api_text, 
                                   font=("Arial", 9), fg="red")
                api_label.pack(anchor="w")
            else:
                no_api_label = tk.Label(desc_frame, text="✅ No API key required", 
                                      font=("Arial", 9), fg="green")
                no_api_label.pack(anchor="w")
            
            # Quick tips (collapsible)
            if tips:
                tips_frame = ttk.Frame(desc_frame)
                tips_frame.pack(fill="x", pady=(5, 0))
                
                # Tips toggle button
                self.tips_visible = tk.BooleanVar(value=False)
                tips_btn = tk.Button(tips_frame, text="💡 Show Quick Tips", 
                                   command=lambda: self.toggle_tips(tips_frame, tool_key, tips))
                tips_btn.pack(anchor="w")
                
        except Exception as e:
            # Silently handle any errors in description display
            logging.warning(f"Could not add description for {tool_key}: {e}")

    def add_tab_tooltip(self, tab_name, tool_key):
        """Add tooltip to notebook tab."""
        try:
            short_desc = get_short_description(tool_key)
            if short_desc and short_desc != "Tool description not available":
                # Create a simple tooltip by binding to the tab
                self.create_tooltip_for_tab(tab_name, short_desc)
        except Exception as e:
            logging.warning(f"Could not add tooltip for {tool_key}: {e}")

    def create_tooltip_for_tab(self, tab_name, description):
        """Create a tooltip for a specific tab."""
        def show_tooltip(event):
            # Simple tooltip implementation - could be enhanced
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            
            label = tk.Label(tooltip, text=description, background="lightyellow", 
                           relief="solid", borderwidth=1, font=("Arial", 9),
                           wraplength=300)
            label.pack()
            
            # Auto-hide after 3 seconds
            tooltip.after(3000, tooltip.destroy)
        
        # This is a simplified tooltip - in a full implementation you'd want
        # to bind to the actual tab widget, but tkinter notebook tabs are complex
        pass

    def toggle_tips(self, parent_frame, tool_key, tips):
        """Toggle display of quick tips."""
        # Remove existing tips if any
        for widget in parent_frame.winfo_children():
            if isinstance(widget, tk.Frame) and hasattr(widget, 'tips_frame'):
                widget.destroy()
                return
        
        # Create tips display
        tips_display = tk.Frame(parent_frame)
        tips_display.tips_frame = True  # Mark as tips frame
        tips_display.pack(fill="x", pady=(5, 0))
        
        tk.Label(tips_display, text="Quick Tips:", font=("Arial", 9, "bold")).pack(anchor="w")
        
        for i, tip in enumerate(tips, 1):
            tip_label = tk.Label(tips_display, text=f"  {i}. {tip}", 
                               font=("Arial", 8), fg="gray30", wraplength=650)
            tip_label.pack(anchor="w", padx=(10, 0))

    def create_tool_ui(self, frame, tool):
        """Creates the UI elements for a specific tool."""
        
        tool.create_selection_mode_controls(frame)

        # If the tool has language selection capability, create the UI
        if isinstance(tool, LanguageSelectionMixin):
            tool.create_language_selection()

        if hasattr(tool, 'create_specific_controls') and callable(tool.create_specific_controls):
            tool.create_specific_controls(frame)
        
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
        """Opens a dialog to configure API keys, including Adobe Client ID/Secret."""
        api_config_window = tk.Toplevel(self)
        api_config_window.title("API Key Configuration")
        api_config_window.geometry("550x250") # Example adjusted size

        api_keys = self.config_manager.get_api_keys()
        api_entries = {}

        managed_api_names = [
            "openai",
            "deepl",
            "elevenlabs",
            "adobe_client_id",      # Managed here
            "adobe_client_secret"   # Managed here
        ]

        for api_name in managed_api_names:
            frame = ttk.Frame(api_config_window)
            frame.pack(pady=5, padx=10, fill="x")

            if api_name == "adobe_client_id":
                label_text = "Adobe Client ID:"
            elif api_name == "adobe_client_secret":
                 label_text = "Adobe Client Secret:"
            else:
                 label_text = f"{api_name.replace('_', ' ').title()} API Key:"

            # Set the width when CREATING the Label
            label = ttk.Label(frame, text=label_text, width=20) # Set width here
            # Pack the label WITHOUT the width option
            label.pack(side=tk.LEFT, padx=5, anchor='w') # Removed width=20 from here

            entry = ttk.Entry(frame, width=45)
            if "secret" in api_name.lower():
                entry.config(show="*")
            entry.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

            if api_name in api_keys and api_keys[api_name]:
                entry.insert(0, api_keys[api_name])

            api_entries[api_name] = entry

        save_button = ttk.Button(api_config_window, text="Save",
                               command=lambda: self.save_api_keys(api_entries, api_config_window))
        save_button.pack(pady=15)

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

    def show_tool_overview(self):
        """Show overview of all available tools."""
        try:
            from core.tool_descriptions import get_tool_list_for_gui
            
            # Create overview window
            overview_window = tk.Toplevel(self)
            overview_window.title("Tool Overview")
            overview_window.geometry("700x500")
            overview_window.resizable(True, True)
            
            # Create scrollable frame
            canvas = tk.Canvas(overview_window)
            scrollbar = ttk.Scrollbar(overview_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Title
            title_label = tk.Label(scrollable_frame, text="Language Toolkit - Tool Overview", 
                                 font=("Arial", 16, "bold"), fg="navy")
            title_label.pack(pady=10)
            
            # Get all tools
            tools = get_tool_list_for_gui()
            
            for tool in tools:
                # Tool frame
                tool_frame = ttk.LabelFrame(scrollable_frame, text=tool["title"], padding=10)
                tool_frame.pack(fill="x", padx=10, pady=5)
                
                # Description
                desc_label = tk.Label(tool_frame, text=tool["description"], 
                                    font=("Arial", 10), wraplength=600)
                desc_label.pack(anchor="w")
                
                # API requirement
                if tool["has_api_requirement"]:
                    api_label = tk.Label(tool_frame, text=f"🔑 Requires: {tool['api_required']} API key", 
                                       font=("Arial", 9), fg="red")
                    api_label.pack(anchor="w", pady=(5, 0))
                else:
                    api_label = tk.Label(tool_frame, text="✅ No API key required", 
                                       font=("Arial", 9), fg="green")
                    api_label.pack(anchor="w", pady=(5, 0))
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not show tool overview: {e}")

    def show_api_requirements(self):
        """Show API key requirements for all tools."""
        try:
            from core.tool_descriptions import get_tool_requirements
            
            requirements = get_tool_requirements()
            
            # Create requirements window
            req_window = tk.Toplevel(self)
            req_window.title("API Key Requirements")
            req_window.geometry("600x400")
            
            # Title
            title_label = tk.Label(req_window, text="API Key Requirements", 
                                 font=("Arial", 16, "bold"), fg="navy")
            title_label.pack(pady=10)
            
            # Instructions
            instructions = tk.Label(req_window, 
                                  text="Configure API keys via Configuration → API Keys menu",
                                  font=("Arial", 10), fg="gray40")
            instructions.pack(pady=(0, 10))
            
            # Scrollable frame for requirements
            canvas = tk.Canvas(req_window)
            scrollbar = ttk.Scrollbar(req_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            for tool_name, req in requirements.items():
                tool_frame = ttk.LabelFrame(scrollable_frame, text=tool_name.replace("_", " ").title(), padding=10)
                tool_frame.pack(fill="x", padx=10, pady=5)
                
                if req["api_required"]:
                    req_label = tk.Label(tool_frame, text=f"Required: {req['api_required']}", 
                                       font=("Arial", 10, "bold"), fg="red")
                    req_label.pack(anchor="w")
                    
                    desc_label = tk.Label(tool_frame, text=req["api_description"], 
                                        font=("Arial", 9), fg="gray40")
                    desc_label.pack(anchor="w")
                else:
                    no_req_label = tk.Label(tool_frame, text="No API key required", 
                                          font=("Arial", 10), fg="green")
                    no_req_label.pack(anchor="w")
            
            canvas.pack(side="left", fill="both", expand=True, padx=(10, 0))
            scrollbar.pack(side="right", fill="y", padx=(0, 10))
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not show API requirements: {e}")

    def show_about(self):
        """Show about dialog."""
        about_text = """Language Toolkit
        
A comprehensive suite of tools for language processing, document conversion, and content creation.

Features:
• PowerPoint Translation
• Audio Transcription  
• Text Translation
• Document Conversion
• Text-to-Speech Generation
• Video Creation and Merging
• Sequential Processing Workflows

Built with Python and integrates with leading AI services for professional-quality results."""
        
        messagebox.showinfo("About Language Toolkit", about_text)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()

