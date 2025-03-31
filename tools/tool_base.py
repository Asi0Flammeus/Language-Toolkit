import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import queue
import logging


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


