# language_toolkit/gui/config_dialogs.py

import tkinter as tk
from tkinter import ttk, messagebox
import sys

from pathlib import Path
sys.path.append("../")
from config.styles import BACKGROUND_COLOR, ACCENT_COLOR



class ConfigDialogs:
    def __init__(self, master, config_manager):
        self.master = master
        self.config_manager = config_manager

    def open_api_key_config(self):
        """Opens a dialog to configure API keys, including adding new ones."""
        api_config_window = tk.Toplevel(self.master, bg=BACKGROUND_COLOR)
        api_config_window.title("API Key Configuration")

        # Ensure the window appears on top
        api_config_window.transient(self.master)
        api_config_window.grab_set()

        api_keys = self.config_manager.get_api_keys()
        api_entries = {}
        api_names = list(api_keys.keys()) + [""]  # Include a blank entry for a new key

        for api_name in api_names:
            frame = ttk.Frame(api_config_window)
            frame.config(bg=BACKGROUND_COLOR)
            frame.pack(pady=5, padx=10, fill="x")  # Ensure fill="x"

            label = ttk.Label(
                frame,
                text=f"{api_name.capitalize()} API Key:" if api_name else "New API Key:",
                background=BACKGROUND_COLOR,  # Explicitly set background
                foreground=ACCENT_COLOR,  # Explicitly set foreground
            )
            label.pack(side=tk.LEFT, padx=5)

            entry = ttk.Entry(frame, width=40, bg="white", fg="black")
            entry.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

            if api_name and api_name in api_keys:
                entry.insert(0, api_keys[api_name])

            api_entries[api_name] = entry

        # New API Key Frame
        new_key_frame = ttk.Frame(api_config_window)
        new_key_frame.config(bg=BACKGROUND_COLOR)
        new_key_frame.pack(pady=5, padx=10, fill="x")

        new_key_label = ttk.Label(new_key_frame, text="New API Name:",
                                  background=BACKGROUND_COLOR,
                                  foreground=ACCENT_COLOR)
        new_key_label.pack(side=tk.LEFT, padx=5)

        new_key_name = ttk.Entry(new_key_frame, width=40, bg="white", fg="black")
        new_key_name.pack(side=tk.LEFT, expand=True, fill="x", padx=5)

        def save_api_keys():
            api_keys_to_save = {}
            for api_name, entry in api_entries.items():
                if api_name:
                    api_keys_to_save[api_name] = entry.get()

            # Get new api key
            new_api_name = new_key_name.get()
            if new_api_name:
                api_keys_to_save[new_api_name] = api_entries[""].get()  # Get value in blank key

            self.save_api_keys_to_config(api_keys_to_save, api_config_window)  # Save all keys

        save_button = ttk.Button(api_config_window, text="Save", command=save_api_keys)
        save_button.pack(pady=10)

    def save_api_keys_to_config(self, api_keys, window):
        self.config_manager.save_api_keys(api_keys)
        window.destroy()
        messagebox.showinfo("Info", "API keys saved successfully.")

    def open_elevenlabs_config(self):
        # (The rest of the ElevenLabs configuration dialog remains the same)
        elevenlabs_config_window = tk.Toplevel(self.master, bg=BACKGROUND_COLOR)
        elevenlabs_config_window.title("ElevenLabs Voices Configuration")

         # Load current ElevenLabs config
        elevenlabs_config = self.config_manager.get_elevenlabs_config()

         # Voice list frame
        voices_frame = ttk.Frame(elevenlabs_config_window)
        voices_frame.config(bg=BACKGROUND_COLOR)
        voices_frame.pack(pady=5, padx=10, fill="x")

         # Listbox to show voices
        voice_list = tk.Listbox(voices_frame, width=40, bg="white", fg="black")  # Set listbox colors
        voice_list.pack(side=tk.LEFT, fill="both", expand=True)

         # Scrollbar for the listbox
        voice_scrollbar = ttk.Scrollbar(voices_frame, command=voice_list.yview, bg=BACKGROUND_COLOR, activebackground=ACCENT_COLOR)
        voice_scrollbar.pack(side=tk.RIGHT, fill="y")
        voice_list.config(yscrollcommand=voice_scrollbar.set)

         # Populate the listbox with existing voices
        for name, id in elevenlabs_config.items():
            voice_list.insert(tk.END, f"{name} ({id})")

         # Add/Edit/Delete buttons
        button_frame = ttk.Frame(elevenlabs_config_window)
        button_frame.config(bg=BACKGROUND_COLOR)
        button_frame.pack(pady=5, padx=10, fill="x")

        add_button = ttk.Button(button_frame, text="Add Voice", command=lambda: self.add_elevenlabs_voice(elevenlabs_config, voice_list))
        add_button.pack(side=tk.LEFT, padx=5)

        edit_button = ttk.Button(button_frame, text="Edit Voice", command=lambda: self.edit_elevenlabs_voice(elevenlabs_config, voice_list))
        edit_button.pack(side=tk.LEFT, padx=5)

        delete_button = ttk.Button(button_frame, text="Delete Voice", command=lambda: self.delete_elevenlabs_voice(elevenlabs_config, voice_list))
        delete_button.pack(side=tk.LEFT, padx=5)

         # Save button
        save_button = ttk.Button(elevenlabs_config_window, text="Save", command=lambda: self.save_elevenlabs_config_changes(elevenlabs_config, voice_list, elevenlabs_config_window))
        save_button.pack(pady=10)

    def add_elevenlabs_voice(self, elevenlabs_config, voice_list):
        """Adds a new ElevenLabs voice to the config."""
        add_window = tk.Toplevel(self.master, bg=BACKGROUND_COLOR)
        add_window.title("Add ElevenLabs Voice")

        # Name
        name_label = ttk.Label(add_window, text="Voice Name:")
        name_label.pack(pady=5, padx=10)
        name_entry = ttk.Entry(add_window, width=30, bg="white", fg="black")  # Set entry colors
        name_entry.pack(pady=5, padx=10)

        # ID
        id_label = ttk.Label(add_window, text="Voice ID:")
        id_label.pack(pady=5, padx=10)
        id_entry = ttk.Entry(add_window, width=30, bg="white", fg="black")  # Set entry colors
        id_entry.pack(pady=5, padx=10)

        def save_new_voice():
            name = name_entry.get()
            id = id_entry.get()
            if name and id:
                elevenlabs_config[name] = id
                voice_list.insert(tk.END, f"{name} ({id})")
                self.config_manager.save_elevenlabs_config(elevenlabs_config)  # Save config changes
                add_window.destroy()
            else:
                messagebox.showerror("Error", "Name and ID are required.")

        save_button = ttk.Button(add_window, text="Save", command=save_new_voice)
        save_button.pack(pady=10)

    def edit_elevenlabs_voice(self, elevenlabs_config, voice_list):
        """Edits an existing ElevenLabs voice."""
        selected_index = voice_list.curselection()
        if not selected_index:
            messagebox.showinfo("Info", "Select a voice to edit.")
            return

        selected_index = selected_index[0]
        selected_text = voice_list.get(selected_index)
        name, id = selected_text.split("(")
        name = name.strip()
        id = id.replace(")","").strip() # Extract the voice ID.

        edit_window = tk.Toplevel(self.master, bg=BACKGROUND_COLOR)
        edit_window.title("Edit ElevenLabs Voice")

        # Name
        name_label = ttk.Label(edit_window, text="Voice Name:")
        name_label.pack(pady=5, padx=10)
        name_entry = ttk.Entry(edit_window, width=30, bg="white", fg="black")  # Set entry colors
        name_entry.pack(pady=5, padx=10)
        name_entry.insert(0,name) #Populate field with initial value

        # ID
        id_label = ttk.Label(edit_window, text="Voice ID:")
        id_label.pack(pady=5, padx=10)
        id_entry = ttk.Entry(edit_window, width=30, bg="white", fg="black")  # Set entry colors
        id_entry.pack(pady=5, padx=10)
        id_entry.insert(0, id) #Populate field with initial value

        def save_edited_voice():
            new_name = name_entry.get()
            new_id = id_entry.get()
            if new_name and new_id:
                del elevenlabs_config[name] # Delete old voice config
                elevenlabs_config[new_name] = new_id
                voice_list.delete(selected_index)
                voice_list.insert(selected_index, f"{new_name} ({new_id})")
                self.config_manager.save_elevenlabs_config(elevenlabs_config)  # Save config changes
                edit_window.destroy()
            else:
                messagebox.showerror("Error", "Name and ID are required.")

        save_button = ttk.Button(edit_window, text="Save", command=save_edited_voice)
        save_button.pack(pady=10)

    def delete_elevenlabs_voice(self, elevenlabs_config, voice_list):
        """Deletes an ElevenLabs voice from the config."""
        selected_index = voice_list.curselection()
        if not selected_index:
            messagebox.showinfo("Info", "Select a voice to delete.")
            return

        selected_index = selected_index[0]
        selected_text = voice_list.get(selected_index)
        name, id = selected_text.split("(")
        name = name.strip()
        id = id.replace(")","").strip() # Extract the voice ID.

        if messagebox.askyesno("Confirm", f"Delete voice '{name}'?"):
            del elevenlabs_config[name]
            voice_list.delete(selected_index)
            self.config_manager.save_elevenlabs_config(self.config_manager.elevenlabs_config)  # Save config changes

    def save_elevenlabs_config_changes(self, elevenlabs_config, voice_list, window):
         """Saves the changes in ElevenLabs voices configuration"""
         self.config_manager.save_elevenlabs_config(elevenlabs_config) #Save config changes
         window.destroy()
         messagebox.showinfo("Info", "ElevenLabs voices saved successfully.")

