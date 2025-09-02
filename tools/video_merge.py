"""Video merge tool for creating MP4 videos from MP3 audio and PNG images."""

import tkinter as tk
from tkinter import ttk, filedialog
import os
import re
import subprocess
import logging
from pathlib import Path

from ui.base_tool import ToolBase


class VideoMergeTool(ToolBase):
    """
    Merges MP3 audio files with PNG images to create MP4 videos.
    Uses ffmpeg directly instead of moviepy for better reliability.
    
    Matches files based on 2-digit number patterns in filenames,
    where digits are separated by underscore or hyphen.
    Adds a 0.5s silence between clips in the final video.
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        # We don't use self.supported_extensions in the usual way
        self.supported_extensions = {'.mp3', '.png'}
        
        # Force selection mode to folder only
        self.selection_mode = tk.StringVar(value="folder")
        # Toggle for recursive batch mode (process subfolders)
        self.recursive_mode = tk.BooleanVar(value=False)
        
        # Intro/Outro options
        self.use_intro = tk.BooleanVar(value=False)
        # Path to intro media file
        self.intro_path = Path(__file__).parent.parent / "media" / "planB_intro.mp4"
        
        # Check dependencies
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if ffmpeg is installed and available."""
        self.dependencies_met = False
        try:
            # Check if ffmpeg is available in PATH
            result = subprocess.run(['ffmpeg', '-version'], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, 
                                   text=True)
            if result.returncode == 0:
                self.dependencies_met = True
                version_info = result.stdout.split('\n')[0]
                logging.debug(f"Found ffmpeg: {version_info}")
            else:
                logging.debug("ffmpeg command returned non-zero exit code")
                # Don't send progress update during initialization
        except FileNotFoundError:
            logging.debug("ffmpeg not found in PATH")
            # Don't send progress update during initialization
        except Exception as e:
            logging.debug(f"Error checking ffmpeg: {str(e)}")
            # Don't send progress update during initialization
            
    def create_selection_mode_controls(self, parent_frame):
        """Override to only show folder selection mode."""
        mode_frame = ttk.LabelFrame(parent_frame, text="Input Mode")
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(mode_frame, text="This tool accepts folders containing matching MP3 and PNG files").pack(padx=10, pady=5)
        note_frame = ttk.Frame(mode_frame)
        note_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(note_frame, text="Note: Files are matched by the same 2-digit number in their names").pack(side=tk.LEFT)
        # Recursive batch mode toggle: when enabled, each subfolder is processed separately
        ttk.Checkbutton(mode_frame,
                        text="Recursive batch mode (process subfolders)",
                        variable=self.recursive_mode).pack(anchor='w', padx=10, pady=5)
        
    def create_specific_controls(self, parent_frame):
        """Creates UI elements specific to VideoMergeTool (intro/outro options)."""
        options_frame = ttk.LabelFrame(parent_frame, text="Video Options")
        options_frame.pack(fill='x', padx=5, pady=5)
        
        # Intro option
        intro_check = ttk.Checkbutton(options_frame,
                                     text="Add Plan B intro to beginning",
                                     variable=self.use_intro)
        intro_check.pack(anchor='w', padx=10, pady=5)

        
    def select_input_paths(self):
        """Override to only allow folder selection."""
        path = filedialog.askdirectory(title="Select Folder with MP3 and PNG Files")
        if path:
            self.input_paths = [Path(path)]
            self.update_input_display()
            return True
        return False
            
    def before_processing(self):
        """Pre-processing setup and validation."""
        if not self.dependencies_met:
            self._check_dependencies()  # Check again in case user installed ffmpeg
            if not self.dependencies_met:
                # Now it's appropriate to inform the user since they're trying to process
                self.send_progress_update("ERROR: ffmpeg not found in PATH. Please install ffmpeg first.")
                raise ImportError("ffmpeg not found. Please install ffmpeg and make sure it's in your PATH.")

    def process_file(self, input_file, output_dir):
        """Not used for this tool - we process directories instead."""
        pass

    def _process_paths_threaded(self):
        """Override to implement directory-based processing instead of file-based."""
        try:
            self.before_processing()
            
            if not self.input_paths:
                self.send_progress_update("No input directory selected.")
                return
                
            input_dir = self.input_paths[0]
            if not input_dir.is_dir():
                self.send_progress_update(f"Error: {input_dir} is not a directory.")
                return
                
            # Create output directory if it doesn't exist
            output_dir = self.output_path
            output_dir.mkdir(parents=True, exist_ok=True)
                
            # Process the directory
            self.process_directory(input_dir, output_dir)
                
            self.after_processing()
            
        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.send_progress_update(error_msg)
            logging.exception(error_msg)
        finally:
            self.stop_flag.clear()
            self.processing_thread = None
            self.send_progress_update("Processing complete")
            
    def process_directory(self, input_dir, output_dir):
        """Processes MP3/PNG pairs in either single-folder or recursive mode to create MP4 videos."""
        from core.video_merger import VideoMergerCore
        
        # Determine mode: flat (single folder) or recursive per subfolder
        if not getattr(self, 'recursive_mode', None) or not self.recursive_mode.get():
            self.send_progress_update(f"Processing single-folder mode: {input_dir}")
            # Collect MP3 and PNG files directly in the selected folder
            try:
                entries = os.listdir(input_dir)
            except Exception as e:
                self.send_progress_update(f"Error reading directory {input_dir}: {e}")
                return
            mp3_files = sorted([input_dir / f for f in entries if f.lower().endswith('.mp3')])
            png_files = sorted([input_dir / f for f in entries if f.lower().endswith('.png')])
            self.send_progress_update(f"Found {len(mp3_files)} MP3 and {len(png_files)} PNG in {input_dir}")
            # Match files by identifier
            file_pairs = self.match_file_pairs(mp3_files, png_files)
            if not file_pairs:
                self.send_progress_update(f"No matching MP3/PNG pairs found in {input_dir}")
                return
            self.send_progress_update(f"Found {len(file_pairs)} matching pairs in {input_dir}")
            # Sort file pairs by numeric ID
            file_pairs.sort(key=lambda x: x[0])
            # Generate output filename based on the first MP3 file (remove 2-digit identifier)
            _, first_mp3, _ = file_pairs[0]
            mp3_stem = first_mp3.stem
            identifier_pattern = r'[_-](\d{2})(?:[_-])'
            output_name = re.sub(identifier_pattern, '_', mp3_stem)
            end_pattern = r'[_-]\d{2}$'
            output_name = re.sub(end_pattern, '', output_name)
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{output_name}.mp4"
            self.send_progress_update(f"Output file will be: {output_file}")
            self.create_video_with_ffmpeg(file_pairs, output_file)
            return
        # Recursive mode: walk through all subdirectories
        self.send_progress_update(f"Scanning directory recursively: {input_dir}")
        for dirpath, dirnames, filenames in os.walk(input_dir):
            curr_dir = Path(dirpath)
            # Collect MP3 and PNG files in the current directory
            mp3_files = sorted([curr_dir / f for f in filenames if f.lower().endswith('.mp3')])
            png_files = sorted([curr_dir / f for f in filenames if f.lower().endswith('.png')])
            if not mp3_files or not png_files:
                continue
            self.send_progress_update(f"Found {len(mp3_files)} MP3 and {len(png_files)} PNG in {curr_dir}")
            # Match files by identifier
            file_pairs = self.match_file_pairs(mp3_files, png_files)
            if not file_pairs:
                self.send_progress_update(f"No matching MP3/PNG pairs found in {curr_dir}")
                continue
            self.send_progress_update(f"Found {len(file_pairs)} matching pairs in {curr_dir}")
            # Sort file pairs by numeric ID
            file_pairs.sort(key=lambda x: x[0])
            # Generate output filename based on the first MP3 file (remove 2-digit identifier)
            _, first_mp3, _ = file_pairs[0]
            mp3_stem = first_mp3.stem
            identifier_pattern = r'[_-](\d{2})(?:[_-])'
            output_name = re.sub(identifier_pattern, '_', mp3_stem)
            end_pattern = r'[_-]\d{2}$'
            output_name = re.sub(end_pattern, '', output_name)
            output_file = curr_dir / f"{output_name}.mp4"
            self.send_progress_update(f"Output file will be: {output_file}")
            # Create the output video
            self.create_video_with_ffmpeg(file_pairs, output_file)

        
    def match_file_pairs(self, mp3_files, png_files):
        """
        Match MP3 and PNG files based on a generic two-digit index in their filenames.
        The index is defined as exactly two digits not part of a larger digit sequence
        and can be surrounded by any non-digit character (e.g., '_01_', '-01-', '.01.').
        """
        file_pairs = []
        mp3_dict = {}
        png_dict = {}

        # Compile a regex to match exactly two digits not adjacent to other digits
        id_pattern = re.compile(r'(?<!\d)(\d{2})(?!\d)')

        # Extract indices for PNG files
        for png_file in png_files:
            match = id_pattern.search(png_file.name)
            if match:
                idx = match.group(1)
                self.send_progress_update(f"PNG found index {idx} in {png_file.name}")
                png_dict[idx] = png_file

        # Extract indices for MP3 files
        for mp3_file in mp3_files:
            match = id_pattern.search(mp3_file.name)
            if match:
                idx = match.group(1)
                self.send_progress_update(f"MP3 found index {idx} in {mp3_file.name}")
                mp3_dict[idx] = mp3_file

        # Match pairs by index
        matched_png_indices = set()
        
        for idx in sorted(mp3_dict.keys(), key=lambda x: int(x)):
            mp3_file = mp3_dict[idx]
            png_file = png_dict.get(idx)
            if png_file:
                self.send_progress_update(f"Matched index {idx}: {mp3_file.name} + {png_file.name}")
                file_pairs.append((idx, mp3_file, png_file))
                matched_png_indices.add(idx)
            else:
                self.send_progress_update(f"No PNG match for MP3 index {idx}: {mp3_file.name}")



        # Return pairs sorted by numeric index
        return sorted(file_pairs, key=lambda x: int(x[0]))

    
    def create_video_with_ffmpeg(self, file_pairs, output_file):
        """
        Create a video from matched MP3/PNG pairs using the VideoMergerCore.
        Handles adding silence between clips and intro.
        """
        from core.video_merger import VideoMergerCore
        
        try:
            # Check if should skip
            if self.check_output_exists.get() and output_file.exists():
                self.send_progress_update(f"Skipping video creation - output already exists: {output_file.name}")
                return
                
            # Create progress callback for the merger
            def progress_callback(message):
                if not self.stop_flag.is_set():
                    self.send_progress_update(message)
                else:
                    raise InterruptedError("Processing stopped by user")
            
            # Initialize video merger
            merger = VideoMergerCore(progress_callback)
            
            # Prepare intro path
            intro_video = self.intro_path if self.use_intro.get() and self.intro_path.exists() else None
            
            # Use the new create_video_from_file_pairs method
            success = merger.create_video_from_file_pairs(
                file_pairs=file_pairs,
                output_path=output_file,
                silence_duration=0.2,  # 0.2 seconds silence between clips
                intro_video=intro_video,
                outro_audio=None
            )
            
            if not success:
                raise RuntimeError("Video creation failed")
            
        except Exception as e:
            error_msg = f"Error creating video: {str(e)}"
            self.send_progress_update(error_msg)
            logging.exception(error_msg)