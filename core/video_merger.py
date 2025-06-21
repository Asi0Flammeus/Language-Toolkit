"""Video Merger Core Functionality"""

import logging
import subprocess
import os
import re
import mimetypes
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any

logger = logging.getLogger(__name__)

class VideoMergerCore:
    """Core video merger functionality without GUI dependencies."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize video merger core.
        
        Args:
            progress_callback: Optional callback function for progress updates
        """
        self.progress_callback = progress_callback or (lambda x: None)
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """Check if FFmpeg is available."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, check=True)
            self.progress_callback("FFmpeg is available")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("FFmpeg is not installed or not available in PATH")
    
    def create_video_from_files(self, input_dir: Path, output_path: Path, 
                               duration_per_slide: float = 3.0, 
                               audio_file: Optional[Path] = None,
                               fade_duration: float = 0.5) -> bool:
        """
        Create video from images and optional audio.
        
        Args:
            input_dir: Directory containing input images
            output_path: Path to output video file
            duration_per_slide: Duration per slide in seconds
            audio_file: Optional audio file to add
            fade_duration: Fade transition duration in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Creating video from files in: {input_dir}")
            
            # Get image files
            image_files = self._get_image_files(input_dir)
            if not image_files:
                raise ValueError("No valid image files found in input directory")
            
            self.progress_callback(f"Found {len(image_files)} image files")
            
            # Create video from images
            temp_video = output_path.parent / f"temp_{output_path.stem}.mp4"
            
            success = self._create_video_from_images(
                image_files, temp_video, duration_per_slide, fade_duration
            )
            
            if not success:
                return False
            
            # Add audio if provided
            if audio_file and audio_file.exists():
                self.progress_callback("Adding audio track...")
                success = self._add_audio_to_video(temp_video, audio_file, output_path)
                
                # Clean up temp video
                if temp_video.exists():
                    temp_video.unlink()
                    
                if not success:
                    return False
            else:
                # Just rename temp video to final output
                temp_video.rename(output_path)
            
            self.progress_callback("Video creation completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to create video: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def _get_image_files(self, directory: Path) -> List[Path]:
        """Get sorted list of image files from directory."""
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif'}
        
        image_files = []
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                image_files.append(file_path)
        
        # Sort files naturally (handle numeric sequences)
        image_files.sort(key=lambda x: self._natural_sort_key(x.name))
        return image_files
    
    def _natural_sort_key(self, text: str) -> List:
        """Generate natural sort key for filenames with numbers."""
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]
    
    def _create_video_from_images(self, image_files: List[Path], output_path: Path,
                                 duration_per_slide: float, fade_duration: float) -> bool:
        """Create video from image files using FFmpeg."""
        try:
            # Create input file list for FFmpeg
            input_list_file = output_path.parent / "input_list.txt"
            
            with open(input_list_file, 'w') as f:
                for image_file in image_files:
                    f.write(f"file '{image_file.absolute()}'\n")
                    f.write(f"duration {duration_per_slide}\n")
                # Repeat last image to ensure proper duration
                if image_files:
                    f.write(f"file '{image_files[-1].absolute()}'\n")
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg', '-y',  # Overwrite output files
                '-f', 'concat',
                '-safe', '0',
                '-i', str(input_list_file),
                '-vf', f'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-r', '30',  # 30 FPS
                str(output_path)
            ]
            
            self.progress_callback("Running FFmpeg to create video...")
            
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Clean up input list file
            if input_list_file.exists():
                input_list_file.unlink()
            
            self.progress_callback("Video from images created successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error: {e.stderr}")
            self.progress_callback(f"FFmpeg error: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error creating video from images: {e}")
            self.progress_callback(f"Error: {e}")
            return False
    
    def _add_audio_to_video(self, video_path: Path, audio_path: Path, output_path: Path) -> bool:
        """Add audio track to video using FFmpeg."""
        try:
            # Build FFmpeg command to add audio
            cmd = [
                'ffmpeg', '-y',  # Overwrite output files
                '-i', str(video_path),  # Video input
                '-i', str(audio_path),  # Audio input
                '-c:v', 'copy',  # Copy video stream
                '-c:a', 'aac',   # Encode audio as AAC
                '-shortest',     # Stop when shortest stream ends
                str(output_path)
            ]
            
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            self.progress_callback("Audio added to video successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg error adding audio: {e.stderr}")
            self.progress_callback(f"FFmpeg error: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error adding audio to video: {e}")
            self.progress_callback(f"Error: {e}")
            return False
    
    def merge_videos(self, input_videos: List[Path], output_path: Path) -> bool:
        """
        Merge multiple video files into one.
        
        Args:
            input_videos: List of input video file paths
            output_path: Path to output merged video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if len(input_videos) < 2:
                raise ValueError("At least 2 video files are required for merging")
            
            self.progress_callback(f"Merging {len(input_videos)} video files")
            
            # Create input file list for FFmpeg
            input_list_file = output_path.parent / "merge_list.txt"
            
            with open(input_list_file, 'w') as f:
                for video_file in input_videos:
                    if not self.validate_video_file(video_file):
                        raise ValueError(f"Invalid video file: {video_file}")
                    f.write(f"file '{video_file.absolute()}'\n")
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg', '-y',  # Overwrite output files
                '-f', 'concat',
                '-safe', '0',
                '-i', str(input_list_file),
                '-c', 'copy',  # Copy streams without re-encoding
                str(output_path)
            ]
            
            self.progress_callback("Running FFmpeg to merge videos...")
            
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Clean up input list file
            if input_list_file.exists():
                input_list_file.unlink()
            
            self.progress_callback("Video merge completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to merge videos: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def validate_video_file(self, file_path: Path) -> bool:
        """Validate that the file is a supported video format."""
        if not file_path.exists():
            return False
        
        # Check file extension
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        if file_path.suffix.lower() not in video_extensions:
            return False
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and not mime_type.startswith('video/'):
            return False
        
        return True
    
    def validate_audio_file(self, file_path: Path) -> bool:
        """Validate that the file is a supported audio format."""
        if not file_path.exists():
            return False
        
        # Check file extension
        audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg'}
        if file_path.suffix.lower() not in audio_extensions:
            return False
        
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and not mime_type.startswith('audio/'):
            return False
        
        return True
    
    def get_supported_video_formats(self) -> List[str]:
        """Get list of supported video formats."""
        return ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
    
    def get_supported_audio_formats(self) -> List[str]:
        """Get list of supported audio formats."""
        return ['.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg']
    
    def get_supported_image_formats(self) -> List[str]:
        """Get list of supported image formats."""
        return ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif']