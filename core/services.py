"""
Service management utilities for Language Toolkit.
Provides centralized API service initialization and management across GUI and API applications.
"""

import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union, List

logger = logging.getLogger(__name__)

# Service type variable for type safety
T = TypeVar('T')

class ServiceType(Enum):
    """Enumeration of supported service types"""
    DEEPL = "deepl"
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    CONVERTAPI = "convertapi"

class APIKeyError(Exception):
    """Exception raised when API key is missing or invalid"""
    def __init__(self, service: str, message: Optional[str] = None):
        self.service = service
        if message is None:
            message = f"{service} API key not configured. Please add your API key in the Configuration menu."
        super().__init__(message)

class ServiceError(Exception):
    """Exception raised when service initialization fails"""
    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(f"Failed to initialize {service} service: {message}")

class ServiceManager:
    """
    Centralized service management for API integrations.
    
    Provides consistent API key retrieval, service initialization, and error handling
    across the Language Toolkit application.
    
    Features:
        - Centralized API key management
        - Consistent error handling and messaging
        - Type-safe service creation
        - Progress callback support
        - Service validation and health checking
        - Lazy service initialization
    
    Example usage:
        # Basic service creation
        service_manager = ServiceManager(config_manager)
        translator = service_manager.get_service(
            ServiceType.DEEPL, 
            PPTXTranslationCore,
            progress_callback=my_callback
        )
        
        # Helper methods for common services
        translator = service_manager.get_deepl_translator(progress_callback)
        transcriber = service_manager.get_openai_transcriber(progress_callback)
        
        # Validate all configured services
        service_manager.validate_all_services()
    """
    
    # Mapping of service types to API key names in configuration
    SERVICE_KEY_MAPPING = {
        ServiceType.DEEPL: "deepl",
        ServiceType.OPENAI: "openai", 
        ServiceType.ELEVENLABS: "elevenlabs",
        ServiceType.CONVERTAPI: "convertapi"
    }
    
    def __init__(self, config_manager):
        """
        Initialize ServiceManager with configuration.
        
        Args:
            config_manager: ConfigManager instance for API key retrieval
        """
        self.config_manager = config_manager
        self._api_keys_cache: Optional[Dict[str, str]] = None
        
    def _get_api_keys(self) -> Dict[str, str]:
        """Get API keys with caching"""
        if self._api_keys_cache is None:
            self._api_keys_cache = self.config_manager.get_api_keys()
        return self._api_keys_cache
    
    def _invalidate_api_keys_cache(self) -> None:
        """Invalidate the API keys cache"""
        self._api_keys_cache = None
        
    def get_api_key(self, service: Union[ServiceType, str]) -> str:
        """
        Get API key for a specific service.
        
        Args:
            service: Service type or service name string
            
        Returns:
            API key string
            
        Raises:
            APIKeyError: If API key is not configured
        """
        if isinstance(service, ServiceType):
            key_name = self.SERVICE_KEY_MAPPING[service]
            service_name = service.value
        else:
            key_name = service
            service_name = service
            
        api_keys = self._get_api_keys()
        api_key = api_keys.get(key_name)
        
        if not api_key:
            raise APIKeyError(service_name)
            
        return api_key
    
    def has_api_key(self, service: Union[ServiceType, str]) -> bool:
        """
        Check if API key is configured for a service.
        
        Args:
            service: Service type or service name string
            
        Returns:
            True if API key is configured, False otherwise
        """
        try:
            self.get_api_key(service)
            return True
        except APIKeyError:
            return False
    
    def get_service(self, 
                   service_type: ServiceType,
                   service_class: Type[T],
                   progress_callback: Optional[Callable[[str], None]] = None,
                   **kwargs) -> T:
        """
        Create and initialize a service instance.
        
        Args:
            service_type: Type of service to create
            service_class: Service class to instantiate
            progress_callback: Optional progress callback function
            **kwargs: Additional arguments to pass to service constructor
            
        Returns:
            Initialized service instance
            
        Raises:
            APIKeyError: If API key is not configured
            ServiceError: If service initialization fails
        """
        try:
            api_key = self.get_api_key(service_type)
            
            # Build constructor arguments
            init_kwargs = {"api_key": api_key}
            if progress_callback is not None:
                init_kwargs["progress_callback"] = progress_callback
            init_kwargs.update(kwargs)
            
            # Create service instance
            service = service_class(**init_kwargs)
            
            logger.debug(f"Initialized {service_type.value} service: {service_class.__name__}")
            return service
            
        except APIKeyError:
            raise
        except Exception as e:
            raise ServiceError(service_type.value, str(e))
    
    def get_deepl_service(self, 
                         service_class: Type[T],
                         progress_callback: Optional[Callable[[str], None]] = None) -> T:
        """
        Helper method to create DeepL-based services.
        
        Args:
            service_class: DeepL service class (e.g., PPTXTranslationCore, TextTranslationCore)
            progress_callback: Optional progress callback
            
        Returns:
            Initialized DeepL service
        """
        return self.get_service(ServiceType.DEEPL, service_class, progress_callback)
    
    def get_openai_service(self,
                          service_class: Type[T], 
                          progress_callback: Optional[Callable[[str], None]] = None) -> T:
        """
        Helper method to create OpenAI-based services.
        
        Args:
            service_class: OpenAI service class (e.g., AudioTranscriptionCore)
            progress_callback: Optional progress callback
            
        Returns:
            Initialized OpenAI service
        """
        return self.get_service(ServiceType.OPENAI, service_class, progress_callback)
    
    def get_elevenlabs_service(self,
                              service_class: Type[T],
                              progress_callback: Optional[Callable[[str], None]] = None) -> T:
        """
        Helper method to create ElevenLabs-based services.
        
        Args:
            service_class: ElevenLabs service class (e.g., TextToSpeechCore)
            progress_callback: Optional progress callback
            
        Returns:
            Initialized ElevenLabs service
        """
        return self.get_service(ServiceType.ELEVENLABS, service_class, progress_callback)
    
    def get_convertapi_service(self,
                              service_class: Type[T],
                              progress_callback: Optional[Callable[[str], None]] = None) -> T:
        """
        Helper method to create ConvertAPI-based services.
        
        Args:
            service_class: ConvertAPI service class (e.g., PPTXConverterCore)
            progress_callback: Optional progress callback
            
        Returns:
            Initialized ConvertAPI service
        """
        return self.get_service(ServiceType.CONVERTAPI, service_class, progress_callback)
    
    def validate_service(self, service_type: ServiceType) -> bool:
        """
        Validate that a service can be initialized.
        
        Args:
            service_type: Service type to validate
            
        Returns:
            True if service is valid, False otherwise
        """
        try:
            self.get_api_key(service_type)
            return True
        except APIKeyError:
            return False
    
    def validate_all_services(self) -> Dict[ServiceType, bool]:
        """
        Validate all services and return their status.
        
        Returns:
            Dictionary mapping service types to their validation status
        """
        results = {}
        for service_type in ServiceType:
            results[service_type] = self.validate_service(service_type)
        return results
    
    def get_missing_services(self) -> List[ServiceType]:
        """
        Get list of services with missing API keys.
        
        Returns:
            List of service types with missing API keys
        """
        missing = []
        for service_type in ServiceType:
            if not self.validate_service(service_type):
                missing.append(service_type)
        return missing
    
    def get_configured_services(self) -> List[ServiceType]:
        """
        Get list of services with configured API keys.
        
        Returns:
            List of service types with configured API keys
        """
        configured = []
        for service_type in ServiceType:
            if self.validate_service(service_type):
                configured.append(service_type)
        return configured
    
    def refresh_api_keys(self) -> None:
        """
        Refresh API keys cache from configuration.
        
        Useful when configuration has been updated and services need to reload keys.
        """
        self._invalidate_api_keys_cache()
        logger.debug("API keys cache refreshed")

# Convenience functions for commonly used services
def create_service_manager(config_manager) -> ServiceManager:
    """
    Create a ServiceManager instance.
    
    Args:
        config_manager: ConfigManager instance
        
    Returns:
        ServiceManager instance
    """
    return ServiceManager(config_manager)

def get_service_display_name(service_type: ServiceType) -> str:
    """
    Get user-friendly display name for a service.
    
    Args:
        service_type: Service type
        
    Returns:
        User-friendly service name
    """
    display_names = {
        ServiceType.DEEPL: "DeepL Translation",
        ServiceType.OPENAI: "OpenAI (Whisper)",
        ServiceType.ELEVENLABS: "ElevenLabs Text-to-Speech",
        ServiceType.CONVERTAPI: "ConvertAPI"
    }
    return display_names.get(service_type, service_type.value.title())

def get_service_setup_help(service_type: ServiceType) -> str:
    """
    Get setup help text for a service.
    
    Args:
        service_type: Service type
        
    Returns:
        Help text for setting up the service
    """
    help_text = {
        ServiceType.DEEPL: "Visit https://www.deepl.com/pro-api to get your DeepL API key",
        ServiceType.OPENAI: "Visit https://platform.openai.com/api-keys to get your OpenAI API key",
        ServiceType.ELEVENLABS: "Visit https://elevenlabs.io/app/speech-synthesis to get your ElevenLabs API key",
        ServiceType.CONVERTAPI: "Visit https://www.convertapi.com/user to get your ConvertAPI secret"
    }
    return help_text.get(service_type, f"Configure your {service_type.value} API key")

# Exception handling decorators
def handle_service_errors(func):
    """
    Decorator to handle common service errors and provide user-friendly messages.
    
    Usage:
        @handle_service_errors
        def my_service_function():
            # Service code that might raise APIKeyError or ServiceError
            pass
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIKeyError as e:
            logger.error(f"API key error in {func.__name__}: {e}")
            raise
        except ServiceError as e:
            logger.error(f"Service error in {func.__name__}: {e}")
            raise
        except Exception as e:
            # Convert unexpected errors to ServiceError for consistency
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise ServiceError("unknown", str(e))
    return wrapper