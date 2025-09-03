"""Error Handler for Sequential Processing."""

import logging
import traceback
from typing import Optional, Callable, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categories of errors for better organization."""
    API_ERROR = "api_error"
    FILE_ERROR = "file_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    PROCESSING_ERROR = "processing_error"
    CONFIGURATION_ERROR = "configuration_error"


@dataclass
class ErrorInfo:
    """Information about an error."""
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    details: Optional[str] = None
    file_path: Optional[str] = None
    recovery_action: Optional[str] = None
    exception: Optional[Exception] = None


class ErrorHandler:
    """Comprehensive error handling for sequential processing."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize error handler.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback or (lambda x: None)
        self.errors = []
        self.warnings = []
        self.retry_counts = {}
        self.max_retries = 3
    
    def handle_error(self, error: Exception, context: str, 
                    category: ErrorCategory = ErrorCategory.PROCESSING_ERROR,
                    file_path: Optional[str] = None,
                    retry_key: Optional[str] = None) -> bool:
        """
        Handle an error with appropriate logging and recovery.
        
        Args:
            error: The exception that occurred
            context: Context where error occurred
            category: Category of the error
            file_path: Optional file path related to error
            retry_key: Optional key for retry tracking
            
        Returns:
            True if should retry, False otherwise
        """
        # Log the error
        logger.exception(f"Error in {context}: {str(error)}")
        
        # Determine severity
        severity = self._determine_severity(error, category)
        
        # Create error info
        error_info = ErrorInfo(
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            message=f"{context}: {str(error)}",
            details=traceback.format_exc(),
            file_path=file_path,
            recovery_action=self._suggest_recovery(error, category),
            exception=error
        )
        
        # Store error
        if severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
            self.errors.append(error_info)
        else:
            self.warnings.append(error_info)
        
        # Report to user
        self._report_error(error_info)
        
        # Check if should retry
        if retry_key and severity != ErrorSeverity.CRITICAL:
            return self._should_retry(retry_key)
        
        return False
    
    def _determine_severity(self, error: Exception, 
                           category: ErrorCategory) -> ErrorSeverity:
        """Determine the severity of an error."""
        # Critical errors
        if isinstance(error, (MemoryError, SystemError)):
            return ErrorSeverity.CRITICAL
        
        # API errors
        if category == ErrorCategory.API_ERROR:
            if "quota" in str(error).lower() or "limit" in str(error).lower():
                return ErrorSeverity.CRITICAL
            elif "unauthorized" in str(error).lower() or "forbidden" in str(error).lower():
                return ErrorSeverity.CRITICAL
            else:
                return ErrorSeverity.ERROR
        
        # File errors
        if category == ErrorCategory.FILE_ERROR:
            if isinstance(error, PermissionError):
                return ErrorSeverity.CRITICAL
            elif isinstance(error, FileNotFoundError):
                return ErrorSeverity.WARNING
            else:
                return ErrorSeverity.ERROR
        
        # Network errors
        if category == ErrorCategory.NETWORK_ERROR:
            if "timeout" in str(error).lower():
                return ErrorSeverity.WARNING
            else:
                return ErrorSeverity.ERROR
        
        # Default
        return ErrorSeverity.ERROR
    
    def _suggest_recovery(self, error: Exception, 
                         category: ErrorCategory) -> str:
        """Suggest recovery action for an error."""
        error_str = str(error).lower()
        
        # API errors
        if category == ErrorCategory.API_ERROR:
            if "quota" in error_str or "limit" in error_str:
                return "Check API quota limits and try again later"
            elif "unauthorized" in error_str:
                return "Verify API key configuration in settings"
            elif "rate" in error_str:
                return "Reduce processing speed or wait before retrying"
        
        # File errors
        elif category == ErrorCategory.FILE_ERROR:
            if isinstance(error, PermissionError):
                return "Check file permissions and ensure write access"
            elif isinstance(error, FileNotFoundError):
                return "Verify input file exists and path is correct"
            elif "space" in error_str:
                return "Free up disk space and try again"
        
        # Network errors
        elif category == ErrorCategory.NETWORK_ERROR:
            if "timeout" in error_str:
                return "Check internet connection and retry"
            elif "connection" in error_str:
                return "Verify network connectivity and firewall settings"
        
        # Configuration errors
        elif category == ErrorCategory.CONFIGURATION_ERROR:
            return "Review configuration settings and API keys"
        
        # Default
        return "Review error details and check documentation"
    
    def _report_error(self, error_info: ErrorInfo):
        """Report error to user via progress callback."""
        icon = {
            ErrorSeverity.INFO: "ℹ️",
            ErrorSeverity.WARNING: "⚠️",
            ErrorSeverity.ERROR: "❌",
            ErrorSeverity.CRITICAL: "🚨"
        }[error_info.severity]
        
        message = f"{icon} {error_info.message}"
        
        if error_info.recovery_action:
            message += f"\n   💡 {error_info.recovery_action}"
        
        if error_info.file_path:
            message += f"\n   📄 File: {error_info.file_path}"
        
        self.progress_callback(message)
    
    def _should_retry(self, retry_key: str) -> bool:
        """Check if operation should be retried."""
        if retry_key not in self.retry_counts:
            self.retry_counts[retry_key] = 0
        
        self.retry_counts[retry_key] += 1
        
        if self.retry_counts[retry_key] <= self.max_retries:
            self.progress_callback(
                f"🔄 Retrying ({self.retry_counts[retry_key]}/{self.max_retries})..."
            )
            return True
        
        return False
    
    def get_error_summary(self) -> str:
        """Get summary of all errors."""
        if not self.errors and not self.warnings:
            return "✅ No errors encountered"
        
        summary = "\n📊 Error Summary:\n"
        
        if self.warnings:
            summary += f"⚠️ Warnings: {len(self.warnings)}\n"
            for warning in self.warnings[:5]:  # Show first 5
                summary += f"  • {warning.message}\n"
            if len(self.warnings) > 5:
                summary += f"  ... and {len(self.warnings) - 5} more\n"
        
        if self.errors:
            summary += f"❌ Errors: {len(self.errors)}\n"
            for error in self.errors[:5]:  # Show first 5
                summary += f"  • {error.message}\n"
            if len(self.errors) > 5:
                summary += f"  ... and {len(self.errors) - 5} more\n"
        
        return summary
    
    def export_error_log(self, output_path: str):
        """Export detailed error log to file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("Sequential Processing Error Log\n")
                f.write("=" * 50 + "\n\n")
                
                if self.warnings:
                    f.write("WARNINGS\n")
                    f.write("-" * 30 + "\n")
                    for warning in self.warnings:
                        f.write(f"\n[{warning.timestamp}] {warning.severity.value.upper()}\n")
                        f.write(f"Category: {warning.category.value}\n")
                        f.write(f"Message: {warning.message}\n")
                        if warning.file_path:
                            f.write(f"File: {warning.file_path}\n")
                        if warning.recovery_action:
                            f.write(f"Recovery: {warning.recovery_action}\n")
                        f.write("\n")
                
                if self.errors:
                    f.write("\nERRORS\n")
                    f.write("-" * 30 + "\n")
                    for error in self.errors:
                        f.write(f"\n[{error.timestamp}] {error.severity.value.upper()}\n")
                        f.write(f"Category: {error.category.value}\n")
                        f.write(f"Message: {error.message}\n")
                        if error.file_path:
                            f.write(f"File: {error.file_path}\n")
                        if error.recovery_action:
                            f.write(f"Recovery: {error.recovery_action}\n")
                        if error.details:
                            f.write(f"\nStack Trace:\n{error.details}\n")
                        f.write("\n")
                
                self.progress_callback(f"📝 Error log exported to: {output_path}")
                
        except Exception as e:
            logger.exception(f"Failed to export error log: {str(e)}")
            self.progress_callback(f"❌ Failed to export error log: {str(e)}")
    
    def clear(self):
        """Clear all errors and reset state."""
        self.errors.clear()
        self.warnings.clear()
        self.retry_counts.clear()