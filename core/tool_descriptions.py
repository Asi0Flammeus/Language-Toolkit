"""
Tool Descriptions for GUI Display

This module provides user-friendly descriptions for each tool that can be
displayed in tooltips, help sections, or information panels in the GUI.
"""

def get_tool_descriptions():
    """
    Get user-friendly descriptions for each tool.
    
    Returns:
        dict: Tool descriptions suitable for GUI display
    """
    return {
        "pptx_translation": {
            "title": "PPTX Translation",
            "description": "Translate PowerPoint presentations while preserving formatting and layout",
            "details": "Converts text content in slides, tables, and shapes to your target language using DeepL AI",
            "use_case": "Perfect for creating multilingual presentations or localizing business content"
        },
        
        "audio_transcription": {
            "title": "Audio Transcription", 
            "description": "Convert spoken audio files into accurate text transcripts",
            "details": "Uses OpenAI Whisper AI to transcribe speech from various audio formats",
            "use_case": "Ideal for meeting notes, interview transcripts, or accessibility documentation"
        },
        
        "text_translation": {
            "title": "Text Translation",
            "description": "Translate plain text files between multiple languages",
            "details": "High-quality translation of text documents using DeepL's advanced AI technology",
            "use_case": "Great for translating articles, documents, or any written content"
        },
        
        "pptx_to_pdf_png": {
            "title": "PPTX Export",
            "description": "Export PowerPoint presentations to PDF documents, PNG, or WEBP images",
            "details": "Creates high-quality PDF files or individual slide images from your presentations",
            "use_case": "Useful for sharing presentations or creating print-ready materials"
        },
        
        "text_to_speech": {
            "title": "Text to Speech",
            "description": "Generate realistic audio narration from text files",
            "details": "Creates natural-sounding speech using ElevenLabs AI voices with customizable settings",
            "use_case": "Perfect for voiceovers, audiobooks, or accessibility audio content"
        },
        
        "video_merge": {
            "title": "Video Merge",
            "description": "Create videos from images or merge multiple video files",
            "details": "Combines image sequences into videos with optional audio, or merges existing videos",
            "use_case": "Great for creating presentations, slideshows, or combining video clips"
        },
        
        "sequential_processing": {
            "title": "Sequential Processing",
            "description": "Run multiple tools in sequence for complete workflow automation",
            "details": "Chains together translation, conversion, and audio generation for end-to-end processing",
            "use_case": "Automates complex workflows like creating multilingual video presentations"
        },
        
        "reward_evaluator": {
            "title": "Reward Evaluator",
            "description": "Calculate proofreading rewards for presentations and text documents",
            "details": "Unified tool that evaluates PowerPoint presentations and text files to determine proofreading compensation based on language difficulty and content type",
            "use_case": "Perfect for calculating fair payment for proofreading services across different document types"
        },
        
        "transcript_cleaner": {
            "title": "Clean Raw Transcript",
            "description": "Clean and tighten raw audio transcripts for professional presentation",
            "details": "Uses Claude AI to remove filler words, fix grammar, and produce polished transcripts while maintaining speaker voice",
            "use_case": "Ideal for converting raw recordings into presentation-ready transcripts"
        }
    }

def get_tool_requirements():
    """
    Get API key requirements for each tool.
    
    Returns:
        dict: API requirements for each tool
    """
    return {
        "pptx_translation": {
            "api_required": "DeepL",
            "api_description": "DeepL API key for translation services"
        },
        
        "audio_transcription": {
            "api_required": "OpenAI", 
            "api_description": "OpenAI API key for Whisper transcription"
        },
        
        "text_translation": {
            "api_required": "DeepL",
            "api_description": "DeepL API key for translation services"
        },
        
        "pptx_to_pdf_png": {
            "api_required": "ConvertAPI",
            "api_description": "ConvertAPI key for document conversion"
        },
        
        "text_to_speech": {
            "api_required": "ElevenLabs",
            "api_description": "ElevenLabs API key for voice synthesis"
        },
        
        "video_merge": {
            "api_required": None,
            "api_description": "No API key required (uses local FFmpeg)"
        },
        
        "sequential_processing": {
            "api_required": "Multiple",
            "api_description": "Requires API keys for the selected tools in the sequence"
        },
        
        "reward_evaluator": {
            "api_required": None,
            "api_description": "No API key required (uses local document analysis)"
        },
        
        "transcript_cleaner": {
            "api_required": "Anthropic (Claude)",
            "api_description": "Anthropic API key for Claude AI transcript cleaning"
        }
    }

def get_supported_formats():
    """
    Get supported file formats for each tool.
    
    Returns:
        dict: Supported input and output formats
    """
    return {
        "pptx_translation": {
            "input": [".pptx"],
            "output": [".pptx"],
            "notes": "PowerPoint presentations only"
        },
        
        "audio_transcription": {
            "input": [".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"],
            "output": [".txt"],
            "notes": "Most common audio formats supported"
        },
        
        "text_translation": {
            "input": [".txt"],
            "output": [".txt"], 
            "notes": "Plain text files with UTF-8 encoding"
        },
        
        "pptx_to_pdf_png": {
            "input": [".pptx"],
            "output": [".pdf", ".png"],
            "notes": "PDF for documents, PNG for individual slides"
        },
        
        "text_to_speech": {
            "input": [".txt"],
            "output": [".mp3"],
            "notes": "Generates high-quality MP3 audio files"
        },
        
        "video_merge": {
            "input": [".png", ".jpg", ".jpeg", ".mp4", ".avi", ".mov"],
            "output": [".mp4"],
            "notes": "Images for slideshow creation, videos for merging"
        },
        
        "sequential_processing": {
            "input": ["Various"],
            "output": ["Various"],
            "notes": "Depends on selected tools in the sequence"
        },
        
        "reward_evaluator": {
            "input": [".pptx", ".ppt", ".txt"],
            "output": [".csv"],
            "notes": "Analyzes PowerPoint and text files with configurable reward modes"
        },
        
        "transcript_cleaner": {
            "input": [".txt"],
            "output": [".txt"],
            "notes": "Cleans raw transcripts, removes filler words, fixes grammar"
        }
    }

def get_quick_tips():
    """
    Get quick usage tips for each tool.
    
    Returns:
        dict: Helpful tips for users
    """
    return {
        "pptx_translation": [
            "Ensure your DeepL API key is configured before starting",
            "Large presentations may take several minutes to process",
            "Original formatting and layout will be preserved"
        ],
        
        "audio_transcription": [
            "Clear audio produces better transcription results",
            "Supported audio length up to 25MB per file",
            "Language auto-detection works best with longer audio"
        ],
        
        "text_translation": [
            "Break very large texts into smaller files for better processing",
            "UTF-8 encoding is required for proper character support",
            "Auto-detect source language or specify for better accuracy"
        ],
        
        "pptx_to_pdf_png": [
            "PDF format creates a single document with all slides",
            "PNG format creates individual image files per slide", 
            "Requires ConvertAPI subscription for processing"
        ],
        
        "text_to_speech": [
            "Preview voice samples before processing large texts",
            "Adjust voice settings for optimal results",
            "Processing time depends on text length"
        ],
        
        "video_merge": [
            "Images will be sorted alphabetically for video creation",
            "Audio file is optional for image-to-video conversion",
            "FFmpeg must be installed for video processing"
        ],
        
        "sequential_processing": [
            "Configure all required API keys before starting",
            "Review the processing order before running",
            "Total time depends on all selected operations"
        ],
        
        "reward_evaluator": [
            "Select the target language for accurate difficulty factors",
            "Choose reward mode: Image PPTX (1.5x), Video PPTX (1.0x), or TXT files",
            "Use recursive processing for multiple files in folders"
        ],
        
        "transcript_cleaner": [
            "Ensure your Anthropic (Claude) API key is configured",
            "Cleaned files are saved with '-ai-cleaned.txt' suffix",
            "Preserves technical terms and speaker's voice while removing filler words"
        ]
    }

def get_tool_info(tool_name):
    """
    Get comprehensive information about a specific tool.
    
    Args:
        tool_name: Name of the tool (e.g., 'pptx_translation')
    
    Returns:
        dict: Complete tool information including description, requirements, formats, and tips
    """
    descriptions = get_tool_descriptions()
    requirements = get_tool_requirements()
    formats = get_supported_formats()
    tips = get_quick_tips()
    
    if tool_name not in descriptions:
        return None
    
    return {
        "description": descriptions[tool_name],
        "requirements": requirements[tool_name],
        "formats": formats[tool_name],
        "tips": tips[tool_name]
    }

def get_short_description(tool_name):
    """
    Get a short description suitable for tooltips or brief help text.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        str: Short description text
    """
    descriptions = get_tool_descriptions()
    if tool_name in descriptions:
        return descriptions[tool_name]["description"]
    return "Tool description not available"

def get_tool_list_for_gui():
    """
    Get a formatted list of all tools with their basic info for GUI display.
    
    Returns:
        list: List of dictionaries with tool information
    """
    descriptions = get_tool_descriptions()
    requirements = get_tool_requirements()
    
    tools = []
    for tool_name, desc in descriptions.items():
        req = requirements.get(tool_name, {})
        tools.append({
            "name": tool_name,
            "title": desc["title"],
            "description": desc["description"],
            "api_required": req.get("api_required"),
            "has_api_requirement": req.get("api_required") is not None
        })
    
    return tools