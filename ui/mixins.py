"""Mixin classes for UI functionality in Language Toolkit."""

import tkinter as tk
from tkinter import ttk


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