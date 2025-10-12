"""
Business Logic Processors for Language Toolkit.

This module provides shared business logic processors that eliminate code duplication
between main.py and api_server.py. Each processor handles specific workflows while
maintaining consistent interfaces for both GUI and API applications.

Common Patterns Consolidated:
    - File processing workflows (input validation, processing, output)
    - Translation workflows with language validation
    - Audio processing workflows with format validation
    - Document conversion workflows
    - Batch processing with progress tracking
    - Error handling and recovery strategies
    - Progress reporting across different interfaces
    - Task lifecycle management
    - Temporary directory management

Usage Examples:
    # Single file translation
    processor = TranslationProcessor(service_manager, progress_reporter)
    result = processor.process_file(input_file, output_file, source_lang, target_lang)
    
    # Batch audio transcription
    processor = AudioProcessor(service_manager, progress_reporter)
    results = processor.process_batch(input_files, output_dir, options)
    
    # Document conversion
    processor = ConversionProcessor(service_manager, progress_reporter)
    result = processor.convert_document(input_file, output_format)
"""

import logging
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, Set, Tuple

# Import our core modules
from .file_utils import (
    create_temp_dir, safe_cleanup, validate_file_path, get_file_extension,
    create_output_filename, should_skip_processing, get_file_size_mb
)
from .services import ServiceManager, ServiceType, APIKeyError, ServiceError
from .task_manager import TaskManager, TaskStatus, Task
from .validation import (
    validate_file_size, validate_language_code, validate_file_extension,
    validate_output_format
)

logger = logging.getLogger(__name__)

class BatchContext:
    """
    Track request IDs for request stitching across batch processing.

    Maintains separate request ID chains per teacher/voice to enable
    seamless voice continuity across multiple audio segments.
    """

    def __init__(self):
        """Initialize batch context with empty request ID tracking."""
        self.request_ids_by_teacher = {}  # {teacher_name: [id1, id2, id3]}
        self._lock = threading.Lock()

    def add_request(self, teacher_name: str, request_id: str) -> None:
        """
        Add request ID for teacher (keeps last 3).

        Args:
            teacher_name: Name of the teacher/voice
            request_id: ElevenLabs request ID from API response
        """
        if not teacher_name or not request_id:
            return

        with self._lock:
            if teacher_name not in self.request_ids_by_teacher:
                self.request_ids_by_teacher[teacher_name] = []

            ids = self.request_ids_by_teacher[teacher_name]
            ids.append(request_id)

            # Keep only last 3 request IDs (ElevenLabs limit)
            if len(ids) > 3:
                ids.pop(0)

            logger.debug(f"Added request ID for {teacher_name}: {request_id} (total: {len(ids)})")

    def get_previous_ids(self, teacher_name: str) -> List[str]:
        """
        Get previous request IDs for teacher.

        Args:
            teacher_name: Name of the teacher/voice

        Returns:
            List of previous request IDs (max 3)
        """
        with self._lock:
            return self.request_ids_by_teacher.get(teacher_name, []).copy()

    def reset(self, teacher_name: Optional[str] = None) -> None:
        """
        Clear context for specific teacher or all teachers.

        Args:
            teacher_name: Specific teacher to reset, or None for all
        """
        with self._lock:
            if teacher_name:
                self.request_ids_by_teacher.pop(teacher_name, None)
                logger.debug(f"Reset context for {teacher_name}")
            else:
                self.request_ids_by_teacher.clear()
                logger.debug("Reset all batch context")

class ProcessingStatus(Enum):
    """Status of processing operations"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"

class ProcessorType(Enum):
    """Types of processors available"""
    TRANSLATION = "translation"
    AUDIO = "audio"
    CONVERSION = "conversion"
    BATCH = "batch"

@dataclass
class ProcessingResult:
    """Standardized result object for all processing operations"""
    status: ProcessingStatus
    input_path: Optional[Path] = None
    output_path: Optional[Path] = None
    message: str = ""
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time: float = 0.0
    
    @property
    def success(self) -> bool:
        """Check if processing was successful"""
        return self.status == ProcessingStatus.COMPLETED
    
    @property
    def skipped(self) -> bool:
        """Check if processing was skipped"""
        return self.status == ProcessingStatus.SKIPPED

@dataclass
class ProcessorConfig:
    """Configuration for processors"""
    skip_existing: bool = True
    max_file_size_mb: float = 100.0
    temp_dir: Optional[Path] = None
    progress_interval: float = 0.5
    max_retries: int = 3
    timeout_seconds: Optional[float] = None
    
    # File type specific settings
    allowed_extensions: Optional[Set[str]] = None
    output_formats: Optional[List[str]] = None
    
    # Processing specific settings
    batch_size: int = 10
    concurrent_workers: int = 4

class ProgressReporter:
    """Unified progress reporting interface for GUI and API"""
    
    def __init__(self, 
                 callback: Optional[Callable[[str], None]] = None,
                 task_manager: Optional[TaskManager] = None,
                 task_id: Optional[str] = None):
        """
        Initialize progress reporter.
        
        Args:
            callback: Progress callback function (for GUI)
            task_manager: Task manager instance (for API)
            task_id: Task ID for API progress tracking
        """
        self.callback = callback
        self.task_manager = task_manager
        self.task_id = task_id
        self._last_report_time = 0
        self._report_interval = 0.5  # Minimum time between reports
    
    def report_progress(self, message: str, progress: Optional[float] = None) -> None:
        """
        Report progress to appropriate interface.
        
        Args:
            message: Progress message
            progress: Progress percentage (0-100, optional)
        """
        current_time = time.time()
        
        # Throttle progress reports
        if current_time - self._last_report_time < self._report_interval:
            return
        
        self._last_report_time = current_time
        
        # Format message with progress if provided
        if progress is not None:
            formatted_message = f"{message} ({progress:.1f}%)"
        else:
            formatted_message = message
        
        # Report to GUI callback
        if self.callback:
            try:
                self.callback(formatted_message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        # Report to API task manager
        if self.task_manager and self.task_id:
            try:
                self.task_manager.update_task_progress(
                    self.task_id, 
                    formatted_message,
                    progress
                )
            except Exception as e:
                logger.warning(f"Task manager progress update failed: {e}")
        
        # Always log progress
        logger.debug(f"Progress: {formatted_message}")
    
    def report_error(self, error: Union[str, Exception]) -> None:
        """Report error through progress interface"""
        error_msg = f"Error: {str(error)}"
        self.report_progress(error_msg)
        logger.error(error_msg)
    
    def report_completion(self, message: str = "Processing completed") -> None:
        """Report completion through progress interface"""
        self.report_progress(message, 100.0)

class ErrorHandler:
    """Centralized error handling for processors"""
    
    def __init__(self, max_retries: int = 3, progress_reporter: Optional[ProgressReporter] = None):
        """
        Initialize error handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            progress_reporter: Progress reporter for error notifications
        """
        self.max_retries = max_retries
        self.progress_reporter = progress_reporter
    
    def handle_error(self, 
                    error: Exception,
                    operation: str,
                    input_path: Optional[Path] = None,
                    attempt: int = 1) -> ProcessingResult:
        """
        Handle processing errors with appropriate responses.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
            input_path: Input file path (for logging)
            attempt: Current attempt number
            
        Returns:
            ProcessingResult with error information
        """
        error_msg = self._format_error_message(error, operation, input_path, attempt)
        
        # Report error through progress interface
        if self.progress_reporter:
            self.progress_reporter.report_error(error_msg)
        
        # Log error with appropriate level
        if isinstance(error, (APIKeyError, ServiceError)):
            logger.error(error_msg)
        elif attempt <= self.max_retries:
            logger.warning(f"{error_msg} (attempt {attempt}/{self.max_retries})")
        else:
            logger.error(f"{error_msg} (giving up after {self.max_retries} attempts)")
        
        return ProcessingResult(
            status=ProcessingStatus.FAILED,
            input_path=input_path,
            message=error_msg,
            error=error
        )
    
    def _format_error_message(self, 
                             error: Exception,
                             operation: str,
                             input_path: Optional[Path],
                             attempt: int) -> str:
        """Format a consistent error message"""
        file_info = f" for {input_path.name}" if input_path else ""
        attempt_info = f" (attempt {attempt})" if attempt > 1 else ""
        
        if isinstance(error, APIKeyError):
            return f"API key not configured for {error.service}: {str(error)}"
        elif isinstance(error, ServiceError):
            return f"Service error in {operation}{file_info}: {str(error)}"
        else:
            return f"Failed {operation}{file_info}{attempt_info}: {str(error)}"
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if an operation should be retried.
        
        Args:
            error: The exception that occurred
            attempt: Current attempt number
            
        Returns:
            True if operation should be retried
        """
        # Don't retry configuration errors
        if isinstance(error, (APIKeyError, ValueError)):
            return False
        
        # Don't retry if we've exceeded max attempts
        if attempt >= self.max_retries:
            return False
        
        # Retry network/service errors
        if isinstance(error, ServiceError):
            return True
        
        # Retry generic exceptions (but not file not found, etc.)
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        return False

@contextmanager
def temp_directory_manager(prefix: str = "processor_"):
    """Context manager for temporary directory lifecycle"""
    temp_dir = None
    try:
        temp_dir = create_temp_dir(prefix)
        logger.debug(f"Created temporary directory: {temp_dir}")
        yield temp_dir
    finally:
        if temp_dir:
            safe_cleanup(temp_dir)
            logger.debug(f"Cleaned up temporary directory: {temp_dir}")

class BaseProcessor(ABC):
    """
    Abstract base class for all processors.
    
    Provides common functionality for file processing, error handling,
    progress reporting, and task management.
    """
    
    def __init__(self,
                 service_manager: ServiceManager,
                 progress_reporter: Optional[ProgressReporter] = None,
                 config: Optional[ProcessorConfig] = None):
        """
        Initialize base processor.
        
        Args:
            service_manager: Service manager for API access
            progress_reporter: Progress reporting interface
            config: Processor configuration
        """
        self.service_manager = service_manager
        self.progress_reporter = progress_reporter or ProgressReporter()
        self.config = config or ProcessorConfig()
        self.error_handler = ErrorHandler(
            max_retries=self.config.max_retries,
            progress_reporter=self.progress_reporter
        )
        
        # Processing state
        self._cancel_requested = threading.Event()
        self._processing_lock = threading.Lock()
    
    @abstractmethod
    def get_processor_type(self) -> ProcessorType:
        """Get the type of this processor"""
        pass
    
    @abstractmethod
    def get_required_service_type(self) -> ServiceType:
        """Get the required service type for this processor"""
        pass
    
    def validate_service_availability(self) -> None:
        """
        Validate that required services are available.
        
        Raises:
            APIKeyError: If required API key is not configured
        """
        service_type = self.get_required_service_type()
        if not self.service_manager.has_api_key(service_type):
            raise APIKeyError(service_type.value)
    
    def validate_input_file(self, file_path: Path) -> Path:
        """
        Validate input file with processor-specific rules.
        
        Args:
            file_path: Path to input file
            
        Returns:
            Validated path object
            
        Raises:
            ValueError: If file validation fails
        """
        # Basic file existence and type validation
        validated_path = validate_file_path(
            file_path, 
            must_exist=True,
            allowed_extensions=self.config.allowed_extensions
        )
        
        # File size validation
        if self.config.max_file_size_mb > 0:
            validate_file_size(
                get_file_size_mb(validated_path) * 1024 * 1024,  # Convert back to bytes
                str(validated_path),
                "general"
            )
        
        return validated_path
    
    def should_skip_output(self, input_path: Path, output_path: Path) -> bool:
        """
        Check if processing should be skipped due to existing output.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            
        Returns:
            True if processing should be skipped
        """
        return should_skip_processing(
            input_path,
            output_path,
            check_exists=self.config.skip_existing
        )
    
    def create_output_path(self, 
                          input_path: Path,
                          output_dir: Optional[Path] = None,
                          suffix: str = "",
                          new_extension: Optional[str] = None) -> Path:
        """
        Create output file path based on input file.
        
        Args:
            input_path: Input file path
            output_dir: Output directory (uses input dir if None)
            suffix: Suffix to add to filename stem
            new_extension: New file extension
            
        Returns:
            Generated output file path
        """
        if output_dir is None:
            output_dir = input_path.parent
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        output_filename = create_output_filename(
            input_path,
            suffix=suffix,
            new_extension=new_extension
        )
        
        return output_dir / output_filename
    
    def request_cancellation(self) -> None:
        """Request cancellation of current processing"""
        self._cancel_requested.set()
        self.progress_reporter.report_progress("Cancellation requested...")
    
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested"""
        return self._cancel_requested.is_set()
    
    def reset_cancellation(self) -> None:
        """Reset cancellation state for new operations"""
        self._cancel_requested.clear()

class FileProcessor(BaseProcessor):
    """
    Processor for single file operations.
    
    Handles the standard workflow of input validation, processing,
    and output generation for individual files.
    """
    
    def process_file(self,
                    input_path: Union[str, Path],
                    output_path: Optional[Union[str, Path]] = None,
                    **processing_options) -> ProcessingResult:
        """
        Process a single file with standardized workflow.
        
        Args:
            input_path: Path to input file
            output_path: Path for output file (auto-generated if None)
            **processing_options: Processor-specific options
            
        Returns:
            ProcessingResult with operation details
        """
        start_time = time.time()
        input_path = Path(input_path)
        
        try:
            # Reset cancellation state
            self.reset_cancellation()
            
            # Validate service availability
            self.progress_reporter.report_progress("Checking service availability...")
            self.validate_service_availability()
            
            # Validate input file
            self.progress_reporter.report_progress("Validating input file...")
            validated_input = self.validate_input_file(input_path)
            
            # Determine output path
            if output_path is None:
                output_path = self.create_output_path(validated_input, **processing_options)
            else:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if processing should be skipped
            if self.should_skip_output(validated_input, output_path):
                return ProcessingResult(
                    status=ProcessingStatus.SKIPPED,
                    input_path=validated_input,
                    output_path=output_path,
                    message=f"Skipped {validated_input.name} - output already exists",
                    processing_time=time.time() - start_time
                )
            
            # Perform the actual processing
            self.progress_reporter.report_progress(f"Processing {validated_input.name}...")
            result = self._process_file_implementation(
                validated_input, 
                output_path, 
                **processing_options
            )
            
            # Update result with timing
            result.processing_time = time.time() - start_time
            
            if result.success:
                self.progress_reporter.report_completion(
                    f"Successfully processed {validated_input.name}"
                )
            
            return result
            
        except Exception as e:
            return self.error_handler.handle_error(
                e, 
                "file processing",
                input_path
            )
    
    @abstractmethod
    def _process_file_implementation(self,
                                   input_path: Path,
                                   output_path: Path,
                                   **options) -> ProcessingResult:
        """
        Implement the actual file processing logic.
        
        Subclasses must override this method to provide specific processing logic.
        
        Args:
            input_path: Validated input file path
            output_path: Output file path
            **options: Processing options
            
        Returns:
            ProcessingResult with operation details
        """
        pass

class BatchProcessor(BaseProcessor):
    """
    Processor for batch operations on multiple files.
    
    Provides progress tracking, error handling, and cancellation
    support for processing multiple files.
    """
    
    def process_batch(self,
                     input_files: List[Union[str, Path]],
                     output_dir: Optional[Union[str, Path]] = None,
                     **processing_options) -> List[ProcessingResult]:
        """
        Process multiple files with progress tracking.
        
        Args:
            input_files: List of input file paths
            output_dir: Output directory for processed files
            **processing_options: Processing options for each file
            
        Returns:
            List of ProcessingResult objects
        """
        start_time = time.time()
        results = []
        
        # Convert to Path objects
        input_paths = [Path(f) for f in input_files]
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        total_files = len(input_paths)
        self.progress_reporter.report_progress(
            f"Starting batch processing of {total_files} files..."
        )
        
        for i, input_path in enumerate(input_paths, 1):
            # Check for cancellation
            if self.is_cancelled():
                self.progress_reporter.report_progress("Batch processing cancelled")
                break
            
            # Report progress
            progress = (i - 1) / total_files * 100
            self.progress_reporter.report_progress(
                f"Processing file {i}/{total_files}: {input_path.name}",
                progress
            )
            
            # Process individual file
            try:
                result = self._process_single_file_in_batch(
                    input_path,
                    output_dir,
                    **processing_options
                )
                results.append(result)
                
            except Exception as e:
                error_result = self.error_handler.handle_error(
                    e,
                    f"batch processing file {i}/{total_files}",
                    input_path
                )
                results.append(error_result)
        
        # Report batch completion
        successful_count = sum(1 for r in results if r.success)
        skipped_count = sum(1 for r in results if r.skipped)
        failed_count = len(results) - successful_count - skipped_count
        
        total_time = time.time() - start_time
        completion_message = (
            f"Batch processing completed: {successful_count} successful, "
            f"{skipped_count} skipped, {failed_count} failed "
            f"({total_time:.1f}s total)"
        )
        
        self.progress_reporter.report_completion(completion_message)
        
        return results
    
    @abstractmethod
    def _process_single_file_in_batch(self,
                                    input_path: Path,
                                    output_dir: Optional[Path],
                                    **options) -> ProcessingResult:
        """
        Process a single file within a batch operation.
        
        Args:
            input_path: Input file path
            output_dir: Output directory
            **options: Processing options
            
        Returns:
            ProcessingResult for this file
        """
        pass

class TranslationProcessor(FileProcessor):
    """
    Processor for translation operations.
    
    Handles text and document translation with language validation
    and DeepL service integration.
    """
    
    def get_processor_type(self) -> ProcessorType:
        return ProcessorType.TRANSLATION
    
    def get_required_service_type(self) -> ServiceType:
        return ServiceType.DEEPL
    
    def _process_file_implementation(self,
                                   input_path: Path,
                                   output_path: Path,
                                   source_language: str,
                                   target_language: str,
                                   **options) -> ProcessingResult:
        """
        Implement translation processing.
        
        Args:
            input_path: Input file path
            output_path: Output file path
            source_language: Source language code
            target_language: Target language code
            **options: Additional translation options
            
        Returns:
            ProcessingResult with translation details
        """
        try:
            # Validate language codes
            source_lang = validate_language_code(source_language, is_target=False)
            target_lang = validate_language_code(target_language, is_target=True)
            
            # Determine translation service based on file type
            file_ext = get_file_extension(input_path, lowercase=True)
            
            if file_ext == '.txt':
                from core.text_translation_config import TextTranslationCore
                service_class = TextTranslationCore
            elif file_ext == '.pptx':
                from core.pptx_translation import PPTXTranslationCore
                service_class = PPTXTranslationCore
            else:
                raise ValueError(f"Unsupported file type for translation: {file_ext}")
            
            # Create translation service
            translator = self.service_manager.get_deepl_service(
                service_class,
                progress_callback=self.progress_reporter.report_progress
            )
            
            # Perform translation
            if file_ext == '.txt':
                success = translator.translate_text_file(
                    input_path, output_path, source_lang, target_lang
                )
            else:  # PPTX
                success = translator.translate_pptx(
                    input_path, output_path, source_lang, target_lang
                )
            
            if success:
                return ProcessingResult(
                    status=ProcessingStatus.COMPLETED,
                    input_path=input_path,
                    output_path=output_path,
                    message=f"Translated {input_path.name} from {source_lang} to {target_lang}",
                    metadata={
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "file_type": file_ext
                    }
                )
            else:
                raise RuntimeError("Translation service returned failure")
            
        except Exception as e:
            return self.error_handler.handle_error(
                e,
                f"translating {input_path.name}",
                input_path
            )

class AudioProcessor(FileProcessor):
    """
    Processor for audio operations.
    
    Handles audio transcription and text-to-speech with format validation
    and service integration.
    """
    
    def get_processor_type(self) -> ProcessorType:
        return ProcessorType.AUDIO
    
    def get_required_service_type(self) -> ServiceType:
        # Return the most commonly used service; specific operations can override
        return ServiceType.OPENAI
    
    def _process_file_implementation(self,
                                   input_path: Path,
                                   output_path: Path,
                                   operation: str,
                                   batch_context: Optional[BatchContext] = None,
                                   **options) -> ProcessingResult:
        """
        Implement audio processing.

        Args:
            input_path: Input file path
            output_path: Output file path
            operation: Type of operation ('transcribe' or 'synthesize')
            batch_context: Optional BatchContext for request stitching
            **options: Operation-specific options

        Returns:
            ProcessingResult with audio processing details
        """
        try:
            if operation == 'transcribe':
                return self._process_transcription(input_path, output_path, **options)
            elif operation == 'synthesize':
                return self._process_text_to_speech(input_path, output_path, batch_context, **options)
            else:
                raise ValueError(f"Unknown audio operation: {operation}")

        except Exception as e:
            return self.error_handler.handle_error(
                e,
                f"audio {operation}",
                input_path
            )
    
    def _process_transcription(self, input_path: Path, output_path: Path, **options) -> ProcessingResult:
        """Process audio transcription using OpenAI Whisper"""
        from core.transcription import AudioTranscriptionCore
        
        # Create transcription service
        transcriber = self.service_manager.get_openai_service(
            AudioTranscriptionCore,
            progress_callback=self.progress_reporter.report_progress
        )
        
        # Perform transcription
        success = transcriber.transcribe_audio(input_path, output_path)
        
        if success:
            return ProcessingResult(
                status=ProcessingStatus.COMPLETED,
                input_path=input_path,
                output_path=output_path,
                message=f"Transcribed {input_path.name}",
                metadata={"operation": "transcribe"}
            )
        else:
            raise RuntimeError("Transcription service returned failure")
    
    def _process_text_to_speech(self, input_path: Path, output_path: Path,
                                batch_context: Optional[BatchContext] = None,
                                **options) -> ProcessingResult:
        """
        Process text-to-speech using ElevenLabs with optional batch context for request stitching.

        Args:
            input_path: Input text file path
            output_path: Output audio file path
            batch_context: Optional BatchContext for request stitching across files
            **options: Additional voice settings

        Returns:
            ProcessingResult with operation details
        """
        from core.text_to_speech import TextToSpeechCore

        # Create TTS service
        tts = self.service_manager.get_elevenlabs_service(
            TextToSpeechCore,
            progress_callback=self.progress_reporter.report_progress
        )

        # Extract teacher name from filename for request stitching
        teacher_name = tts.extract_voice_from_filename(input_path)

        # Get previous request IDs if same teacher and batch context available
        previous_request_ids = None
        if batch_context and teacher_name:
            previous_request_ids = batch_context.get_previous_ids(teacher_name)
            if previous_request_ids:
                logger.info(f"Using {len(previous_request_ids)} previous request IDs for {teacher_name}")

        # Perform text-to-speech with request stitching
        success, request_id = tts.text_to_speech_file(
            input_path, output_path,
            voice_settings=options.get('voice_settings'),
            previous_request_ids=previous_request_ids
        )

        # Update batch context with new request ID
        if batch_context and teacher_name and request_id:
            batch_context.add_request(teacher_name, request_id)

        if success:
            return ProcessingResult(
                status=ProcessingStatus.COMPLETED,
                input_path=input_path,
                output_path=output_path,
                message=f"Generated speech for {input_path.name}",
                metadata={
                    "operation": "synthesize",
                    "teacher": teacher_name,
                    "request_id": request_id,
                    "used_stitching": bool(previous_request_ids)
                }
            )
        else:
            raise RuntimeError("Text-to-speech service returned failure")

class ConversionProcessor(FileProcessor):
    """
    Processor for document conversion operations.
    
    Handles PPTX to PDF conversion with format validation
    and ConvertAPI service integration.
    """
    
    def get_processor_type(self) -> ProcessorType:
        return ProcessorType.CONVERSION
    
    def get_required_service_type(self) -> ServiceType:
        return ServiceType.CONVERTAPI
    
    def _process_file_implementation(self,
                                   input_path: Path,
                                   output_path: Path,
                                   output_format: str = "pdf",
                                   **options) -> ProcessingResult:
        """
        Implement document conversion.
        
        Args:
            input_path: Input file path
            output_path: Output file path  
            output_format: Target format (e.g., 'pdf', 'png')
            **options: Conversion-specific options
            
        Returns:
            ProcessingResult with conversion details
        """
        try:
            # Validate output format
            allowed_formats = {'pdf', 'png', 'webp'}  # Standard PPTX conversion formats
            validated_format = validate_output_format(output_format, allowed_formats)
            
            # Determine converter service based on input type
            input_ext = get_file_extension(input_path, lowercase=True)
            
            if input_ext == '.pptx':
                from core.pptx_converter import PPTXConverterCore
                service_class = PPTXConverterCore
            else:
                raise ValueError(f"Unsupported file type for conversion: {input_ext}")
            
            # Create converter service
            converter = self.service_manager.get_convertapi_service(
                service_class,
                progress_callback=self.progress_reporter.report_progress
            )
            
            # Get group_elements option if provided (defaults to False)
            group_elements = options.get('group_elements', False)
            
            # Perform conversion based on format
            if validated_format == 'pdf':
                success = converter.convert_pptx_to_pdf(input_path, output_path)
            elif validated_format == 'png':
                result_files = converter.convert_pptx_to_png(input_path, output_path.parent, group_elements)
                success = len(result_files) > 0
            elif validated_format == 'webp':
                result_files = converter.convert_pptx_to_webp(input_path, output_path.parent, group_elements=group_elements)
                success = len(result_files) > 0
            else:
                raise ValueError(f"Unsupported output format: {validated_format}")
            
            if success:
                return ProcessingResult(
                    status=ProcessingStatus.COMPLETED,
                    input_path=input_path,
                    output_path=output_path,
                    message=f"Converted {input_path.name} to {validated_format}",
                    metadata={
                        "input_format": input_ext,
                        "output_format": validated_format
                    }
                )
            else:
                raise RuntimeError("Conversion service returned failure")
                
        except Exception as e:
            return self.error_handler.handle_error(
                e,
                f"converting {input_path.name}",
                input_path
            )

# Convenience functions for creating processors

def create_translation_processor(service_manager: ServiceManager,
                               progress_reporter: Optional[ProgressReporter] = None,
                               config: Optional[ProcessorConfig] = None) -> TranslationProcessor:
    """Create a translation processor with appropriate configuration"""
    if config is None:
        config = ProcessorConfig(
            allowed_extensions={'.txt', '.pptx'},
            max_file_size_mb=50.0
        )
    return TranslationProcessor(service_manager, progress_reporter, config)

def create_audio_processor(service_manager: ServiceManager,
                         progress_reporter: Optional[ProgressReporter] = None,
                         config: Optional[ProcessorConfig] = None) -> AudioProcessor:
    """Create an audio processor with appropriate configuration"""
    if config is None:
        config = ProcessorConfig(
            allowed_extensions={'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'},
            max_file_size_mb=100.0
        )
    return AudioProcessor(service_manager, progress_reporter, config)

def create_conversion_processor(service_manager: ServiceManager,
                              progress_reporter: Optional[ProgressReporter] = None,
                              config: Optional[ProcessorConfig] = None) -> ConversionProcessor:
    """Create a conversion processor with appropriate configuration"""
    if config is None:
        config = ProcessorConfig(
            allowed_extensions={'.pptx'},
            output_formats=['pdf', 'png'],
            max_file_size_mb=25.0
        )
    return ConversionProcessor(service_manager, progress_reporter, config)

# Factory function for creating processors by type

def create_processor(processor_type: ProcessorType,
                    service_manager: ServiceManager,
                    progress_reporter: Optional[ProgressReporter] = None,
                    config: Optional[ProcessorConfig] = None) -> BaseProcessor:
    """
    Factory function to create processors by type.
    
    Args:
        processor_type: Type of processor to create
        service_manager: Service manager instance
        progress_reporter: Progress reporter instance
        config: Processor configuration
        
    Returns:
        Appropriate processor instance
    """
    if processor_type == ProcessorType.TRANSLATION:
        return create_translation_processor(service_manager, progress_reporter, config)
    elif processor_type == ProcessorType.AUDIO:
        return create_audio_processor(service_manager, progress_reporter, config)
    elif processor_type == ProcessorType.CONVERSION:
        return create_conversion_processor(service_manager, progress_reporter, config)
    else:
        raise ValueError(f"Unknown processor type: {processor_type}")