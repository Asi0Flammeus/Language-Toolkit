"""Sequential Image Processing (SIP) tool for course materials."""

import os
import shutil
import logging
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import tkinter as tk
from tkinter import ttk, messagebox

from ui.base_tool import ToolBase
from ui.mixins import LanguageSelectionMixin
from core.processors import ProgressReporter, ProcessorConfig, create_translation_processor
from core.pptx_converter import PPTXConverterCore

logger = logging.getLogger(__name__)


class SequentialImageProcessingTool(ToolBase, LanguageSelectionMixin):
    """Sequential Image Processing for course materials with PPTX translation and MD update."""
    
    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx'}
        
        # Language selection variables (inherited from LanguageSelectionMixin)
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")
        
        # Get BEC_REPO path from environment
        self.bec_repo_path = os.getenv('BEC_REPO')
        if not self.bec_repo_path:
            logging.warning("BEC_REPO environment variable not set")
        
        # API keys
        self.api_key_deepl = self.config_manager.get_api_keys().get("deepl")
        self.api_key_convertapi = self.config_manager.get_api_keys().get("convertapi")
        
        if not self.api_key_deepl:
            logging.warning("DeepL API key not configured")
        if not self.api_key_convertapi:
            logging.warning("ConvertAPI key not configured")
    
    def create_specific_controls(self, parent_frame):
        """Create UI elements specific to SIP tool."""
        # BEC Repo path display
        if self.bec_repo_path:
            repo_frame = ttk.LabelFrame(parent_frame, text="BEC Repository")
            repo_frame.pack(fill='x', padx=5, pady=5)
            
            repo_label = ttk.Label(repo_frame, text=f"Path: {self.bec_repo_path}")
            repo_label.pack(padx=5, pady=5)
    
    def get_course_indexes(self) -> List[str]:
        """Extract course indexes from BEC repo courses folder."""
        if not self.bec_repo_path:
            return []
        
        courses_path = Path(self.bec_repo_path) / "bitcoin-educational-content" / "courses"
        if not courses_path.exists():
            # Try alternate path structure
            courses_path = Path(self.bec_repo_path) / "courses"
            if not courses_path.exists():
                self.send_progress_update(f"❌ Courses folder not found in {self.bec_repo_path}")
                return []
        
        # Get all subdirectory names in courses folder
        course_indexes = []
        for item in courses_path.iterdir():
            if item.is_dir():
                course_indexes.append(item.name)
        
        return sorted(course_indexes)
    
    def extract_course_index_from_filename(self, pptx_path: Path) -> Optional[str]:
        """Extract course index from PPTX filename by matching with available courses."""
        course_indexes = self.get_course_indexes()
        if not course_indexes:
            return None
        
        filename = pptx_path.stem.lower()
        
        # Try to find matching course index
        for index in course_indexes:
            # Direct match
            if index.lower() in filename:
                return index
            # Try matching with underscores replaced by hyphens
            if index.lower().replace('-', '_') in filename:
                return index
            # Try matching with hyphens replaced by underscores  
            if index.lower().replace('_', '-') in filename:
                return index
        
        return None
    
    def translate_pptx(self, input_file: Path, output_dir: Path, target_lang: str) -> Optional[Path]:
        """Translate PPTX file to target language."""
        try:
            # Create output filename
            output_filename = f"{input_file.stem}_{target_lang}{input_file.suffix}"
            output_file = output_dir / output_filename
            
            # Skip if already exists
            if self.check_output_exists.get() and output_file.exists():
                self.send_progress_update(f"⏩ Skipping translation - file exists: {output_filename}")
                return output_file
            
            self.send_progress_update(f"🌐 Translating to {target_lang}: {input_file.name}")
            
            # Create translation processor
            progress_reporter = ProgressReporter(callback=lambda msg: (
                self.send_progress_update(msg) if not self.stop_flag.is_set()
                else (_ for _ in ()).throw(InterruptedError("Processing stopped"))
            ))
            
            processor = create_translation_processor(
                self.service_manager,
                progress_reporter=progress_reporter,
                config=ProcessorConfig(
                    skip_existing=self.check_output_exists.get(),
                    allowed_extensions={'.pptx'},
                    max_file_size_mb=50.0
                )
            )
            
            # Process the file
            result = processor.process_file(
                input_file,
                output_file,
                source_language=self.source_lang.get(),
                target_language=target_lang
            )
            
            if result.success:
                self.send_progress_update(f"✅ Translated: {output_filename}")
                return output_file
            else:
                self.send_progress_update(f"❌ Failed to translate: {result.message}")
                return None
                
        except Exception as e:
            self.send_progress_update(f"❌ Error translating: {e}")
            logging.exception(f"Error translating {input_file}")
            return None
    
    def export_pptx_to_webp(self, pptx_file: Path, output_dir: Path) -> List[Path]:
        """Export PPTX slides to WEBP images."""
        try:
            self.send_progress_update(f"🖼️ Exporting to WEBP: {pptx_file.name}")
            
            # Create converter
            converter = PPTXConverterCore(
                api_key=self.api_key_convertapi,
                progress_callback=self.send_progress_update
            )
            
            # Convert to WEBP
            webp_files = converter.convert_pptx_to_webp(
                input_path=pptx_file,
                output_dir=output_dir,
                quality=85
            )
            
            if webp_files:
                self.send_progress_update(f"✅ Exported {len(webp_files)} WEBP files")
                return [Path(f) for f in webp_files]
            else:
                self.send_progress_update(f"❌ Failed to export WEBP files")
                return []
                
        except Exception as e:
            self.send_progress_update(f"❌ Error exporting to WEBP: {e}")
            logging.exception(f"Error exporting {pptx_file}")
            return []
    
    def update_markdown_files(self, course_index: str, lang: str, images_moved: int) -> bool:
        """Update image paths in markdown files for the course."""
        try:
            if not self.bec_repo_path or not course_index:
                return False
            
            # Find the course markdown file
            courses_path = Path(self.bec_repo_path) / "bitcoin-educational-content" / "courses"
            if not courses_path.exists():
                courses_path = Path(self.bec_repo_path) / "courses"
            
            # The markdown file is directly at courses/{course_index}/{lang}.md
            md_file = courses_path / course_index / f"{lang}.md"
            if not md_file.exists():
                self.send_progress_update(f"⚠️ Markdown file not found: {md_file}")
                return False
            
            md_files = [md_file]
            
            total_updates = 0
            for md_file in md_files:
                # Read the markdown file
                content = md_file.read_text(encoding='utf-8')
                
                # Count images referenced in the file - only match .webp image references
                # Look for image references with .webp extension
                image_pattern = r'!\[.*?\]\([^)]*\.webp\)'
                matches = re.findall(image_pattern, content)
                
                if not matches:
                    # If no .webp images found, skip this file
                    self.send_progress_update(f"ℹ️ No .webp image references found in {md_file.name}")
                    continue
                
                # Log what we found for debugging
                self.send_progress_update(f"📊 Found {len(matches)} image references in {md_file.name}")
                
                # Check if the number of images matches what we moved
                if len(matches) != images_moved:
                    difference = abs(len(matches) - images_moved)
                    if len(matches) > images_moved:
                        self.send_progress_update(
                            f"⚠️ Image count mismatch in {md_file.name}: "
                            f"MD has {len(matches)} references but only {images_moved} images were converted "
                            f"(MD has {difference} MORE references)"
                        )
                    else:
                        self.send_progress_update(
                            f"⚠️ Image count mismatch in {md_file.name}: "
                            f"MD has {len(matches)} references but {images_moved} images were converted "
                            f"(MD has {difference} FEWER references)"
                        )
                    # Continue anyway but with warning
                    self.send_progress_update(f"⚠️ Proceeding with update despite mismatch...")
                
                # Update all image paths to point to ./assets/{lang}/ with numeric names
                # Replace each .webp image reference with numbered format
                image_counter = [1]  # Use list to allow modification in nested function
                
                def update_path(match):
                    # Keep the alt text and other parts, just update the path
                    full_match = match.group(0)
                    # Extract alt text if present
                    alt_text_match = re.match(r'!\[(.*?)\]', full_match)
                    alt_text = alt_text_match.group(1) if alt_text_match else ""
                    result = f'![{alt_text}](./assets/{lang}/{image_counter[0]:03d}.webp)'
                    image_counter[0] += 1
                    return result
                
                # Use the same pattern for replacement - match any .webp image reference
                updated_content = re.sub(r'!\[.*?\]\([^)]*\.webp\)', update_path, content)
                
                # Write the updated content
                md_file.write_text(updated_content, encoding='utf-8')
                total_updates += 1
                self.send_progress_update(f"✅ Updated {md_file.name}")
            
            return total_updates > 0
            
        except Exception as e:
            self.send_progress_update(f"❌ Error updating markdown files: {e}")
            logging.exception(f"Error updating markdown for course {course_index}")
            return False
    
    def move_webp_to_assets(self, webp_files: List[Path], course_index: str, 
                            lang: str) -> Tuple[int, Path]:
        """Move WEBP files to the course assets directory with numeric names."""
        try:
            if not self.bec_repo_path or not course_index:
                return 0, None
            
            # Determine the assets path
            courses_path = Path(self.bec_repo_path) / "bitcoin-educational-content" / "courses"
            if not courses_path.exists():
                courses_path = Path(self.bec_repo_path) / "courses"
            
            assets_dir = courses_path / course_index / "assets" / lang
            assets_dir.mkdir(parents=True, exist_ok=True)
            
            # Sort files to maintain order
            webp_files = sorted(webp_files)
            
            moved_count = 0
            for i, webp_file in enumerate(webp_files, 1):
                # Rename with numeric format (001.webp, 002.webp, etc.)
                dest_file = assets_dir / f"{i:03d}.webp"
                shutil.move(str(webp_file), str(dest_file))
                moved_count += 1
                
            self.send_progress_update(f"✅ Moved {moved_count} WEBP files to {assets_dir} (renamed as 001.webp - {moved_count:03d}.webp)")
            return moved_count, assets_dir
            
        except Exception as e:
            self.send_progress_update(f"❌ Error moving WEBP files: {e}")
            logging.exception(f"Error moving files for course {course_index}")
            return 0, None
    
    def process_file(self, input_file: Path, output_dir: Path = None):
        """Process a single PPTX file through the SIP workflow."""
        if input_file.suffix.lower() != ".pptx":
            self.send_progress_update(f"⏩ Skipping non-PPTX file: {input_file}")
            return
        
        try:
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")
            
            # Extract course index
            course_index = self.extract_course_index_from_filename(input_file)
            if not course_index:
                self.send_progress_update(
                    f"⚠️ Could not determine course index for: {input_file.name}"
                )
                # Continue processing without course index
            else:
                self.send_progress_update(f"📚 Course index: {course_index}")
            
            # Process the single target language from standard language selection
            target_lang = self.target_lang.get()
            
            if not target_lang:
                self.send_progress_update("⚠️ No target language selected")
                return
            
            # Process the target language
            languages_to_process = [target_lang]
            for target_lang in languages_to_process:
                if self.stop_flag.is_set():
                    raise InterruptedError("Processing stopped by user")
                
                self.send_progress_update(f"\n🌍 Processing language: {target_lang}")
                
                # Step 1: Translate PPTX
                translated_pptx = self.translate_pptx(input_file, output_dir, target_lang)
                if not translated_pptx:
                    continue
                
                # Step 2: Export to WEBP (save to output directory first)
                webp_files = self.export_pptx_to_webp(translated_pptx, output_dir)
                if not webp_files:
                    continue
                
                # Step 3: Move WEBP files to course assets (if course index found)
                if course_index and self.bec_repo_path:
                    moved_count, assets_dir = self.move_webp_to_assets(
                        webp_files, course_index, target_lang
                    )
                    
                    # Step 4: Update markdown files
                    if moved_count > 0:
                        success = self.update_markdown_files(
                            course_index, target_lang, moved_count
                        )
                        if success:
                            self.send_progress_update(
                                f"✅ Completed processing for {target_lang}"
                            )
                        else:
                            self.send_progress_update(
                                f"⚠️ Completed but couldn't update markdown for {target_lang}"
                            )
                else:
                    self.send_progress_update(
                        f"✅ Exported WEBP files for {target_lang} (no course integration)"
                    )
            
            self.send_progress_update(f"\n✅ Finished processing: {input_file.name}")
            
        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error processing {input_file.name}: {e}"
            self.send_progress_update(f"❌ {error_message}")
            logging.exception(error_message)
    
    def before_processing(self):
        """Setup before processing starts."""
        # Validate configuration
        if not self.api_key_deepl:
            messagebox.showerror("Configuration Error", "DeepL API key not configured")
            return False
        
        if not self.api_key_convertapi:
            messagebox.showerror("Configuration Error", "ConvertAPI key not configured")
            return False
        
        # Check if BEC_REPO is set
        if not self.bec_repo_path:
            result = messagebox.askyesno(
                "Configuration Warning",
                "BEC_REPO environment variable not set.\n"
                "Continue without course integration?"
            )
            if not result:
                return False
        
        return True