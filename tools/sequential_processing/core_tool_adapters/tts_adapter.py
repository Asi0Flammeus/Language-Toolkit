"""Text-to-Speech Adapter for Sequential Processing."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Callable

from . import CoreToolAdapter
from core.text_to_speech import TextToSpeechCore

logger = logging.getLogger(__name__)


class TTSAdapter(CoreToolAdapter):
    """Adapter for Text-to-Speech Core Tool."""
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize TTS adapter.
        
        Args:
            api_key: ElevenLabs API key
            progress_callback: Optional callback for progress updates
        """
        super().__init__(progress_callback)
        self.api_key = api_key
        self.tool = None
    
    def _initialize_tool(self):
        """Initialize the core tool if not already done."""
        if not self.tool:
            self.tool = TextToSpeechCore(
                api_key=self.api_key,
                progress_callback=self.progress_callback
            )
    
    def process(self, input_path: Path, output_path: Path, params: Dict[str, Any]) -> Path:
        """
        Generate audio from text file using intelligent voice detection.
        
        Uses the same method as the main text-to-speech tool:
        - Extracts voice name from filename (e.g., 'test_Rachel_en.txt' -> 'Rachel')
        - Matches against available API voices
        - Falls back to first available voice if no match found
        
        Args:
            input_path: Path to input text file
            output_path: Path to output location (directory or file)
            params: Optional voice_settings override
            
        Returns:
            Path to generated audio file, or None if failed
        """
        self._initialize_tool()
        
        # Get voice settings if provided
        voice_settings = params.get('voice_settings', {
            'stability': 0.75,
            'similarity_boost': 0.75,
            'style': 0.0,
            'use_speaker_boost': False
        })
        
        # If output_path is a directory, create output file path
        if output_path.is_dir():
            output_file = output_path / f"{input_path.stem}.mp3"
        else:
            output_file = output_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.report_progress(f"Generating audio from: {input_path.name}")
            
            # Use text_to_speech_file method which automatically detects voice from filename
            # This is EXACTLY the same method used by the main text-to-speech tool
            success, request_id = self.tool.text_to_speech_file(
                input_path=input_path,
                output_path=output_file,
                voice_settings=voice_settings
            )

            if success:
                self.report_progress(f"✓ Audio saved to: {output_file}")
                return output_file
            else:
                self.report_progress(f"✗ Failed to generate audio from: {input_path.name}")
                return None
                
        except Exception as e:
            logger.exception(f"Error generating audio from {input_path}: {str(e)}")
            self.report_progress(f"✗ Error generating audio: {str(e)}")
            return None
    
    def validate_input(self, input_path: Path) -> bool:
        """
        Validate if the input is a text file.
        
        Args:
            input_path: Path to validate
            
        Returns:
            True if input is a text file
        """
        return input_path.suffix.lower() == '.txt' and input_path.exists()