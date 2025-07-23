"""
FastAPI server for Language Toolkit API
Provides REST endpoints for all language processing tools
"""

import asyncio
import json
import logging
import os
import queue
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
import subprocess
import time
import requests
import boto3
from botocore.exceptions import ClientError, BotoCoreError

import uvicorn
from dotenv import load_dotenv
from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form,
                     HTTPException, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field, validator

# Load environment variables from .env file
load_dotenv()

# Run migration if needed (before importing other modules)
try:
    import subprocess
    subprocess.run([sys.executable, "migrate_secret.py", "--auto"], check=False)
except Exception:
    pass  # Migration script might not exist or fail, continue anyway

# Import core functionality modules
from core.config import ConfigManager
from core.pptx_converter import PPTXConverterCore
from core.pptx_translation import PPTXTranslationCore
from core.s3_utils import S3ClientWrapper
from core.text_to_speech import TextToSpeechCore
from core.text_translation import TextTranslationCore
from core.transcription import AudioTranscriptionCore
from core.video_merger import VideoMergerCore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Language Toolkit API",
    description="API for document processing, translation, transcription, and video creation",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8280",
        "http://127.0.0.1:8280",
    ],  # Frontend dev servers
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Simple in-memory rate limiting
from collections import defaultdict
from datetime import datetime
import time

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.requests[client_id] = [req_time for req_time in self.requests[client_id] if req_time > minute_ago]

        # Check rate limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False

        # Record this request
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(requests_per_minute=60)

# Global task storage
active_tasks: Dict[str, Dict] = {}
config_manager = ConfigManager(use_project_api_keys=True)

# Authentication setup
security = OAuth2PasswordBearer(tokenUrl="token")

# -----------------------------
# JWT Auth configuration
# -----------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")  # Override in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# File upload configuration
# -----------------------------
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))  # 100MB default
MAX_PPTX_SIZE = int(os.getenv("MAX_PPTX_SIZE", str(50 * 1024 * 1024)))   # 50MB for PPTX
MAX_AUDIO_SIZE = int(os.getenv("MAX_AUDIO_SIZE", str(200 * 1024 * 1024))) # 200MB for audio
MAX_TEXT_SIZE = int(os.getenv("MAX_TEXT_SIZE", str(10 * 1024 * 1024)))    # 10MB for text

# Validation constants
# -----------------------------
# Load supported language codes from configuration file
def load_supported_languages():
    """Load supported languages from supported_languages.json"""
    try:
        with open("supported_languages.json", "r") as f:
            languages = json.load(f)
        source_langs = set(languages.get("source_languages", {}).keys())
        target_langs = set(languages.get("target_languages", {}).keys())
        return source_langs, target_langs
    except Exception as e:
        logger.error(f"Failed to load supported_languages.json: {e}")
        # Fallback to default languages if file not found
        source_langs = {
            "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hu", "id",
            "it", "ja", "lt", "lv", "nl", "pl", "pt", "ro", "ru", "sk", "sl", "sv",
            "tr", "uk", "zh"
        }
        target_langs = {
            "bg", "cs", "da", "de", "el", "en-gb", "en-us", "es", "et", "fi", "fr",
            "hu", "id", "it", "ja", "ko", "lt", "lv", "nl", "pl", "pt-br", "pt-pt",
            "ro", "ru", "sk", "sl", "sv", "tr", "uk", "zh"
        }
        return source_langs, target_langs

# Load language constants
VALID_SOURCE_LANGUAGES, VALID_TARGET_LANGUAGES = load_supported_languages()

# Supported file extensions
SUPPORTED_PPTX_EXTENSIONS = {".pptx"}
SUPPORTED_TEXT_EXTENSIONS = {".txt"}
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".mp4", ".mpga", ".mpeg", ".ogg", ".flac"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}
SUPPORTED_CONVERSION_FORMATS = {"pdf", "png", "webp"}

def load_client_credentials() -> Dict[str, str]:
    """Load allowed client_id -> client_secret mapping from client_credentials.json
    This avoids the need for a database while still supporting credential rotation.
    """
    credentials: Dict[str, str] = {}
    cred_file = Path(__file__).parent / "client_credentials.json"
    try:
        if cred_file.exists():
            with open(cred_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for entry in data.get("clients", []):
                    cid = entry.get("client_id")
                    csec = entry.get("client_secret")
                    if cid and csec:
                        credentials[cid] = csec
        else:
            logger.warning(f"Client credentials file not found: {cred_file}")
    except Exception as exc:
        logger.error(f"Failed to load client credentials: {exc}")
    return credentials

CLIENT_CREDENTIALS = load_client_credentials()

async def verify_token(token: str = Depends(security)) -> str:
    """Validate JWT access token and return the associated client_id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: Optional[str] = payload.get("sub")
        if client_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload", headers={"WWW-Authenticate": "Bearer"})

        # Apply rate limiting
        if not rate_limiter.is_allowed(client_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")

        return client_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})

async def run_tool_async(tool_class, task_id: str, input_files: List[Path],
                        output_dir: Path, **kwargs):
    """Run a core tool asynchronously"""
    try:
        # Update task status
        active_tasks[task_id]["status"] = "running"

        # Get API keys
        api_keys = config_manager.get_api_keys()

        # Progress callback
        def progress_callback(message: str):
            if "messages" in active_tasks[task_id]:
                active_tasks[task_id]["messages"].append(message)
            logger.info(f"Task {task_id}: {message}")

        # Initialize tool based on type
        if tool_class == TextTranslationCore:
            deepl_key = api_keys.get("deepl")
            if not deepl_key:
                raise ValueError("DeepL API key not configured")
            tool = TextTranslationCore(deepl_key, progress_callback)
        elif tool_class == AudioTranscriptionCore:
            openai_key = api_keys.get("openai")
            if not openai_key:
                raise ValueError("OpenAI API key not configured")
            tool = AudioTranscriptionCore(openai_key, progress_callback)
        elif tool_class == TextToSpeechCore:
            elevenlabs_key = api_keys.get("elevenlabs")
            if not elevenlabs_key:
                raise ValueError("ElevenLabs API key not configured")
            tool = TextToSpeechCore(elevenlabs_key, progress_callback)
        else:
            raise ValueError(f"Unsupported tool class: {tool_class}")

        # Run processing in thread
        def process_files():
            try:
                result_files = []

                for input_file in input_files:
                    if input_file.is_file():
                        if tool_class == TextTranslationCore:
                            # Text translation
                            output_file = output_dir / f"translated_{input_file.name}"
                            success = tool.translate_text_file(
                                input_file, output_file,
                                kwargs.get("source_lang"), kwargs.get("target_lang")
                            )
                            if success:
                                result_files.append(str(output_file))
                        elif tool_class == AudioTranscriptionCore:
                            # Audio transcription
                            output_file = output_dir / f"transcript_{input_file.stem}.txt"
                            success = tool.transcribe_audio_file(input_file, output_file)
                            if success:
                                result_files.append(str(output_file))
                        elif tool_class == TextToSpeechCore:
                            # Text to speech
                            output_file = output_dir / f"audio_{input_file.stem}.mp3"
                            success = tool.text_to_speech_file(input_file, output_file)
                            if success:
                                result_files.append(str(output_file))

                # Update task with results
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["result_files"] = result_files

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(e)

        # Run in thread
        thread = threading.Thread(target=process_files)
        thread.start()

        # Wait for completion
        while thread.is_alive():
            await asyncio.sleep(0.5)

        thread.join()

    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)

class TaskStatus(BaseModel):
    """Task status response model"""
    task_id: str
    status: str = Field(..., description="Task status: pending, running, completed, failed")
    progress: Optional[str] = None
    error: Optional[str] = None
    result_files: Optional[List[str]] = None
    manifest: Optional[Dict] = None
    source_lang: Optional[str] = None

class TranslationRequest(BaseModel):
    """PPTX translation request model"""
    source_lang: str = Field(..., description="Source language code (e.g., 'en')")
    target_lang: str = Field(..., description="Target language code (e.g., 'fr')")

class MultiTranslationRequest(BaseModel):
    """Multi-language translation request model"""
    source_lang: str = Field(..., description="Source language code (e.g., 'en')")
    target_langs: List[str] = Field(..., description="List of target language codes")

class ConversionRequest(BaseModel):
    """PPTX conversion request model"""
    output_format: str = Field(..., description="Output format: 'pdf' or 'png'")

    @validator('output_format')
    def validate_output_format_field(cls, v):
        """Validate output format against allowed formats"""
        allowed_formats = {'pdf', 'png', 'webp'}
        validate_output_format(v, allowed_formats)
        return v.lower().strip()

class TaskProgressQueue:
    """Thread-safe progress queue for tasks"""
    def __init__(self):
        self._queue = queue.Queue()
        self._messages = []

    def put(self, message: str):
        self._queue.put(message)
        self._messages.append(message)

    def get_all_messages(self) -> List[str]:
        # Drain the queue
        messages = []
        try:
            while True:
                messages.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        return self._messages + messages

def create_task_id() -> str:
    """Generate a unique task ID"""
    return str(uuid.uuid4())

def get_temp_dir() -> Path:
    """Create and return a temporary directory for file processing"""
    temp_dir = Path(tempfile.mkdtemp(prefix="language_toolkit_"))
    return temp_dir

def validate_s3_path(path: str) -> bool:
    """Validate S3 path to prevent directory traversal attacks"""
    # Check for path traversal attempts
    if ".." in path or path.startswith("/") or "\\" in path:
        return False

    # Check for suspicious patterns
    suspicious_patterns = ["~", "${", "$(", "`", "%", "&", "|", ";", "<", ">", "\n", "\r", "\0"]
    for pattern in suspicious_patterns:
        if pattern in path:
            return False

    # Ensure path components are reasonable
    parts = path.split("/")
    for part in parts:
        if len(part) > 255 or len(part) == 0:
            return False

    return True

def validate_file_size(file: UploadFile, file_type: str = "general") -> None:
    """
    Validate uploaded file size against configured limits.

    Args:
        file: The uploaded file to validate
        file_type: Type of file for specific size limits ('pptx', 'audio', 'text', 'general')

    Raises:
        HTTPException: If file size exceeds the limit
    """
    if not hasattr(file, 'size') or file.size is None:
        # Try to get size from file content if size attribute not available
        if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
            current_pos = file.file.tell()
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(current_pos)  # Return to original position
        else:
            # If we can't determine size, allow it to proceed (will be caught later if too large)
            logger.warning(f"Could not determine size for file: {file.filename}")
            return
    else:
        file_size = file.size

    # Determine size limit based on file type
    size_limits = {
        "pptx": MAX_PPTX_SIZE,
        "audio": MAX_AUDIO_SIZE,
        "text": MAX_TEXT_SIZE,
        "general": MAX_FILE_SIZE
    }

    max_size = size_limits.get(file_type, MAX_FILE_SIZE)

    if file_size > max_size:
        size_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File '{file.filename}' is too large ({actual_mb:.1f}MB). "
                   f"Maximum allowed size for {file_type} files is {size_mb:.1f}MB."
        )

    logger.info(f"File size validation passed: {file.filename} ({file_size} bytes)")

def get_file_type_from_filename(filename: str) -> str:
    """Determine file type category from filename for size validation."""
    if not filename:
        return "general"

    extension = Path(filename).suffix.lower()

    if extension == '.pptx':
        return "pptx"
    elif extension in ['.txt']:
        return "text"
    elif extension in ['.wav', '.mp3', '.m4a', '.webm', '.mp4', '.mpga', '.mpeg', '.ogg', '.flac']:
        return "audio"
    else:
        return "general"

def validate_language_code(language: str, is_target: bool = False) -> None:
    """
    Validate language code against supported languages.

    Args:
        language: Language code to validate
        is_target: Whether this is a target language (allows more variants)

    Raises:
        HTTPException: If language code is invalid
    """
    if not language or not isinstance(language, str):
        raise HTTPException(
            status_code=400,
            detail="Language code must be a non-empty string"
        )

    language = language.lower().strip()
    valid_languages = VALID_TARGET_LANGUAGES if is_target else VALID_SOURCE_LANGUAGES

    if language not in valid_languages:
        lang_type = "target" if is_target else "source"
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {lang_type} language code: '{language}'. "
                   f"Supported codes: {', '.join(sorted(valid_languages))}"
        )

def validate_file_extension(filename: str, allowed_extensions: set) -> None:
    """
    Validate file extension against allowed extensions.

    Args:
        filename: Name of the file to validate
        allowed_extensions: Set of allowed extensions (with dots)

    Raises:
        HTTPException: If file extension is not allowed
    """
    if not filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")

    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: '{extension}'. "
                   f"Supported formats: {', '.join(sorted(allowed_extensions))}"
        )

def validate_output_format(format_str: str, allowed_formats: set) -> None:
    """
    Validate output format against allowed formats.

    Args:
        format_str: Format string to validate
        allowed_formats: Set of allowed format strings

    Raises:
        HTTPException: If format is not allowed
    """
    if not format_str or not isinstance(format_str, str):
        raise HTTPException(status_code=400, detail="Output format must be a non-empty string")

    format_str = format_str.lower().strip()
    if format_str not in allowed_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid output format: '{format_str}'. "
                   f"Supported formats: {', '.join(sorted(allowed_formats))}"
        )

def validate_duration_per_slide(duration: Optional[float]) -> float:
    """
    Validate duration per slide parameter.

    Args:
        duration: Duration value to validate

    Returns:
        Validated duration value

    Raises:
        HTTPException: If duration is invalid
    """
    if duration is None:
        return 3.0  # Default value

    if not isinstance(duration, (int, float)):
        raise HTTPException(status_code=400, detail="Duration must be a number")

    if duration <= 0:
        raise HTTPException(status_code=400, detail="Duration must be greater than 0")

    if duration > 60:
        raise HTTPException(status_code=400, detail="Duration must be 60 seconds or less")

    return float(duration)

def cleanup_temp_dir(temp_dir: Path):
    """Clean up temporary directory"""
    try:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except Exception as e:
        logger.error(f"Error cleaning up temp dir {temp_dir}: {e}")

async def run_pptx_translation_async(task_id: str, input_files: List[Path],
                                   output_dir: Path, source_lang: str, target_lang: str):
    """Run PPTX translation asynchronously"""
    try:
        # Update task status
        active_tasks[task_id]["status"] = "running"

        # Get API key
        api_keys = config_manager.get_api_keys()
        deepl_key = api_keys.get("deepl")
        if not deepl_key:
            raise ValueError("DeepL API key not configured")

        # Progress callback
        def progress_callback(message: str):
            active_tasks[task_id]["messages"].append(message)
            logger.info(f"Task {task_id}: {message}")

        # Initialize PPTX translation core
        translator = PPTXTranslationCore(deepl_key, progress_callback)

        # Run processing in thread
        def process_files():
            try:
                result_files = []

                for input_file in input_files:
                    if input_file.is_file() and input_file.suffix.lower() == '.pptx':
                        progress_callback(f"Starting translation of {input_file.name}")
                        output_file = output_dir / f"translated_{input_file.name}"

                        # Check input file size and existence
                        progress_callback(f"Input file size: {input_file.stat().st_size} bytes")

                        success = translator.translate_pptx(input_file, output_file, source_lang, target_lang)

                        if success:
                            # Check output file was created and has content
                            if output_file.exists():
                                output_size = output_file.stat().st_size
                                progress_callback(f"Translation successful. Output file size: {output_size} bytes")
                                result_files.append(str(output_file))
                            else:
                                progress_callback(f"Error: Output file was not created: {output_file}")
                                raise RuntimeError(f"Translation claimed success but output file missing: {output_file}")
                        else:
                            progress_callback(f"Translation failed for {input_file.name}")
                            raise RuntimeError(f"Failed to translate {input_file.name}")

                # Update task with results
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["result_files"] = result_files

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(e)

        # Run in thread
        thread = threading.Thread(target=process_files)
        thread.start()

        # Wait for completion
        while thread.is_alive():
            await asyncio.sleep(0.5)

        thread.join()

    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)

async def run_pptx_conversion_async(task_id: str, input_files: List[Path],
                                   output_dir: Path, output_format: str):
    """Run PPTX to PDF/PNG conversion asynchronously"""
    try:
        # Update task status
        active_tasks[task_id]["status"] = "running"

        # Get API key
        api_keys = config_manager.get_api_keys()
        convertapi_key = api_keys.get("convertapi")
        if not convertapi_key:
            raise ValueError("ConvertAPI key not configured")

        # Progress callback
        def progress_callback(message: str):
            active_tasks[task_id]["messages"].append(message)
            logger.info(f"Task {task_id}: {message}")

        # Initialize PPTX converter core
        converter = PPTXConverterCore(convertapi_key, progress_callback)

        # Run processing in thread
        def process_files():
            try:
                result_files = []

                for input_file in input_files:
                    if input_file.is_file() and input_file.suffix.lower() == '.pptx':
                        if output_format.lower() == 'pdf':
                            output_file = output_dir / f"{input_file.stem}.pdf"
                            success = converter.convert_pptx_to_pdf(input_file, output_file)
                            if success:
                                result_files.append(str(output_file))
                        elif output_format.lower() == 'png':
                            png_files = converter.convert_pptx_to_png(input_file, output_dir)
                            result_files.extend(png_files)
                        elif output_format.lower() == 'webp':
                            webp_files = converter.convert_pptx_to_webp(input_file, output_dir)
                            result_files.extend(webp_files)
                        else:
                            raise ValueError(f"Unsupported output format: {output_format}")

                        if not result_files:
                            raise RuntimeError(f"Failed to convert {input_file.name}")

                # Update task with results
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["result_files"] = result_files

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(e)

        # Run in thread
        thread = threading.Thread(target=process_files)
        thread.start()

        # Wait for completion
        while thread.is_alive():
            await asyncio.sleep(0.5)

        thread.join()

    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)

async def run_video_merger_async(task_id: str, input_files: List[Path],
                                output_dir: Path, duration_per_slide: float = 3.0,
                                audio_file: Optional[Path] = None):
    """Run video merger asynchronously"""
    try:
        # Update task status
        active_tasks[task_id]["status"] = "running"

        # Progress callback
        def progress_callback(message: str):
            active_tasks[task_id]["messages"].append(message)
            logger.info(f"Task {task_id}: {message}")

        # Initialize video merger core
        merger = VideoMergerCore(progress_callback)

        # Run processing in thread
        def process_files():
            try:
                result_files = []

                # Check if we have image files or video files
                image_files = [f for f in input_files if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif']]
                video_files = [f for f in input_files if merger.validate_video_file(f)]

                if image_files:
                    # Create video from images
                    output_file = output_dir / "merged_video.mp4"

                    # Create temporary directory for images
                    temp_img_dir = output_dir / "temp_images"
                    temp_img_dir.mkdir(exist_ok=True)

                    # Copy images to temp directory (to ensure proper ordering)
                    for i, img_file in enumerate(image_files):
                        temp_img_path = temp_img_dir / f"image_{i:04d}{img_file.suffix}"
                        temp_img_path.write_bytes(img_file.read_bytes())

                    success = merger.create_video_from_files(
                        temp_img_dir, output_file, duration_per_slide, audio_file
                    )

                    # Clean up temp directory
                    import shutil
                    shutil.rmtree(temp_img_dir)

                    if success:
                        result_files.append(str(output_file))

                elif video_files:
                    # Merge videos
                    output_file = output_dir / "merged_video.mp4"
                    success = merger.merge_videos(video_files, output_file)
                    if success:
                        result_files.append(str(output_file))
                else:
                    raise ValueError("No valid image or video files found")

                if not result_files:
                    raise RuntimeError("Failed to create video")

                # Update task with results
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["result_files"] = result_files

            except Exception as e:
                logger.error(f"Task {task_id} failed: {e}")
                active_tasks[task_id]["status"] = "failed"
                active_tasks[task_id]["error"] = str(e)

        # Run in thread
        thread = threading.Thread(target=process_files)
        thread.start()

        # Wait for completion
        while thread.is_alive():
            await asyncio.sleep(0.5)

        thread.join()

    except Exception as e:
        logger.error(f"Failed to start task {task_id}: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)

@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with API information"""
    return {
        "message": "Language Toolkit API",
        "version": "1.0.0",
        "endpoints": {
            "translate_pptx": "/translate/pptx",
            "translate_text": "/translate/text",
            "transcribe_audio": "/transcribe/audio",
            "convert_pptx": "/convert/pptx",
            "text_to_speech": "/tts",
            "merge_video": "/video/merge",
            "task_status": "/tasks/{task_id}",
            "download_results": "/download/{task_id}",
            "download_single_file": "/download/{task_id}/{file_index}",
            "token": "/token",
            "list_tasks": "/tasks",
            "cleanup_task": "/tasks/{task_id}",
            "translate_pptx_s3": "/translate/pptx_s3",
            "transcribe_audio_s3": "/transcribe/audio_s3",
            "translate_text_s3": "/translate/text_s3",
            "translate_course_s3": "/translate/course_s3",
            "video_merge_tool_s3": "/video/merge_tool_s3"
        },
        "notes": {
            "single_file_download": "When a task has only one result file, /download/{task_id} returns the file directly",
            "multiple_files_download": "When a task has multiple result files, /download/{task_id} returns a ZIP archive",
            "individual_file_download": "Use /download/{task_id}/{file_index} to download a specific file (0-based index)"
        }
    }

# Health Check Infrastructure
# -----------------------------
class HealthStatus:
    """Health status constants"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthCache:
    """Simple cache for health check results"""
    def __init__(self, ttl_seconds: int = 30):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> Optional[dict]:
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return result
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: dict):
        self.cache[key] = (value, time.time())

# Global health cache instance
health_cache = HealthCache(ttl_seconds=30)

async def check_dependency_with_timeout(check_func: Callable, timeout: float = 5.0) -> dict:
    """Run a health check function with timeout"""
    try:
        # Create a task that can be cancelled
        task = asyncio.create_task(asyncio.to_thread(check_func))
        result = await asyncio.wait_for(task, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"Health check timed out after {timeout}s"
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": str(e)
        }

def check_s3_health() -> dict:
    """Check S3 connectivity and accessibility"""
    try:
        start_time = time.time()

        # Get S3 client
        s3_client = boto3.client('s3')

        # List buckets to test connectivity
        response = s3_client.list_buckets()

        latency_ms = int((time.time() - start_time) * 1000)

        return {
            "status": HealthStatus.HEALTHY,
            "latency_ms": latency_ms,
            "buckets_accessible": len(response.get('Buckets', []))
        }
    except (ClientError, BotoCoreError) as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"S3 error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"Unexpected error: {str(e)}"
        }

def check_deepl_health() -> dict:
    """Check DeepL API key validity and quota"""
    try:
        api_keys = config_manager.get_api_keys()
        deepl_key = api_keys.get("deepl")

        if not deepl_key:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "DeepL API key not configured"
            }

        # Check usage and limits
        headers = {"Authorization": f"DeepL-Auth-Key {deepl_key}"}
        response = requests.get("https://api-free.deepl.com/v2/usage", headers=headers, timeout=3)

        if response.status_code == 200:
            usage_data = response.json()
            character_count = usage_data.get("character_count", 0)
            character_limit = usage_data.get("character_limit", 0)

            remaining = character_limit - character_count if character_limit > 0 else None

            # Consider degraded if less than 10% quota remaining
            if remaining is not None and character_limit > 0:
                usage_percent = (character_count / character_limit) * 100
                status = HealthStatus.DEGRADED if usage_percent > 90 else HealthStatus.HEALTHY
            else:
                status = HealthStatus.HEALTHY

            return {
                "status": status,
                "quota_used": character_count,
                "quota_limit": character_limit,
                "quota_remaining": remaining
            }
        else:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"DeepL API error: {response.status_code}"
            }
    except requests.RequestException as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"DeepL request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"DeepL check error: {str(e)}"
        }

def check_openai_health() -> dict:
    """Check OpenAI API key validity"""
    try:
        api_keys = config_manager.get_api_keys()
        openai_key = api_keys.get("openai")

        if not openai_key:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "OpenAI API key not configured"
            }

        # Test with a simple models list request
        headers = {"Authorization": f"Bearer {openai_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=3)

        if response.status_code == 200:
            return {"status": HealthStatus.HEALTHY}
        elif response.status_code == 401:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "Invalid OpenAI API key"
            }
        elif response.status_code == 429:
            return {
                "status": HealthStatus.DEGRADED,
                "error": "OpenAI rate limited"
            }
        else:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"OpenAI API error: {response.status_code}"
            }
    except requests.RequestException as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"OpenAI request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"OpenAI check error: {str(e)}"
        }

def check_elevenlabs_health() -> dict:
    """Check ElevenLabs API key validity"""
    try:
        api_keys = config_manager.get_api_keys()
        elevenlabs_key = api_keys.get("elevenlabs")

        if not elevenlabs_key:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "ElevenLabs API key not configured"
            }

        # Test with user info endpoint
        headers = {"xi-api-key": elevenlabs_key}
        response = requests.get("https://api.elevenlabs.io/v1/user", headers=headers, timeout=3)

        if response.status_code == 200:
            user_data = response.json()
            subscription = user_data.get("subscription", {})
            quota_used = subscription.get("character_count", 0)
            quota_limit = subscription.get("character_limit", 0)

            remaining = quota_limit - quota_used if quota_limit > 0 else None

            # Consider degraded if less than 10% quota remaining
            if remaining is not None and quota_limit > 0:
                usage_percent = (quota_used / quota_limit) * 100
                status = HealthStatus.DEGRADED if usage_percent > 90 else HealthStatus.HEALTHY
            else:
                status = HealthStatus.HEALTHY

            return {
                "status": status,
                "quota_used": quota_used,
                "quota_limit": quota_limit,
                "quota_remaining": remaining
            }
        elif response.status_code == 401:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "Invalid ElevenLabs API key"
            }
        elif response.status_code == 429:
            return {
                "status": HealthStatus.DEGRADED,
                "error": "ElevenLabs rate limited"
            }
        else:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"ElevenLabs API error: {response.status_code}"
            }
    except requests.RequestException as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"ElevenLabs request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"ElevenLabs check error: {str(e)}"
        }

def check_convertapi_health() -> dict:
    """Check ConvertAPI key validity"""
    try:
        api_keys = config_manager.get_api_keys()
        convertapi_key = api_keys.get("convertapi")

        if not convertapi_key:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "ConvertAPI key not configured"
            }

        # Test with a simple user info request
        response = requests.get(f"https://v2.convertapi.com/user?Secret={convertapi_key}", timeout=3)

        if response.status_code == 200:
            user_data = response.json()
            seconds_left = user_data.get("SecondsLeft", 0)

            # Consider degraded if less than 100 seconds remaining
            status = HealthStatus.DEGRADED if seconds_left < 100 else HealthStatus.HEALTHY

            return {
                "status": status,
                "seconds_remaining": seconds_left
            }
        elif response.status_code == 401:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": "Invalid ConvertAPI key"
            }
        else:
            return {
                "status": HealthStatus.UNHEALTHY,
                "error": f"ConvertAPI error: {response.status_code}"
            }
    except requests.RequestException as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"ConvertAPI request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "error": f"ConvertAPI check error: {str(e)}"
        }

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Enhanced health check endpoint with dependency monitoring"""

    # Check cache first
    cached_result = health_cache.get("full_health")
    if cached_result:
        return cached_result

    start_time = time.time()

    # Define dependency checks
    dependency_checks = {
        "s3": check_s3_health,
        "deepl": check_deepl_health,
        "openai": check_openai_health,
        "elevenlabs": check_elevenlabs_health,
        "convertapi": check_convertapi_health
    }

    # Run all dependency checks concurrently with timeout
    dependencies = {}
    check_tasks = []

    for service_name, check_func in dependency_checks.items():
        task = check_dependency_with_timeout(check_func, timeout=3.0)
        check_tasks.append((service_name, task))

    # Wait for all checks to complete
    for service_name, task in check_tasks:
        try:
            result = await task
            dependencies[service_name] = result
        except Exception as e:
            dependencies[service_name] = {
                "status": HealthStatus.UNHEALTHY,
                "error": f"Check failed: {str(e)}"
            }

    # Determine overall status
    overall_status = HealthStatus.HEALTHY
    unhealthy_count = 0
    degraded_count = 0

    for service_name, result in dependencies.items():
        if result["status"] == HealthStatus.UNHEALTHY:
            unhealthy_count += 1
        elif result["status"] == HealthStatus.DEGRADED:
            degraded_count += 1

    # Overall status logic
    if unhealthy_count > 0:
        overall_status = HealthStatus.DEGRADED if unhealthy_count <= 2 else HealthStatus.UNHEALTHY
    elif degraded_count > 0:
        overall_status = HealthStatus.DEGRADED

    total_time = int((time.time() - start_time) * 1000)

    result = {
        "status": overall_status,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "check_duration_ms": total_time,
        "dependencies": dependencies
    }

    # Cache the result
    health_cache.set("full_health", result)

    return result

@app.post("/token")
async def generate_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Exchange client_id / client_secret for a short-lived JWT access token."""
    client_id = form_data.username
    client_secret = form_data.password

    # Validate credentials if any configured; allow all if list is empty
    if CLIENT_CREDENTIALS:
        expected_secret = CLIENT_CREDENTIALS.get(client_id)
        if expected_secret != client_secret:
            raise HTTPException(status_code=401, detail="Invalid client credentials")

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": client_id, "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.post("/translate/pptx", response_model=TaskStatus)
async def translate_pptx(
    background_tasks: BackgroundTasks,
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Translate PPTX files from source to target language"""
    # Validate parameters
    validate_language_code(source_lang, is_target=False)
    validate_language_code(target_lang, is_target=True)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        # Validate file extension
        validate_file_extension(file.filename, SUPPORTED_PPTX_EXTENSIONS)

        # Validate file size
        validate_file_size(file, "pptx")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Initialize task
    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": input_files,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": source_lang
    }

    # Start background task
    background_tasks.add_task(
        run_pptx_translation_async,
        task_id,
        input_files,
        output_dir,
        source_lang,
        target_lang
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=source_lang)

@app.post("/translate/text", response_model=TaskStatus)
async def translate_text(
    background_tasks: BackgroundTasks,
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Translate text files from source to target language"""
    # Validate parameters
    validate_language_code(source_lang, is_target=False)
    validate_language_code(target_lang, is_target=True)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        # Validate file extension
        validate_file_extension(file.filename, SUPPORTED_TEXT_EXTENSIONS)

        # Validate file size
        validate_file_size(file, "text")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Initialize task
    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": input_files,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": source_lang
    }

    # Start background task
    background_tasks.add_task(
        run_tool_async,
        TextTranslationCore,
        task_id,
        input_files,
        output_dir,
        source_lang=source_lang,
        target_lang=target_lang
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=source_lang)

@app.post("/transcribe/audio", response_model=TaskStatus)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Transcribe audio files to text"""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []

    for file in files:
        # Validate file extension
        validate_file_extension(file.filename, SUPPORTED_AUDIO_EXTENSIONS)

        # Validate file size
        validate_file_size(file, "audio")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Initialize task
    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": input_files,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": None # Audio transcription doesn't have a source language
    }

    # Start background task
    background_tasks.add_task(
        run_tool_async,
        AudioTranscriptionCore,
        task_id,
        input_files,
        output_dir
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=None)

@app.post("/convert/pptx", response_model=TaskStatus)
async def convert_pptx(
    background_tasks: BackgroundTasks,
    output_format: str = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Convert PPTX files to PDF, PNG, or WEBP"""
    # Validate parameters
    validate_output_format(output_format, SUPPORTED_CONVERSION_FORMATS)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        # Validate file extension
        validate_file_extension(file.filename, SUPPORTED_PPTX_EXTENSIONS)

        # Validate file size
        validate_file_size(file, "pptx")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Initialize task
    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": input_files,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": None # Conversion doesn't have a source language
    }

    # Start background task
    background_tasks.add_task(
        run_pptx_conversion_async,
        task_id,
        input_files,
        output_dir,
        output_format
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=None)

@app.post("/tts", response_model=TaskStatus)
async def text_to_speech(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Convert text files to speech"""
    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        # Validate file extension
        validate_file_extension(file.filename, ['.txt'])

        # Validate file size
        validate_file_size(file, "text")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Initialize task
    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": input_files,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": None # TTS doesn't have a source language
    }

    # Start background task
    background_tasks.add_task(
        run_tool_async,
        TextToSpeechCore,
        task_id,
        input_files,
        output_dir
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=None)

@app.post("/video/merge", response_model=TaskStatus)
async def merge_video(
    background_tasks: BackgroundTasks,
    duration_per_slide: Optional[float] = Form(3.0),
    files: List[UploadFile] = File(...),
    audio_file: Optional[UploadFile] = File(None),
    token: str = Depends(verify_token)
):
    """Create video from images or merge video files"""
    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        # Validate file extension - accept both image and video files
        allowed_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif',
                            '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
        validate_file_extension(file.filename, allowed_extensions)

        # Validate file size (use general limit for mixed media)
        validate_file_size(file, "general")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Save audio file if provided
    audio_path = None
    if audio_file and audio_file.filename:
        # Validate audio file extension
        audio_extensions = ['.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg']
        validate_file_extension(audio_file.filename, audio_extensions)

        # Validate audio file size
        validate_file_size(audio_file, "audio")

        audio_path = input_dir / audio_file.filename
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)

    # Initialize task
    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": input_files,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": None # Video merger doesn't have a source language
    }

    # Start background task
    background_tasks.add_task(
        run_video_merger_async,
        task_id,
        input_files,
        output_dir,
        duration_per_slide,
        audio_path
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=None)

@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str, token: str = Depends(verify_token)):
    """Get the status of a specific task"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress"),
        error=task.get("error"),
        result_files=task.get("result_files"),
        manifest=task.get("manifest"),
        source_lang=task.get("source_lang")
    )

@app.get("/download/{task_id}")
async def download_results(task_id: str, token: str = Depends(verify_token)):
    """Download the results of a completed task"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    result_files = task.get("result_files", [])
    if not result_files:
        raise HTTPException(status_code=404, detail="No result files found")

    logger.info(f"Download request for task {task_id}: {len(result_files)} files found")
    logger.info(f"Result files: {result_files}")

    # If single file, return it directly
    if len(result_files) == 1:
        file_path = Path(result_files[0])
        logger.info(f"Single file download: {file_path}")
        logger.info(f"File exists: {file_path.exists()}")
        logger.info(f"File size: {file_path.stat().st_size if file_path.exists() else 'N/A'} bytes")
        logger.info(f"File absolute path: {file_path.absolute()}")

        if file_path.exists() and file_path.is_file():
            # Determine media type based on file extension
            media_type = 'application/octet-stream'
            if file_path.suffix.lower() == '.pdf':
                media_type = 'application/pdf'
            elif file_path.suffix.lower() in ['.pptx', '.ppt']:
                media_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            elif file_path.suffix.lower() == '.txt':
                media_type = 'text/plain'
            elif file_path.suffix.lower() == '.mp3':
                media_type = 'audio/mpeg'
            elif file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                media_type = f'image/{file_path.suffix.lower().lstrip(".")}'

            logger.info(f"Returning single file: {file_path.name} with media type: {media_type}")
            return FileResponse(
                path=str(file_path),
                filename=file_path.name,
                media_type=media_type
            )
        else:
            logger.error(f"Single file not found or not a file: {file_path}")
            logger.error(f"Path exists: {file_path.exists()}, Is file: {file_path.is_file() if file_path.exists() else 'N/A'}")
            # Fall through to ZIP creation to see if that works

    # Multiple files: create zip archive
    logger.info(f"Creating ZIP archive for {len(result_files)} files")
    import io
    import zipfile

    zip_buffer = io.BytesIO()
    files_added = 0
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path_str in result_files:
            file_path = Path(file_path_str)
            logger.info(f"Processing file for ZIP: {file_path}, exists: {file_path.exists()}")
            if file_path.exists() and file_path.is_file():
                zip_file.write(file_path, file_path.name)
                files_added += 1
                logger.info(f"Added to ZIP: {file_path.name}")

    logger.info(f"ZIP created with {files_added} files, buffer size: {zip_buffer.tell()} bytes")
    zip_buffer.seek(0)

    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=results_{task_id}.zip"}
    )

@app.get("/download/{task_id}/{file_index}")
async def download_single_file(task_id: str, file_index: int, token: str = Depends(verify_token)):
    """Download a specific file from a completed task by index"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    result_files = task.get("result_files", [])
    if not result_files:
        raise HTTPException(status_code=404, detail="No result files found")

    if file_index < 0 or file_index >= len(result_files):
        raise HTTPException(status_code=400, detail=f"Invalid file index. Must be 0-{len(result_files)-1}")

    file_path = Path(result_files[file_index])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Determine media type based on file extension
    media_type = 'application/octet-stream'
    if file_path.suffix.lower() == '.pdf':
        media_type = 'application/pdf'
    elif file_path.suffix.lower() in ['.pptx', '.ppt']:
        media_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    elif file_path.suffix.lower() == '.txt':
        media_type = 'text/plain'
    elif file_path.suffix.lower() == '.mp3':
        media_type = 'audio/mpeg'
    elif file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
        media_type = f'image/{file_path.suffix.lower().lstrip(".")}'

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type
    )

@app.delete("/tasks/{task_id}")
async def cleanup_task(task_id: str, token: str = Depends(verify_token)):
    """Clean up a task and its temporary files"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    temp_dir = task.get("temp_dir")

    if temp_dir:
        cleanup_temp_dir(Path(temp_dir))

    del active_tasks[task_id]

    return {"message": f"Task {task_id} cleaned up successfully"}

@app.get("/tasks")
async def list_tasks(token: str = Depends(verify_token)):
    """List all active tasks"""
    return {
        "tasks": [
            {
                "task_id": task_id,
                "status": task["status"],
                "progress": task.get("progress"),
                "error": task.get("error"),
                "result_files": task.get("result_files"),
                "manifest": task.get("manifest"),
                "source_lang": task.get("source_lang")
            }
            for task_id, task in active_tasks.items()
        ]
    }

# --------------------------------------
# S3 Request Models
# --------------------------------------
class PPTXS3Request(BaseModel):
    """Request model for translating PPTX files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input PPTX files")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for translated files")
    source_lang: str = Field(..., description="Source language code (e.g., 'en')")
    target_lang: str = Field(..., description="Target language code (e.g., 'fr')")

    @validator('input_keys')
    def validate_input_keys(cls, v):
        if not v or len(v) == 0:
            raise ValueError("input_keys cannot be empty")
        for key in v:
            if not key or not isinstance(key, str):
                raise ValueError("Each input key must be a non-empty string")
        return v

    @validator('source_lang')
    def validate_source_lang(cls, v):
        if v.lower().strip() not in VALID_SOURCE_LANGUAGES:
            raise ValueError(f"Invalid source language: {v}. Supported: {', '.join(sorted(VALID_SOURCE_LANGUAGES))}")
        return v.lower().strip()

    @validator('target_lang')
    def validate_target_lang(cls, v):
        if v.lower().strip() not in VALID_TARGET_LANGUAGES:
            raise ValueError(f"Invalid target language: {v}. Supported: {', '.join(sorted(VALID_TARGET_LANGUAGES))}")
        return v.lower().strip()


class AudioS3Request(BaseModel):
    """Request model for transcribing audio files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input audio files")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for transcription results")

    @validator('input_keys')
    def validate_input_keys(cls, v):
        if not v or len(v) == 0:
            raise ValueError("input_keys cannot be empty")
        for key in v:
            if not key or not isinstance(key, str):
                raise ValueError("Each input key must be a non-empty string")
        return v

# New request model for translating text files stored in S3
class TextS3Request(BaseModel):
    """Request model for translating text files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input text files (.txt)")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for translated files")
    source_lang: str = Field(..., description="Source language code (e.g., 'en')")
    target_lang: str = Field(..., description="Target language code (e.g., 'fr')")

    @validator('input_keys')
    def validate_input_keys(cls, v):
        if not v or len(v) == 0:
            raise ValueError("input_keys cannot be empty")
        for key in v:
            if not key or not isinstance(key, str):
                raise ValueError("Each input key must be a non-empty string")
        return v

    @validator('source_lang')
    def validate_source_lang(cls, v):
        if v.lower().strip() not in VALID_SOURCE_LANGUAGES:
            raise ValueError(f"Invalid source language: {v}. Supported: {', '.join(sorted(VALID_SOURCE_LANGUAGES))}")
        return v.lower().strip()

    @validator('target_lang')
    def validate_target_lang(cls, v):
        if v.lower().strip() not in VALID_TARGET_LANGUAGES:
            raise ValueError(f"Invalid target language: {v}. Supported: {', '.join(sorted(VALID_TARGET_LANGUAGES))}")
        return v.lower().strip()

# --------------------------------------
# Course Translation S3 Request
# --------------------------------------

class CourseS3Request(BaseModel):
    """Request model for translating all PPTX & TXT of a course from S3."""
    course_id: str = Field(..., description="Unique identifier of the course")
    source_lang: str = Field(..., description="Language currently present in S3")
    target_langs: List[str] = Field(..., description="List of target language codes")
    output_prefix: Optional[str] = Field(None, description="Optional root prefix for translated course (defaults to original 'contribute/')")
    use_english: bool = Field(False, description="If true, use already-translated English version as source instead of original language")

    @validator('course_id')
    def validate_course_id(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("course_id must be a non-empty string")
        return v.strip()

    @validator('source_lang')
    def validate_source_lang(cls, v):
        if v.lower().strip() not in VALID_SOURCE_LANGUAGES:
            raise ValueError(f"Invalid source language: {v}. Supported: {', '.join(sorted(VALID_SOURCE_LANGUAGES))}")
        return v.lower().strip()

    @validator('target_langs')
    def validate_target_langs(cls, v):
        if not v or len(v) == 0:
            raise ValueError("target_langs cannot be empty")
        for lang in v:
            if lang.lower().strip() not in VALID_TARGET_LANGUAGES:
                raise ValueError(f"Invalid target language: {lang}. Supported: {', '.join(sorted(VALID_TARGET_LANGUAGES))}")
        return [lang.lower().strip() for lang in v]

class TTSS3Request(BaseModel):
    """Request model for generating speech from TXT files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input text files (.txt)")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for generated audio files")

    @validator('input_keys')
    def validate_input_keys(cls, v):
        if not v or len(v) == 0:
            raise ValueError("input_keys cannot be empty")
        for key in v:
            if not key or not isinstance(key, str):
                raise ValueError("Each input key must be a non-empty string")
        return v

# -------------------------------------------------------------------
# New request model for direct text-to-speech with S3 upload (no TXT).
# -------------------------------------------------------------------

class ProfessorInfo(BaseModel):
    """Professor information for voice matching."""
    id: str = Field(..., description="Professor ID")
    name: str = Field(..., description="Professor name")
    is_coordinator: bool = Field(..., description="Whether this professor is the course coordinator")

class TTSTextRequest(BaseModel):
    """Request body for generating speech from a raw text string and uploading the result to S3."""

    text: str = Field(..., description="Text content to convert to speech")
    output_key: str = Field(..., description="Destination S3 key (path + filename) for the generated MP3, e.g. 'audio/course/00.mp3'")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice_id to use (optional)")
    professors: Optional[List[ProfessorInfo]] = Field(None, description="List of professors for voice matching (used if voice_id not provided)")
    # NEW: allow a simple string field when only a single professor name is supplied by the client
    professor: Optional[str] = Field(None, description="Single professor name used to select voice (fallback when 'professors' list is not provided)")

# --------------------------------------
# Background runners for S3 workflows
# --------------------------------------
async def run_pptx_translation_s3_async(task_id: str, input_keys: List[str], output_prefix: Optional[str],
                                       output_dir: Path, source_lang: str, target_lang: str):
    """Download PPTX from S3, translate, upload results back to S3."""
    try:
        active_tasks[task_id]["status"] = "running"
        api_keys = config_manager.get_api_keys()
        deepl_key = api_keys.get("deepl")
        if not deepl_key:
            raise ValueError("DeepL API key not configured")

        # S3 client
        s3 = S3ClientWrapper()

        def progress_callback(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        # Download input files
        temp_input_dir = output_dir.parent / "input"
        input_files = s3.download_files(input_keys, temp_input_dir)

        # Translator
        translator = PPTXTranslationCore(deepl_key, progress_callback)
        result_local_paths: List[Path] = []

        for i, input_file in enumerate(input_files):
            if input_file.suffix.lower() != ".pptx":
                raise ValueError(f"Unsupported file type {input_file}")

            progress_callback(f"Starting translation of {input_file.name}")
            output_file = output_dir / f"translated_{input_file.name}"

            # Check input file size and existence
            progress_callback(f"Input file size: {input_file.stat().st_size} bytes")

            success = translator.translate_pptx(input_file, output_file, source_lang, target_lang)

            if success:
                # Check output file was created and has content
                if output_file.exists():
                    output_size = output_file.stat().st_size
                    progress_callback(f"Translation successful. Output file size: {output_size} bytes")
                    result_local_paths.append(output_file)
                else:
                    progress_callback(f"Error: Output file was not created: {output_file}")
                    raise RuntimeError(f"Translation claimed success but output file missing: {output_file}")
            else:
                progress_callback(f"Translation failed for {input_file.name}")
                raise RuntimeError(f"Failed to translate {input_file.name}")

        # Upload results using original key structure
        result_keys = s3.upload_files_with_mapping(result_local_paths, input_keys, output_prefix)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = result_keys

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)


async def run_audio_transcription_s3_async(task_id: str, input_keys: List[str], output_prefix: Optional[str],
                                          output_dir: Path):
    """Download audio from S3, transcribe, upload results back to S3."""
    try:
        active_tasks[task_id]["status"] = "running"
        api_keys = config_manager.get_api_keys()
        openai_key = api_keys.get("openai")
        if not openai_key:
            raise ValueError("OpenAI API key not configured")

        s3 = S3ClientWrapper()

        def progress_callback(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        temp_input_dir = output_dir.parent / "input"
        input_files = s3.download_files(input_keys, temp_input_dir)

        transcriber = AudioTranscriptionCore(openai_key, progress_callback)
        result_local_paths: List[Path] = []

        for i, input_file in enumerate(input_files):
            if not transcriber.validate_audio_file(input_file):
                raise ValueError(f"Unsupported audio format: {input_file.name}")
            output_file = output_dir / f"transcript_{input_file.stem}.txt"
            success = transcriber.transcribe_audio(input_file, output_file)
            if success:
                result_local_paths.append(output_file)
            else:
                raise RuntimeError(f"Failed to transcribe {input_file.name}")

        # Upload results using original key structure
        result_keys = s3.upload_files_with_mapping(result_local_paths, input_keys, output_prefix)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = result_keys

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)

# --------------------------------------
# Background runner for Course Translation (TXT + PPTX) from S3
# --------------------------------------

async def run_course_translation_s3_async(task_id: str, course_id: str, source_lang: str, target_langs: List[str],
                                         output_prefix: Optional[str], temp_dir: Path):
    """Translate all .pptx and .txt for given course and upload results back preserving structure."""
    try:
        active_tasks[task_id]["status"] = "running"

        api_keys = config_manager.get_api_keys()
        deepl_key = api_keys.get("deepl")
        if not deepl_key:
            raise ValueError("DeepL API key not configured")

        s3 = S3ClientWrapper()

        source_prefix = f"contribute/{course_id}/{source_lang}/"

        def progress(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        # List all pptx & txt keys under source_prefix
        keys = [k for k in s3.list_files(source_prefix, extensions=[".pptx", ".txt"]) if not Path(k).name.startswith('.')]
        if not keys:
            raise RuntimeError(f"No .pptx or .txt files found under {source_prefix}")

        progress(f"Found {len(keys)} files to process")

        # Prepare translators
        pptx_translator = PPTXTranslationCore(deepl_key, progress)
        text_translator = TextTranslationCore(deepl_key, progress)

        manifest: Dict[str, Any] = {}

        def insert_manifest(path_parts: List[str], value: str):
            node = manifest
            for part in path_parts[:-1]:
                node = node.setdefault(part, {})
            node[path_parts[-1]] = value

        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Build mapping from TXT filenames to slide_id
        import shutil
        import uuid
        slide_id_cache: Dict[Tuple[str, str, str], str] = {}  # (part_id, chapter_id, stem) -> uuid
        for key in keys:
            if key.lower().endswith('.txt') and not Path(key).name.startswith('.'):
                rel = "/".join(Path(key).parts[3:])
                parts = rel.split('/')  # part_id/chapter_id/text/filename
                if len(parts) == 4 and parts[2] == 'text':
                    part_id, chapter_id, _, filename = parts
                    stem = Path(filename).stem
                    slide_id_cache.setdefault((part_id, chapter_id, stem), uuid.uuid4().hex)

        # Download all files
        local_files = s3.download_files(keys, input_dir)
        key_to_local = dict(zip(keys, local_files))


        # -----------------------------------------------------------
        # Organise files by (part_id, chapter_id)
        # -----------------------------------------------------------

        from collections import defaultdict

        # Data structures
        chapter_txts_split: Dict[Tuple[str, str], Dict[str, Tuple[str, Path]]] = defaultdict(dict)
        # (part,chap) -> {slide_id: (stem, path)}
        chapter_txts_unsplit: Dict[Tuple[str, str], List[Tuple[str, str, Path]]] = defaultdict(list)
        # (part,chap) -> list(stem, slide_id, path)  slide_id generated later

        chapter_pptx_unsplit: Dict[Tuple[str, str], Path] = {}
        chapter_pptx_split: Dict[Tuple[str, str], Dict[str, Path]] = defaultdict(dict)  # slide_id -> path

        for src_key, local_path in key_to_local.items():
            if Path(src_key).name.startswith('.'):
                continue

            rel = "/".join(Path(src_key).parts[3:])
            parts = rel.split('/')
            if len(parts) < 4:
                continue
            part_id, chapter_id, folder_type, filename = parts[0], parts[1], parts[2], parts[3]

            # Determine structure
            if len(parts) == 5:
                # Already split path
                slide_id = parts[2]
                folder_split = parts[3]
                filename_split = parts[4]
                if folder_split == 'text':
                    stem = Path(filename_split).stem
                    chapter_txts_split[(part_id, chapter_id)][slide_id] = (stem, local_path)
                elif folder_split == 'pptx' and filename_split.lower().endswith('.pptx'):
                    chapter_pptx_split[(part_id, chapter_id)][slide_id] = local_path
            else:  # len(parts)==4  unsplit original structure
                if folder_type == 'text':
                    stem = Path(filename).stem
                    slide_id = slide_id_cache.setdefault((part_id, chapter_id, stem), uuid.uuid4().hex)
                    chapter_txts_unsplit[(part_id, chapter_id)].append((stem, slide_id, local_path))
                elif folder_type == 'pptx' and filename.lower().endswith('.pptx'):
                    chapter_pptx_unsplit[(part_id, chapter_id)] = local_path

        # -----------------------------------------------------------
        # Process per chapter & per target language
        # -----------------------------------------------------------

        from core.pptx_utils import split_pptx_to_single_slides

        def deepl_target(code: str) -> str:
            """Map target language code for DeepL API to required variants (e.g., en -> en-us, pt -> pt-pt)."""
            code_lower = code.lower()
            if code_lower == 'en':
                return 'en-us'
            if code_lower == 'pt':
                return 'pt-pt'
            return code

        for (part_id, chapter_id), pptx_path in chapter_pptx_unsplit.items():
            txt_entries = sorted(chapter_txts_unsplit.get((part_id, chapter_id), []), key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
            if not txt_entries:
                progress(f"No TXT files for chapter {part_id}/{chapter_id}, skipping PPTX")
                continue

            stems = [stem for stem, _, _ in txt_entries]

            for target_lang in target_langs:
                # Translate full pptx once per target language per chapter
                translated_full = output_dir / f"translated_{target_lang}_{part_id}_{chapter_id}.pptx"
                success = pptx_translator.translate_pptx(pptx_path, translated_full, source_lang, deepl_target(target_lang))
                if not success:
                    raise RuntimeError(f"Failed to translate PPTX {pptx_path} to {target_lang}")

                # Split into slides with filenames matching stems + .pptx
                slide_filenames = [f"{stem}.pptx" for stem in stems]
                split_out_dir = output_dir / "slides_split"
                split_out_dir.mkdir(parents=True, exist_ok=True)

                slide_paths = split_pptx_to_single_slides(translated_full, split_out_dir, slide_filenames)

                for (stem, slide_id, _), slide_path in zip(txt_entries, slide_paths):
                    # Target key
                    target_rel_key = f"{part_id}/{chapter_id}/{slide_id}/pptx/{stem}.pptx"
                    root_prefix = output_prefix.rstrip('/') + '/' if output_prefix else 'contribute/'
                    target_key = f"{root_prefix}{course_id}/{target_lang}/{target_rel_key}"

                    s3._client.upload_file(str(slide_path), s3.bucket, target_key)

                    # Manifest
                    insert_manifest([course_id, target_lang, part_id, chapter_id, slide_id, 'pptx'], f"{stem}.pptx")

            # Process TXT files now (they are common to all langs)
            for (stem, slide_id, txt_local) in txt_entries:
                for target_lang in target_langs:
                    target_rel_key = f"{part_id}/{chapter_id}/{slide_id}/text/{stem}.txt"
                    root_prefix = output_prefix.rstrip('/') + '/' if output_prefix else 'contribute/'
                    target_key = f"{root_prefix}{course_id}/{target_lang}/{target_rel_key}"

                    local_out_path = output_dir / target_lang / part_id / chapter_id / slide_id / 'text' / f"{stem}.txt"
                    local_out_path.parent.mkdir(parents=True, exist_ok=True)

                    success = text_translator.translate_text_file(txt_local, local_out_path, source_lang, deepl_target(target_lang))
                    if not success:
                        raise RuntimeError(f"Failed to translate TXT {txt_local}")

                    s3._client.upload_file(str(local_out_path), s3.bucket, target_key)

                    insert_manifest([course_id, target_lang, part_id, chapter_id, slide_id, 'text'], f"{stem}.txt")

        # -----------------------------------------------------------
        # Process chapters ALREADY split (slide_id present)
        # -----------------------------------------------------------

        for (part_id, chapter_id), slide_map in chapter_pptx_split.items():
            for slide_id, mini_pptx_local in slide_map.items():
                # Retrieve corresponding txt info
                txt_entry = chapter_txts_split.get((part_id, chapter_id), {}).get(slide_id)
                stem = Path(mini_pptx_local).stem  # assume same stem as txt

                for target_lang in target_langs:
                    # Translate the mini PPTX directly
                    local_pptx_out = output_dir / target_lang / part_id / chapter_id / slide_id / 'pptx' / f"{stem}.pptx"
                    local_pptx_out.parent.mkdir(parents=True, exist_ok=True)

                    success = pptx_translator.translate_pptx(mini_pptx_local, local_pptx_out, source_lang, deepl_target(target_lang))
                    if not success:
                        raise RuntimeError(f"Failed to translate mini-PPTX {mini_pptx_local} to {target_lang}")

                    root_prefix = output_prefix.rstrip('/') + '/' if output_prefix else 'contribute/'
                    target_pptx_key = f"{root_prefix}{course_id}/{target_lang}/{part_id}/{chapter_id}/{slide_id}/pptx/{stem}.pptx"
                    s3._client.upload_file(str(local_pptx_out), s3.bucket, target_pptx_key)

                    insert_manifest([course_id, target_lang, part_id, chapter_id, slide_id, 'pptx'], f"{stem}.pptx")

                    # If we have txt
                    if txt_entry:
                        stem_txt, txt_local_path = txt_entry
                        local_txt_out = output_dir / target_lang / part_id / chapter_id / slide_id / 'text' / f"{stem_txt}.txt"
                        local_txt_out.parent.mkdir(parents=True, exist_ok=True)

                        success_txt = text_translator.translate_text_file(txt_local_path, local_txt_out, source_lang, deepl_target(target_lang))
                        if not success_txt:
                            raise RuntimeError(f"Failed to translate TXT {txt_local_path}")

                        target_txt_key = f"{root_prefix}{course_id}/{target_lang}/{part_id}/{chapter_id}/{slide_id}/text/{stem_txt}.txt"
                        s3._client.upload_file(str(local_txt_out), s3.bucket, target_txt_key)

                        insert_manifest([course_id, target_lang, part_id, chapter_id, slide_id, 'text'], f"{stem_txt}.txt")

        # Save manifest locally and upload
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        manifest_key = f"{output_prefix.rstrip('/') + '/' if output_prefix else 'contribute/'}{course_id}/manifest.json"
        s3._client.upload_file(str(manifest_path), s3.bucket, manifest_key)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = [manifest_key]
        active_tasks[task_id]["manifest"] = manifest

    except Exception as e:
        logger.error(f"Course task {task_id} failed: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)
    finally:
        # Clean temporary directory to avoid disk bloat
        cleanup_temp_dir(temp_dir)

# --------------------------------------
# Background runner for Text Translation from S3
# --------------------------------------

async def run_text_translation_s3_async(task_id: str, input_keys: List[str], output_prefix: Optional[str],
                                       output_dir: Path, source_lang: str, target_lang: str):
    """Download .txt files from S3, translate, upload back to S3."""
    try:
        active_tasks[task_id]["status"] = "running"
        api_keys = config_manager.get_api_keys()
        deepl_key = api_keys.get("deepl")
        if not deepl_key:
            raise ValueError("DeepL API key not configured")

        s3 = S3ClientWrapper()

        def progress_callback(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        temp_input_dir = output_dir.parent / "input"
        input_files = s3.download_files(input_keys, temp_input_dir)

        translator = TextTranslationCore(deepl_key, progress_callback)
        result_local_paths: List[Path] = []

        for input_file in input_files:
            if input_file.suffix.lower() != ".txt":
                raise ValueError(f"Unsupported file type {input_file}")

            output_file = output_dir / f"translated_{input_file.name}"
            progress_callback(f"Translating {input_file.name}")

            success = translator.translate_text_file(input_file, output_file, source_lang, target_lang)
            if success:
                result_local_paths.append(output_file)
            else:
                raise RuntimeError(f"Failed to translate {input_file.name}")

        # Upload preserving structure
        result_keys = s3.upload_files_with_mapping(result_local_paths, input_keys, output_prefix)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = result_keys

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)

# --------------------------------------
# Background runner for Text-to-Speech from S3
# --------------------------------------

async def run_tts_s3_async(task_id: str, input_keys: List[str], output_prefix: Optional[str],
                           output_dir: Path):
    """Download text files from S3, generate audio using ElevenLabs, then upload MP3s back to S3."""
    try:
        # Mark task as running
        active_tasks[task_id]["status"] = "running"

        # Retrieve ElevenLabs API key
        api_keys = config_manager.get_api_keys()
        elevenlabs_key: Optional[str] = api_keys.get("elevenlabs")
        if not elevenlabs_key:
            raise ValueError("ElevenLabs API key not configured")

        # Prepare S3 client and local workspace
        s3 = S3ClientWrapper()

        def progress(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        temp_input_dir = output_dir.parent / "input"
        input_files = s3.download_files(input_keys, temp_input_dir)

        # Initialise TTS core
        tts_core = TextToSpeechCore(elevenlabs_key, progress)

        result_local_paths: List[Path] = []

        for input_path in input_files:
            if input_path.suffix.lower() != ".txt":
                raise ValueError(f"Unsupported file type {input_path}")

            output_path = output_dir / f"audio_{input_path.stem}.mp3"
            progress(f"Generating audio for {input_path.name}")

            success = tts_core.text_to_speech_file(input_path, output_path)
            if not success:
                raise RuntimeError(f"Failed to generate audio for {input_path.name}")

            result_local_paths.append(output_path)

        # Upload back to S3 (preserve structure or apply output_prefix)
        result_keys = s3.upload_files_with_mapping(result_local_paths, input_keys, output_prefix)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = result_keys

    except Exception as exc:
        logger.error(f"TTS task {task_id} failed: {exc}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(exc)

# --------------------------------------
# Background runner for direct Text -> Speech (upload to S3)
# --------------------------------------

async def run_tts_text_s3_async(task_id: str, text: str, output_key: str, voice_id: Optional[str], temp_dir: Path, professors: Optional[List[dict]] = None, professor_name: Optional[str] = None) -> None:
    """Generate audio from raw text and upload to S3 at *output_key*."""

    try:
        active_tasks[task_id]["status"] = "running"

        api_keys = config_manager.get_api_keys()
        elevenlabs_key = api_keys.get("elevenlabs")
        if not elevenlabs_key:
            raise ValueError("ElevenLabs API key not configured")

        # Prepare working dirs
        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Write text to a temporary file (the core expects a file path)
        input_path = input_dir / "input.txt"
        with open(input_path, "w", encoding="utf-8") as fh:
            fh.write(text)

        output_path = output_dir / "audio.mp3"

        def progress(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        tts = TextToSpeechCore(elevenlabs_key, progress)

        # Determine voice_id to use
        final_voice_id = voice_id

        # (1) Try direct match from *professor_name* if supplied
        if not final_voice_id and professor_name:
            vid = tts.find_voice_by_name(professor_name)
            if vid:
                final_voice_id = vid
                progress(f"Using professor name match: {final_voice_id}")

        # (2) If no voice_id provided, try professor voice matching list (legacy workflow)
        if not final_voice_id and professors:
            voices_data = load_voices_data()
            # If voices_data is empty, build a quick voice_map from live voices fetched above
            if not voices_data:
                voice_map_live = {v.get("name", "").lower(): v.get("voice_id") for v in tts.get_voices()}
                voices_data = {"voice_map": voice_map_live}

            final_voice_id = select_voice_for_course(professors, voices_data)
            if final_voice_id:
                progress(f"Using professor-matched voice: {final_voice_id}")

        # Generate audio with determined voice
        if final_voice_id:
            success = tts.generate_audio(input_path, output_path, final_voice_id)
        else:
            # Use helper that auto-detects voice from filename (will pick default)
            success = tts.text_to_speech_file(input_path, output_path)
            if not final_voice_id:
                progress("Using default voice selection (no voice_id or professor match)")

        if not success:
            raise RuntimeError("Failed to generate audio from text")

        # Upload to S3 at exact output_key
        s3 = S3ClientWrapper()
        s3._client.upload_file(str(output_path), s3.bucket, output_key)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = [output_key]

    except Exception as exc:
        logger.error(f"TTS-text task {task_id} failed: {exc}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(exc)

    finally:
        # Clean up temp directory
        cleanup_temp_dir(temp_dir)

# --------------------------------------
# S3 Endpoints
# --------------------------------------
@app.post("/translate/pptx_s3", response_model=TaskStatus)
async def translate_pptx_s3(request: PPTXS3Request, background_tasks: BackgroundTasks, token: str = Depends(verify_token)):
    """Translate PPTX files stored in S3 and upload results back to S3."""
    # Validate S3 paths
    for key in request.input_keys:
        if not validate_s3_path(key):
            raise HTTPException(status_code=400, detail=f"Invalid S3 path: {key}")

    if request.output_prefix and not validate_s3_path(request.output_prefix):
        raise HTTPException(status_code=400, detail=f"Invalid S3 output prefix: {request.output_prefix}")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    output_dir = temp_dir / "output"
    output_dir.mkdir(parents=True)

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": request.input_keys,  # store keys instead of paths
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": request.source_lang
    }

    background_tasks.add_task(
        run_pptx_translation_s3_async,
        task_id,
        request.input_keys,
        request.output_prefix,
        output_dir,
        request.source_lang,
        request.target_lang
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=request.source_lang)


@app.post("/transcribe/audio_s3", response_model=TaskStatus)
async def transcribe_audio_s3(request: AudioS3Request, background_tasks: BackgroundTasks, token: str = Depends(verify_token)):
    """Transcribe audio files stored in S3 and upload transcripts back to S3."""
    # Validate S3 paths
    for key in request.input_keys:
        if not validate_s3_path(key):
            raise HTTPException(status_code=400, detail=f"Invalid S3 path: {key}")

    if request.output_prefix and not validate_s3_path(request.output_prefix):
        raise HTTPException(status_code=400, detail=f"Invalid S3 output prefix: {request.output_prefix}")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    output_dir = temp_dir / "output"
    output_dir.mkdir(parents=True)

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": request.input_keys,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": None
    }

    background_tasks.add_task(
        run_audio_transcription_s3_async,
        task_id,
        request.input_keys,
        request.output_prefix,
        output_dir
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=None)


# --------------------------------------
# Text Translation S3 Endpoint
# --------------------------------------


@app.post("/translate/text_s3", response_model=TaskStatus)
async def translate_text_s3(
    request: TextS3Request,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Translate text files stored in S3 and upload results back to S3."""
    # Validate S3 paths
    for key in request.input_keys:
        if not validate_s3_path(key):
            raise HTTPException(status_code=400, detail=f"Invalid S3 path: {key}")

    if request.output_prefix and not validate_s3_path(request.output_prefix):
        raise HTTPException(status_code=400, detail=f"Invalid S3 output prefix: {request.output_prefix}")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    output_dir = temp_dir / "output"
    output_dir.mkdir(parents=True)

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": request.input_keys,
        "output_dir": output_dir,
        "messages": [],
        "manifest": None,
        "source_lang": request.source_lang
    }

    background_tasks.add_task(
        run_text_translation_s3_async,
        task_id,
        request.input_keys,
        request.output_prefix,
        output_dir,
        request.source_lang,
        request.target_lang,
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=request.source_lang)

# --------------------------------------
# Course Translation Endpoint
# --------------------------------------


@app.post("/translate/course_s3", response_model=TaskStatus)
async def translate_course_s3(
    request: CourseS3Request,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Translate all PPTX & TXT for a course in S3 to multiple target languages."""
    # Validate output prefix if provided
    if request.output_prefix and not validate_s3_path(request.output_prefix):
        raise HTTPException(status_code=400, detail=f"Invalid S3 output prefix: {request.output_prefix}")

    task_id = create_task_id()
    temp_dir = get_temp_dir()

    # Determine effective source language (could be 'en' if use_english=True)
    effective_source_lang = "en" if request.use_english else request.source_lang

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "messages": [],
        "manifest": None,
        "source_lang": effective_source_lang,
    }

    background_tasks.add_task(
        run_course_translation_s3_async,
        task_id,
        request.course_id,
        effective_source_lang,
        request.target_langs,
        request.output_prefix,
        temp_dir,
    )

    return TaskStatus(task_id=task_id, status="pending", source_lang=effective_source_lang)

# --------------------------------------
# Text-to-Speech S3 Endpoint
# --------------------------------------

@app.post("/tts_s3", response_model=TaskStatus)
async def text_to_speech_s3(
    request: TTSS3Request,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Generate speech from text files stored in S3 and upload MP3 results."""

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    output_dir = temp_dir / "output"
    output_dir.mkdir(parents=True)

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": request.input_keys,
        "output_dir": output_dir,
        "messages": []
    }

    background_tasks.add_task(
        run_tts_s3_async,
        task_id,
        request.input_keys,
        request.output_prefix,
        output_dir,
    )

    return TaskStatus(task_id=task_id, status="pending")

# --------------------------------------
# Direct Text-to-Speech & S3 upload Endpoint
# --------------------------------------

@app.post("/tts_text_s3", response_model=TaskStatus)
async def text_to_speech_text_s3(
    request: TTSTextRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """Generate MP3 from a raw text string and upload it to S3 at *output_key*."""

    task_id = create_task_id()
    temp_dir = get_temp_dir()

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "messages": []
    }

    # Convert professors to dict format for background task
    professors_data = None
    if request.professors:
        professors_data = [
            {
                "id": prof.id,
                "name": prof.name,
                "is_coordinator": prof.is_coordinator
            }
            for prof in request.professors
        ]

    # Pass the simple professor name as well (may be None)
    background_tasks.add_task(
        run_tts_text_s3_async,
        task_id,
        request.text,
        request.output_key,
        request.voice_id,
        temp_dir,
        professors_data,
        request.professor,  # <–– new arg
    )

    return TaskStatus(task_id=task_id, status="pending")

# --------------------------------------
# Course Video Generation S3 Request
# --------------------------------------
class CourseVideoS3Request(BaseModel):
    """Request model for creating a full course video from S3 PPTX + MP3."""
    course_id: str = Field(..., description="Unique identifier of the course")
    language: str = Field(..., description="Language of the course (ISO-639-1)")
    output_key: Optional[str] = Field(None, description="Destination S3 key for the resulting MP4. Defaults to 'contribute/<course_id>/<language>/video.mp4'")
    professors: Optional[List[ProfessorInfo]] = Field(None, description="List of professors associated with this course for voice matching")


# --------------------------------------
# Background runner for Course Video Generation from S3
# --------------------------------------
async def run_course_video_s3_async(task_id: str, course_id: str, language: str, output_key: Optional[str], professors: Optional[List[dict]] = None) -> None:
    """Generate a complete course video by converting PPTX→PNG and merging with existing MP3 files."""
    temp_root = None
    try:
        active_tasks[task_id]["status"] = "running"

        from pathlib import Path  # ensure Path available early

        api_keys = config_manager.get_api_keys()
        convertapi_key = api_keys.get("convertapi")
        if not convertapi_key:
            raise ValueError("ConvertAPI key not configured")

        s3 = S3ClientWrapper()

        source_prefix = f"contribute/{course_id}/{language}/"

        def progress(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            active_tasks[task_id]["progress"] = msg
            logger.info(f"Task {task_id}: {msg}")

        progress("Starting course video generation...")

        # Gather PPTX and MP3 keys
        progress("Scanning S3 for PPTX files...")
        all_files = s3.list_files(source_prefix)

        # First collect every .pptx under the prefix (excluding hidden files)
        pptx_keys = [
            k for k in all_files if k.lower().endswith('.pptx') and not Path(k).name.startswith('.')
        ]

        # If any proof-read versions exist (filename ending with '-proofread.pptx'),
        # restrict the list to those only – this ensures the final video uses the
        # reviewer-approved slides and ignores the original drafts.
        proofread_pptx = [k for k in pptx_keys if Path(k).stem.endswith('-proofread')]
        if proofread_pptx:
            pptx_keys = proofread_pptx

        progress(f"Found {len(pptx_keys)} PPTX files: {[Path(k).name for k in pptx_keys]}")

        if not pptx_keys:
            raise RuntimeError(f"No .pptx files found under {source_prefix}")

        progress("Scanning S3 for MP3 files...")
        mp3_keys = [k for k in all_files if k.lower().endswith('.mp3') and not Path(k).name.startswith('.')]
        progress(f"Found {len(mp3_keys)} MP3 files: {[Path(k).name for k in mp3_keys]}")

        # Load voices data for potential TTS generation
        voices_data = load_voices_data()
        selected_voice_id = None

        if not mp3_keys:
            progress("No MP3 audio tracks found")

            # Try to use professor voice matching for TTS generation
            if professors and voices_data:
                progress(f"Attempting voice matching for {len(professors)} professors...")
                selected_voice_id = select_voice_for_course(professors, voices_data)

                if selected_voice_id:
                    progress(f"Selected voice ID for course: {selected_voice_id}")
                    # Note: TTS generation would require text content which isn't implemented here
                    # This is a placeholder for future TTS integration
                else:
                    progress("No matching professor voices found")

            if not selected_voice_id:
                progress("Warning: No MP3 audio tracks found and no voice match available – video will be silent")
        else:
            # Log professor info even when MP3s exist (for debugging)
            if professors:
                progress(f"Professor info available: {[p['name'] for p in professors]} (using existing MP3s)")
                # Still try voice matching for logging/debugging purposes
                selected_voice_id = select_voice_for_course(professors, voices_data)
                if selected_voice_id:
                    progress(f"Note: Professor voice match available ({selected_voice_id}) but using existing MP3 files")

        # Create temp dirs
        import tempfile
        temp_root = Path(tempfile.mkdtemp(prefix="course_video_"))
        input_dir = temp_root / "input"
        output_dir = temp_root / "output"
        slides_dir = temp_root / "slides"
        audio_dir = temp_root / "audio"

        for directory in [input_dir, output_dir, slides_dir, audio_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        progress(f"Created temp directory: {temp_root}")

        # Download PPTX files
        progress("Downloading PPTX files from S3...")
        local_pptx = s3.download_files(pptx_keys, input_dir)
        progress(f"Downloaded {len(local_pptx)} PPTX files")

        # Download MP3 files if they exist
        local_mp3 = []
        if mp3_keys:
            progress("Downloading MP3 files from S3...")
            local_mp3 = s3.download_files(mp3_keys, audio_dir)
            progress(f"Downloaded {len(local_mp3)} MP3 files")

        # Convert PPTX → PNG
        progress("Converting PPTX files to PNG images...")
        from core.pptx_converter import PPTXConverterCore
        converter = PPTXConverterCore(convertapi_key, progress)
        slide_counter = 0
        generated_images: List[Path] = []

        for i, pptx_path in enumerate(sorted(local_pptx), 1):
            progress(f"Converting PPTX {i}/{len(local_pptx)}: {pptx_path.name}")

            try:
                images = converter.convert_pptx_to_png(pptx_path, slides_dir)
                progress(f"Generated {len(images)} images from {pptx_path.name}")

                # Renumber images to sequential filenames for proper ordering
                for img_path_str in images:
                    img_path = Path(img_path_str)
                    if not img_path.exists():
                        progress(f"Warning: Generated image does not exist: {img_path}")
                        continue

                    new_name = f"{slide_counter:03d}.png"
                    new_path = slides_dir / new_name
                    img_path.rename(new_path)
                    generated_images.append(new_path)
                    slide_counter += 1

            except Exception as conversion_error:
                progress(f"Error converting {pptx_path.name}: {conversion_error}")
                # Continue with other files instead of failing completely
                continue

        if not generated_images:
            raise RuntimeError("PNG conversion produced no slides")

        progress(f"Successfully generated {len(generated_images)} slide images")

        # Create video from images and audio with per-slide durations
        progress("Creating video from slides and audio...")
        from core.video_merger import VideoMergerCore
        merger = VideoMergerCore(progress)
        output_file = output_dir / "course_video.mp4"

        # Use individual audio files for per-slide durations if available
        if local_mp3 and len(local_mp3) > 0:
            progress(f"Using per-slide audio durations for {len(local_mp3)} audio files")

            # Sort audio files to match slide order
            sorted_mp3 = sorted(local_mp3)

            # Create video using course video generation logic with per-slide audio durations
            success = create_course_video_with_audio_durations(
                slides_dir, output_file, sorted_mp3, progress
            )
        else:
            # Fallback to fixed duration when no audio files available
            duration_per_slide = 3.0 if len(generated_images) <= 10 else 2.0
            progress(f"No audio files found, using fixed {duration_per_slide}s per slide for {len(generated_images)} slides")

            success = merger.create_video_from_files(
                slides_dir, output_file,
                duration_per_slide=duration_per_slide,
                audio_file=None
            )

        if not success or not output_file.exists():
            raise RuntimeError("Video creation failed")

        progress(f"Successfully created video: {output_file} ({output_file.stat().st_size} bytes)")

        # Determine destination key
        if not output_key:
            output_key = f"contribute/{course_id}/{language}/video.mp4"

        # Upload to S3
        progress(f"Uploading video to S3: {output_key}")
        s3._client.upload_file(str(output_file), s3.bucket, output_key)
        progress("Video upload completed successfully")

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = [output_key]
        active_tasks[task_id]["progress"] = "100%"

    except Exception as e:
        error_msg = f"Course video task {task_id} failed: {e}"
        logger.error(error_msg, exc_info=True)
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)
        active_tasks[task_id]["progress"] = f"Failed: {e}"
    finally:
        # Cleanup temp directory
        if temp_root and temp_root.exists():
            import shutil
            try:
                progress("Cleaning up temporary files...")
                shutil.rmtree(temp_root, ignore_errors=True)
            except Exception as cleanup_error:
                logger.warning(
                    f"Failed to cleanup temp directory {temp_root}: {cleanup_error}")


# --------------------------------------
# API route for course video generation
# --------------------------------------
@app.post("/video/course_s3", response_model=TaskStatus)
async def generate_course_video_s3(
    request: CourseVideoS3Request,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    task_id = create_task_id()
    active_tasks[task_id] = {
        "status": "pending",
        "messages": [],
        "progress": None,
        "error": None,
        "result_files": [],
    }

    # Convert professors to dict format for background task
    professors_data = None
    if request.professors:
        professors_data = [
            {
                "id": prof.id,
                "name": prof.name,
                "is_coordinator": prof.is_coordinator
            }
            for prof in request.professors
        ]

    # Start background task
    background_tasks.add_task(
        run_course_video_s3_async,
        task_id,
        request.course_id,
        request.language,
        request.output_key,
        professors_data,
    )

    return TaskStatus(task_id=task_id, status="pending")

# --------------------------------------
# Helper function for course video generation with audio durations
# --------------------------------------
def create_course_video_with_audio_durations(slides_dir: Path, output_file: Path,
                                            audio_files: List[Path],
                                            progress_callback: Callable[[str], None]) -> bool:
    """
    Create course video from PNG slides with individual audio durations.
    Uses ffmpeg to create video segments and concatenate them.
    """
    try:
        import json

        # Get image files from slides directory
        image_files = []
        for file_path in slides_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                image_files.append(file_path)

        # Sort files naturally
        image_files.sort(key=lambda x: str(x.name))

        if len(image_files) != len(audio_files):
            progress_callback(f"Warning: {len(image_files)} images but {len(audio_files)} audio files")

        # Get duration for each audio file using ffprobe
        def get_audio_duration(audio_file: Path) -> float:
            try:
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    str(audio_file)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                progress_callback(f"Audio duration for {audio_file.name}: {duration:.2f}s")
                return duration
            except Exception as e:
                progress_callback(f"Warning: Could not get duration for {audio_file.name}, using 3.0s default")
                return 3.0

        # Create temporary directory for segments
        temp_dir = output_file.parent / "temp_course_video_segments"
        temp_dir.mkdir(exist_ok=True)

        segment_files = []

        # Create video segment for each slide+audio pair
        for i, (image_file, audio_file) in enumerate(zip(image_files, audio_files)):
            progress_callback(f"Creating segment {i+1}/{len(image_files)}: {image_file.name} + {audio_file.name}")

            segment_file = temp_dir / f"segment_{i:03d}.mp4"
            segment_files.append(segment_file)

            # Create video segment with image and audio
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', str(image_file),
                '-i', str(audio_file),
                '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264',
                '-tune', 'stillimage',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-pix_fmt', 'yuv420p',
                '-r', '30',
                '-shortest',  # Stop when shortest stream (audio) ends
                str(segment_file)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                progress_callback(f"Error creating segment {i+1}: {result.stderr}")
                raise RuntimeError(f"ffmpeg error: {result.stderr}")

        # Create concat file for final video assembly
        concat_file = temp_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for segment in segment_files:
                f.write(f"file '{segment.absolute()}'\n")

        # Concatenate all segments into final video
        progress_callback("Concatenating all segments into final video...")

        concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(output_file)
        ]

        concat_result = subprocess.run(concat_cmd, capture_output=True, text=True)

        if concat_result.returncode != 0:
            progress_callback(f"Error concatenating segments: {concat_result.stderr}")
            raise RuntimeError(f"ffmpeg concatenation error: {concat_result.stderr}")

        progress_callback(f"Successfully created course video: {output_file}")

        # Clean up temporary files
        progress_callback("Cleaning up temporary files...")
        for file in segment_files:
            file.unlink(missing_ok=True)
        concat_file.unlink(missing_ok=True)
        temp_dir.rmdir()

        return True

    except Exception as e:
        progress_callback(f"Error creating course video with audio durations: {e}")
        return False

# --------------------------------------
# Video Merge Tool S3 Request (matches MP3+PNG by 2-digit patterns)
# --------------------------------------
class VideoMergeToolS3Request(BaseModel):
    """Request model for merging MP3 + PNG files using VideoMergeTool logic."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input MP3 and PNG files")
    output_key: str = Field(..., description="Destination S3 key for the resulting MP4 video")
    recursive_mode: bool = Field(False, description="If true, process subfolders separately")

# --------------------------------------
# Background runner for VideoMergeTool-style S3 processing
# --------------------------------------
async def run_video_merge_tool_s3_async(task_id: str, input_keys: List[str], output_key: str,
                                       recursive_mode: bool, temp_dir: Path):
    """Download MP3/PNG files from S3, match by 2-digit patterns, create MP4 with ffmpeg, upload result."""
    try:
        active_tasks[task_id]["status"] = "running"

        def progress(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")

        # Check ffmpeg availability
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   text=True)
            if result.returncode != 0:
                raise RuntimeError("ffmpeg command returned non-zero exit code")
            progress("ffmpeg is available")
        except FileNotFoundError:
            raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg first.")

        s3 = S3ClientWrapper()

        # Create working directories
        input_dir = temp_dir / "input"
        output_dir = temp_dir / "output"
        input_dir.mkdir(parents=True)
        output_dir.mkdir(parents=True)

        # Download files from S3
        progress(f"Downloading {len(input_keys)} files from S3...")
        local_files = s3.download_files(input_keys, input_dir)

        # Separate MP3 and PNG files
        mp3_files = [f for f in local_files if f.suffix.lower() == '.mp3']
        png_files = [f for f in local_files if f.suffix.lower() == '.png']

        progress(f"Found {len(mp3_files)} MP3 and {len(png_files)} PNG files")

        if not mp3_files or not png_files:
            raise ValueError("Need both MP3 and PNG files to create video")

        # Match files by 2-digit identifier (VideoMergeTool logic)
        file_pairs = match_file_pairs_by_digit_pattern(mp3_files, png_files, progress)

        if not file_pairs:
            raise ValueError("No matching MP3/PNG pairs found based on 2-digit patterns")

        progress(f"Found {len(file_pairs)} matching pairs")

        # Sort pairs by numeric ID
        file_pairs.sort(key=lambda x: int(x[0]))

        # Generate output filename (remove 2-digit identifier from first MP3)
        _, first_mp3, _ = file_pairs[0]
        mp3_stem = first_mp3.stem
        import re
        identifier_pattern = r'[_-](\d{2})(?:[_-])'
        output_name = re.sub(identifier_pattern, '_', mp3_stem)
        end_pattern = r'[_-]\d{2}$'
        output_name = re.sub(end_pattern, '', output_name)

        output_file = output_dir / f"{output_name}.mp4"
        progress(f"Creating video: {output_file}")

        # Create video using ffmpeg (VideoMergeTool style)
        create_video_with_ffmpeg_videomergetool(file_pairs, output_file, progress)

        if not output_file.exists():
            raise RuntimeError("Video creation failed - output file not created")

        # Upload result to S3
        progress(f"Uploading video to S3: {output_key}")
        s3._client.upload_file(str(output_file), s3.bucket, output_key)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = [output_key]

    except Exception as e:
        error_msg = f"VideoMergeTool task {task_id} failed: {e}"
        logger.error(error_msg, exc_info=True)
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)
    finally:
        # Clean up temp directory
        cleanup_temp_dir(temp_dir)

def match_file_pairs_by_digit_pattern(mp3_files: List[Path], png_files: List[Path],
                                    progress_callback: Callable[[str], None]) -> List[Tuple[str, Path, Path]]:
    """
    Match MP3 and PNG files based on 2-digit pattern in filenames.
    Returns list of (digit_id, mp3_path, png_path) tuples.
    Based on VideoMergeTool.match_file_pairs logic.
    """
    import re

    file_pairs = []
    mp3_dict = {}
    png_dict = {}

    # Regex to match exactly two digits not adjacent to other digits
    id_pattern = re.compile(r'(?<!\d)(\d{2})(?!\d)')

    # Extract indices for PNG files
    for png_file in png_files:
        match = id_pattern.search(png_file.name)
        if match:
            idx = match.group(1)
            progress_callback(f"PNG found index {idx} in {png_file.name}")
            png_dict[idx] = png_file

    # Extract indices for MP3 files
    for mp3_file in mp3_files:
        match = id_pattern.search(mp3_file.name)
        if match:
            idx = match.group(1)
            progress_callback(f"MP3 found index {idx} in {mp3_file.name}")
            mp3_dict[idx] = mp3_file

    # Match pairs by index
    for idx in sorted(mp3_dict.keys(), key=lambda x: int(x)):
        mp3_file = mp3_dict[idx]
        png_file = png_dict.get(idx)
        if png_file:
            progress_callback(f"Matched index {idx}: {mp3_file.name} + {png_file.name}")
            file_pairs.append((idx, mp3_file, png_file))
        else:
            progress_callback(f"No PNG match for MP3 index {idx}: {mp3_file.name}")

    return sorted(file_pairs, key=lambda x: int(x[0]))

def create_video_with_ffmpeg_videomergetool(file_pairs: List[Tuple[str, Path, Path]],
                                           output_file: Path,
                                           progress_callback: Callable[[str], None]):
    """
    Create video from matched MP3/PNG pairs using ffmpeg.
    Based on VideoMergeTool.create_video_with_ffmpeg logic.
    Adds 0.2s silence between clips.
    """
    import subprocess
    import tempfile

    try:
        # Create temporary directory for segments
        temp_dir = output_file.parent / "temp_video_files"
        temp_dir.mkdir(exist_ok=True)

        segment_files = []

        # Process each pair and create individual video segments
        for idx, (numeric_id, mp3_file, png_file) in enumerate(file_pairs):
            progress_callback(f"Processing pair {idx+1}/{len(file_pairs)}: {numeric_id}")

            # Create segment file path
            segment_file = temp_dir / f"segment_{idx:03d}.mp4"
            segment_files.append(segment_file)

            # Run ffmpeg to create video segment from image and audio
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', str(png_file),
                '-i', str(mp3_file),
                '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-c:v', 'libx264',
                '-tune', 'stillimage',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-pix_fmt', 'yuv420p',
                '-shortest',
                str(segment_file)
            ]

            progress_callback(f"Creating segment for pair {idx+1}...")

            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            if result.returncode != 0:
                progress_callback(f"Error creating segment {idx+1}: {result.stderr}")
                raise RuntimeError(f"ffmpeg error: {result.stderr}")

            # Add silence between clips (except after last segment)
            if idx < len(file_pairs) - 1:
                silence_file = temp_dir / f"silence_{idx:03d}.mp4"
                segment_files.append(silence_file)

                # Create 0.2 second silence with the same image
                silence_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1',
                    '-i', str(png_file),
                    '-f', 'lavfi',
                    '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                    '-c:v', 'libx264',
                    '-t', '0.2',  # 0.2 seconds silence
                    '-c:a', 'aac',
                    '-pix_fmt', 'yuv420p',
                    str(silence_file)
                ]

                progress_callback(f"Adding silence after segment {idx+1}...")

                silence_result = subprocess.run(silence_cmd, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, text=True)

                if silence_result.returncode != 0:
                    progress_callback(f"Error creating silence {idx+1}: {silence_result.stderr}")
                    raise RuntimeError(f"ffmpeg error: {silence_result.stderr}")

        # Create file list for concatenation
        concat_file = temp_dir / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for segment in segment_files:
                f.write(f"file '{segment.absolute()}'\n")

        # Concatenate all segments into final video
        progress_callback("Concatenating all segments...")

        concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',
            str(output_file)
        ]

        concat_result = subprocess.run(concat_cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)

        if concat_result.returncode != 0:
            progress_callback(f"Error concatenating: {concat_result.stderr}")
            raise RuntimeError(f"ffmpeg error: {concat_result.stderr}")

        progress_callback(f"Successfully created video: {output_file}")

        # Clean up temporary files
        progress_callback("Cleaning up temporary files...")
        for file in segment_files:
            file.unlink(missing_ok=True)
        concat_file.unlink(missing_ok=True)
        temp_dir.rmdir()

    except Exception as e:
        error_msg = f"Error creating video with VideoMergeTool logic: {str(e)}"
        progress_callback(error_msg)
        raise RuntimeError(error_msg)

# --------------------------------------
# VideoMergeTool API Endpoint
# --------------------------------------
@app.post("/video/merge_tool_s3", response_model=TaskStatus)
async def video_merge_tool_s3(
    request: VideoMergeToolS3Request,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
):
    """
    Merge MP3 and PNG files using VideoMergeTool logic:
    - Matches files by 2-digit number patterns in filenames
    - Creates MP4 video using ffmpeg with 0.2s silence between clips
    - Supports the same matching logic as the VideoMergeTool from main.py
    """
    task_id = create_task_id()
    temp_dir = get_temp_dir()

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "messages": [],
    }

    # Start background task
    background_tasks.add_task(
        run_video_merge_tool_s3_async,
        task_id,
        request.input_keys,
        request.output_key,
        request.recursive_mode,
        temp_dir,
    )

    return TaskStatus(task_id=task_id, status="pending")

# Add this after the existing imports at the top
def match_professor_voice(professor_name: str, voices_data: dict) -> Optional[str]:
    """Return the ElevenLabs *voice_id* that exactly matches the given professor name.

    The previous implementation maintained large hard-coded dictionaries to map
    professor names to voice names.  This is no longer necessary because the
    calling application now provides the correct professor name (or voice_id);
    the Language-Toolkit only needs to resolve that name in the *voices_data*
    mapping it loads from *elevenlabs_voices.json*.

    Matching is performed case-insensitively against the keys in
    ``voices_data["voice_map"]``.  If no match is found, the function returns
    ``None`` and the caller can fall back to its default behaviour.
    """

    if not professor_name or not voices_data:
        return None

    voice_map: dict = voices_data.get("voice_map", {})
    if not voice_map:
        logger.warning("No voice map found in voices data")
        return None

    # Perform a case-insensitive lookup
    name_lower = professor_name.lower().strip()
    for voice_name, voice_id in voice_map.items():
        if voice_name.lower() == name_lower:
            logger.info(
                f"Voice match: '{professor_name}' -> '{voice_name}' ({voice_id})"
            )
            return voice_id

    # No match found
    logger.info(f"No voice match found for professor: '{professor_name}'")
    return None

def load_voices_data() -> dict:
    """Load the ElevenLabs voices configuration data."""
    voices_file = Path("elevenlabs_voices.json")
    try:
        if voices_file.exists():
            with open(voices_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            logger.warning("ElevenLabs voices file not found")
            return {}
    except Exception as e:
        logger.error(f"Error loading voices data: {e}")
        return {}

def select_voice_for_course(professors: List[dict], voices_data: dict) -> Optional[str]:
    """
    Select the most appropriate voice for a course based on its professors.
    Prioritizes coordinators over associated professors.

    Args:
        professors: List of professor dicts with 'name', 'id', 'is_coordinator' fields
        voices_data: Loaded voices configuration data

    Returns:
        voice_id string if a match is found, None otherwise
    """
    if not professors or not voices_data:
        return None

    # Sort professors - coordinators first, then by name
    sorted_professors = sorted(professors,
                             key=lambda p: (not p.get('is_coordinator', False), p.get('name', '')))

    # Try to find a voice match, starting with coordinators
    for professor in sorted_professors:
        professor_name = professor.get('name', '')
        if professor_name:
            voice_id = match_professor_voice(professor_name, voices_data)
            if voice_id:
                coordinator_status = "coordinator" if professor.get('is_coordinator') else "associated"
                logger.info(f"Selected voice for course: {professor_name} ({coordinator_status}) -> {voice_id}")
                return voice_id

    logger.info("No matching voices found for any course professors")
    return None

# --------------------------------------
# Reward Evaluator Endpoints
# --------------------------------------
class RewardEvaluationRequest(BaseModel):
    """Request model for reward evaluation."""
    file_path: Optional[str] = Field(None, description="Path to single file to evaluate")
    folder_path: Optional[str] = Field(None, description="Path to folder to evaluate")
    target_language: str = Field(..., description="Target language code (e.g., 'en', 'fr', 'es')")
    reward_mode: str = Field(..., description="Reward mode: 'image', 'video', or 'txt'")
    recursive: bool = Field(False, description="Whether to search folders recursively")

@app.post("/reward/evaluate", response_model=Dict)
async def evaluate_reward(request: RewardEvaluationRequest):
    """
    Evaluate reward for a single file or folder of files.
    Supports PPTX files (image/video modes) and TXT files.
    """
    try:
        from core.unified_reward_evaluator import UnifiedRewardEvaluator
        evaluator = UnifiedRewardEvaluator()
        
        # Validate reward mode
        if request.reward_mode not in ['image', 'video', 'txt']:
            raise HTTPException(status_code=400, detail=f"Invalid reward mode: {request.reward_mode}")
        
        # Validate language
        available_languages = evaluator.get_available_languages()
        if request.target_language not in available_languages:
            raise HTTPException(
                status_code=400, 
                detail=f"Language '{request.target_language}' not supported. Available: {available_languages}"
            )
        
        # Process request
        if request.file_path:
            # Single file evaluation
            result = evaluator.evaluate_file(
                request.file_path,
                request.target_language,
                request.reward_mode
            )
            return {"results": [result]}
            
        elif request.folder_path:
            # Folder evaluation
            results = evaluator.evaluate_folder(
                request.folder_path,
                request.target_language,
                request.reward_mode,
                request.recursive
            )
            
            # Add summary statistics
            summary = evaluator.get_summary_stats(results)
            return {
                "results": results,
                "summary": summary
            }
        else:
            raise HTTPException(status_code=400, detail="Either file_path or folder_path must be provided")
            
    except Exception as e:
        logger.error(f"Reward evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reward/languages")
async def get_reward_languages():
    """Get list of supported languages for reward evaluation."""
    try:
        from core.unified_reward_evaluator import UnifiedRewardEvaluator
        evaluator = UnifiedRewardEvaluator()
        languages = evaluator.get_available_languages()
        
        # Get language factors for additional info
        language_info = {}
        for lang in languages:
            if lang in evaluator.language_factors:
                language_info[lang] = {
                    "code": lang,
                    "factor": evaluator.language_factors[lang]
                }
        
        return {
            "languages": languages,
            "language_factors": language_info
        }
    except Exception as e:
        logger.error(f"Error getting languages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reward/evaluate_s3", response_model=TaskStatus)
async def evaluate_reward_s3(
    background_tasks: BackgroundTasks,
    s3_key: str = Body(..., description="S3 key of file or prefix of folder to evaluate"),
    target_language: str = Body(..., description="Target language code"),
    reward_mode: str = Body(..., description="Reward mode: 'image', 'video', or 'txt'"),
    is_folder: bool = Body(False, description="Whether s3_key is a folder prefix"),
    output_key: Optional[str] = Body(None, description="S3 key for output CSV file")
):
    """
    Evaluate reward for files in S3. Returns a task ID for async processing.
    Results are saved to S3 as a CSV file.
    """
    task_id = str(uuid.uuid4())
    active_tasks[task_id] = {
        "status": "pending",
        "messages": [],
        "result": None
    }
    
    background_tasks.add_task(
        run_reward_evaluation_s3_async,
        task_id,
        s3_key,
        target_language,
        reward_mode,
        is_folder,
        output_key
    )
    
    return TaskStatus(task_id=task_id, status="pending")

async def run_reward_evaluation_s3_async(
    task_id: str,
    s3_key: str,
    target_language: str,
    reward_mode: str,
    is_folder: bool,
    output_key: Optional[str]
):
    """Background task for S3 reward evaluation."""
    temp_dir = None
    try:
        active_tasks[task_id]["status"] = "running"
        
        from core.unified_reward_evaluator import UnifiedRewardEvaluator
        evaluator = UnifiedRewardEvaluator()
        
        s3 = S3ClientWrapper()
        temp_dir = Path(tempfile.mkdtemp())
        
        def progress(msg: str):
            active_tasks[task_id]["messages"].append(msg)
            logger.info(f"Task {task_id}: {msg}")
        
        progress("Starting reward evaluation...")
        
        results = []
        
        if is_folder:
            # List files in S3 folder
            progress(f"Listing files in S3 folder: {s3_key}")
            files = s3.list_files(s3_key)
            
            # Filter based on reward mode
            if reward_mode == 'txt':
                files = [f for f in files if f.lower().endswith('.txt')]
            elif reward_mode in ['image', 'video']:
                files = [f for f in files if f.lower().endswith(('.pptx', '.ppt'))]
            
            progress(f"Found {len(files)} files to evaluate")
            
            # Download and evaluate each file
            for i, file_key in enumerate(files, 1):
                progress(f"Processing file {i}/{len(files)}: {file_key}")
                
                # Download file
                local_path = temp_dir / Path(file_key).name
                s3.download_file(file_key, str(local_path))
                
                # Evaluate
                result = evaluator.evaluate_file(
                    str(local_path),
                    target_language,
                    reward_mode
                )
                result['file_key'] = file_key
                results.append(result)
                
                # Clean up
                local_path.unlink()
                
        else:
            # Single file
            progress(f"Downloading file: {s3_key}")
            local_path = temp_dir / Path(s3_key).name
            s3.download_file(s3_key, str(local_path))
            
            progress("Evaluating file...")
            result = evaluator.evaluate_file(
                str(local_path),
                target_language,
                reward_mode
            )
            result['file_key'] = s3_key
            results.append(result)
            
            local_path.unlink()
        
        # Generate summary
        summary = evaluator.get_summary_stats(results)
        
        # Create CSV output
        progress("Creating CSV output...")
        csv_path = temp_dir / "reward_evaluation_results.csv"
        
        import csv
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            if results and not any('error' in r for r in results):
                # Determine fieldnames based on mode
                if reward_mode == 'txt':
                    fieldnames = ['file_key', 'word_count', 'reward_euros']
                else:
                    fieldnames = ['file_key', 'total_slides', 'total_text_boxes', 
                                'total_words', 'total_reward']
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    row = {k: result.get(k, '') for k in fieldnames}
                    writer.writerow(row)
                
                # Add summary row
                writer.writerow({})  # Empty row
                writer.writerow({'file_key': 'SUMMARY'})
                writer.writerow({'file_key': f"Total Files: {summary['total_files']}"})
                writer.writerow({'file_key': f"Total Reward: €{summary['total_reward']:.4f}"})
                if 'average_reward' in summary:
                    writer.writerow({'file_key': f"Average Reward: €{summary['average_reward']:.4f}"})
        
        # Upload CSV to S3
        if not output_key:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            output_key = f"reward_evaluations/{reward_mode}_{target_language}_{timestamp}.csv"
        
        progress(f"Uploading results to S3: {output_key}")
        s3.upload_file(str(csv_path), output_key)
        
        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result"] = {
            "output_key": output_key,
            "summary": summary
        }
        active_tasks[task_id]["download_url"] = f"/download/{task_id}"
        
        progress(f"Evaluation complete. Results saved to: {output_key}")
        
    except Exception as e:
        logger.error(f"Reward evaluation error: {e}")
        active_tasks[task_id]["status"] = "failed"
        active_tasks[task_id]["error"] = str(e)
    finally:
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
