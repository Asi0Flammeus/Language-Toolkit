"""
Unified task and progress management for Language Toolkit.
Provides consistent task lifecycle management across GUI and API applications.
"""

import logging
import threading
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import queue

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """Enumeration of possible task states"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    """
    Represents a single processing task with progress tracking and lifecycle management.
    """
    
    def __init__(self, task_id: str):
        self.id = task_id
        self.status = TaskStatus.PENDING
        self.messages: List[str] = []
        self.progress: Optional[float] = None  # 0.0 to 1.0 for percentage
        self.error: Optional[str] = None
        self.result_files: List[str] = []
        self.metadata: Dict[str, Any] = {}  # For additional task-specific data
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Cancellation support
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        
    def update_status(self, status: TaskStatus) -> None:
        """Update task status and timestamp"""
        self.status = status
        self.updated_at = datetime.now()
        logger.debug(f"Task {self.id} status updated to: {status.value}")
        
    def add_message(self, message: str) -> None:
        """Add a progress message"""
        self.messages.append(message)
        self.updated_at = datetime.now()
        logger.debug(f"Task {self.id} message: {message}")
        
    def set_progress(self, progress: float) -> None:
        """Set progress percentage (0.0 to 1.0)"""
        self.progress = max(0.0, min(1.0, progress))
        self.updated_at = datetime.now()
        
    def set_error(self, error: str) -> None:
        """Set error message and update status to failed"""
        self.error = error
        self.update_status(TaskStatus.FAILED)
        logger.error(f"Task {self.id} failed: {error}")
        
    def add_result_file(self, file_path: str) -> None:
        """Add a result file path"""
        self.result_files.append(file_path)
        self.updated_at = datetime.now()
        
    def request_stop(self) -> None:
        """Request task cancellation"""
        self._stop_event.set()
        logger.info(f"Stop requested for task {self.id}")
        
    def is_stop_requested(self) -> bool:
        """Check if stop has been requested"""
        return self._stop_event.is_set()
        
    def clear_stop(self) -> None:
        """Clear the stop request (used when starting new processing)"""
        self._stop_event.clear()
        
    def set_thread(self, thread: threading.Thread) -> None:
        """Set the processing thread reference"""
        self._thread = thread
        
    def get_thread(self) -> Optional[threading.Thread]:
        """Get the processing thread reference"""
        return self._thread
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation"""
        return {
            "task_id": self.id,
            "status": self.status.value,
            "messages": self.messages.copy(),
            "progress": self.progress,
            "error": self.error,
            "result_files": self.result_files.copy(),
            "metadata": self.metadata.copy(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class ProgressCallback:
    """
    Progress callback function that can be used by core modules.
    Provides a consistent interface while supporting different backends.
    """
    
    def __init__(self, task_id: str, task_manager: 'TaskManager'):
        self.task_id = task_id
        self.task_manager = task_manager
        
    def __call__(self, message: str, progress: Optional[float] = None) -> None:
        """
        Send a progress update.
        
        Args:
            message: Progress message
            progress: Optional progress percentage (0.0 to 1.0)
        """
        self.task_manager.add_progress_message(self.task_id, message)
        if progress is not None:
            self.task_manager.set_progress(self.task_id, progress)

class TaskManager:
    """
    Centralized task management system supporting both GUI and API applications.
    """
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._lock = threading.RLock()  # Thread-safe operations
        
        # Optional adapters for different progress reporting systems
        self._progress_adapters: List['ProgressAdapter'] = []
        
    def create_task(self, task_id: Optional[str] = None) -> Task:
        """
        Create and register a new task.
        
        Args:
            task_id: Optional task ID, generates UUID if not provided
            
        Returns:
            Created Task instance
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
            
        with self._lock:
            if task_id in self.tasks:
                raise ValueError(f"Task {task_id} already exists")
                
            task = Task(task_id)
            self.tasks[task_id] = task
            logger.info(f"Created task {task_id}")
            
            # Notify adapters
            for adapter in self._progress_adapters:
                adapter.on_task_created(task)
                
            return task
            
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        with self._lock:
            return self.tasks.get(task_id)
            
    def update_status(self, task_id: str, status: TaskStatus) -> None:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                old_status = task.status
                task.update_status(status)
                
                # Notify adapters
                for adapter in self._progress_adapters:
                    adapter.on_status_change(task, old_status, status)
                    
    def add_progress_message(self, task_id: str, message: str) -> None:
        """
        Add a progress message to a task.
        
        Args:
            task_id: Task ID
            message: Progress message
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.add_message(message)
                
                # Notify adapters
                for adapter in self._progress_adapters:
                    adapter.on_progress_message(task, message)
                    
    def set_progress(self, task_id: str, progress: float) -> None:
        """
        Set task progress percentage.
        
        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                old_progress = task.progress
                task.set_progress(progress)
                
                # Notify adapters
                for adapter in self._progress_adapters:
                    adapter.on_progress_update(task, old_progress, progress)
                    
    def set_error(self, task_id: str, error: str) -> None:
        """
        Set task error and mark as failed.
        
        Args:
            task_id: Task ID
            error: Error message
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.set_error(error)
                
                # Notify adapters
                for adapter in self._progress_adapters:
                    adapter.on_error(task, error)
                    
    def add_result_file(self, task_id: str, file_path: str) -> None:
        """Add a result file to a task"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.add_result_file(file_path)
                
    def request_stop(self, task_id: str) -> None:
        """Request task cancellation"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.request_stop()
                
                # Notify adapters
                for adapter in self._progress_adapters:
                    adapter.on_stop_requested(task)
                    
    def is_stop_requested(self, task_id: str) -> bool:
        """Check if stop has been requested for a task"""
        with self._lock:
            task = self.tasks.get(task_id)
            return task.is_stop_requested() if task else False
            
    def get_progress_callback(self, task_id: str) -> ProgressCallback:
        """
        Get a progress callback function for a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            ProgressCallback instance that can be passed to core modules
        """
        return ProgressCallback(task_id, self)
        
    def cleanup_task(self, task_id: str) -> None:
        """
        Remove a task from the manager.
        
        Args:
            task_id: Task ID to remove
        """
        with self._lock:
            task = self.tasks.pop(task_id, None)
            if task:
                logger.info(f"Cleaned up task {task_id}")
                
                # Notify adapters
                for adapter in self._progress_adapters:
                    adapter.on_task_cleanup(task)
                    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks"""
        with self._lock:
            return list(self.tasks.values())
            
    def get_active_tasks(self) -> List[Task]:
        """Get all active (pending or running) tasks"""
        with self._lock:
            return [task for task in self.tasks.values() 
                   if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
                   
    def add_progress_adapter(self, adapter: 'ProgressAdapter') -> None:
        """Add a progress adapter for custom progress reporting"""
        self._progress_adapters.append(adapter)
        
    def remove_progress_adapter(self, adapter: 'ProgressAdapter') -> None:
        """Remove a progress adapter"""
        if adapter in self._progress_adapters:
            self._progress_adapters.remove(adapter)

class ProgressAdapter:
    """
    Base class for progress adapters that integrate with different UI systems.
    """
    
    def on_task_created(self, task: Task) -> None:
        """Called when a new task is created"""
        pass
        
    def on_status_change(self, task: Task, old_status: TaskStatus, new_status: TaskStatus) -> None:
        """Called when task status changes"""
        pass
        
    def on_progress_message(self, task: Task, message: str) -> None:
        """Called when a progress message is added"""
        pass
        
    def on_progress_update(self, task: Task, old_progress: Optional[float], new_progress: float) -> None:
        """Called when progress percentage is updated"""
        pass
        
    def on_error(self, task: Task, error: str) -> None:
        """Called when a task error occurs"""
        pass
        
    def on_stop_requested(self, task: Task) -> None:
        """Called when task cancellation is requested"""
        pass
        
    def on_task_cleanup(self, task: Task) -> None:
        """Called when a task is cleaned up"""
        pass

class QueueProgressAdapter(ProgressAdapter):
    """
    Progress adapter for GUI applications using a queue.Queue for progress reporting.
    """
    
    def __init__(self, progress_queue: queue.Queue):
        self.progress_queue = progress_queue
        
    def on_progress_message(self, task: Task, message: str) -> None:
        """Send progress message to queue"""
        try:
            self.progress_queue.put(message)
        except Exception as e:
            logger.error(f"Failed to send progress message to queue: {e}")
            
    def on_error(self, task: Task, error: str) -> None:
        """Send error message to queue"""
        try:
            self.progress_queue.put(f"ERROR: {error}")
        except Exception as e:
            logger.error(f"Failed to send error message to queue: {e}")

class DictProgressAdapter(ProgressAdapter):
    """
    Progress adapter for API applications using a dictionary for task storage.
    Maintains compatibility with the existing active_tasks pattern.
    """
    
    def __init__(self, active_tasks: Dict[str, Dict]):
        self.active_tasks = active_tasks
        
    def on_task_created(self, task: Task) -> None:
        """Initialize task entry in active_tasks dictionary"""
        self.active_tasks[task.id] = {
            "status": task.status.value,
            "messages": [],
            "progress": task.progress,
            "error": task.error,
            "result_files": task.result_files.copy(),
            "manifest": task.metadata.get("manifest"),
            "source_lang": task.metadata.get("source_lang"),
            "temp_dir": task.metadata.get("temp_dir"),
            "input_files": task.metadata.get("input_files"),
            "output_dir": task.metadata.get("output_dir")
        }
        
    def on_status_change(self, task: Task, old_status: TaskStatus, new_status: TaskStatus) -> None:
        """Update status in active_tasks dictionary"""
        if task.id in self.active_tasks:
            self.active_tasks[task.id]["status"] = new_status.value
            
    def on_progress_message(self, task: Task, message: str) -> None:
        """Add message to active_tasks dictionary"""
        if task.id in self.active_tasks:
            self.active_tasks[task.id]["messages"].append(message)
            
    def on_error(self, task: Task, error: str) -> None:
        """Set error in active_tasks dictionary"""
        if task.id in self.active_tasks:
            self.active_tasks[task.id]["error"] = error
            
    def on_task_cleanup(self, task: Task) -> None:
        """Remove task from active_tasks dictionary"""
        self.active_tasks.pop(task.id, None)

# Global task manager instance
_global_task_manager: Optional[TaskManager] = None

def get_task_manager() -> TaskManager:
    """Get the global task manager instance"""
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = TaskManager()
    return _global_task_manager

def set_task_manager(task_manager: TaskManager) -> None:
    """Set the global task manager instance"""
    global _global_task_manager
    _global_task_manager = task_manager