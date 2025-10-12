"""SVP-1: Batch Translation tool for PPTX and TXT files."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
from pathlib import Path

from ui.base_tool import ToolBase
from ui.mixins import LanguageSelectionMixin
from tools.sequential_processing.sequential_orchestrator import SequentialOrchestrator


class SVPTranslationTool(ToolBase, LanguageSelectionMixin):
    """SVP-1: Batch translation of PPTX and TXT files."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx', '.txt'}

        # Language selection variables
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")

        # Multiple target languages selection
        self.selected_target_langs = set()

        # Force selection mode to folder
        self.selection_mode = tk.StringVar(value="folder")

        # Initialize the orchestrator with API keys from config
        api_keys = config_manager.get_api_keys()
        orchestrator_config = {
            'deepl_api_key': api_keys.get('deepl'),
            'convertapi_key': api_keys.get('convertapi'),
            'elevenlabs_api_key': api_keys.get('elevenlabs')
        }

        # Create orchestrator with progress callback
        self.orchestrator = SequentialOrchestrator(
            config=orchestrator_config,
            progress_callback=self.send_progress_update
        )

        # Get supported languages from orchestrator
        self.supported_languages = self.orchestrator.get_supported_languages()

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
        """Process translations for each target language."""
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
            target=self._process_translations,
            daemon=True
        )
        self.processing_thread.start()

    def _process_translations(self):
        """Process translation phase only."""
        try:
            self.before_processing()

            # Set the stop flag on the orchestrator
            self.orchestrator.stop_flag = self.stop_flag

            # Process using the orchestrator (translation phase only)
            input_path = self.input_paths[0] if self.input_paths else None

            if not input_path:
                self.send_progress_update("❌ No input path selected")
                return

            success = self.orchestrator.process_translation_phase(
                input_path=input_path,
                output_path=self.output_path,
                source_lang=self.source_lang.get(),
                target_langs=list(self.selected_target_langs),
                skip_existing=self.check_output_exists.get()
            )

            if success:
                self.after_processing()
            else:
                self.send_progress_update("⚠️ Translation completed with errors")

        except Exception as e:
            self.send_progress_update(f"❌ Error during translation: {str(e)}")
            logging.exception("Error during translation processing")

    def stop_processing(self):
        """Stop the current processing operation."""
        super().stop_processing()
        if hasattr(self, 'orchestrator'):
            self.orchestrator.stop_processing()

    def validate_configuration(self):
        """Validate that translation tools are available."""
        if not hasattr(self, 'orchestrator'):
            return False

        availability = self.orchestrator.validate_configuration()

        # Check only translation-related tools
        required_tools = ['pptx_translation', 'text_translation']
        missing_tools = [tool for tool in required_tools if not availability.get(tool)]

        if missing_tools:
            self.send_progress_update(
                f"⚠️ Missing API keys for: {', '.join(missing_tools)}\n"
                "Please configure DeepL API key in settings."
            )
            return False

        return True
