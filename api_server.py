"""
FastAPI server for Language Toolkit API
Provides REST endpoints for all language processing tools
"""

import asyncio
import logging
import queue
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union
import tempfile
import shutil
import os

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

# Import our existing tools
from main import (
    ConfigManager, 
    PPTXTranslationTool, 
    AudioTranscriptionTool, 
    TextTranslationTool, 
    PPTXtoPDFTool,
    TextToSpeechTool,
    VideoMergeTool,
    SequentialProcessingTool
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Language Toolkit API",
    description="API for document processing, translation, transcription, and video creation",
    version="1.0.0"
)

# Global task storage
active_tasks: Dict[str, Dict] = {}
config_manager = ConfigManager()

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

async def run_tool_async(tool_class, task_id: str, input_files: List[Path], 
                        output_dir: Path, **kwargs):
    """Run a tool asynchronously"""
    try:
        # Update task status
        active_tasks[task_id]["status"] = "running"
        
        # Create progress queue
        progress_queue = TaskProgressQueue()
        
        # Initialize tool
        tool = tool_class(
            master=None,  # No GUI needed
            config_manager=config_manager,
            progress_queue=progress_queue
        )
        
        # Set tool parameters
        for key, value in kwargs.items():
            if hasattr(tool, key):
                getattr(tool, key).set(value)
        
        # Set input paths and output path
        tool.input_paths = input_files
        tool.output_path = output_dir
        
        # Run processing in thread
        def process_files():
            try:
                tool.before_processing()
                
                for input_file in input_files:
                    if input_file.is_file():
                        tool.process_file(input_file, output_dir)
                
                tool.after_processing()
                
                # Update task with results
                result_files = list(output_dir.glob("*"))
                active_tasks[task_id]["status"] = "completed"
                active_tasks[task_id]["result_files"] = [str(f) for f in result_files]
                
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
            # Update progress
            messages = progress_queue.get_all_messages()
            if messages:
                active_tasks[task_id]["progress"] = messages[-1]
        
        thread.join()
        
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
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
            "sequential_process": "/process/sequential",
            "task_status": "/tasks/{task_id}",
            "download_result": "/download/{task_id}"
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
    files: List[UploadFile] = File(...)
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
        "output_dir": output_dir
    }
    
    # Start background task
    background_tasks.add_task(
        run_tool_async,
        PPTXTranslationTool,
        task_id,
        input_files,
        output_dir,
        source_lang=source_lang,
        target_lang=target_lang
    )
    
    return TaskStatus(task_id=task_id, status="pending")

@app.post("/translate/text", response_model=TaskStatus)
async def translate_text(
    background_tasks: BackgroundTasks,
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    files: List[UploadFile] = File(...)
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
        "output_dir": output_dir
    }
    
    # Start background task
    background_tasks.add_task(
        run_tool_async,
        TextTranslationTool,
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
    files: List[UploadFile] = File(...)
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
        "output_dir": output_dir
    }
    
    # Start background task
    background_tasks.add_task(
        run_tool_async,
        AudioTranscriptionTool,
        task_id,
        input_files,
        output_dir
    )
    
    return TaskStatus(task_id=task_id, status="pending")

@app.post("/convert/pptx", response_model=TaskStatus)
async def convert_pptx(
    background_tasks: BackgroundTasks,
    output_format: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """Convert PPTX files to PDF or PNG"""
    if output_format not in ["pdf", "png"]:
        raise HTTPException(status_code=400, detail="Output format must be 'pdf' or 'png'")
    
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
        "output_dir": output_dir
    }
    
    # Start background task
    background_tasks.add_task(
        run_tool_async,
        PPTXtoPDFTool,
        task_id,
        input_files,
        output_dir,
        output_format=output_format
    )
    
    return TaskStatus(task_id=task_id, status="pending")

@app.post("/tts", response_model=TaskStatus)
async def text_to_speech(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
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
        "output_dir": output_dir
    }
    
    # Start background task
    background_tasks.add_task(
        run_tool_async,
        TextToSpeechTool,
        task_id,
        input_files,
        output_dir
    )
    
    return TaskStatus(task_id=task_id, status="pending")

@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
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
async def download_results(task_id: str):
    """Download the results of a completed task"""
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = active_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    
    result_files = task.get("result_files", [])
    if not result_files:
        raise HTTPException(status_code=404, detail="No result files found")
    
    # If single file, return it directly
    if len(result_files) == 1:
        file_path = Path(result_files[0])
        if file_path.exists():
            return FileResponse(
                path=str(file_path),
                filename=file_path.name,
                media_type='application/octet-stream'
            )
    
    # Multiple files: create zip archive
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_path_str in result_files:
            file_path = Path(file_path_str)
            if file_path.exists() and file_path.is_file():
                zip_file.write(file_path, file_path.name)
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        io.BytesIO(zip_buffer.read()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=results_{task_id}.zip"}
    )

@app.delete("/tasks/{task_id}")
async def cleanup_task(task_id: str):
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
async def list_tasks():
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