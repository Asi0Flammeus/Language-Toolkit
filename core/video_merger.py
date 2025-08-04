"""
Video Merger Core Module

This module provides video creation and merging functionality using FFmpeg.
It can create videos from image sequences, merge multiple videos, and add audio tracks.

Usage Examples:
    GUI: Integrated with file browsers, timeline controls, and video preview
    API: Used via REST endpoints for video processing services
    CLI: Command-line video creation and merging for automation

Features:
    - FFmpeg integration for professional video processing
    - Create videos from image sequences (PNG, JPG, etc.)
    - Merge multiple video files into one
    - Add audio tracks to videos
    - Customizable slide duration and transitions
    - Support for various video and audio formats
    - Progress callback support for user feedback
    - Professional output quality (1920x1080, 30fps)

Video Creation Capabilities:
    - Image sequence to video conversion
    - Automatic image sorting and sequencing
    - Customizable duration per slide/image
    - Fade transitions between slides
    - Audio overlay support
    - Professional video encoding (H.264)

Supported Formats:
    Video: MP4, AVI, MOV, MKV, WebM, FLV, WMV
    Audio: MP3, WAV, AAC, M4A, FLAC, OGG
    Images: PNG, JPG, JPEG, BMP, TIFF, GIF
"""

import logging
import subprocess
import os
import re
import mimetypes
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class VideoMergerCore:
    """
    Core video merger functionality using FFmpeg.
    
    This class provides comprehensive video processing capabilities including
    creating videos from image sequences, merging videos, and adding audio.
    It uses FFmpeg for professional-quality video processing.
    
    Key Features:
        - Professional video processing via FFmpeg
        - Image sequence to video conversion
        - Video merging and concatenation
        - Audio track integration
        - Customizable timing and transitions
        - Multi-format support
        - High-quality output (1920x1080, 30fps)
    
    Requirements:
        - FFmpeg installed and available in PATH
        - Valid input files (images, videos, audio)
        - Sufficient disk space for processing
    
    Example Usage:
        merger = VideoMergerCore()
        
        # Create video from images
        success = merger.create_video_from_files(
            input_dir=Path("images/"),
            output_path=Path("video.mp4"),
            duration_per_slide=3.0,
            audio_file=Path("soundtrack.mp3")
        )
        
        # Merge multiple videos
        success = merger.merge_videos(
            input_videos=[Path("video1.mp4"), Path("video2.mp4")],
            output_path=Path("merged.mp4")
        )
    """
    
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
                               fade_duration: float = 0.5,
                               intro_video: Optional[Path] = None,
                               outro_audio: Optional[Path] = None,
                               use_outro_for_last_slide: bool = False) -> bool:
        """
        Create video from images and optional audio.
        
        Args:
            input_dir: Directory containing input images
            output_path: Path to output video file
            duration_per_slide: Duration per slide in seconds
            audio_file: Optional audio file to add
            fade_duration: Fade transition duration in seconds
            intro_video: Optional intro video to prepend
            outro_audio: Optional outro audio to use for last slide
            use_outro_for_last_slide: If True and outro_audio provided, use it for last slide
            
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
            
            # Handle outro audio for last slide if requested
            actual_audio_file = audio_file
            if use_outro_for_last_slide and outro_audio and outro_audio.exists() and image_files:
                # Create a temporary video for all but the last image
                if len(image_files) > 1:
                    temp_video_main = output_path.parent / f"temp_main_{output_path.stem}.mp4"
                    success = self._create_video_from_images(
                        image_files[:-1], temp_video_main, duration_per_slide, fade_duration
                    )
                    if not success:
                        return False
                    
                    # Create video for last image with outro audio
                    temp_video_last = output_path.parent / f"temp_last_{output_path.stem}.mp4"
                    success = self._create_video_from_images(
                        [image_files[-1]], temp_video_last, duration_per_slide, fade_duration
                    )
                    if not success:
                        return False
                    
                    # Add outro audio to last segment
                    temp_video_last_audio = output_path.parent / f"temp_last_audio_{output_path.stem}.mp4"
                    success = self._add_audio_to_video(temp_video_last, outro_audio, temp_video_last_audio)
                    if not success:
                        return False
                    
                    # Merge the two videos
                    success = self.merge_videos([temp_video_main, temp_video_last_audio], temp_video)
                    
                    # Clean up temp files
                    for f in [temp_video_main, temp_video_last, temp_video_last_audio]:
                        if f.exists():
                            f.unlink()
                    
                    if not success:
                        return False
                else:
                    # Only one image, use outro audio directly
                    actual_audio_file = outro_audio
                    success = self._create_video_from_images(
                        image_files, temp_video, duration_per_slide, fade_duration
                    )
                    if not success:
                        return False
            else:
                # Standard processing without outro modification
                success = self._create_video_from_images(
                    image_files, temp_video, duration_per_slide, fade_duration
                )
                if not success:
                    return False
            
            # Now handle the final video composition
            videos_to_concat = []
            
            # Add intro if provided
            if intro_video and intro_video.exists():
                if not self.validate_video_file(intro_video):
                    self.progress_callback(f"Warning: Invalid intro video format: {intro_video}")
                else:
                    videos_to_concat.append(intro_video)
                    self.progress_callback("Including intro video")
            
            # Add main video
            videos_to_concat.append(temp_video)
            
            # If we have multiple videos to concatenate
            if len(videos_to_concat) > 1:
                self.progress_callback("Merging intro with main video...")
                final_temp = output_path.parent / f"final_temp_{output_path.stem}.mp4"
                success = self.merge_videos(videos_to_concat, final_temp)
                
                if success:
                    # Add audio if provided and not already added
                    if actual_audio_file and actual_audio_file.exists() and not use_outro_for_last_slide:
                        self.progress_callback("Adding audio track...")
                        success = self._add_audio_to_video(final_temp, actual_audio_file, output_path)
                        if final_temp.exists():
                            final_temp.unlink()
                    else:
                        final_temp.rename(output_path)
                
                # Clean up temp video
                if temp_video.exists():
                    temp_video.unlink()
            else:
                # No intro, just handle audio
                if actual_audio_file and actual_audio_file.exists():
                    self.progress_callback("Adding audio track...")
                    success = self._add_audio_to_video(temp_video, actual_audio_file, output_path)
                    
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
    
    def create_video_from_file_pairs(self, file_pairs: List[Tuple[str, Path, Path]], 
                                    output_path: Path,
                                    silence_duration: float = 0.2,
                                    intro_video: Optional[Path] = None,
                                    outro_audio: Optional[Path] = None) -> bool:
        """
        Create video from matched audio/image file pairs.
        
        This method is similar to the VideoMergeTool functionality, creating a video
        from pairs of audio and image files with silence between segments.
        
        Args:
            file_pairs: List of tuples (identifier, audio_path, image_path)
            output_path: Path to output video file
            silence_duration: Duration of silence between segments in seconds
            intro_video: Optional intro video to prepend
            outro_audio: Optional outro audio to replace last segment's audio
            
        Returns:
            True if successful, False otherwise
        """
        import tempfile
        
        try:
            if not file_pairs:
                raise ValueError("No file pairs provided")
            
            self.progress_callback(f"Creating video from {len(file_pairs)} file pairs")
            
            # Create temporary directory for segments
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                segment_files = []
                
                # Process each pair and create individual video segments
                for idx, (identifier, audio_file, image_file) in enumerate(file_pairs):
                    if not image_file.exists():
                        raise FileNotFoundError(f"Missing image file for pair {identifier}")
                    if audio_file and not audio_file.exists():
                        raise FileNotFoundError(f"Missing audio file for pair {identifier}")
                    
                    self.progress_callback(f"Processing pair {idx+1}/{len(file_pairs)}: {identifier}")
                    
                    # Create segment file path
                    segment_file = temp_path / f"segment_{idx:03d}.mp4"
                    segment_files.append(segment_file)
                    
                    # Check if this is the last slide and outro is enabled
                    is_last_slide = (idx == len(file_pairs) - 1)
                    actual_audio_file = audio_file
                    
                    # Handle cases where there's no audio file (PNG without MP3 match)
                    if not audio_file:
                        if outro_audio and outro_audio.exists():
                            actual_audio_file = outro_audio
                            self.progress_callback(f"Using outro audio for PNG without MP3 (slide {idx+1} of {len(file_pairs)})")
                        else:
                            raise ValueError(f"No audio file for pair {identifier} and no outro audio provided")
                    elif is_last_slide and outro_audio and outro_audio.exists():
                        actual_audio_file = outro_audio
                        self.progress_callback(f"Using outro audio for last slide (slide {idx+1} of {len(file_pairs)})")
                    else:
                        self.progress_callback(f"Using original audio for slide {idx+1} of {len(file_pairs)}")
                    
                    # Create video segment from image and audio
                    cmd = [
                        'ffmpeg', '-y',
                        '-loop', '1',
                        '-i', str(image_file),
                        '-i', str(actual_audio_file),
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                        '-c:v', 'libx264',
                        '-tune', 'stillimage',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-ar', '44100',
                        '-ac', '2',
                        '-shortest',
                        '-pix_fmt', 'yuv420p',
                        str(segment_file)
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        logger.error(f"FFmpeg error: {result.stderr}")
                        raise RuntimeError(f"Failed to create segment {idx}")
                    
                    # Add silence segment between clips (except after last)
                    if idx < len(file_pairs) - 1 and silence_duration > 0:
                        silence_file = temp_path / f"silence_{idx:03d}.mp4"
                        segment_files.append(silence_file)
                        
                        # Create silence with the same image
                        silence_cmd = [
                            'ffmpeg', '-y',
                            '-loop', '1',
                            '-i', str(image_file),
                            '-f', 'lavfi', 
                            '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                            '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                            '-c:v', 'libx264',
                            '-t', str(silence_duration),
                            '-c:a', 'aac',
                            '-pix_fmt', 'yuv420p',
                            str(silence_file)
                        ]
                        
                        result = subprocess.run(silence_cmd, capture_output=True, text=True)
                        if result.returncode != 0:
                            logger.error(f"FFmpeg silence error: {result.stderr}")
                
                # Create concatenation list
                concat_file = temp_path / "concat_list.txt"
                with open(concat_file, 'w') as f:
                    # Add intro if provided
                    if intro_video and intro_video.exists():
                        # Since the intro video has been fixed, we can use it directly
                        # Just ensure it's compatible by re-encoding with same settings as other segments
                        processed_intro = temp_path / "intro_processed.mp4"
                        
                        self.progress_callback("Processing intro video...")
                        intro_cmd = [
                            'ffmpeg', '-y',
                            '-i', str(intro_video),
                            '-c:v', 'libx264',  # Re-encode to ensure compatibility
                            '-pix_fmt', 'yuv420p',  # Standard pixel format
                            '-c:a', 'aac',  # Re-encode audio to ensure compatibility
                            '-b:a', '192k',
                            '-ar', '44100',
                            '-ac', '2',
                            '-map', '0:v:0',  # Map video stream
                            '-map', '0:a:0?',  # Map audio stream if it exists
                            str(processed_intro)
                        ]
                        
                        result = subprocess.run(intro_cmd, capture_output=True, text=True)
                        
                        if result.returncode != 0:
                            self.progress_callback("Warning: Failed to process intro video, using original")
                            # Try to use the original intro video directly
                            processed_intro = intro_video
                            result.returncode = 0  # Reset to allow inclusion
                        
                        if processed_intro.exists() and result.returncode == 0:
                            f.write(f"file '{processed_intro.absolute()}'\n")
                            self.progress_callback("Including intro video")
                        else:
                            self.progress_callback("Warning: Could not include intro video")
                    
                    # Add all video segments
                    self.progress_callback(f"Adding {len(segment_files)} segments to concatenation list")
                    for i, segment in enumerate(segment_files):
                        f.write(f"file '{segment.absolute()}'\n")
                        self.progress_callback(f"Added segment {i+1}: {segment.name}")
                
                # Concatenate all segments into final video
                self.progress_callback("Concatenating all segments...")
                
                # Use copy codec since all segments are now compatible
                concat_cmd = [
                    'ffmpeg', '-y',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(concat_file),
                    '-c', 'copy',
                    str(output_path)
                ]
                
                result = subprocess.run(concat_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"FFmpeg concat error: {result.stderr}")
                    raise RuntimeError("Failed to concatenate video segments")
                
                self.progress_callback("Video creation completed successfully")
                return True
                
        except Exception as e:
            error_msg = f"Failed to create video from file pairs: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False