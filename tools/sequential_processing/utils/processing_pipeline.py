"""Processing Pipeline for Sequential Processing."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Container for processing results from each step."""
    pptx_files: List[Path] = field(default_factory=list)
    png_files: List[Path] = field(default_factory=list)
    txt_files: List[Path] = field(default_factory=list)
    audio_files: List[Path] = field(default_factory=list)
    video_files: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ProcessingPipeline:
    """Manages the processing workflow with dependency tracking."""
    
    def __init__(self, adapters: Dict[str, Any], 
                 progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the processing pipeline.
        
        Args:
            adapters: Dictionary of core tool adapters
            progress_callback: Optional callback for progress updates
        """
        self.adapters = adapters
        self.progress_callback = progress_callback or (lambda x: None)
        self.stop_flag = None
    
    def set_stop_flag(self, stop_flag):
        """Set the stop flag for interrupting processing."""
        self.stop_flag = stop_flag
    
    def process_subfolder(self, subfolder_path: Path, output_path: Path,
                         source_lang: str, target_lang: str,
                         relative_path: str = '.',
                         use_intro: bool = False,
                         skip_existing: bool = True) -> ProcessingResult:
        """
        Process all files in a subfolder.

        Args:
            subfolder_path: Path to the subfolder to process
            output_path: Root output path for this language
            source_lang: Source language code
            target_lang: Target language code
            relative_path: Relative path from input root
            use_intro: Whether to add intro video
            skip_existing: Whether to skip files that already exist

        Returns:
            ProcessingResult containing all generated files
        """
        result = ProcessingResult()

        # Create output subdirectory preserving structure
        if relative_path != '.':
            subfolder_output = output_path / relative_path
        else:
            subfolder_output = output_path
        subfolder_output.mkdir(parents=True, exist_ok=True)

        self.progress_callback(f"\n📁 Processing folder: {relative_path}")
        
        # Step 1: Process PPTX files
        pptx_files = list(subfolder_path.glob('*.pptx'))
        if pptx_files:
            self.progress_callback(f"Found {len(pptx_files)} PPTX files")
            for pptx_file in pptx_files:
                if self.stop_flag and self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    return result
                
                # Check if we should skip this PPTX file
                expected_pptx = subfolder_output / f"{pptx_file.stem}_{target_lang}.pptx"
                if skip_existing and expected_pptx.exists():
                    self.progress_callback(f"⏩ Skipping {pptx_file.name} - translated file already exists")
                    result.pptx_files.append(expected_pptx)
                    
                    # Check for existing PNG files
                    existing_pngs = list(subfolder_output.glob(f"{expected_pptx.stem}_slide_*.png"))
                    if existing_pngs:
                        self.progress_callback(f"⏩ Found {len(existing_pngs)} existing PNG files")
                        result.png_files.extend(sorted(existing_pngs))
                    else:
                        # Export to PNG if they don't exist
                        png_files = self._export_pptx_to_png(expected_pptx, subfolder_output)
                        result.png_files.extend(png_files)
                else:
                    # Translate PPTX
                    translated_pptx = self._translate_pptx(
                        pptx_file, subfolder_output, source_lang, target_lang
                    )
                    if translated_pptx:
                        result.pptx_files.append(translated_pptx)
                        
                        # Export to PNG
                        png_files = self._export_pptx_to_png(translated_pptx, subfolder_output)
                        result.png_files.extend(png_files)
                    else:
                        result.errors.append(f"Failed to translate {pptx_file.name}")
        
        # Step 2: Process text files
        txt_files = list(subfolder_path.glob('*.txt'))
        if txt_files:
            self.progress_callback(f"Found {len(txt_files)} text files")
            for txt_file in txt_files:
                if self.stop_flag and self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    return result
                
                # Check if we should skip this text file
                expected_txt = subfolder_output / f"{txt_file.stem}_{target_lang}.txt"
                expected_audio = subfolder_output / f"{txt_file.stem}_{target_lang}.mp3"
                
                if skip_existing and expected_txt.exists():
                    self.progress_callback(f"⏩ Skipping {txt_file.name} - translated file already exists")
                    result.txt_files.append(expected_txt)
                    
                    # Check for existing audio file
                    if expected_audio.exists():
                        self.progress_callback(f"⏩ Found existing audio file: {expected_audio.name}")
                        result.audio_files.append(expected_audio)
                    else:
                        # Generate audio if it doesn't exist
                        audio_file = self._generate_audio(expected_txt, subfolder_output)
                        if audio_file:
                            result.audio_files.append(audio_file)
                        else:
                            result.errors.append(f"Failed to generate audio for {txt_file.name}")
                else:
                    # Translate text
                    translated_txt = self._translate_text(
                        txt_file, subfolder_output, source_lang, target_lang
                    )
                    if translated_txt:
                        result.txt_files.append(translated_txt)
                        
                        # Generate audio
                        audio_file = self._generate_audio(translated_txt, subfolder_output)
                        if audio_file:
                            result.audio_files.append(audio_file)
                        else:
                            result.errors.append(f"Failed to generate audio for {txt_file.name}")
                    else:
                        result.errors.append(f"Failed to translate {txt_file.name}")
        
        # Step 3: Generate video if we have materials
        if result.png_files or result.audio_files:
            video_file = self._generate_video(
                subfolder_output, result.png_files, result.audio_files, subfolder_path, use_intro, skip_existing
            )
            if video_file:
                result.video_files.append(video_file)
            elif video_file is None and len(result.png_files) != len(result.audio_files):
                # Count mismatch - this was already reported, don't add as error
                # The folder was skipped gracefully
                pass
            else:
                # Actual error in video generation
                result.errors.append(f"Failed to generate video for {relative_path}")
        
        return result

    def process_translation_only(self, subfolder_path: Path, output_path: Path,
                                 source_lang: str, target_lang: str,
                                 relative_path: str = '.',
                                 skip_existing: bool = True) -> ProcessingResult:
        """
        Process translation phase only (PPTX and TXT translation).

        Args:
            subfolder_path: Path to the subfolder to process
            output_path: Root output path for this language
            source_lang: Source language code
            target_lang: Target language code
            relative_path: Relative path from input root
            skip_existing: Whether to skip files that already exist

        Returns:
            ProcessingResult containing all translated files
        """
        result = ProcessingResult()

        # Create output subdirectory preserving structure
        if relative_path != '.':
            subfolder_output = output_path / relative_path
        else:
            subfolder_output = output_path
        subfolder_output.mkdir(parents=True, exist_ok=True)

        self.progress_callback(f"\n📁 Processing folder: {relative_path}")

        # Step 1: Process PPTX files
        pptx_files = list(subfolder_path.glob('*.pptx'))
        if pptx_files:
            self.progress_callback(f"Found {len(pptx_files)} PPTX files")
            for pptx_file in pptx_files:
                if self.stop_flag and self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    return result

                expected_pptx = subfolder_output / f"{pptx_file.stem}_{target_lang}.pptx"
                if skip_existing and expected_pptx.exists():
                    self.progress_callback(f"⏩ Skipping {pptx_file.name} - translated file already exists")
                    result.pptx_files.append(expected_pptx)
                else:
                    # Translate PPTX
                    translated_pptx = self._translate_pptx(
                        pptx_file, subfolder_output, source_lang, target_lang
                    )
                    if translated_pptx:
                        result.pptx_files.append(translated_pptx)
                    else:
                        result.errors.append(f"Failed to translate {pptx_file.name}")

        # Step 2: Process text files
        txt_files = list(subfolder_path.glob('*.txt'))
        if txt_files:
            self.progress_callback(f"Found {len(txt_files)} text files")
            for txt_file in txt_files:
                if self.stop_flag and self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    return result

                expected_txt = subfolder_output / f"{txt_file.stem}_{target_lang}.txt"

                if skip_existing and expected_txt.exists():
                    self.progress_callback(f"⏩ Skipping {txt_file.name} - translated file already exists")
                    result.txt_files.append(expected_txt)
                else:
                    # Translate text
                    translated_txt = self._translate_text(
                        txt_file, subfolder_output, source_lang, target_lang
                    )
                    if translated_txt:
                        result.txt_files.append(translated_txt)
                    else:
                        result.errors.append(f"Failed to translate {txt_file.name}")

        return result

    def process_export_only(self, subfolder_path: Path, output_path: Path,
                            target_lang: str, relative_path: str = '.',
                            use_intro: bool = False,
                            skip_existing: bool = True) -> ProcessingResult:
        """
        Process export phase only (PNG export, TTS, video merge).

        Args:
            subfolder_path: Path to the subfolder to process (should contain translated files)
            output_path: Root output path for this language
            target_lang: Target language code
            relative_path: Relative path from input root
            use_intro: Whether to add intro video
            skip_existing: Whether to skip files that already exist

        Returns:
            ProcessingResult containing all generated files
        """
        result = ProcessingResult()

        # Create output subdirectory preserving structure
        if relative_path != '.':
            subfolder_output = output_path / relative_path
        else:
            subfolder_output = output_path
        subfolder_output.mkdir(parents=True, exist_ok=True)

        self.progress_callback(f"\n📁 Processing folder: {relative_path}")

        # Step 1: Find translated PPTX files and export to PNG
        translated_pptx_files = list(subfolder_output.glob(f'*_{target_lang}.pptx'))
        if translated_pptx_files:
            self.progress_callback(f"Found {len(translated_pptx_files)} translated PPTX files")
            for pptx_file in translated_pptx_files:
                if self.stop_flag and self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    return result

                result.pptx_files.append(pptx_file)

                # Check for existing PNG files
                existing_pngs = list(subfolder_output.glob(f"{pptx_file.stem}_slide_*.png"))
                if existing_pngs and skip_existing:
                    self.progress_callback(f"⏩ Found {len(existing_pngs)} existing PNG files for {pptx_file.name}")
                    result.png_files.extend(sorted(existing_pngs))
                else:
                    # Export to PNG
                    png_files = self._export_pptx_to_png(pptx_file, subfolder_output)
                    result.png_files.extend(png_files)

        # Step 2: Find translated text files and generate audio
        translated_txt_files = list(subfolder_output.glob(f'*_{target_lang}.txt'))
        if translated_txt_files:
            self.progress_callback(f"Found {len(translated_txt_files)} translated text files")
            for txt_file in translated_txt_files:
                if self.stop_flag and self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    return result

                result.txt_files.append(txt_file)

                expected_audio = subfolder_output / f"{txt_file.stem}.mp3"

                if expected_audio.exists() and skip_existing:
                    self.progress_callback(f"⏩ Found existing audio file: {expected_audio.name}")
                    result.audio_files.append(expected_audio)
                else:
                    # Generate audio
                    audio_file = self._generate_audio(txt_file, subfolder_output)
                    if audio_file:
                        result.audio_files.append(audio_file)
                    else:
                        result.errors.append(f"Failed to generate audio for {txt_file.name}")

        # Step 3: Generate video if we have materials
        if result.png_files or result.audio_files:
            video_file = self._generate_video(
                subfolder_output, result.png_files, result.audio_files, subfolder_path, use_intro, skip_existing
            )
            if video_file:
                result.video_files.append(video_file)
            elif video_file is None and len(result.png_files) != len(result.audio_files):
                # Count mismatch - this was already reported, don't add as error
                # The folder was skipped gracefully
                pass
            else:
                # Actual error in video generation
                result.errors.append(f"Failed to generate video for {relative_path}")

        return result

    def _translate_pptx(self, input_file: Path, output_dir: Path,
                       source_lang: str, target_lang: str) -> Optional[Path]:
        """Translate a PPTX file."""
        if 'pptx_translator' not in self.adapters:
            self.progress_callback("⚠️ PPTX translator not available")
            return None
        
        adapter = self.adapters['pptx_translator']
        output_file = output_dir / f"{input_file.stem}_{target_lang}.pptx"
        
        success = adapter.process(
            input_file,
            output_file,
            {'source_lang': source_lang, 'target_lang': target_lang}
        )
        
        return output_file if success else None
    
    def _export_pptx_to_png(self, pptx_file: Path, output_dir: Path) -> List[Path]:
        """Export PPTX slides to PNG images."""
        if 'pptx_exporter' not in self.adapters:
            self.progress_callback("⚠️ PPTX exporter not available")
            return []
        
        adapter = self.adapters['pptx_exporter']
        # Export PNGs to the same directory as the PPTX file, not a subdirectory
        png_files = adapter.process(pptx_file, output_dir, {})
        return png_files
    
    def _translate_text(self, input_file: Path, output_dir: Path,
                       source_lang: str, target_lang: str) -> Optional[Path]:
        """Translate a text file."""
        if 'text_translator' not in self.adapters:
            self.progress_callback("⚠️ Text translator not available")
            return None
        
        adapter = self.adapters['text_translator']
        output_file = output_dir / f"{input_file.stem}_{target_lang}.txt"
        
        success = adapter.process(
            input_file,
            output_file,
            {'source_lang': source_lang, 'target_lang': target_lang}
        )
        
        return output_file if success else None
    
    def _generate_audio(self, text_file: Path, output_dir: Path) -> Optional[Path]:
        """Generate audio from text file."""
        if 'tts' not in self.adapters:
            self.progress_callback("⚠️ TTS engine not available")
            return None
        
        adapter = self.adapters['tts']
        audio_file = output_dir / f"{text_file.stem}.mp3"
        
        result = adapter.process(text_file, audio_file, {})
        return result  # Returns Path or None
    
    def _generate_video(self, output_dir: Path, png_files: List[Path],
                       audio_files: List[Path], input_dir: Path, 
                       use_intro: bool = False, skip_existing: bool = True) -> Optional[Path]:
        """Generate video from images and audio."""
        if 'video_merger' not in self.adapters:
            self.progress_callback("⚠️ Video merger not available")
            return None
        
        # VERIFICATION: Check PNG/MP3 counts before attempting video generation
        if len(png_files) != len(audio_files):
            self.progress_callback("=" * 60)
            self.progress_callback(f"❌ PNG/MP3 count mismatch in {output_dir.name}")
            self.progress_callback(f"   PNG files: {len(png_files)}")
            self.progress_callback(f"   MP3 files: {len(audio_files)}")
            self.progress_callback("   Skipping video generation - counts must match")
            self.progress_callback("   ⏭️  Continuing to next folder...")
            self.progress_callback("=" * 60)
            # Don't treat this as an error, it's a graceful skip
            # The video merger adapter will handle tracking skipped folders
            return None
        
        # Check for intro video based on use_intro flag
        intro_video = None
        if use_intro:
            # First check for intro.mp4 in input directory
            intro_candidates = list(input_dir.glob('intro.mp4'))
            if intro_candidates:
                intro_video = intro_candidates[0]
                self.progress_callback(f"📹 Found intro video: {intro_video.name}")
            else:
                # Check for planB_intro.mp4 in media directory
                media_intro = Path(__file__).parent.parent.parent.parent / "media" / "planB_intro.mp4"
                if media_intro.exists():
                    intro_video = media_intro
                    self.progress_callback(f"📹 Using Plan B intro video")
                else:
                    self.progress_callback("⚠️ Intro requested but no intro video found")
        
        adapter = self.adapters['video_merger']
        video_file = output_dir / "output.mp4"
        
        # Pass parameters matching what the video merger adapter expects
        params = {
            'image_files': sorted(png_files),  # Sort to maintain order
            'audio_files': sorted(audio_files),  # Sort audio files too
            'intro_video': intro_video,
            'use_intro': use_intro  # Pass the use_intro flag
        }
        
        success = adapter.process(output_dir, video_file, params, skip_existing)
        return video_file if success else None
    
    def get_summary(self, results: List[ProcessingResult]) -> str:
        """
        Generate a summary of processing results.
        
        Args:
            results: List of ProcessingResult objects
            
        Returns:
            Summary string
        """
        total_pptx = sum(len(r.pptx_files) for r in results)
        total_png = sum(len(r.png_files) for r in results)
        total_txt = sum(len(r.txt_files) for r in results)
        total_audio = sum(len(r.audio_files) for r in results)
        total_video = sum(len(r.video_files) for r in results)
        total_errors = sum(len(r.errors) for r in results)
        
        summary = f"""
📊 Processing Summary:
• PPTX files translated: {total_pptx}
• PNG slides exported: {total_png}
• Text files translated: {total_txt}
• Audio files generated: {total_audio}
• Videos created: {total_video}
• Errors encountered: {total_errors}
"""
        
        if total_errors > 0:
            summary += "\n⚠️ Errors:\n"
            for result in results:
                for error in result.errors:
                    summary += f"  • {error}\n"
        
        return summary