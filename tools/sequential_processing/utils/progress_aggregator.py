"""Progress Aggregator for Sequential Processing."""

import logging
import time
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of a processing task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskProgress:
    """Progress information for a single task."""
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0.0 to 100.0
    message: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None


class ProgressAggregator:
    """Aggregates progress from multiple processing tasks."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the progress aggregator.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback or (lambda x: None)
        self.tasks: Dict[str, TaskProgress] = {}
        self.total_languages = 0
        self.total_folders = 0
        self.current_language = None
        self.current_folder = None
        self.start_time = None
    
    def initialize(self, languages: List[str], folders: int):
        """
        Initialize progress tracking for a processing session.
        
        Args:
            languages: List of target languages
            folders: Number of folders to process
        """
        self.total_languages = len(languages)
        self.total_folders = folders
        self.start_time = time.time()
        
        # Create tasks for each language/folder combination
        for lang in languages:
            for i in range(folders):
                task_id = f"{lang}_folder_{i}"
                self.tasks[task_id] = TaskProgress(name=task_id)
        
        self.progress_callback(
            f"📋 Initialized processing: {self.total_languages} languages, "
            f"{self.total_folders} folders"
        )
    
    def start_language(self, language: str):
        """Mark the start of processing for a language."""
        self.current_language = language
        self.current_folder = 0
        self.progress_callback(f"\n🌐 Processing language: {language}")
    
    def start_folder(self, folder_name: str):
        """Mark the start of processing for a folder."""
        task_id = f"{self.current_language}_folder_{self.current_folder}"
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.IN_PROGRESS
            task.start_time = time.time()
            task.message = f"Processing {folder_name}"
        
        self.progress_callback(f"📂 Processing folder: {folder_name}")
    
    def update_task(self, step: str, progress: float, message: str = ""):
        """
        Update progress for the current task.
        
        Args:
            step: Current processing step
            progress: Progress percentage (0-100)
            message: Optional status message
        """
        task_id = f"{self.current_language}_folder_{self.current_folder}"
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.progress = progress
            task.message = f"{step}: {message}" if message else step
        
        # Report overall progress
        overall = self.get_overall_progress()
        self.progress_callback(
            f"[{overall:.1f}%] {step}: {message}" if message else f"[{overall:.1f}%] {step}"
        )
    
    def complete_folder(self, success: bool = True, error: Optional[str] = None):
        """Mark the completion of a folder."""
        task_id = f"{self.current_language}_folder_{self.current_folder}"
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            task.progress = 100.0 if success else task.progress
            task.end_time = time.time()
            task.error = error
            
            status_icon = "✅" if success else "❌"
            self.progress_callback(f"{status_icon} Folder completed")
        
        self.current_folder += 1
    
    def get_overall_progress(self) -> float:
        """
        Calculate overall progress percentage.
        
        Returns:
            Overall progress (0-100)
        """
        if not self.tasks:
            return 0.0
        
        total_progress = sum(task.progress for task in self.tasks.values())
        return total_progress / len(self.tasks)
    
    def get_status_summary(self) -> Dict[str, int]:
        """
        Get summary of task statuses.
        
        Returns:
            Dictionary with count of tasks in each status
        """
        summary = {
            TaskStatus.PENDING: 0,
            TaskStatus.IN_PROGRESS: 0,
            TaskStatus.COMPLETED: 0,
            TaskStatus.FAILED: 0,
            TaskStatus.SKIPPED: 0
        }
        
        for task in self.tasks.values():
            summary[task.status] += 1
        
        return summary
    
    def get_time_estimate(self) -> str:
        """
        Estimate remaining time based on current progress.
        
        Returns:
            Formatted time estimate string
        """
        if not self.start_time:
            return "Unknown"
        
        elapsed = time.time() - self.start_time
        progress = self.get_overall_progress()
        
        if progress <= 0:
            return "Calculating..."
        
        # Estimate total time based on current progress
        total_estimated = elapsed / (progress / 100.0)
        remaining = total_estimated - elapsed
        
        if remaining < 60:
            return f"{int(remaining)}s"
        elif remaining < 3600:
            return f"{int(remaining / 60)}m {int(remaining % 60)}s"
        else:
            hours = int(remaining / 3600)
            minutes = int((remaining % 3600) / 60)
            return f"{hours}h {minutes}m"
    
    def get_final_report(self) -> str:
        """
        Generate final processing report.
        
        Returns:
            Formatted report string
        """
        if not self.start_time:
            return "No processing data available"
        
        elapsed = time.time() - self.start_time
        status_summary = self.get_status_summary()
        
        report = f"""
╔══════════════════════════════════════╗
║       PROCESSING COMPLETE            ║
╚══════════════════════════════════════╝

⏱️ Total Time: {self._format_duration(elapsed)}
📊 Overall Progress: {self.get_overall_progress():.1f}%

📈 Task Summary:
  ✅ Completed: {status_summary[TaskStatus.COMPLETED]}
  ❌ Failed: {status_summary[TaskStatus.FAILED]}
  ⏭️ Skipped: {status_summary[TaskStatus.SKIPPED]}
  ⏸️ Pending: {status_summary[TaskStatus.PENDING]}

🌐 Languages Processed: {self.total_languages}
📁 Folders Processed: {self.total_folders}
"""
        
        # Add error details if any
        failed_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.FAILED]
        if failed_tasks:
            report += "\n⚠️ Failed Tasks:\n"
            for task in failed_tasks:
                report += f"  • {task.name}: {task.error or 'Unknown error'}\n"
        
        return report
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            seconds = int(seconds % 60)
            return f"{hours}h {minutes}m {seconds}s"