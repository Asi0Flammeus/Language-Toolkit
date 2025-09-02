"""
API Key Configuration Dialog

This module provides a GUI dialog for configuring API keys used by various tools.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)


class APIKeyDialog(tk.Toplevel):
    """
    Dialog window for configuring API keys.
    
    Provides a user-friendly interface for entering and saving API keys
    for various services used by the Language Toolkit.
    """
    
    def __init__(self, parent, config_manager):
        """
        Initialize the API key configuration dialog.
        
        Args:
            parent: Parent window
            config_manager: ConfigManager instance for loading/saving keys
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.api_keys = config_manager.get_api_keys()
        
        # Window setup
        self.title("API Key Configuration")
        self.geometry("600x400")
        self.resizable(False, False)
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        # Create UI
        self.create_widgets()
        
        # Center the dialog
        self.center_window()
        
        # Load current values
        self.load_current_keys()
    
    def center_window(self):
        """Center the dialog on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_widgets(self):
        """Create the dialog widgets."""
        # Main frame
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(main_frame, 
                                text="Configure API Keys", 
                                font=("", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Instructions
        instructions = ttk.Label(main_frame,
                                text="Enter your API keys below. Keys are stored locally in your configuration.",
                                wraplength=550)
        instructions.pack(pady=(0, 10))
        
        # Scrollable frame for API key entries
        canvas = tk.Canvas(main_frame, height=250)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # API key entries
        self.key_vars = {}
        self.create_key_entries(scrollable_frame)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Button frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, pady=10, padx=10)
        
        # Save button
        save_button = ttk.Button(button_frame, 
                                text="Save", 
                                command=self.save_keys,
                                width=10)
        save_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Cancel button
        cancel_button = ttk.Button(button_frame, 
                                  text="Cancel", 
                                  command=self.destroy,
                                  width=10)
        cancel_button.pack(side=tk.RIGHT)
        
        # Clear all button
        clear_button = ttk.Button(button_frame,
                                 text="Clear All",
                                 command=self.clear_all_keys,
                                 width=10)
        clear_button.pack(side=tk.LEFT)
    
    def create_key_entries(self, parent):
        """Create entry fields for each API key."""
        # Define API services and their descriptions
        api_services = [
            ("openai", "OpenAI", "For audio transcription (Whisper) and GPT-4 fallback"),
            ("anthropic", "Anthropic", "For transcript cleaning with Claude AI"),
            ("deepl", "DeepL", "For high-quality text and presentation translation"),
            ("elevenlabs", "ElevenLabs", "For realistic text-to-speech generation"),
            ("convertapi", "ConvertAPI", "For PowerPoint to PDF/PNG conversion"),
        ]
        
        for i, (key_name, display_name, description) in enumerate(api_services):
            # Frame for each API key
            key_frame = ttk.LabelFrame(parent, text=display_name, padding="10")
            key_frame.grid(row=i, column=0, sticky="ew", padx=5, pady=5)
            parent.columnconfigure(0, weight=1)
            
            # Description label
            desc_label = ttk.Label(key_frame, text=description, font=("", 9))
            desc_label.pack(anchor="w")
            
            # Entry field
            self.key_vars[key_name] = tk.StringVar()
            entry = ttk.Entry(key_frame, 
                            textvariable=self.key_vars[key_name],
                            show="*",
                            width=50)
            entry.pack(fill=tk.X, pady=(5, 0))
            
            # Show/hide button
            show_var = tk.BooleanVar(value=False)
            show_check = ttk.Checkbutton(key_frame,
                                        text="Show",
                                        variable=show_var,
                                        command=lambda e=entry, v=show_var: self.toggle_visibility(e, v))
            show_check.pack(anchor="w", pady=(2, 0))
    
    def toggle_visibility(self, entry, show_var):
        """Toggle password visibility for an entry field."""
        if show_var.get():
            entry.configure(show="")
        else:
            entry.configure(show="*")
    
    def load_current_keys(self):
        """Load current API keys into the entry fields."""
        for key_name, var in self.key_vars.items():
            if key_name in self.api_keys:
                var.set(self.api_keys[key_name])
    
    def clear_all_keys(self):
        """Clear all API key fields."""
        result = messagebox.askyesno("Clear All Keys",
                                     "Are you sure you want to clear all API keys?",
                                     parent=self)
        if result:
            for var in self.key_vars.values():
                var.set("")
    
    def save_keys(self):
        """Save the API keys to configuration."""
        try:
            # Collect non-empty keys
            new_keys = {}
            for key_name, var in self.key_vars.items():
                value = var.get().strip()
                if value:
                    new_keys[key_name] = value
            
            # Save to configuration
            self.config_manager.save_api_keys(new_keys)
            
            messagebox.showinfo("Success", 
                              "API keys saved successfully!",
                              parent=self)
            self.destroy()
            
        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")
            messagebox.showerror("Error",
                               f"Failed to save API keys: {str(e)}",
                               parent=self)