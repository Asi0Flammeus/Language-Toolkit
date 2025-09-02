"""
Audio Transcription Core Module

This module provides audio-to-text transcription functionality using OpenAI's Whisper API.
It can convert spoken audio in various formats into accurate text transcriptions.

Usage Examples:
    GUI: Integrated with file browsers, progress bars, and language selection dropdowns
    API: Used via REST endpoints for transcription services and batch processing
    CLI: Command-line audio transcription for automation workflows

Features:
    - OpenAI Whisper API integration for state-of-the-art transcription
    - Support for multiple audio formats (MP3, WAV, M4A, OGG, FLAC, WebM)
    - Language detection and manual language specification
    - Progress callback support for user feedback
    - Robust error handling and validation
    - High accuracy transcription results

Supported Audio Formats:
    - MP3 (most common)
    - WAV (uncompressed)
    - M4A (Apple format)
    - OGG (open source)
    - FLAC (lossless)
    - WebM (web format)
"""

import logging
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, List

import openai
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class AudioTranscriptionCore:
    """
    Core audio transcription functionality using OpenAI Whisper API.
    
    This class provides high-quality audio-to-text transcription capabilities
    supporting multiple audio formats and languages. It uses OpenAI's Whisper
    model for accurate speech recognition.
    
    Key Features:
        - State-of-the-art transcription via OpenAI Whisper
        - Multi-format audio support
        - Automatic language detection
        - Manual language specification support
        - Progress tracking with callback support
        - Comprehensive error handling
        - High accuracy results
    
    Requirements:
        - OpenAI API key
        - openai Python library
        - Valid audio input files
    
    Example Usage:
        transcriber = AudioTranscriptionCore(api_key="your-openai-key")
        success = transcriber.transcribe_audio(
            input_path=Path("audio.mp3"),
            output_path=Path("transcript.txt"),
            language="en"  # Optional
        )
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize audio transcription core.
        
        Args:
            api_key: OpenAI API key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            logger.debug("OpenAI client initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
    
    def transcribe_audio(self, input_path: Path, output_path: Path, 
                        language: Optional[str] = None) -> bool:
        """
        Transcribe audio file to text with automatic file splitting for large files.
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output text file
            language: Optional language code for transcription
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Starting transcription of: {input_path}")
            
            # Validate input file
            if not self.validate_audio_file(input_path):
                raise ValueError(f"Invalid audio file: {input_path}")
            
            # Check file size (25MB limit for OpenAI Whisper API)
            file_size_mb = input_path.stat().st_size / (1024 * 1024)
            self.progress_callback(f"Audio file size: {file_size_mb:.1f} MB")
            
            if file_size_mb > 24:  # Use 24MB as threshold to be safe
                self.progress_callback("Large file detected, splitting into chunks...")
                audio_files = self._prepare_audio_files(input_path)
                
                # Transcribe each chunk
                full_transcript = ""
                for i, audio_file_path in enumerate(audio_files, 1):
                    self.progress_callback(f"Transcribing chunk {i}/{len(audio_files)}")
                    
                    # Retry logic for each chunk
                    chunk_transcript = None
                    for attempt in range(3):
                        try:
                            with open(audio_file_path, 'rb') as audio_file:
                                transcript = self.client.audio.transcriptions.create(
                                    model="whisper-1",
                                    file=audio_file,
                                    language=language
                                )
                                chunk_transcript = transcript.text
                                break
                        except Exception as chunk_error:
                            if attempt == 2:  # Last attempt
                                raise chunk_error
                            self.progress_callback(f"Chunk {i} failed, retrying... ({chunk_error})")
                    
                    if chunk_transcript:
                        full_transcript += chunk_transcript + " "
                
                # Clean up temporary files
                for temp_file in audio_files:
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors
                
                final_transcript = full_transcript.strip()
            else:
                # Small file, transcribe directly
                with open(input_path, 'rb') as audio_file:
                    transcript = self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )
                final_transcript = transcript.text
            
            # Save transcription
            self.progress_callback(f"Saving transcription to: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_transcript)
            
            self.progress_callback("Audio transcription completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to transcribe audio: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def _prepare_audio_files(self, input_path: Path) -> List[Path]:
        """
        Split large audio file into chunks for processing.
        
        Args:
            input_path: Path to large audio file
            
        Returns:
            List of paths to temporary audio chunk files
        """
        try:
            self.progress_callback("Loading audio for splitting...")
            
            # Load audio file using pydub
            audio = AudioSegment.from_file(input_path)
            
            # Calculate chunk duration (aim for ~20MB chunks)
            # Estimate: MP3 @ 128kbps ≈ 1MB per minute, so ~20 minutes per chunk
            chunk_duration_ms = 20 * 60 * 1000  # 20 minutes in milliseconds
            audio_duration_ms = len(audio)
            
            self.progress_callback(f"Audio duration: {audio_duration_ms/1000/60:.1f} minutes")
            
            # Calculate number of chunks needed
            num_chunks = max(1, (audio_duration_ms + chunk_duration_ms - 1) // chunk_duration_ms)
            self.progress_callback(f"Splitting into {num_chunks} chunks")
            
            # Create temporary files
            temp_files = []
            
            for i in range(num_chunks):
                start_ms = i * chunk_duration_ms
                end_ms = min((i + 1) * chunk_duration_ms, audio_duration_ms)
                
                self.progress_callback(f"Creating chunk {i+1}/{num_chunks}")
                
                # Extract chunk
                chunk = audio[start_ms:end_ms]
                
                # Create temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                temp_path = Path(temp_file.name)
                temp_file.close()
                
                # Export chunk
                chunk.export(temp_path, format="mp3")
                temp_files.append(temp_path)
                
                self.progress_callback(f"Chunk {i+1} saved: {temp_path.stat().st_size / 1024 / 1024:.1f} MB")
            
            return temp_files
            
        except Exception as e:
            # Clean up any created files on error
            for temp_file in temp_files:
                try:
                    temp_file.unlink()
                except Exception:
                    pass
            raise RuntimeError(f"Failed to split audio file: {e}")
    
    def validate_audio_file(self, file_path: Path) -> bool:
        """Validate that the file is a supported audio format."""
        if not file_path.exists():
            return False
        
        supported_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm'}
        return file_path.suffix.lower() in supported_extensions
    
    def get_supported_formats(self) -> list:
        """Get list of supported audio formats."""
        return ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm']

    def transcribe_audio_file(self, input_path: Path, output_path: Path, language: Optional[str] = None) -> bool:
        """Backward-compatibility wrapper.

        api_server.py historically expected a ``transcribe_audio_file`` method.  The
        core implementation was later renamed to :py:meth:`transcribe_audio`.  To
        avoid breaking the public API we provide this thin wrapper that simply
        delegates to the new name.
        """
        return self.transcribe_audio(input_path, output_path, language)