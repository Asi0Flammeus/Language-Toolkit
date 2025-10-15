"""Video Merger Adapter for Sequential Processing."""

import logging
import re
import os
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List, Tuple

from . import CoreToolAdapter
from core.video_merger import VideoMergerCore
from ..utils.filename_cleaner import FilenameCleanerUtility

logger = logging.getLogger(__name__)


class VideoMergerAdapter(CoreToolAdapter):
    """Adapter for Video Merger Core Tool."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize video merger adapter.

        Args:
            progress_callback: Optional callback for progress updates
        """
        super().__init__(progress_callback)
        self.tool = None
        # Path to intro media file (same as video merger tool)
        self.intro_path = Path(__file__).parent.parent.parent.parent / "media" / "planB_intro.mp4"

        # Initialize filename cleaner for removing voice names
        api_key = os.getenv('ELEVENLABS_API_KEY')
        self.filename_cleaner = FilenameCleanerUtility(api_key=api_key)
        
        # Track folders skipped due to PNG/MP3 count mismatch
        self.skipped_folders = []
    
    def _initialize_tool(self):
        """Initialize the core tool if not already done."""
        if not self.tool:
            self.tool = VideoMergerCore(progress_callback=self.progress_callback)
    
    def match_file_pairs(self, mp3_files: List[Path], png_files: List[Path]) -> List[Tuple[str, Path, Path]]:
        """
        Match MP3 and PNG files based on a generic two-digit index in their filenames.
        This is the EXACT same logic as the video merger tool.
        
        Args:
            mp3_files: List of MP3 file paths
            png_files: List of PNG file paths
            
        Returns:
            List of tuples (index, mp3_file, png_file)
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
                self.report_progress(f"PNG found index {idx} in {png_file.name}")
                png_dict[idx] = png_file

        # Extract indices for MP3 files
        for mp3_file in mp3_files:
            match = id_pattern.search(mp3_file.name)
            if match:
                idx = match.group(1)
                self.report_progress(f"MP3 found index {idx} in {mp3_file.name}")
                mp3_dict[idx] = mp3_file

        # Match pairs by index
        for idx in sorted(mp3_dict.keys(), key=lambda x: int(x)):
            mp3_file = mp3_dict[idx]
            png_file = png_dict.get(idx)
            if png_file:
                self.report_progress(f"Matched index {idx}: {mp3_file.name} + {png_file.name}")
                file_pairs.append((idx, mp3_file, png_file))
            else:
                self.report_progress(f"No PNG match for MP3 index {idx}: {mp3_file.name}")

        # Return pairs sorted by numeric index
        return sorted(file_pairs, key=lambda x: int(x[0]))
    
    def process(self, input_path: Path, output_path: Path, params: Dict[str, Any], skip_existing: bool = True) -> bool:
        """
        Create video from images and audio files using the EXACT same process as video merger tool.
        
        Args:
            input_path: Path to directory containing images and audio
            output_path: Path to output video file
            params: Parameters including:
                - 'image_files': List of PNG file paths
                - 'audio_files': List of audio file paths (MP3)
                - 'intro_video': Optional Path to intro.mp4
                - 'use_intro': Boolean flag to use intro
            
        Returns:
            True if successful OR if gracefully skipped due to mismatch, False for actual errors
        """
        self._initialize_tool()
        
        # Get parameters
        image_files = params.get('image_files', [])
        audio_files = params.get('audio_files', [])
        intro_video = params.get('intro_video', None)
        use_intro = params.get('use_intro', False)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # VERIFICATION: Check if PNG count matches MP3 count
            if len(image_files) != len(audio_files):
                self.report_progress("=" * 60)
                self.report_progress("❌ PNG/MP3 COUNT MISMATCH - SKIPPING VIDEO CREATION")
                self.report_progress(f"   Folder: {input_path.name}")
                self.report_progress(f"   Found {len(image_files)} PNG files")
                self.report_progress(f"   Found {len(audio_files)} MP3 files")
                
                # Find which indices are missing matches
                png_indices = set()
                mp3_indices = set()
                id_pattern = re.compile(r'(?<!\d)(\d{2})(?!\d)')
                
                for png_file in image_files:
                    match = id_pattern.search(png_file.name)
                    if match:
                        png_indices.add(match.group(1))
                
                for mp3_file in audio_files:
                    match = id_pattern.search(mp3_file.name)
                    if match:
                        mp3_indices.add(match.group(1))
                
                # Report missing matches
                png_only = png_indices - mp3_indices
                mp3_only = mp3_indices - png_indices
                
                if png_only:
                    self.report_progress(f"   PNG files without matching MP3: {', '.join(sorted(png_only))}")
                if mp3_only:
                    self.report_progress(f"   MP3 files without matching PNG: {', '.join(sorted(mp3_only))}")
                
                self.report_progress("   ⚠️  Video compilation requires equal number of PNG and MP3 files")
                self.report_progress("   ⚠️  Please ensure all slides have corresponding audio files")
                self.report_progress("   ⏭️  Continuing to next folder...")
                self.report_progress("=" * 60)
                
                # Track this skipped folder
                self.skipped_folders.append(str(input_path))
                
                # Return True to indicate graceful handling (not a critical error)
                # This allows the process to continue to the next folder
                return True
            
            # Match MP3 and PNG files using the exact same logic as video merger
            if not audio_files or not image_files:
                self.report_progress("✗ Need both audio and image files to create video")
                # This is also a graceful skip, not a critical error
                self.skipped_folders.append(str(input_path))
                return True
            
            self.report_progress(f"✓ Counts match: {len(audio_files)} MP3 and {len(image_files)} PNG files")
            
            # Match files by identifier (EXACT same as video merger)
            file_pairs = self.match_file_pairs(audio_files, image_files)
            
            if not file_pairs:
                self.report_progress("✗ No matching MP3/PNG pairs found")
                self.skipped_folders.append(str(input_path))
                return True
            
            # Additional verification: Check if all pairs are complete
            if len(file_pairs) != len(audio_files):
                self.report_progress(f"⚠️  Warning: Only {len(file_pairs)} matched pairs from {len(audio_files)} files")
                self.report_progress("   Some files could not be matched by index")
                self.report_progress("   ⏭️  Skipping this folder and continuing...")
                self.skipped_folders.append(str(input_path))
                # Still skip if not all files could be matched
                return True
            
            self.report_progress(f"✓ Successfully matched {len(file_pairs)} file pairs")
            
            # Sort file pairs by numeric ID (already done in match_file_pairs)
            
            # Generate output filename based on the first MP3 file
            if file_pairs:
                _, first_mp3, _ = file_pairs[0]
                mp3_stem = first_mp3.stem

                # First remove 2-digit identifier
                identifier_pattern = r'[_-](\d{2})(?:[_-])'
                output_name = re.sub(identifier_pattern, '_', mp3_stem)
                end_pattern = r'[_-]\d{2}$'
                output_name = re.sub(end_pattern, '', output_name)

                # Then remove voice names using the filename cleaner
                cleaned_filename = self.filename_cleaner.remove_voice_from_filename(output_name)

                # Update output path with cleaned name
                output_path = output_path.parent / f"{cleaned_filename}.mp4"
                self.report_progress(f"Output file will be: {output_path}")
                
                # Check if output already exists
                if skip_existing and output_path.exists():
                    self.report_progress(f"⏩ Skipping video creation - output already exists: {output_path.name}")
                    return True
            
            # Prepare intro video if requested
            intro_video_path = None
            if use_intro:
                if intro_video and intro_video.exists():
                    intro_video_path = intro_video
                    self.report_progress(f"📹 Using provided intro video: {intro_video.name}")
                elif self.intro_path.exists():
                    intro_video_path = self.intro_path
                    self.report_progress(f"📹 Using Plan B intro video")
                else:
                    self.report_progress("⚠️ Intro requested but no intro video found")
            
            # Create video using the EXACT same method as video merger
            success = self.tool.create_video_from_file_pairs(
                file_pairs=file_pairs,
                output_path=output_path,
                silence_duration=0.2,  # 0.2 seconds silence between clips (same as video merger)
                intro_video=intro_video_path,
                outro_audio=None
            )
            
            if success:
                self.report_progress(f"✓ Video saved to: {output_path}")
            else:
                self.report_progress(f"✗ Failed to create video")
                
            return success
            
        except Exception as e:
            logger.exception(f"Error creating video: {str(e)}")
            self.report_progress(f"✗ Error creating video: {str(e)}")
            return False
    
    def validate_input(self, input_path: Path) -> bool:
        """
        Validate if the input directory contains processable files.
        
        Args:
            input_path: Path to validate (should be a directory)
            
        Returns:
            True if input is valid
        """
        if not input_path.exists():
            return False
        
        if input_path.is_file():
            # Single file validation
            return input_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.mp3', '.wav', '.mp4']
        
        # Directory validation - just check it exists
        return input_path.is_dir()