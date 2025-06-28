"""
FastAPI server for Language Toolkit API
Provides REST endpoints for all language processing tools
"""

import asyncio
import json
import logging
import queue
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union
import tempfile
import shutil
import os

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form, Depends
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import core functionality modules
from core.config import ConfigManager
from core.pptx_translation import PPTXTranslationCore
from core.transcription import AudioTranscriptionCore
from core.text_translation import TextTranslationCore
from core.text_to_speech import TextToSpeechCore
from core.pptx_converter import PPTXConverterCore
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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global task storage
active_tasks: Dict[str, Dict] = {}
config_manager = ConfigManager(use_project_api_keys=True)

# Authentication setup
security = HTTPBearer()

def load_auth_tokens() -> List[str]:
    """Load whitelisted authentication tokens from auth_tokens.json"""
    try:
        auth_file = Path(__file__).parent / "auth_tokens.json"
        if auth_file.exists():
            with open(auth_file, 'r', encoding='utf-8') as f:
                auth_data = json.load(f)
                return auth_data.get("tokens", [])
        else:
            logger.warning(f"Auth tokens file not found: {auth_file}")
            return []
    except Exception as e:
        logger.error(f"Failed to load auth tokens: {e}")
        return []

# Load authorized tokens
AUTHORIZED_TOKENS = load_auth_tokens()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the provided authentication token"""
    if not AUTHORIZED_TOKENS:
        logger.warning("No authorized tokens configured - allowing all requests")
        return credentials.credentials
    
    if credentials.credentials not in AUTHORIZED_TOKENS:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

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
                        output_file = output_dir / f"translated_{input_file.name}"
                        
                        success = translator.translate_pptx(
                            input_file, output_file, source_lang, target_lang
                        )
                        
                        if success:
                            result_files.append(str(output_file))
                        else:
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
            "list_tasks": "/tasks",
            "cleanup_task": "/tasks/{task_id}"
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
    import zipfile
    import io
    
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

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )