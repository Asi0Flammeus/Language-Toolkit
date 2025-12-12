#!/usr/bin/env python3
"""CLI tool for Video Merge without GUI."""

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# Core imports
from core.video_merger import VideoMergerCore


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


class FilenameCleanerSimple:
    """Simple filename cleaner for removing voice names."""

    def __init__(self):
        """Initialize with default voice names."""
        self.voice_names = self._load_voice_names()

    def _load_voice_names(self) -> set:
        """Load voice names from elevenlabs_languages.json."""
        try:
            import json
            lang_file = Path(__file__).parent / "elevenlabs_languages.json"
            if lang_file.exists():
                with open(lang_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    voices = set()
                    for lang_data in data.get('languages', {}).values():
                        if isinstance(lang_data, dict):
                            for voice in lang_data.get('voices', []):
                                if isinstance(voice, dict) and 'name' in voice:
                                    voices.add(voice['name'].lower())
                    return voices
        except Exception:
            pass
        return set()

    def remove_voice_from_filename(self, filename: str) -> str:
        """Remove voice names from filename."""
        result = filename
        for voice in self.voice_names:
            pattern = re.compile(rf'[_-]?{re.escape(voice)}[_-]?', re.IGNORECASE)
            result = pattern.sub('_', result)
        # Clean up multiple underscores
        result = re.sub(r'_+', '_', result)
        result = result.strip('_')
        return result


def setup_logging(verbose: bool = False):
    """Setup basic logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )


def match_file_pairs(
    mp3_files: List[Path],
    png_files: List[Path],
    logger
) -> List[Tuple[str, Path, Path]]:
    """
    Match MP3 and PNG files based on a generic two-digit index in their filenames.

    Args:
        mp3_files: List of MP3 file paths
        png_files: List of PNG file paths
        logger: Logger instance

    Returns:
        List of tuples (index, mp3_file, png_file)
    """
    file_pairs = []
    mp3_dict = {}
    png_dict = {}

    # Compile a regex to match exactly two digits not adjacent to other digits
    id_pattern = re.compile(r'(?<!\d)(\d{2})(?!\d)')

    # Extract indices for PNG files
    for png_file in png_files:
        match = id_pattern.search(png_file.name)
        if match:
            idx = match.group(1)
            logger.log(f"  PNG index {idx}: {png_file.name}")
            png_dict[idx] = png_file

    # Extract indices for MP3 files
    for mp3_file in mp3_files:
        match = id_pattern.search(mp3_file.name)
        if match:
            idx = match.group(1)
            logger.log(f"  MP3 index {idx}: {mp3_file.name}")
            mp3_dict[idx] = mp3_file

    # Match pairs by index
    for idx in sorted(mp3_dict.keys(), key=lambda x: int(x)):
        mp3_file = mp3_dict[idx]
        png_file = png_dict.get(idx)
        if png_file:
            file_pairs.append((idx, mp3_file, png_file))
        else:
            logger.log(f"  No PNG match for MP3 index {idx}: {mp3_file.name}")

    return sorted(file_pairs, key=lambda x: int(x[0]))


def process_directory(
    input_dir: Path,
    output_dir: Path,
    intro_path: Optional[Path],
    skip_existing: bool,
    logger
) -> bool:
    """
    Process a single directory to create video from MP3/PNG pairs.

    Args:
        input_dir: Directory containing MP3 and PNG files
        output_dir: Output directory for video
        intro_path: Optional path to intro video
        skip_existing: Whether to skip if output exists
        logger: Logger instance

    Returns:
        True if successful or gracefully skipped, False on error
    """
    filename_cleaner = FilenameCleanerSimple()

    try:
        # Collect files
        entries = os.listdir(input_dir)
        mp3_files = sorted([input_dir / f for f in entries if f.lower().endswith('.mp3')])
        png_files = sorted([input_dir / f for f in entries if f.lower().endswith(('.png', '.webp'))])

        logger.log(f"Found {len(mp3_files)} MP3 and {len(png_files)} PNG files")

        if not mp3_files or not png_files:
            logger.log("No MP3 or PNG files found - skipping")
            return True

        # Verify counts match
        if len(mp3_files) != len(png_files):
            logger.log("=" * 60)
            logger.log("❌ PNG/MP3 COUNT MISMATCH - SKIPPING VIDEO CREATION")
            logger.log(f"   Found {len(png_files)} PNG files")
            logger.log(f"   Found {len(mp3_files)} MP3 files")

            # Find which indices are missing
            id_pattern = re.compile(r'(?<!\d)(\d{2})(?!\d)')
            png_indices = {id_pattern.search(f.name).group(1) for f in png_files if id_pattern.search(f.name)}
            mp3_indices = {id_pattern.search(f.name).group(1) for f in mp3_files if id_pattern.search(f.name)}

            png_only = png_indices - mp3_indices
            mp3_only = mp3_indices - png_indices

            if png_only:
                logger.log(f"   PNG without MP3: {', '.join(sorted(png_only))}")
            if mp3_only:
                logger.log(f"   MP3 without PNG: {', '.join(sorted(mp3_only))}")

            logger.log("=" * 60)
            return True  # Graceful skip

        # Match file pairs
        logger.log("Matching file pairs by index...")
        file_pairs = match_file_pairs(mp3_files, png_files, logger)

        if not file_pairs:
            logger.log("No matching pairs found - skipping")
            return True

        if len(file_pairs) != len(mp3_files):
            logger.log(f"⚠️  Only {len(file_pairs)} matched from {len(mp3_files)} files - skipping")
            return True

        logger.log(f"✓ Matched {len(file_pairs)} file pairs")

        # Generate output filename
        _, first_mp3, _ = file_pairs[0]
        mp3_stem = first_mp3.stem

        # Remove 2-digit identifier
        identifier_pattern = r'[_-](\d{2})(?:[_-])'
        output_name = re.sub(identifier_pattern, '_', mp3_stem)
        end_pattern = r'[_-]\d{2}$'
        output_name = re.sub(end_pattern, '', output_name)

        # Remove voice names
        output_name = filename_cleaner.remove_voice_from_filename(output_name)

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{output_name}.mp4"

        logger.log(f"Output file: {output_file}")

        # Check if should skip
        if skip_existing and output_file.exists():
            logger.log(f"⏩ Skipping - output already exists")
            return True

        # Create video
        merger = VideoMergerCore(progress_callback=logger.log)
        success = merger.create_video_from_file_pairs(
            file_pairs=file_pairs,
            output_path=output_file,
            silence_duration=0.2,
            intro_video=intro_path,
            outro_audio=None
        )

        if success:
            logger.log(f"✓ Video saved: {output_file}")
        else:
            logger.log("✗ Failed to create video")

        return success

    except Exception as e:
        logger.log(f"✗ Error: {str(e)}")
        logging.exception("Error processing directory")
        return False


def run_video_merge(
    input_path: Path,
    output_path: Path,
    intro_path: Optional[Path],
    recursive: bool,
    skip_existing: bool,
    logger
) -> bool:
    """
    Run the video merge process.

    Args:
        input_path: Input folder path
        output_path: Output folder path
        intro_path: Optional intro video path
        recursive: Whether to process subdirectories
        skip_existing: Whether to skip existing files
        logger: Logger instance

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.log("")
        logger.log("=" * 60)
        logger.log("Starting Video Merge Process")
        logger.log(f"Input:  {input_path}")
        logger.log(f"Output: {output_path}")
        logger.log(f"Intro:  {intro_path if intro_path else 'None'}")
        logger.log(f"Recursive: {'Yes' if recursive else 'No'}")
        logger.log(f"Skip existing: {'Yes' if skip_existing else 'No'}")
        logger.log("=" * 60)
        logger.log("")

        skipped_folders = []
        processed_folders = []

        if not recursive:
            # Process single directory
            logger.log(f"Processing: {input_path}")
            success = process_directory(
                input_dir=input_path,
                output_dir=output_path,
                intro_path=intro_path,
                skip_existing=skip_existing,
                logger=logger
            )
            if success:
                processed_folders.append(str(input_path))
            else:
                skipped_folders.append(str(input_path))
        else:
            # Recursive processing
            logger.log(f"Scanning recursively: {input_path}")
            for dirpath, dirnames, filenames in os.walk(input_path):
                curr_dir = Path(dirpath)

                # Check if directory has MP3 and PNG files
                has_mp3 = any(f.lower().endswith('.mp3') for f in filenames)
                has_png = any(f.lower().endswith(('.png', '.webp')) for f in filenames)

                if not has_mp3 or not has_png:
                    continue

                logger.log("")
                logger.log("-" * 40)
                logger.log(f"Processing: {curr_dir}")

                # Calculate relative output path
                rel_path = curr_dir.relative_to(input_path)
                curr_output = output_path / rel_path

                success = process_directory(
                    input_dir=curr_dir,
                    output_dir=curr_output,
                    intro_path=intro_path,
                    skip_existing=skip_existing,
                    logger=logger
                )

                if success:
                    processed_folders.append(str(curr_dir))
                else:
                    skipped_folders.append(str(curr_dir))

        # Summary
        logger.log("")
        logger.log("=" * 60)
        logger.log("SUMMARY")
        logger.log(f"  Processed: {len(processed_folders)} folders")
        logger.log(f"  Skipped:   {len(skipped_folders)} folders")

        if skipped_folders:
            logger.log("")
            logger.log("Skipped folders:")
            for folder in skipped_folders:
                logger.log(f"  - {folder}")

        logger.log("=" * 60)
        logger.log("✓ Video merge completed!")

        return True

    except KeyboardInterrupt:
        logger.log("\n⏹️  Process interrupted by user")
        return False
    except Exception as e:
        logger.log(f"\n❌ Critical error: {str(e)}")
        logging.exception("Error during video merge")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Video Merge CLI Tool - Create videos from MP3/PNG pairs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single directory
  %(prog)s -i ./slides -o ./output

  # Process recursively with intro video
  %(prog)s -i ./languages -o ./videos --recursive --intro

  # Process without skipping existing files
  %(prog)s -i ./input -o ./output --no-skip

  # Run in background with log file
  %(prog)s -i ./input -o ./output --recursive --log progress.log &
  tail -f progress.log

File naming convention:
  Files are matched by a 2-digit index in their names:
  - slide_01_title.png matches audio_01_narrator.mp3
  - lesson-02-intro.png matches lesson-02-speech.mp3
        """
    )

    # Required arguments
    parser.add_argument(
        '-i', '--input',
        type=Path,
        required=True,
        help='Input folder containing MP3 and PNG/WEBP files'
    )

    parser.add_argument(
        '-o', '--output',
        type=Path,
        required=True,
        help='Output folder for generated videos'
    )

    # Optional arguments
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Process subdirectories recursively'
    )

    parser.add_argument(
        '--intro',
        action='store_true',
        help='Add Plan B intro video to generated videos'
    )

    parser.add_argument(
        '--intro-path',
        type=Path,
        help='Custom intro video path (default: media/planB_intro.mp4)'
    )

    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Process all files even if output already exists (default: skip existing)'
    )

    parser.add_argument(
        '--log',
        type=Path,
        help='Log file path for progress output'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

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

        # Create output directory
        args.output.mkdir(parents=True, exist_ok=True)

        # Determine intro path
        intro_path = None
        if args.intro:
            if args.intro_path and args.intro_path.exists():
                intro_path = args.intro_path
            else:
                default_intro = Path(__file__).parent / "media" / "planB_intro.mp4"
                if default_intro.exists():
                    intro_path = default_intro
                else:
                    logger.log("⚠️  Intro requested but no intro video found")

        # Run the video merge process
        success = run_video_merge(
            input_path=args.input,
            output_path=args.output,
            intro_path=intro_path,
            recursive=args.recursive,
            skip_existing=not args.no_skip,
            logger=logger
        )

        return 0 if success else 1

    finally:
        logger.close()


if __name__ == "__main__":
    sys.exit(main())
