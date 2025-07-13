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
from typing import Any, Dict, List, Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import (BackgroundTasks, Depends, FastAPI, File, Form,
                     HTTPException, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field

# Load environment variables from .env file
load_dotenv()

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

async def verify_token(token: str = Depends(security)):
    """Validate JWT access token and return the associated client_id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        client_id: Optional[str] = payload.get("sub")
        if client_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload", headers={"WWW-Authenticate": "Bearer"})
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
async def root():
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
            "translate_course_s3": "/translate/course_s3"
        },
        "notes": {
            "single_file_download": "When a task has only one result file, /download/{task_id} returns the file directly",
            "multiple_files_download": "When a task has multiple result files, /download/{task_id} returns a ZIP archive",
            "individual_file_download": "Use /download/{task_id}/{file_index} to download a specific file (0-based index)"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

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
    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        if not file.filename.endswith('.pptx'):
            raise HTTPException(status_code=400, detail="Only PPTX files are supported")

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
        "messages": []
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

    return TaskStatus(task_id=task_id, status="pending")

@app.post("/translate/text", response_model=TaskStatus)
async def translate_text(
    background_tasks: BackgroundTasks,
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Translate text files from source to target language"""
    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        if not file.filename.endswith('.txt'):
            raise HTTPException(status_code=400, detail="Only TXT files are supported")

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
        "messages": []
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

    return TaskStatus(task_id=task_id, status="pending")

@app.post("/transcribe/audio", response_model=TaskStatus)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Transcribe audio files to text"""
    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    supported_formats = {'.wav', '.mp3', '.m4a', '.webm', '.mp4', '.mpga', '.mpeg'}

    for file in files:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in supported_formats:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {file_ext}. Supported: {supported_formats}"
            )

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
        "messages": []
    }

    # Start background task
    background_tasks.add_task(
        run_tool_async,
        AudioTranscriptionCore,
        task_id,
        input_files,
        output_dir
    )

    return TaskStatus(task_id=task_id, status="pending")

@app.post("/convert/pptx", response_model=TaskStatus)
async def convert_pptx(
    background_tasks: BackgroundTasks,
    output_format: str = Form(...),
    files: List[UploadFile] = File(...),
    token: str = Depends(verify_token)
):
    """Convert PPTX files to PDF, PNG, or WEBP"""
    if output_format not in ["pdf", "png", "webp"]:
        raise HTTPException(status_code=400, detail="Output format must be 'pdf', 'png', or 'webp'")

    task_id = create_task_id()
    temp_dir = get_temp_dir()
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Save uploaded files
    input_files = []
    for file in files:
        if not file.filename.endswith('.pptx'):
            raise HTTPException(status_code=400, detail="Only PPTX files are supported")

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
        "messages": []
    }

    # Start background task
    background_tasks.add_task(
        run_pptx_conversion_async,
        task_id,
        input_files,
        output_dir,
        output_format
    )

    return TaskStatus(task_id=task_id, status="pending")

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
        if not file.filename.endswith('.txt'):
            raise HTTPException(status_code=400, detail="Only TXT files are supported")

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
        "messages": []
    }

    # Start background task
    background_tasks.add_task(
        run_tool_async,
        TextToSpeechCore,
        task_id,
        input_files,
        output_dir
    )

    return TaskStatus(task_id=task_id, status="pending")

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
        # Accept both image and video files
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.gif',
                            '.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400,
                              detail=f"Unsupported file format: {file_ext}. "
                                   f"Supported: {', '.join(allowed_extensions)}")

        file_path = input_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        input_files.append(file_path)

    # Save audio file if provided
    audio_path = None
    if audio_file and audio_file.filename:
        audio_extensions = {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg'}
        audio_ext = Path(audio_file.filename).suffix.lower()

        if audio_ext not in audio_extensions:
            raise HTTPException(status_code=400,
                              detail=f"Unsupported audio format: {audio_ext}. "
                                   f"Supported: {', '.join(audio_extensions)}")

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
        "messages": []
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

    return TaskStatus(task_id=task_id, status="pending")

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
        result_files=task.get("result_files")
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
                "progress": task.get("progress")
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


class AudioS3Request(BaseModel):
    """Request model for transcribing audio files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input audio files")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for transcription results")

# New request model for translating text files stored in S3
class TextS3Request(BaseModel):
    """Request model for translating text files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input text files (.txt)")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for translated files")
    source_lang: str = Field(..., description="Source language code (e.g., 'en')")
    target_lang: str = Field(..., description="Target language code (e.g., 'fr')")

# --------------------------------------
# Course Translation S3 Request
# --------------------------------------

class CourseS3Request(BaseModel):
    """Request model for translating all PPTX & TXT of a course from S3."""
    course_id: str = Field(..., description="Unique identifier of the course")
    source_lang: str = Field(..., description="Language currently present in S3")
    target_langs: List[str] = Field(..., description="List of target language codes")
    output_prefix: Optional[str] = Field(None, description="Optional root prefix for translated course (defaults to original 'contribute/')")

class TTSS3Request(BaseModel):
    """Request model for generating speech from TXT files stored in S3."""
    input_keys: List[str] = Field(..., description="S3 object keys of the input text files (.txt)")
    output_prefix: Optional[str] = Field(None, description="Destination S3 prefix for generated audio files")

# -------------------------------------------------------------------
# New request model for direct text-to-speech with S3 upload (no TXT).
# -------------------------------------------------------------------

class TTSTextRequest(BaseModel):
    """Request body for generating speech from a raw text string and uploading the result to S3."""

    text: str = Field(..., description="Text content to convert to speech")
    output_key: str = Field(..., description="Destination S3 key (path + filename) for the generated MP3, e.g. 'audio/course/00.mp3'")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice_id to use (optional)")

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
        chapter_txts: Dict[Tuple[str, str], List[Tuple[str, str, Path]]] = defaultdict(list)  # (part,chap) -> [(stem, slide_id, local_path)]
        chapter_pptx: Dict[Tuple[str, str], Path] = {}

        for src_key, local_path in key_to_local.items():
            if Path(src_key).name.startswith('.'):
                continue

            rel = "/".join(Path(src_key).parts[3:])
            parts = rel.split('/')
            if len(parts) < 4:
                continue
            part_id, chapter_id, folder_type, filename = parts[0], parts[1], parts[2], parts[3]

            if folder_type == 'text':
                stem = Path(filename).stem
                slide_id = slide_id_cache.setdefault((part_id, chapter_id, stem), uuid.uuid4().hex)
                chapter_txts[(part_id, chapter_id)].append((stem, slide_id, local_path))
            elif folder_type == 'pptx' and filename.lower().endswith('.pptx'):
                chapter_pptx[(part_id, chapter_id)] = local_path

        # -----------------------------------------------------------
        # Process per chapter & per target language
        # -----------------------------------------------------------

        from core.pptx_utils import split_pptx_to_single_slides

        for (part_id, chapter_id), pptx_path in chapter_pptx.items():
            txt_entries = sorted(chapter_txts.get((part_id, chapter_id), []), key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
            if not txt_entries:
                progress(f"No TXT files for chapter {part_id}/{chapter_id}, skipping PPTX")
                continue

            stems = [stem for stem, _, _ in txt_entries]

            for target_lang in target_langs:
                # Translate full pptx once per target language per chapter
                translated_full = output_dir / f"translated_{target_lang}_{part_id}_{chapter_id}.pptx"
                success = pptx_translator.translate_pptx(pptx_path, translated_full, source_lang, target_lang)
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

                    success = text_translator.translate_text_file(txt_local, local_out_path, source_lang, target_lang)
                    if not success:
                        raise RuntimeError(f"Failed to translate TXT {txt_local}")

                    s3._client.upload_file(str(local_out_path), s3.bucket, target_key)

                    insert_manifest([course_id, target_lang, part_id, chapter_id, slide_id, 'text'], f"{stem}.txt")

        # Save manifest locally and upload
        manifest_path = output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        manifest_key = f"{output_prefix.rstrip('/') + '/' if output_prefix else 'contribute/'}{course_id}/manifest.json"
        s3._client.upload_file(str(manifest_path), s3.bucket, manifest_key)

        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result_files"] = [manifest_key]

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

async def run_tts_text_s3_async(task_id: str, text: str, output_key: str, voice_id: Optional[str], temp_dir: Path):
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

        # If voice_id explicitly provided we bypass filename detection
        if voice_id:
            success = tts.generate_audio(input_path, output_path, voice_id)
        else:
            # Use helper that auto-detects voice from filename (will pick default)
            success = tts.text_to_speech_file(input_path, output_path)

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
    task_id = create_task_id()
    temp_dir = get_temp_dir()
    output_dir = temp_dir / "output"
    output_dir.mkdir(parents=True)

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "input_files": request.input_keys,  # store keys instead of paths
        "output_dir": output_dir,
        "messages": []
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

    return TaskStatus(task_id=task_id, status="pending")


@app.post("/transcribe/audio_s3", response_model=TaskStatus)
async def transcribe_audio_s3(request: AudioS3Request, background_tasks: BackgroundTasks, token: str = Depends(verify_token)):
    """Transcribe audio files stored in S3 and upload transcripts back to S3."""
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
        run_audio_transcription_s3_async,
        task_id,
        request.input_keys,
        request.output_prefix,
        output_dir
    )

    return TaskStatus(task_id=task_id, status="pending")


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
        run_text_translation_s3_async,
        task_id,
        request.input_keys,
        request.output_prefix,
        output_dir,
        request.source_lang,
        request.target_lang,
    )

    return TaskStatus(task_id=task_id, status="pending")

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

    task_id = create_task_id()
    temp_dir = get_temp_dir()

    active_tasks[task_id] = {
        "status": "pending",
        "temp_dir": temp_dir,
        "messages": []
    }

    background_tasks.add_task(
        run_course_translation_s3_async,
        task_id,
        request.course_id,
        request.source_lang,
        request.target_langs,
        request.output_prefix,
        temp_dir,
    )

    return TaskStatus(task_id=task_id, status="pending")

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

    background_tasks.add_task(
        run_tts_text_s3_async,
        task_id,
        request.text,
        request.output_key,
        request.voice_id,
        temp_dir,
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


# --------------------------------------
# Background runner for Course Video Generation from S3
# --------------------------------------
async def run_course_video_s3_async(task_id: str, course_id: str, language: str, output_key: Optional[str]):
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

        if not mp3_keys:
            progress("Warning: No MP3 audio tracks found – video will be silent")

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

        # Prepare concatenated audio if audio tracks exist
        audio_track: Optional[Path] = None
        if local_mp3 and len(local_mp3) > 0:
            progress("Concatenating audio tracks...")
            try:
                concat_list = audio_dir / "concat.txt"
                with open(concat_list, "w", encoding="utf-8") as f:
                    for mp3 in sorted(local_mp3):
                        f.write(f"file '{mp3.absolute()}'\n")

                audio_track = output_dir / "combined_audio.mp3"
                import subprocess
                cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list), "-c", "copy", str(audio_track),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    progress(f"Warning: Audio concatenation failed: {result.stderr}")
                    audio_track = None
                else:
                    progress(f"Successfully created combined audio: {audio_track}")

            except Exception as audio_error:
                progress(f"Warning: Audio processing failed: {audio_error}")
                audio_track = None

        # Create video from images and audio
        progress("Creating video from slides and audio...")
        from core.video_merger import VideoMergerCore
        merger = VideoMergerCore(progress)
        output_file = output_dir / "course_video.mp4"

        # Use a shorter duration per slide if we have many slides
        duration_per_slide = 3.0 if len(generated_images) <= 10 else 2.0
        progress(f"Using {duration_per_slide}s per slide for {len(generated_images)} slides")

        success = merger.create_video_from_files(
            slides_dir, output_file,
            duration_per_slide=duration_per_slide,
            audio_file=audio_track
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

    # Start background task
    background_tasks.add_task(
        run_course_video_s3_async,
        task_id,
        request.course_id,
        request.language,
        request.output_key,
    )

    return TaskStatus(task_id=task_id, status="pending")

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
