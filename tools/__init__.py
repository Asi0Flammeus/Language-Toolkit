"""Tool implementations for Language Toolkit."""

from .text_to_speech import TextToSpeechTool
from .audio_transcription import AudioTranscriptionTool
from .pptx_translation import PPTXTranslationTool
from .text_translation import TextTranslationTool
from .pptx_to_pdf import PPTXtoPDFTool
from .transcript_cleaner import TranscriptCleanerTool
from .video_merge import VideoMergeTool
# Import from the module file directly to avoid conflict with package
import importlib.util
import os
spec = importlib.util.spec_from_file_location(
    "sequential_processing_module",
    os.path.join(os.path.dirname(__file__), "sequential_processing.py")
)
sequential_processing_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sequential_processing_module)
SequentialVideoProcessingTool = sequential_processing_module.SequentialVideoProcessingTool
from .reward_evaluator import RewardEvaluatorTool

__all__ = [
    'TextToSpeechTool',
    'AudioTranscriptionTool', 
    'PPTXTranslationTool',
    'TextTranslationTool',
    'PPTXtoPDFTool',
    'TranscriptCleanerTool',
    'VideoMergeTool',
    'SequentialVideoProcessingTool',
    'RewardEvaluatorTool'
]