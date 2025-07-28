"""
Example: Migrating to core/services.py

This file demonstrates how the new ServiceManager would simplify code in main.py and api_server.py
"""

# ==================== BEFORE (Current Pattern) ====================

# In main.py (TextToSpeechTool.process_file):
def process_file_old(self, file_path):
    # Get API key
    api_key = self.config_manager.get_api_keys().get("elevenlabs")
    if not api_key:
        raise ValueError("ElevenLabs API key not configured. Please add your API key in the Configuration menu.")
    
    # Initialize core TTS module
    from core.text_to_speech import TextToSpeechCore
    tts_core = TextToSpeechCore(api_key=api_key, progress_callback=progress_callback)
    
    # Use the core module to process the file
    return tts_core.process_file(file_path)

# In api_server.py (process_tool):
def process_tool_old(tool_class, *args, **kwargs):
    # Get API keys
    api_keys = config_manager.get_api_keys()
    
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
    # ... and so on for each service


# ==================== AFTER (Using ServiceManager) ====================

from core.services import ServiceManager, ServiceType, APIKeyError

# In main.py (TextToSpeechTool.__init__):
def __init__(self, master, config_manager):
    super().__init__(master, config_manager)
    self.service_manager = ServiceManager(config_manager)
    
    # Check if service is available early
    if not self.service_manager.is_service_available(ServiceType.ELEVENLABS):
        logging.warning("ElevenLabs API key not configured")

# In main.py (TextToSpeechTool.process_file):
def process_file_new(self, file_path):
    try:
        # Single line to get initialized service
        tts_core = self.service_manager.create_text_to_speech(
            progress_callback=self.send_progress_update
        )
        
        # Use the core module to process the file
        return tts_core.process_file(file_path)
    
    except APIKeyError as e:
        # Consistent error handling
        raise ValueError(str(e))

# In api_server.py (simplified process_tool):
def process_tool_new(tool_class, *args, **kwargs):
    service_manager = ServiceManager(config_manager)
    
    try:
        # Single method handles all service types
        tool = service_manager.get_service(
            tool_class,
            progress_callback=progress_callback
        )
        return tool.process(*args, **kwargs)
    
    except APIKeyError as e:
        raise ValueError(str(e))

# In api_server.py (health checks become much simpler):
async def check_deepl_health_new():
    """Check DeepL API key validity and quota"""
    service_manager = ServiceManager(config_manager)
    
    if not service_manager.is_service_available(ServiceType.DEEPL):
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": "DeepL API key not configured"
        }
    
    try:
        # Get service and test it
        translator = service_manager.create_text_translator()
        # ... rest of health check logic
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": str(e)
        }

# Additional benefits:

# 1. Easy service validation in configuration UI
def validate_api_keys(self):
    """Validate all configured API keys"""
    service_manager = ServiceManager(self.config_manager)
    
    # Get validation status for all services
    validation_results = service_manager.validate_all_services()
    
    # Show which services are missing
    missing_services = service_manager.get_missing_services()
    if missing_services:
        messagebox.showwarning(
            "Missing API Keys",
            f"The following services are not configured: {', '.join(missing_services)}"
        )

# 2. Batch service initialization for complex operations
def initialize_all_services(config_manager):
    """Initialize all required services at startup"""
    service_manager = ServiceManager(config_manager)
    
    services = {
        'translator': None,
        'transcriber': None,
        'tts': None,
        'converter': None
    }
    
    # Try to initialize each service
    if service_manager.is_service_available(ServiceType.DEEPL):
        services['translator'] = service_manager.create_text_translator()
    
    if service_manager.is_service_available(ServiceType.OPENAI):
        services['transcriber'] = service_manager.create_audio_transcriber()
    
    # ... etc
    
    return services

# 3. Centralized error messages
# Instead of different error messages in each file, we get consistent messages:
# - "DeepL API key not configured. Please add your API key in the Configuration menu."
# - "OpenAI API key not configured. Please add your API key in the Configuration menu."
# etc.