"""Main application entry point for Language Toolkit."""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
import queue
import logging
from pathlib import Path

# Core imports
from core.config import ConfigManager
from core.tool_descriptions import get_short_description, get_tool_info, get_quick_tips

# UI components
from ui.base_tool import ToolBase
from ui.mixins import LanguageSelectionMixin

# Tool imports
from tools import (
    TextToSpeechTool,
    AudioTranscriptionTool,
    PPTXTranslationTool,
    TextTranslationTool,
    PPTXtoPDFTool,
    TranscriptCleanerTool,
    VideoMergeTool,
    SequentialVideoProcessingTool,
    SequentialImageProcessingTool,
    RewardEvaluatorTool
)

# Constants
SUPPORTED_LANGUAGES_FILE = "supported_languages.json"
API_KEYS_FILE = "api_keys.json"

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class MainApp(TkinterDnD.Tk):
    """Main application class."""

    def __init__(self):
        super().__init__()

        self.title("Course Video Tools")
        self.geometry("800x600")

        # Initialize components
        self.config_manager = ConfigManager(
            use_project_api_keys=True,
            languages_file=SUPPORTED_LANGUAGES_FILE,
            api_keys_file=API_KEYS_FILE
        )
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

        # Create main paned window for resizable layout
        self.main_paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.main_paned.pack(expand=True, fill="both", padx=10, pady=10)

        # Top pane: Notebook (Tab Control)
        self.top_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.top_frame, weight=3)

        self.notebook = ttk.Notebook(self.top_frame)
        self.notebook.pack(expand=True, fill="both")

        # Tool Frames
        self.pptx_translation_tool = self.create_tool_tab("PPTX Translation", PPTXTranslationTool)
        self.audio_transcription_tool = self.create_tool_tab("Audio Transcription", AudioTranscriptionTool)
        self.transcript_cleaner_tool = self.create_tool_tab("Clean Transcript", TranscriptCleanerTool)
        self.text_translation_tool = self.create_tool_tab("Text Translation", TextTranslationTool)
        self.pptx_to_pdf_tool = self.create_tool_tab("PPTX Export", PPTXtoPDFTool)
        self.text_to_speech_tool = self.create_tool_tab("Text to Speech", TextToSpeechTool)  
        self.video_merge_tool = self.create_tool_tab("Video Merge", VideoMergeTool)
        self.sequential_tool = self.create_tool_tab("SVP", SequentialVideoProcessingTool)
        self.sip_tool = self.create_tool_tab("SIP", SequentialImageProcessingTool)
        self.reward_evaluator_tool = self.create_tool_tab("Reward Evaluator", RewardEvaluatorTool)

        # Bottom pane: Progress Text Area
        self.bottom_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.bottom_frame, weight=1)

        # Create header frame with label and collapse button
        header_frame = ttk.Frame(self.bottom_frame)
        header_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        self.progress_label = tk.Label(header_frame, text="Progress:")
        self.progress_label.pack(side=tk.LEFT)
        
        # Add collapse/expand button
        self.progress_collapsed = False
        self.collapse_button = ttk.Button(header_frame, text="▼", width=3, 
                                         command=self.toggle_progress_panel)
        self.collapse_button.pack(side=tk.RIGHT)

        # Create frame for progress text and scrollbar
        self.progress_frame = ttk.Frame(self.bottom_frame)
        self.progress_frame.pack(expand=True, fill="both", padx=10, pady=(0, 10))

        self.progress_text = tk.Text(self.progress_frame, state="disabled", wrap=tk.WORD)
        self.progress_text.pack(side=tk.LEFT, expand=True, fill="both")

        self.sb = tk.Scrollbar(self.progress_frame, command=self.progress_text.yview)
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
            SequentialVideoProcessingTool: "sequential_video_processing",
            RewardEvaluatorTool: "reward_evaluator",
            TranscriptCleanerTool: "transcript_cleaner"
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

        input_button = ttk.Button(input_frame, text="Select Input", command=tool.select_input_paths)
        input_button.pack(side=tk.LEFT, padx=5)

        tool.input_paths_display = tk.Text(input_frame, height=3, width=50, state='disabled')
        tool.input_paths_display.pack(side=tk.LEFT, padx=5, fill='x', expand=True)

        # Make input path display droppable
        tool.input_paths_display.drop_target_register(DND_FILES)
        tool.input_paths_display.dnd_bind('<<Drop>>', tool.handle_drop)

        # Output Path Selection  
        output_frame = ttk.Frame(frame)
        output_frame.pack(pady=5, fill='x', padx=5)

        output_button = ttk.Button(output_frame, text="Select Output", command=tool.select_output_path)
        output_button.pack(side=tk.LEFT, padx=5)

        same_as_input_button = ttk.Button(output_frame, text="Same as Input", command=tool.set_same_as_input)
        same_as_input_button.pack(side=tk.LEFT, padx=5)

        tool.output_path_display = tk.Text(output_frame, height=2, width=50, state='disabled')
        tool.output_path_display.pack(side=tk.LEFT, padx=5, fill='x', expand=True)

        # Options frame
        options_frame = ttk.Frame(frame)
        options_frame.pack(pady=5, fill='x', padx=5)
        
        # Check if output exists checkbox
        check_output_cb = ttk.Checkbutton(
            options_frame, 
            text="Skip existing output files", 
            variable=tool.check_output_exists
        )
        check_output_cb.pack(side=tk.LEFT, padx=10)

        # Process Button
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10, fill='x', padx=5)

        process_button = ttk.Button(button_frame, text="Start Processing", command=tool.process_paths)
        process_button.pack(side=tk.LEFT, padx=5)

        stop_button = ttk.Button(button_frame, text="Stop Processing", command=tool.stop_processing)
        stop_button.pack(side=tk.LEFT, padx=5)

    def process_progress_queue(self):
        """Process messages from the progress queue."""
        try:
            while True:
                message = self.progress_queue.get_nowait()
                self.display_progress_message(message)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_progress_queue)

    def display_progress_message(self, message):
        """Display a progress message in the progress text area."""
        self.progress_text.configure(state="normal")
        self.progress_text.insert(tk.END, f"{message}\n")
        self.progress_text.see(tk.END)
        self.progress_text.configure(state="disabled")

    def toggle_progress_panel(self):
        """Toggle the visibility of the progress panel."""
        if self.progress_collapsed:
            # Expand the progress panel
            self.progress_frame.pack(expand=True, fill="both", padx=10, pady=(0, 10))
            self.collapse_button.config(text="▼")
            self.progress_collapsed = False
            # Restore the paned window weight
            self.main_paned.pane(self.bottom_frame, weight=1)
        else:
            # Collapse the progress panel
            self.progress_frame.pack_forget()
            self.collapse_button.config(text="▲")
            self.progress_collapsed = True
            # Minimize the paned window weight
            self.main_paned.pane(self.bottom_frame, weight=0)

    def open_api_key_config(self):
        """Open API key configuration dialog."""
        from core.api_key_dialog import APIKeyDialog
        dialog = APIKeyDialog(self, self.config_manager)
        self.wait_window(dialog)

    def show_tool_overview(self):
        """Show tool overview dialog."""
        try:
            from core.tool_descriptions import get_all_descriptions
            descriptions = get_all_descriptions()
            
            overview_window = tk.Toplevel(self)
            overview_window.title("Tool Overview")
            overview_window.geometry("800x600")
            overview_window.resizable(True, True)
            
            # Make it modal
            overview_window.transient(self)
            overview_window.grab_set()
            
            # Title
            title = tk.Label(overview_window, text="Language Toolkit - Tool Overview",
                           font=("Arial", 16, "bold"))
            title.pack(pady=10)
            
            # Scrollable frame
            canvas = tk.Canvas(overview_window)
            scrollbar = ttk.Scrollbar(overview_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Display each tool with proper formatting
            for tool_name, tool_info in descriptions.items():
                # Create frame for each tool
                tool_frame = ttk.LabelFrame(scrollable_frame, 
                                           text=tool_info.get("title", tool_name.replace("_", " ").title()), 
                                           padding=15)
                tool_frame.pack(fill="x", padx=15, pady=8)
                
                # Description
                desc_text = tool_info.get("description", "")
                if desc_text:
                    desc_label = tk.Label(tool_frame, text=desc_text, 
                                        font=("Arial", 10, "bold"), 
                                        wraplength=730, justify="left")
                    desc_label.pack(anchor="w", pady=(0, 5))
                
                # Details
                details_text = tool_info.get("details", "")
                if details_text:
                    details_label = tk.Label(tool_frame, text=details_text, 
                                           font=("Arial", 9), 
                                           wraplength=730, justify="left",
                                           fg="gray30")
                    details_label.pack(anchor="w")
            
            canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
            scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
            
            # Close button
            close_btn = ttk.Button(overview_window, text="Close", command=overview_window.destroy)
            close_btn.pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not show tool overview: {e}")

    def show_api_requirements(self):
        """Show API requirements dialog."""
        try:
            from core.tool_descriptions import get_all_api_requirements
            requirements = get_all_api_requirements()
            
            req_window = tk.Toplevel(self)
            req_window.title("API Requirements")
            req_window.geometry("700x500")
            req_window.resizable(True, True)
            
            # Make it modal
            req_window.transient(self)
            req_window.grab_set()
            
            # Title
            title = tk.Label(req_window, text="API Key Requirements by Tool",
                           font=("Arial", 16, "bold"))
            title.pack(pady=10)
            
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
            
            # Display requirements for each tool
            for tool_name, req in requirements.items():
                # Use the tool title if available
                tool_title = tool_name.replace("_", " ").title()
                if tool_name == "pptx_to_pdf_png":
                    tool_title = "PPTX Export"
                elif tool_name == "pptx_translation":
                    tool_title = "PPTX Translation"
                    
                tool_frame = ttk.LabelFrame(scrollable_frame, text=tool_title, padding=12)
                tool_frame.pack(fill="x", padx=15, pady=5)
                
                if req.get("api_required"):
                    # API required label
                    req_label = tk.Label(tool_frame, 
                                       text=f"✓ Required: {req['api_required']}", 
                                       font=("Arial", 10, "bold"), 
                                       fg="darkblue")
                    req_label.pack(anchor="w", pady=(0, 3))
                    
                    # API description
                    if req.get("api_description"):
                        desc_label = tk.Label(tool_frame, 
                                            text=req["api_description"], 
                                            font=("Arial", 9), 
                                            fg="gray30",
                                            wraplength=630,
                                            justify="left")
                        desc_label.pack(anchor="w")
                else:
                    no_req_label = tk.Label(tool_frame, 
                                          text="✓ No API key required", 
                                          font=("Arial", 10), 
                                          fg="darkgreen")
                    no_req_label.pack(anchor="w")
            
            canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
            scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
            
            # Close button
            close_btn = ttk.Button(req_window, text="Close", command=req_window.destroy)
            close_btn.pack(pady=10)
            
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