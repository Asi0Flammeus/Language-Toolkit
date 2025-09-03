"""Core Tool Adapters for Sequential Processing."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List


class CoreToolAdapter(ABC):
    """Abstract base class for core tool adapters."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the core tool adapter.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback or (lambda x: None)
        self.tool = None
    
    @abstractmethod
    def process(self, input_path: Path, output_path: Path, params: Dict[str, Any]) -> Any:
        """
        Process the input file/directory with the core tool.
        
        Args:
            input_path: Path to input file or directory
            output_path: Path to output location
            params: Processing parameters
            
        Returns:
            Processing result (varies by tool)
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_path: Path) -> bool:
        """
        Validate if the input is suitable for this tool.
        
        Args:
            input_path: Path to validate
            
        Returns:
            True if input is valid, False otherwise
        """
        pass
    
    def report_progress(self, message: str):
        """Report progress to callback."""
        if self.progress_callback:
            self.progress_callback(message)