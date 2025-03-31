import tkinter as tk
from tkinter import ttk
from tkinterdnd2 import TkinterDnD, DND_FILES  # Import TkinterDnD
import queue
import sys
from pathlib import Path

sys.path.append("../")
# Internal imports (absolute)
from config.config_manager import ConfigManager
from config.styles import BACKGROUND_COLOR, ACCENT_COLOR
from tools.pptx_to_png_tool import PPTXToPNGTool
from tools.text_translation_tool import TextTranslationTool
from tools.audio_transcription_tool import AudioTranscriptionTool
from tools.audio_generation_tool import AudioGenerationTool
from tools.video_generation_tool import VideoGenerationTool
from tools.pptx_translation_tool import PPTXTranslationTool
from gui.config_dialogs import ConfigDialogs

class MainApp(TkinterDnD.Tk):  # Inherit from TkinterDnD.Tk
    """Main application class."""

    def __init__(self):
        super().__init__()  # Initialize TkinterDnD.Tk

        self.title("Course Video Tools")
        self.geometry("800x600")

        # --- Initialize Components ---
        self.config_manager = ConfigManager()
        self.progress_queue = queue.Queue()  # Queue for progress updates

        # --- Styling ---
        self.configure(bg=BACKGROUND_COLOR)
        self.style = ttk.Style()
        self.style.configure("TNotebook", background=BACKGROUND_COLOR, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=BACKGROUND_COLOR, foreground=ACCENT_COLOR, borderwidth=0)
        self.style.map("TNotebook.Tab", background=[("selected", ACCENT_COLOR)], foreground=[("selected", BACKGROUND_COLOR)])
        self.style.configure("TFrame", background=BACKGROUND_COLOR)
        self.style.configure("TLabel", background=BACKGROUND_COLOR, foreground=ACCENT_COLOR)
        self.style.configure("TButton", background=ACCENT_COLOR, foreground=BACKGROUND_COLOR)

        # --- UI Elements ---
        self.create_widgets()
        self.process_progress_queue()  # Start checking for progress updates

    def create_widgets(self):
        """Creates the main UI elements."""
        # --- Menu ---
        self.menu_bar = tk.Menu(self)
        self.menu_bar.config(bg=BACKGROUND_COLOR, fg=ACCENT_COLOR)

        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.config_menu.config(bg=BACKGROUND_COLOR, fg=ACCENT_COLOR)
        #self.config_menu.add_command(label="API Keys", command=self.open_api_key_config) # Moved to ConfigDialogs
        #self.config_menu.add_command(label="ElevenLabs Voices", command=self.open_elevenlabs_config) # Moved to ConfigDialogs
        self.menu_bar.add_cascade(label="Configuration", menu=self.config_menu)
        self.config(menu=self.menu_bar)

        # ---Config Dialogs---
        self.config_dialogs = ConfigDialogs(self, self.config_manager)
        self.config_menu.add_command(label="API Keys", command=self.config_dialogs.open_api_key_config)
        self.config_menu.add_command(label="ElevenLabs Voices", command=self.config_dialogs.open_elevenlabs_config)


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

        self.progress_text = tk.Text(self, height=10, width=80, state="disabled", bg=BACKGROUND_COLOR, fg=ACCENT_COLOR)
        self.progress_text.pack(expand=False, fill="x", padx=10, pady=(0, 10))

        self.sb = tk.Scrollbar(self, command=self.progress_text.yview, bg=BACKGROUND_COLOR, activebackground=ACCENT_COLOR)
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

