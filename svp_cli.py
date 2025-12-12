#!/usr/bin/env python3
"""CLI tool for Sequential Video Processing without GUI."""

import argparse
import json
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Core imports
from core.config import ConfigManager
from tools.sequential_processing.sequential_orchestrator import SequentialOrchestrator


class FileAndConsoleLogger:
    """Dual logger that writes to both file and console."""

    def __init__(self, log_file: Optional[Path] = None):
        """Initialize logger with optional file output."""
        self.log_file = log_file
        self.file_handle = None

        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.file_handle = open(self.log_file, 'w', encoding='utf-8', buffering=1)

    def log(self, message: str):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"

        # Write to console
        print(formatted_msg)
        sys.stdout.flush()

        # Write to file if enabled
        if self.file_handle:
            self.file_handle.write(formatted_msg + "\n")
            self.file_handle.flush()

    def close(self):
        """Close file handle if open."""
        if self.file_handle:
            self.file_handle.close()


def load_available_languages() -> dict:
    """Load available languages from language_providers.json."""
    try:
        lang_file = Path(__file__).parent / "language_providers.json"
        with open(lang_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {lang['code']: lang['name'] for lang in data['languages']}
    except Exception as e:
        logging.error(f"Failed to load languages: {e}")
        return {}


def validate_languages(lang_codes: List[str], available: dict) -> tuple[List[str], List[str]]:
    """
    Validate language codes against available languages.

    Returns:
        Tuple of (valid_codes, invalid_codes)
    """
    valid = []
    invalid = []

    for code in lang_codes:
        code_lower = code.lower()
        # Check exact match or case-insensitive match
        if code_lower in available or code in available:
            valid.append(code_lower)
        else:
            invalid.append(code)

    return valid, invalid


def setup_logging(verbose: bool = False):
    """Setup basic logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def get_orchestrator(config_manager: ConfigManager, logger) -> SequentialOrchestrator:
    """
    Initialize and return the SequentialOrchestrator.

    Args:
        config_manager: Configuration manager with API keys
        logger: Logger instance for progress updates

    Returns:
        Initialized SequentialOrchestrator
    """
    api_keys = config_manager.get_api_keys()
    orchestrator_config = {
        'deepl_api_key': api_keys.get('deepl'),
        'convertapi_key': api_keys.get('convertapi'),
        'elevenlabs_api_key': api_keys.get('elevenlabs')
    }

    return SequentialOrchestrator(
        config=orchestrator_config,
        progress_callback=logger.log
    )


def run_svp_process(
    mode: str,
    input_path: Path,
    output_path: Path,
    source_lang: str,
    target_langs: List[str],
    use_intro: bool,
    skip_existing: bool,
    logger
) -> bool:
    """
    Run the SVP process based on the selected mode.

    Args:
        mode: Processing mode (full, translate, export)
        input_path: Input folder path
        output_path: Output folder path
        source_lang: Source language code
        target_langs: List of target language codes
        use_intro: Whether to add intro video
        skip_existing: Whether to skip existing files
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        # Initialize config manager
        logger.log("Initializing configuration...")
        config_manager = ConfigManager(
            use_project_api_keys=True,
            languages_file="supported_languages.json",
            api_keys_file="api_keys.json"
        )

        # Get orchestrator
        logger.log("Setting up orchestrator...")
        orchestrator = get_orchestrator(config_manager, logger)

        # Validate configuration
        logger.log("Validating API configuration...")
        availability = orchestrator.validate_configuration()

        missing_tools = []
        if mode in ['full', 'translate']:
            if not availability.get('pptx_translation'):
                missing_tools.append('pptx_translation (DeepL API)')
            if not availability.get('text_translation'):
                missing_tools.append('text_translation (DeepL API)')

        if mode in ['full', 'export']:
            if not availability.get('pptx_export'):
                missing_tools.append('pptx_export (ConvertAPI)')
            if not availability.get('text_to_speech'):
                missing_tools.append('text_to_speech (ElevenLabs API)')

        if missing_tools:
            logger.log(f"❌ Missing required API keys for: {', '.join(missing_tools)}")
            logger.log("Please configure API keys in api_keys.json or environment variables")
            return False

        logger.log("✓ Configuration validated successfully")
        logger.log("")
        logger.log("=" * 60)
        logger.log(f"Starting SVP Process - Mode: {mode.upper()}")
        logger.log(f"Input:  {input_path}")
        logger.log(f"Output: {output_path}")
        logger.log(f"Source: {source_lang}")
        logger.log(f"Targets: {', '.join(target_langs)}")
        if mode in ['full', 'export']:
            logger.log(f"Use intro: {'Yes' if use_intro else 'No'}")
        logger.log(f"Skip existing: {'Yes' if skip_existing else 'No'}")
        logger.log("=" * 60)
        logger.log("")

        # Run appropriate processing mode
        success = False

        if mode == 'full':
            success = orchestrator.process_folder(
                input_path=input_path,
                output_path=output_path,
                source_lang=source_lang,
                target_langs=target_langs,
                use_intro=use_intro,
                skip_existing=skip_existing
            )
        elif mode == 'translate':
            success = orchestrator.process_translation_phase(
                input_path=input_path,
                output_path=output_path,
                source_lang=source_lang,
                target_langs=target_langs,
                skip_existing=skip_existing
            )
        elif mode == 'export':
            success = orchestrator.process_export_phase(
                input_path=input_path,
                output_path=output_path,
                source_lang=source_lang,
                target_langs=target_langs,
                use_intro=use_intro,
                skip_existing=skip_existing
            )

        logger.log("")
        logger.log("=" * 60)
        if success:
            logger.log("✓ Processing completed successfully!")
        else:
            logger.log("⚠ Processing completed with warnings or was interrupted")
        logger.log("=" * 60)

        return success

    except KeyboardInterrupt:
        logger.log("\n⏹️  Process interrupted by user")
        return False
    except Exception as e:
        logger.log(f"\n❌ Critical error: {str(e)}")
        logging.exception("Error during SVP processing")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Sequential Video Processing (SVP) CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full workflow for French and Spanish
  %(prog)s -i ./input -o ./output -s en -t fr es

  # Translate to all available languages
  %(prog)s -i ./input -o ./output -s en -t all

  # Translation phase only for German
  %(prog)s -i ./input -o ./output -s en -t de --mode translate

  # Export phase only (PNG, TTS, video) for Italian
  %(prog)s -i ./input -o ./output -s en -t it --mode export

  # Run in background with log file
  %(prog)s -i ./input -o ./output -s en -t fr --log progress.log &
  tail -f progress.log
        """
    )

    # Required arguments
    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='Input folder containing PPTX and TXT files'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='Output folder for processed files'
    )

    parser.add_argument(
        '-s', '--source',
        type=str,
        required=True,
        help='Source language code (e.g., en, es, fr)'
    )

    parser.add_argument(
        '-t', '--targets',
        type=str,
        nargs='+',
        required=True,
        help='Target language codes (space-separated) or "all" for all available languages'
    )

    # Optional arguments
    parser.add_argument(
        '--mode',
        choices=['full', 'translate', 'export'],
        default='full',
        help='Processing mode: full workflow, translation only, or export only (default: full)'
    )

    parser.add_argument(
        '--intro',
        action='store_true',
        help='Add Plan B intro video to generated videos'
    )

    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Process all files even if output already exists (default: skip existing)'
    )

    parser.add_argument(
        '--log',
        type=Path,
        help='Log file path for progress output (useful for tail -f when running in background)'
    )

    parser.add_argument(
        '--list-languages',
        action='store_true',
        help='List all available language codes and exit'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load available languages
    available_languages = load_available_languages()

    if not available_languages:
        print("Error: Could not load available languages from language_providers.json")
        return 1

    # Handle list languages command
    if args.list_languages:
        print("\nAvailable language codes:")
        print("=" * 60)
        for code, name in sorted(available_languages.items()):
            print(f"  {code:12s} - {name}")
        print("=" * 60)
        print(f"\nTotal: {len(available_languages)} languages")
        return 0

    # Initialize logger
    logger = FileAndConsoleLogger(args.log)

    try:
        # Validate input path
        if not args.input.exists():
            logger.log(f"❌ Error: Input path does not exist: {args.input}")
            return 1

        if not args.input.is_dir():
            logger.log(f"❌ Error: Input path must be a directory: {args.input}")
            return 1

        # Create output directory if it doesn't exist
        args.output.mkdir(parents=True, exist_ok=True)

        # Validate source language
        source_lower = args.source.lower()
        if source_lower not in available_languages:
            logger.log(f"❌ Error: Invalid source language: {args.source}")
            logger.log(f"Use --list-languages to see available options")
            return 1

        # Handle target languages
        target_langs = []

        if len(args.targets) == 1 and args.targets[0].lower() == 'all':
            # Use all available languages except source
            target_langs = [code for code in available_languages.keys() if code != source_lower]
            logger.log(f"Selected ALL languages ({len(target_langs)} targets)")
        else:
            # Validate specified target languages
            valid_langs, invalid_langs = validate_languages(args.targets, available_languages)

            if invalid_langs:
                logger.log(f"❌ Error: Invalid target language(s): {', '.join(invalid_langs)}")
                logger.log("Use --list-languages to see available options")
                return 1

            target_langs = valid_langs

        if not target_langs:
            logger.log("❌ Error: No valid target languages specified")
            return 1

        # Run the SVP process
        success = run_svp_process(
            mode=args.mode,
            input_path=args.input,
            output_path=args.output,
            source_lang=source_lower,
            target_langs=target_langs,
            use_intro=args.intro,
            skip_existing=not args.no_skip,
            logger=logger
        )

        return 0 if success else 1

    finally:
        logger.close()


if __name__ == "__main__":
    sys.exit(main())
