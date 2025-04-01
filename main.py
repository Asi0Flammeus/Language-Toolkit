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
        
        # Initialize display attributes
        self.input_paths_display = None
        self.output_path_display = None

    def select_input_paths(self):
        """Opens a dialog to select one or more input files or directories."""
        paths = filedialog.askdirectory(title="Select Input Directory") if isinstance(self, PPTXTranslationTool) \
               else filedialog.askopenfilenames(title="Select Input Files")
        
        if paths:
            if isinstance(paths, str):  # Single directory selected
                self.input_paths = [Path(paths)]
            else:  # Multiple files selected
                self.input_paths = [Path(p) for p in paths]
            logging.info(f"Input paths selected: {self.input_paths}")
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

    def process_paths(self):
        """Enhanced process_paths method with recursive directory handling."""
        if not self.input_paths:
            messagebox.showerror("Error", "No input paths selected.")
            return

        if self.output_path is None:
            result = messagebox.askyesno("Question", 
                "No output path selected. Output to same directory as input?")
            if result:
                if not self.set_same_as_input():
                    return
            else:
                messagebox.showinfo("Info", "Processing cancelled.")
                return

        threading.Thread(target=self._process_paths_threaded, daemon=True).start()

    def _process_paths_threaded(self):
        """Enhanced threaded processing with recursive directory handling."""
        try:
            self.before_processing()

            total_files = self._count_files()
            processed_files = 0

            for input_path in self.input_paths:
                if input_path.is_file():
                    self._process_single_file(input_path, self.output_path)
                    processed_files += 1
                    self.send_progress_update(f"Processed {processed_files}/{total_files} files")
                elif input_path.is_dir():
                    for file_path in self._get_files_recursively(input_path):
                        output_subdir = self._get_output_subdir(file_path, input_path)
                        self._process_single_file(file_path, output_subdir)
                        processed_files += 1
                        self.send_progress_update(f"Processed {processed_files}/{total_files} files")

            self.after_processing()

        except Exception as e:
            logging.exception("An error occurred during processing:")
            self.send_progress_update(f"Error: {e}")
        finally:
            self.send_progress_update("Processing complete.")

    def _count_files(self):
        """Counts total number of files to be processed."""
        total = 0
        for path in self.input_paths:
            if path.is_file():
                total += 1
            elif path.is_dir():
                total += sum(1 for _ in self._get_files_recursively(path))
        return total

    def _get_files_recursively(self, directory):
        """Generator that yields all relevant files in directory tree."""
        for path in directory.rglob("*"):
            if path.is_file() and self._is_supported_file(path):
                yield path

    def _is_supported_file(self, file_path):
        """Check if file is supported by the tool."""
        return file_path.suffix.lower() == ".pptx"

    def _get_output_subdir(self, file_path, input_base_path):
        """Maintains directory structure in output path."""
        if self.output_path == input_base_path:
            return input_base_path
        
        relative_path = file_path.parent.relative_to(input_base_path)
        output_subdir = self.output_path / relative_path
        output_subdir.mkdir(parents=True, exist_ok=True)
        return output_subdir

    def _process_single_file(self, file_path, output_dir):
        """Process a single file with proper error handling."""
        try:
            self.send_progress_update(f"Processing {file_path.name}...")
            self.process_file(file_path, output_dir)
        except Exception as e:
            self.send_progress_update(f"Error processing {file_path.name}: {e}")
            logging.exception(f"Error processing {file_path}")

    def send_progress_update(self, message: str):
        """Sends a progress update message to the GUI."""
        self.progress_queue.put(message)

    def before_processing(self):
        """Hook for pre-processing setup."""
        pass

    def after_processing(self):
        """Hook for post-processing cleanup."""
        pass

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Abstract method for processing a single file."""
        raise NotImplementedError("Subclasses must implement process_file()")


class PPTXTranslationTool(ToolBase):
    """Translates PPTX files from one language to another."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        
        # Language selection variables
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")
        
        # Create language selection frame
        self.create_language_selection()
        
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
            import pptx
            from pptx import Presentation
            import deepl

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
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        try:
                            # Store original formatting
                            original_paras = []
                            for para in shape.text_frame.paragraphs:
                                para_format = {
                                    'alignment': para.alignment,
                                    'level': para.level,
                                    'line_spacing': para.line_spacing,
                                    'space_before': para.space_before,
                                    'space_after': para.space_after,
                                    'runs': []
                                }
                                
                                for run in para.runs:
                                    run_format = {
                                        'font_name': run.font.name,
                                        'size': run.font.size,
                                        'bold': run.font.bold,
                                        'italic': run.font.italic,
                                        'underline': run.font.underline,
                                        'color': run.font.color.rgb if run.font.color else None,
                                        'language': run.font.language_id if hasattr(run.font, 'language_id') else None
                                    }
                                    para_format['runs'].append(run_format)
                                original_paras.append(para_format)

                            # Translate the text
                            translated_text = translator.translate_text(
                                shape.text,
                                source_lang=source_lang,
                                target_lang=target_lang
                            )
                            
                            # Clear existing text
                            text_frame = shape.text_frame
                            text_frame.clear()
                            
                            # Split translated text into paragraphs
                            translated_paragraphs = translated_text.text.split('\n')
                            
                            # Restore formatting
                            for i, (trans_text, orig_format) in enumerate(zip(translated_paragraphs, original_paras)):
                                if i == 0:
                                    p = text_frame.paragraphs[0]
                                else:
                                    p = text_frame.add_paragraph()
                                
                                # Restore paragraph formatting
                                p.alignment = orig_format['alignment']
                                p.level = orig_format['level']
                                if orig_format['line_spacing']:
                                    p.line_spacing = orig_format['line_spacing']
                                if orig_format['space_before']:
                                    p.space_before = orig_format['space_before']
                                if orig_format['space_after']:
                                    p.space_after = orig_format['space_after']

                                # Add text and restore run formatting
                                if orig_format['runs']:
                                    # Split translated text proportionally among runs
                                    words = trans_text.split()
                                    runs_count = len(orig_format['runs'])
                                    words_per_run = len(words) // runs_count
                                    extra_words = len(words) % runs_count

                                    start_idx = 0
                                    for j, run_format in enumerate(orig_format['runs']):
                                        # Calculate words for this run
                                        word_count = words_per_run + (1 if j < extra_words else 0)
                                        end_idx = start_idx + word_count
                                        run_text = ' '.join(words[start_idx:end_idx])
                                        start_idx = end_idx

                                        # Add run with original formatting
                                        run = p.add_run()
                                        run.text = run_text + (' ' if j < runs_count - 1 else '')
                                        
                                        # Restore run formatting
                                        font = run.font
                                        if run_format['font_name']:
                                            font.name = run_format['font_name']
                                        if run_format['size']:
                                            font.size = run_format['size']
                                        if run_format['bold']:
                                            font.bold = run_format['bold']
                                        if run_format['italic']:
                                            font.italic = run_format['italic']
                                        if run_format['underline']:
                                            font.underline = run_format['underline']
                                        if run_format['color']:
                                            font.color.rgb = run_format['color']
                                        if run_format['language']:
                                            font.language_id = run_format['language']
                                else:
                                    # If no runs in original, add text as single run
                                    p.text = trans_text
                                    
                        except Exception as e:
                            self.send_progress_update(f"Error translating shape: {e}")
                    
                    processed_shapes += 1
                    if processed_shapes % 10 == 0:
                        progress = (processed_shapes / total_shapes) * 100
                        self.send_progress_update(f"Translation progress: {progress:.1f}%")

            # Create output filename
            output_file = output_dir / f"{input_file.stem}_{target_lang}{input_file.suffix}"
            
            # Save the translated presentation
            prs.save(output_file)
            return output_file
            
        except ImportError:
            raise ImportError("Required libraries not installed. Please install python-pptx and deepl")
        except Exception as e:
            raise Exception(f"Translation failed: {str(e)}")

class AudioTranscriptionTool(ToolBase):
    """Transcribes audio files using OpenAI's Whisper API."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        
        # Supported audio extensions
        self.AUDIO_EXTENSIONS = ('.wav', '.mp3', '.m4a', '.webm', '.mp4', '.mpga', '.mpeg')
        self.MAX_SUPPORTED_AUDIO_SIZE_MB = 20

        # Get OpenAI API key from config
        self.api_key = self.config_manager.get_api_keys().get("openai")
        if not self.api_key:
            logging.warning("OpenAI API key not configured")

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Processes a single audio file."""
        if input_file.suffix.lower() not in self.AUDIO_EXTENSIONS:
            self.send_progress_update(f"Skipping non-audio file: {input_file}")
            return

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
        
        # If the tool is PPTXTranslationTool, let it create its language selection UI
        if isinstance(tool, PPTXTranslationTool):
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

        # Process Button
        process_button = ttk.Button(frame, text="Process", command=tool.process_paths)
        process_button.pack(pady=10)

        # Drag and Drop
        input_frame.drop_target_register(DND_FILES)
        input_frame.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, tool))

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

