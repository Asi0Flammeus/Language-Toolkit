"""Sequential processing tool for multiple language workflows."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
from pathlib import Path

from ui.base_tool import ToolBase
from ui.mixins import LanguageSelectionMixin


class SequentialProcessingTool(ToolBase, LanguageSelectionMixin):
    """Tool for processing files through multiple language translations sequentially."""
    
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
        
        # Initialize sub-tools - Import them here to avoid circular imports
        from tools.pptx_translation import PPTXTranslationTool
        from tools.pptx_to_pdf import PPTXtoPDFTool
        from tools.text_translation import TextTranslationTool
        from tools.text_to_speech import TextToSpeechTool
        from tools.video_merge import VideoMergeTool
        
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

    def process_file(self, input_file: Path, output_dir: Path):
        """Process a file using the appropriate sub-tool based on extension."""
        # Use the PPTX translation tool as the primary processor
        # You can extend this to use different tools based on file type
        if input_file.suffix.lower() == '.pptx':
            # Set the target language for the sub-tool
            self.pptx_translation_tool.source_lang.set(self.source_lang.get())
            self.pptx_translation_tool.target_lang.set(self.target_lang.get())
            self.pptx_translation_tool.check_output_exists = self.check_output_exists
            self.pptx_translation_tool.stop_flag = self.stop_flag
            
            # Process the file
            self.pptx_translation_tool.process_file(input_file, output_dir)