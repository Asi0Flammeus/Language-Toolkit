"""Base class for all tools in the Language Toolkit application."""

import tkinter as tk
import threading
import logging
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from core.services import create_service_manager
from core.processors import ProgressReporter
from core.file_utils import should_skip_processing


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
        
        # Initialize service manager for consolidated API access
        self.service_manager = create_service_manager(config_manager)
        
        # Create progress reporter for GUI
        self.progress_reporter = ProgressReporter(callback=self.send_progress_update)
        
        # Add selection mode variable
        self.selection_mode = tk.StringVar(value="file")  # "file" or "folder"
        
        # Add output checking option
        self.check_output_exists = tk.BooleanVar(value=True)  # Default to checking if output exists
        
        # Define supported extensions for the tool (to be overridden by child classes)
        self.supported_extensions = set()
        
        # Initialize display attributes
        self.input_paths_display = None
        self.output_path_display = None

        self.stop_flag = threading.Event()
        self.processing_thread = None

    def stop_processing(self):
        """Signals the processing to stop."""
        if self.stop_flag:
            self.stop_flag.set()
            self.send_progress_update("Stopping processing... Please wait.")
            logging.info("Stop processing requested")

    def create_selection_mode_controls(self, parent_frame):
        """Creates radio buttons for selection mode."""
        mode_frame = ttk.LabelFrame(parent_frame, text="Selection Mode")
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Single File", 
                       variable=self.selection_mode, 
                       value="file").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Folder (Recursive)", 
                       variable=self.selection_mode, 
                       value="folder").pack(side=tk.LEFT, padx=10)

    def select_input_paths(self):
        """Opens a dialog to select input files or directory based on mode."""
        if self.selection_mode.get() == "folder":
            path = filedialog.askdirectory(title="Select Input Directory")
            if path:
                self.input_paths = [Path(path)]
                self.update_input_display()
                return True
        else:
            paths = filedialog.askopenfilenames(
                title="Select Input Files",
                filetypes=[("Supported Files", 
                          [f"*{ext}" for ext in self.supported_extensions])]
            )
            if paths:
                self.input_paths = [Path(p) for p in paths]
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
            if self.selection_mode.get() == "folder":
                self.output_path = self.input_paths[0]
            else:
                self.output_path = self.input_paths[0].parent
            logging.info(f"Output path set to same as input: {self.output_path}")
            self.update_output_display()
            return True
        else:
            messagebox.showwarning("Warning", "Please select input paths first.")
            return False

    def update_input_display(self):
        """Updates the input paths display."""
        if hasattr(self, 'input_paths_display') and self.input_paths_display:
            self.input_paths_display.configure(state='normal')
            self.input_paths_display.delete(1.0, tk.END)
            for path in self.input_paths:
                self.input_paths_display.insert(tk.END, f"{path}\n")
            self.input_paths_display.configure(state='disabled')

    def update_output_display(self):
        """Updates the output path display."""
        if hasattr(self, 'output_path_display') and self.output_path_display:
            self.output_path_display.configure(state='normal')
            self.output_path_display.delete(1.0, tk.END)
            if self.output_path:
                self.output_path_display.insert(tk.END, str(self.output_path))
            self.output_path_display.configure(state='disabled')

    def get_all_files_recursive(self, directory: Path) -> list:
        """Recursively gets all supported files from directory."""
        files = []
        try:
            for item in directory.rglob("*"):
                if item.is_file() and item.suffix.lower() in self.supported_extensions:
                    files.append(item)
        except Exception as e:
            self.send_progress_update(f"Error scanning directory {directory}: {e}")
        return sorted(files)  # Sort files for consistent processing order

    def process_paths(self):
        """Enhanced process_paths method with stop functionality."""
        if not self.input_paths:
            messagebox.showerror("Error", "No input paths selected.")
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
            target=self._process_paths_threaded, 
            daemon=True
        )
        self.processing_thread.start()

    def _process_paths_threaded(self):
        """Enhanced threaded processing with stop functionality."""
        try:
            self.before_processing()
            
            files_to_process = []
            if self.selection_mode.get() == "folder":
                for input_path in self.input_paths:
                    files_to_process.extend(self.get_all_files_recursive(input_path))
            else:
                files_to_process = self.input_paths

            total_files = len(files_to_process)
            self.send_progress_update(f"Found {total_files} files to process")

            for index, file_path in enumerate(files_to_process, 1):
                # Check if processing should stop
                if self.stop_flag.is_set():
                    self.send_progress_update("Processing stopped by user")
                    return

                try:
                    if self.selection_mode.get() == "folder":
                        relative_path = file_path.parent.relative_to(self.input_paths[0])
                        output_dir = self.output_path / relative_path
                    else:
                        output_dir = self.output_path

                    output_dir.mkdir(parents=True, exist_ok=True)

                    self.send_progress_update(
                        f"Processing file {index}/{total_files}: {file_path.name}"
                    )
                    self.process_file(file_path, output_dir)

                except Exception as e:
                    self.send_progress_update(
                        f"Error processing {file_path.name}: {str(e)}"
                    )
                    logging.exception(f"Error processing {file_path}")

            self.after_processing()

        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.send_progress_update(error_msg)
            logging.exception(error_msg)
        finally:
            self.stop_flag.clear()
            self.processing_thread = None
            self.send_progress_update("Processing complete")

    def send_progress_update(self, message: str):
        """Sends a progress update message to the GUI."""
        self.progress_queue.put(message)

    def before_processing(self):
        """Hook for pre-processing setup."""
        pass

    def after_processing(self):
        """Hook for post-processing cleanup."""
        pass

    def process_file(self, input_file: Path, output_dir: Path):
        """Abstract method for processing a single file."""
        raise NotImplementedError("Subclasses must implement process_file()")
    
    def should_skip_file(self, input_file: Path, output_dir: Path, output_extension: str = None) -> bool:
        """Check if processing should be skipped based on existing output."""
        if not self.check_output_exists.get():
            return False
        
        # If no specific extension provided, cannot check
        if not output_extension:
            return False
            
        # Construct expected output filename
        output_filename = input_file.stem + output_extension
        output_file = output_dir / output_filename
        
        # Use consolidated file_utils function
        return should_skip_processing(input_file, output_file, check_exists=True)

    def handle_drop(self, event):
        """Handles drag and drop events."""
        files = event.data.split()
        
        # Filter files based on selection mode and supported extensions
        if self.selection_mode.get() == "folder":
            self.input_paths = [Path(f) for f in files if Path(f).is_dir()]
        else:
            self.input_paths = [
                Path(f) for f in files 
                if Path(f).is_file() and Path(f).suffix.lower() in self.supported_extensions
            ]
        
        if self.input_paths:
            logging.info(f"Files dropped: {self.input_paths}")
            self.update_input_display()
        else:
            messagebox.showwarning(
                "Warning", 
                "No valid input paths found. Please check selection mode and file types."
            )