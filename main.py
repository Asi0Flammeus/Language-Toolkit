import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import json
import os
import subprocess
import logging
from pathlib import Path
import threading
import queue  # Import the queue module

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
            logging.warning(f"Config file not found: {file_path}.  Creating a default.")
            return {}  # Return an empty dictionary if the file doesn't exist
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {file_path}.  Please check the file for errors.")
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
        self.save_json(self.api_keys, self.api_keys_file)



class ToolBase:
    """
    Base class for all tools in the application.  Handles common functionalities
    like file selection, output path management, and progress updates.
    """

    def __init__(self, master, config_manager, progress_queue):
        self.master = master
        self.config_manager = config_manager
        self.progress_queue = progress_queue  # Receive progress updates
        self.input_paths = []
        self.output_path = None
        self.supported_languages = self.config_manager.get_languages()  # Load supported languages

    def select_input_paths(self):
        """Opens a dialog to select one or more input files or directories."""
        paths = filedialog.askopenfilenames(title="Select Input Files/Directories")
        if paths:
            self.input_paths = [Path(p) for p in paths]
            logging.info(f"Input paths selected: {self.input_paths}")
            self.update_input_display()  # Update GUI display
            return True  # Indicate success
        return False  # Indicate failure

    def select_output_path(self):
        """Opens a dialog to select an output directory."""
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_path = Path(path)
            logging.info(f"Output path selected: {self.output_path}")
            self.update_output_display()  # Update GUI display
            return True  # Indicate success
        return False  # Indicate failure

    def set_same_as_input(self):
        """Sets the output path to be the same as the input path."""
        if self.input_paths:
            # If multiple input paths, take the parent of the first one
            self.output_path = self.input_paths[0].parent
            logging.info(f"Output path set to same as input: {self.output_path}")
            self.update_output_display()
            return True
        else:
            messagebox.showwarning("Warning", "Please select input paths first.")
            return False


    def process_paths(self):
        """
        Processes the selected input paths.  This should be overridden by subclasses
        to implement the specific tool logic.  Handles both single files and directories,
        and applies the tool recursively to maintain directory structure if an output
        path is provided.
        """
        if not self.input_paths:
            messagebox.showerror("Error", "No input paths selected.")
            return

        if self.output_path is None:
             result = messagebox.askyesno("Question", "No output path selected.  Output to same directory as input?")
             if result:
                if not self.set_same_as_input():
                    return # Abort if setting same as input fails
             else:
                messagebox.showinfo("Info", "Processing cancelled.")
                return
            
        # Start the processing in a separate thread
        threading.Thread(target=self._process_paths_threaded, daemon=True).start()
    
    def _process_paths_threaded(self):
        """
        Helper function to run the path processing in a separate thread, allowing
        for progress updates and a responsive GUI.
        """
        try:
            self.before_processing()  # Perform setup before processing starts

            for input_path in self.input_paths:
                if input_path.is_file():
                    self.process_file(input_path, self.output_path)
                elif input_path.is_dir():
                    self.process_directory(input_path, self.output_path)
                else:
                    self.send_progress_update(f"Skipping invalid path: {input_path}")

            self.after_processing()  # Perform cleanup and finalization after processing is complete

        except Exception as e:
            logging.exception("An error occurred during processing:")
            self.send_progress_update(f"Error: {e}")

        finally:
            self.send_progress_update("Processing complete.")

    def process_file(self, input_file: Path, output_dir: Path = None):
        """
        Processes a single file.  This method *must* be overridden by subclasses
        to implement the specific tool logic for a single file.
        """
        raise NotImplementedError("Subclasses must implement process_file()")

    def process_directory(self, input_dir: Path, output_dir: Path = None):
        """
        Processes a directory recursively.  If an output directory is provided,
        it maintains the directory structure.  Calls `process_file` for each file found.
        """
        if output_dir:
            # Create corresponding directory structure in the output path
            relative_path = input_dir.relative_to(self.input_paths[0]) # Assuming self.input_paths[0] is the base input dir
            target_dir = output_dir / relative_path
            target_dir.mkdir(parents=True, exist_ok=True)

            for item in input_dir.iterdir():
                if item.is_file():
                    self.process_file(item, target_dir)
                elif item.is_dir():
                    self.process_directory(item, target_dir)  # Recursive call
        else:
            # Output to the same directory as the input (no directory structure maintained)
            for item in input_dir.iterdir():
                if item.is_file():
                    self.process_file(item, input_dir)
                elif item.is_dir():
                    self.process_directory(item, input_dir)  # Recursive call

    def before_processing(self):
        """
        Performs any setup or initialization steps before processing starts.
        Can be overridden by subclasses.
        """
        pass

    def after_processing(self):
        """
        Performs any cleanup or finalization steps after processing is complete.
        Can be overridden by subclasses.
        """
        pass

    def send_progress_update(self, message: str):
        """Sends a progress update message to the GUI."""
        self.progress_queue.put(message)

    # --- GUI Update Methods --- (To be implemented in subclasses)
    def update_input_display(self):
        """Updates the GUI to display the selected input paths."""
        pass

    def update_output_display(self):
        """Updates the GUI to display the selected output path."""
        pass
class PPTXToPNGTool(ToolBase):
    """Converts PPTX files to PNG images (slides by slides) using LibreOffice and ImageMagick."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.adobe_api_key = config_manager.get_api_keys().get("adobe", None)  # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Converts a single PPTX file to PNG images."""
        if input_file.suffix.lower() != ".pptx":
            self.send_progress_update(f"Skipping non-PPTX file: {input_file}")
            return

        try:
            self.send_progress_update(f"Converting {input_file.name} to PNG...")
            # Build the command
            command = [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(input_file)
            ]

            # Execute the command
            result = subprocess.run(command, capture_output=True, text=True, check=True)

            # Extract PDF file path from output directory and input file name
            pdf_file = output_dir / input_file.with_suffix(".pdf").name

            # Convert PDF to a series of PNGs with ImageMagick
            convert_command = [
                "magick",
                "convert",
                "-density",
                "300",  # You can adjust the DPI here
                str(pdf_file),
                str(output_dir / f"{input_file.stem}-%03d.png")  # output to png files in the out_dir
            ]

            # Execute the conversion command
            result = subprocess.run(convert_command, capture_output=True, text=True, check=True)
            self.send_progress_update(f"Successfully converted {input_file.name} to PNG images in {output_dir}")

        except subprocess.CalledProcessError as e:
            error_message = f"Error converting {input_file.name}: {e.stderr}"
            self.send_progress_update(error_message)
            logging.error(error_message)
        except Exception as e:
            error_message = f"Unexpected error processing {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)
class TextTranslationTool(ToolBase):
    """Translates text files from one language to another."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.source_lang = tk.StringVar(value="en")  # Default source language
        self.target_lang = tk.StringVar(value="fr")  # Default target language
        self.api_key = config_manager.get_api_keys().get("deepl", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Translates a single text file."""
        if input_file.suffix.lower() != ".txt":
            self.send_progress_update(f"Skipping non-TXT file: {input_file}")
            return

        try:
            self.send_progress_update(f"Translating {input_file.name}...")
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()

            # Translation logic (replace with your actual translation API call)
            translated_text = self.translate_text(text, self.source_lang.get(), self.target_lang.get())

            output_file = output_dir / f"{input_file.stem}_translated.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(translated_text)

            self.send_progress_update(f"Successfully translated {input_file.name} to {output_file.name}")

        except Exception as e:
            error_message = f"Error translating {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
         """
         Placeholder for translation API call.  Replace with your actual
         translation logic (e.g., using DeepL, Google Translate, etc.).
         """
         #Mock translation
         return f"Translated text from {source_lang} to {target_lang}: {text}"
class AudioTranscriptionTool(ToolBase):
    """Transcribes audio files to text files."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.api_key = config_manager.get_api_keys().get("openai", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Transcribes a single audio file."""
        if input_file.suffix.lower() not in [".mp3", ".wav", ".m4a"]:
            self.send_progress_update(f"Skipping unsupported audio file: {input_file}")
            return

        try:
            self.send_progress_update(f"Transcribing {input_file.name}...")

            # Transcription logic (replace with your actual transcription API call)
            transcript = self.transcribe_audio(input_file)

            output_file = output_dir / f"{input_file.stem}_transcript.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcript)

            self.send_progress_update(f"Successfully transcribed {input_file.name} to {output_file.name}")

        except Exception as e:
            error_message = f"Error transcribing {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def transcribe_audio(self, audio_file: Path) -> str:
        """
        Placeholder for audio transcription API call.  Replace with your actual
        transcription logic (e.g., using OpenAI Whisper API).
        """
        #Mock transcription
        return f"Transcript of {audio_file.name}"
class AudioGenerationTool(ToolBase):
    """Generates audio from text files using ElevenLabs."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.voice_id = tk.StringVar()  # Voice ID for ElevenLabs
        self.elevenlabs_config = config_manager.get_elevenlabs_config() # Load elevenlabs config
        self.api_key = config_manager.get_api_keys().get("elevenlabs", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Generates audio from a single text file."""
        if input_file.suffix.lower() != ".txt":
            self.send_progress_update(f"Skipping non-TXT file: {input_file}")
            return

        try:
            self.send_progress_update(f"Generating audio from {input_file.name}...")
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()

            # Audio generation logic (replace with your actual ElevenLabs API call)
            audio_file = self.generate_audio(text, self.voice_id.get())

            output_file = output_dir / f"{input_file.stem}.mp3"
            # Save the audio file
            self.send_progress_update(f"Successfully generated audio from {input_file.name} to {output_file.name}")

        except Exception as e:
            error_message = f"Error generating audio from {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def generate_audio(self, text: str, voice_id: str) -> Path:
        """
        Placeholder for audio generation API call.  Replace with your actual
        ElevenLabs API logic.
        """
        #Mock audio generation
        return Path("dummy_audio.mp3")
class VideoGenerationTool(ToolBase):
    """Generates a video from a folder of PNG images and MP3 audio files."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)

    def process_directory(self, input_dir: Path, output_dir: Path = None):
        """Generates a video from a folder containing PNG images and MP3 audio files."""

        try:
            self.send_progress_update(f"Generating video from {input_dir.name}...")

            # Video generation logic
            output_file = self.generate_video(input_dir, output_dir)

            self.send_progress_update(f"Successfully generated video to {output_file.name}")

        except Exception as e:
            error_message = f"Error generating video from {input_dir.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def process_file(self, input_file: Path, output_dir: Path = None):
        """
        Dummy implementation to satisfy abstract method requirement.  Video generation
        tool operates on directories, not individual files.
        """
        pass

    def generate_video(self, input_dir: Path, output_dir: Path = None) -> Path:
        """
        Placeholder for video generation logic.  Replace with your actual
        video generation logic (e.g., using MoviePy).
        """
        #Mock video generation
        return Path("dummy_video.mp4")
class PPTXTranslationTool(ToolBase):
    """Translates PPTX files from one language to another."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.source_lang = tk.StringVar(value="en")  # Default source language
        self.target_lang = tk.StringVar(value="fr")  # Default target language
        self.api_key = config_manager.get_api_keys().get("deepl", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Translates a single PPTX file."""
        if input_file.suffix.lower() != ".pptx":
            self.send_progress_update(f"Skipping non-PPTX file: {input_file}")
            return

        try:
            self.send_progress_update(f"Translating {input_file.name}...")

            # Translation logic (replace with your actual translation API call)
            translated_file = self.translate_pptx(input_file, self.source_lang.get(), self.target_lang.get(), output_dir)

            self.send_progress_update(f"Successfully translated {input_file.name} to {translated_file.name}")

        except Exception as e:
            error_message = f"Error translating {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def translate_pptx(self, input_file: Path, source_lang: str, target_lang: str, output_dir: Path) -> Path:
        """
        Placeholder for PPTX translation API call.  Replace with your actual
        translation logic (e.g., using DeepL).
        """
        #Mock translation
        return Path("dummy_translated.pptx")

class MainApp(TkinterDnD.Tk):  # Inherit from TkinterDnD.Tk
    """Main application class."""

    def __init__(self):
        super().__init__()  # Initialize TkinterDnD.Tk

        self.title("Course Video Tools")
        self.geometry("800x600")

        # --- Initialize Components ---
        self.config_manager = ConfigManager()
        self.progress_queue = queue.Queue()  # Queue for progress updates

        # --- UI Elements ---
        self.create_widgets()
        self.process_progress_queue()  # Start checking for progress updates

    def create_widgets(self):
        """Creates the main UI elements."""
        # --- Menu ---
        self.menu_bar = tk.Menu(self)
        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.config_menu.add_command(label="API Keys", command=self.open_api_key_config)
        self.menu_bar.add_cascade(label="Configuration", menu=self.config_menu)
        self.config(menu=self.menu_bar)

        # --- Notebook (Tab Control) ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Tool Frames ---
        self.pptx_translation_tool = self.create_tool_tab("PPTX Translation", PPTXTranslationTool)
        self.pptx_to_png_tool = self.create_tool_tab("PPTX to PNG", PPTXToPNGTool)
        self.text_translation_tool = self.create_tool_tab("Text Translation", TextTranslationTool)
        self.audio_transcription_tool = self.create_tool_tab("Audio Transcription", AudioTranscriptionTool)
        self.audio_generation_tool = self.create_tool_tab("Audio Generation", AudioGenerationTool)
        self.video_generation_tool =  self.create_tool_tab("Video Generation", VideoGenerationTool)

        # --- Progress Text Area ---
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
        tool = tool_class(frame, self.config_manager, self.progress_queue)
        self.create_tool_ui(frame, tool)  # Moved UI creation here to be more modular
        return tool

    def create_tool_ui(self, frame, tool):
        """Creates the UI elements for a specific tool."""
        # --- Input Path Selection ---
        input_frame = ttk.Frame(frame)
        input_frame.pack(pady=5)

        input_label = ttk.Label(input_frame, text="Input Path(s):")
        input_label.pack(side=tk.LEFT, padx=5)

        input_button = ttk.Button(input_frame, text="Select Input", command=tool.select_input_paths)
        input_button.pack(side=tk.LEFT, padx=5)
        
        # --- Output Path Selection ---
        output_frame = ttk.Frame(frame)
        output_frame.pack(pady=5)

        output_label = ttk.Label(output_frame, text="Output Path:")
        output_label.pack(side=tk.LEFT, padx=5)

        output_button = ttk.Button(output_frame, text="Select Output", command=tool.select_output_path)
        output_button.pack(side=tk.LEFT, padx=5)

        same_as_input_button = ttk.Button(output_frame, text="Same as Input", command=tool.set_same_as_input)
        same_as_input_button.pack(side=tk.LEFT, padx=5)

        # --- Process Button ---
        process_button = ttk.Button(frame, text="Process", command=tool.process_paths)
        process_button.pack(pady=10)
        
        # --- Drag and Drop (Example, add to relevant frames as needed) ---
        input_frame.drop_target_register(DND_FILES)
        input_frame.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, tool))
    def on_drop(self, event, tool):
        """Handles drag and drop events."""
        # This is a tuple of file paths.
        files = event.data.split()
        tool.input_paths = [Path(f) for f in files]
        logging.info(f"Files dropped: {tool.input_paths}")
        tool.update_input_display()  # Update GUI display
    def open_api_key_config(self):
        """Opens a dialog to configure API keys."""
        api_config_window = tk.Toplevel(self)
        api_config_window.title("API Key Configuration")

        # Load current API keys
        api_keys = self.config_manager.get_api_keys()

        # Create a dictionary to store the entry widgets
        api_entries = {}

        # Iterate through the desired API keys
        for api_name in ["openai", "anthropic", "deepl", "adobe", "elevenlabs", "google"]:
            # Create a frame for each API key
            frame = ttk.Frame(api_config_window)
            frame.pack(pady=5, padx=10, fill="x")

            # Create label
            label = ttk.Label(frame, text=f"{api_name.capitalize()} API Key:")
            label.pack(side=tk.LEFT, padx=5)

            # Create entry field
            entry = ttk.Entry(frame, width=40)
            entry.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

            # Insert current API key, if available
            if api_name in api_keys:
                entry.insert(0, api_keys[api_name])

            # Store the entry widget in the dictionary
            api_entries[api_name] = entry

        # --- Save Button ---
        save_button = ttk.Button(api_config_window, text="Save", command=lambda: self.save_api_keys(api_entries, api_config_window))
        save_button.pack(pady=10)

    def save_api_keys(self, api_entries, window):
        """Saves the API keys from the configuration dialog."""
        # Retrieve the API keys from the entry widgets
        api_keys = {}
        for api_name, entry in api_entries.items():
            api_keys[api_name] = entry.get()

        # Update the config manager's api_keys
        self.config_manager.api_keys = api_keys  # Update the internal dictionary first
        
        # Save the API keys to the configuration file
        self.config_manager.save_api_keys()  # Don't pass api_keys as an argument
        window.destroy()  # Close the configuration window
        messagebox.showinfo("Info", "API keys saved successfully.")


    def process_progress_queue(self):
        """Processes messages from the progress queue."""
        try:
            while True:
                message = self.progress_queue.get_nowait()
                self.update_progress_text(message)
        except queue.Empty:
            pass  # Queue is empty, do nothing

        self.after(100, self.process_progress_queue)  # Check again after 100ms

    def update_progress_text(self, message):
        """Updates the progress text area with a new message."""
        self.progress_text.config(state="normal")  # Enable editing
        self.progress_text.insert(tk.END, message + "\n")
        self.progress_text.config(state="disabled")  # Disable editing
        self.progress_text.see(tk.END)  # Scroll to the end

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()

