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
        
        # Multiple target languages selection
        self.selected_target_langs = set()
        
        # Group elements option for PNG export
        self.group_elements = tk.BooleanVar(value=False)
        
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
        
        # Export options frame
        export_frame = ttk.LabelFrame(parent_frame, text="Export Options")
        export_frame.pack(fill='x', padx=5, pady=5)
        
        # Group elements checkbox
        ttk.Checkbutton(
            export_frame,
            text="Group elements (crop PNG to content bounds)",
            variable=self.group_elements
        ).pack(padx=5, pady=5, anchor='w')

    def create_language_selection(self):
        """Creates enhanced language selection UI with multiple target language support."""
        # Main language frame
        self.lang_frame = ttk.LabelFrame(self.master, text="Language Selection")
        self.lang_frame.pack(fill='x', padx=5, pady=5)

        # Source language frame
        source_frame = ttk.Frame(self.lang_frame)
        source_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(source_frame, text="Source Language:").pack(side=tk.LEFT, padx=5)
        self.source_lang_combo = ttk.Combobox(
            source_frame, 
            textvariable=self.source_lang,
            values=list(self.supported_languages.get("source_languages", {}).keys()),
            state="readonly",
            width=10
        )
        self.source_lang_combo.pack(side=tk.LEFT, padx=5)

        # Target language selection button
        target_button = ttk.Button(
            self.lang_frame,
            text="Select Target Languages",
            command=self.open_target_language_selector
        )
        target_button.pack(side=tk.LEFT, padx=5, pady=5)

        # Selected languages display
        self.selected_langs_display = tk.Text(
            self.lang_frame,
            height=2,
            width=30,
            wrap=tk.WORD,
            state='disabled'
        )
        self.selected_langs_display.pack(side=tk.LEFT, padx=5, pady=5, fill='x', expand=True)

    def open_target_language_selector(self):
        """Opens a dialog for selecting multiple target languages."""
        selector = tk.Toplevel(self.master)
        selector.title("Select Target Languages")
        selector.geometry("300x400")
        
        # Make dialog modal
        selector.transient(self.master)
        selector.grab_set()
        
        # Create scrollable frame
        main_frame = ttk.Frame(selector)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Variables to store checkbutton states
        checkbutton_vars = {}
        
        # Create checkbuttons for each target language
        target_languages = self.supported_languages.get("target_languages", {})
        for code, name in sorted(target_languages.items()):
            # Display simplified Portuguese codes
            display_code = self.get_display_language_code(code)
            var = tk.BooleanVar(value=code in self.selected_target_langs)
            checkbutton_vars[code] = var
            ttk.Checkbutton(
                scrollable_frame,
                text=f"{display_code} - {name}",
                variable=var
            ).pack(anchor='w', padx=5, pady=2)

        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def save_selection():
            self.selected_target_langs = {
                code for code, var in checkbutton_vars.items() if var.get()
            }
            self.update_selected_languages_display()
            selector.destroy()

        # Add buttons
        button_frame = ttk.Frame(selector)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(
            button_frame,
            text="Select All",
            command=lambda: [var.set(True) for var in checkbutton_vars.values()]
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Clear All",
            command=lambda: [var.set(False) for var in checkbutton_vars.values()]
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Save",
            command=save_selection
        ).pack(side=tk.RIGHT, padx=5)

    def update_selected_languages_display(self):
        """Updates the display of selected target languages."""
        self.selected_langs_display.config(state='normal')
        self.selected_langs_display.delete(1.0, tk.END)
        
        if self.selected_target_langs:
            # Display simplified codes for Portuguese
            display_codes = [self.get_display_language_code(code) for code in sorted(self.selected_target_langs)]
            langs_text = ", ".join(display_codes)
            self.selected_langs_display.insert(tk.END, f"Selected: {langs_text}")
        else:
            self.selected_langs_display.insert(tk.END, "No target languages selected")
        
        self.selected_langs_display.config(state='disabled')

    def get_display_language_code(self, code: str) -> str:
        """Get display-friendly language code (simplify Portuguese codes to 'pt')."""
        if code in ['pt-br', 'pt-pt']:
            return 'pt'
        return code

    def get_deepl_language_code(self, code: str) -> str:
        """Get DeepL-compatible language code (use pt-BR for Portuguese)."""
        if code in ['pt', 'pt-br', 'pt-pt']:
            return 'pt-BR'
        return code
    
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
    
    def translate_pptx(self, input_file: Path, output_dir: Path, display_lang: str, actual_lang_code: str = None) -> Optional[Path]:
        """Translate PPTX file to target language.
        
        Args:
            input_file: Input PPTX file path
            output_dir: Output directory path
            display_lang: Language code for display and file naming (e.g., 'pt')
            actual_lang_code: Actual language code from config (e.g., 'pt-br'), defaults to display_lang
        """
        try:
            # Use actual_lang_code if provided, otherwise use display_lang
            if actual_lang_code is None:
                actual_lang_code = display_lang
            
            # Create output filename using display code
            output_filename = f"{input_file.stem}_{display_lang}{input_file.suffix}"
            output_file = output_dir / output_filename
            
            # Skip if already exists
            if self.check_output_exists.get() and output_file.exists():
                self.send_progress_update(f"⏩ Skipping translation - file exists: {output_filename}")
                return output_file
            
            self.send_progress_update(f"🌐 Translating to {display_lang}: {input_file.name}")
            
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
            
            # Convert to DeepL-compatible language code
            deepl_target_lang = self.get_deepl_language_code(actual_lang_code)
            
            # Process the file
            result = processor.process_file(
                input_file,
                output_file,
                source_language=self.source_lang.get(),
                target_language=deepl_target_lang
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
            
            # Convert to WEBP (with group_elements option if selected)
            webp_files = converter.convert_pptx_to_webp(
                input_path=pptx_file,
                output_dir=output_dir,
                quality=85,
                group_elements=self.group_elements.get()
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
            
            # Use multiple target languages if selected, otherwise fall back to single target
            languages_to_process = list(self.selected_target_langs) if self.selected_target_langs else []
            
            # If no multiple languages selected, use the single target language from standard selection
            if not languages_to_process:
                target_lang = self.target_lang.get()
                if target_lang:
                    languages_to_process = [target_lang]
            
            if not languages_to_process:
                self.send_progress_update("⚠️ No target languages selected")
                return
            
            self.send_progress_update(f"🌍 Processing {len(languages_to_process)} language(s): {', '.join([self.get_display_language_code(lang) for lang in languages_to_process])}")
            
            # Process each target language
            for target_lang in languages_to_process:
                if self.stop_flag.is_set():
                    raise InterruptedError("Processing stopped by user")
                
                # Use display code for user feedback and file paths
                display_code = self.get_display_language_code(target_lang)
                self.send_progress_update(f"\n🌐 Processing language: {display_code}")
                
                # Step 1: Translate PPTX (using display code for file naming)
                translated_pptx = self.translate_pptx(input_file, output_dir, display_code, target_lang)
                if not translated_pptx:
                    continue
                
                # Step 2: Export to WEBP (save to output directory first)
                webp_files = self.export_pptx_to_webp(translated_pptx, output_dir)
                if not webp_files:
                    continue
                
                # Step 3: Move WEBP files to course assets (if course index found)
                if course_index and self.bec_repo_path:
                    moved_count, assets_dir = self.move_webp_to_assets(
                        webp_files, course_index, display_code
                    )
                    
                    # Step 4: Update markdown files
                    if moved_count > 0:
                        success = self.update_markdown_files(
                            course_index, display_code, moved_count
                        )
                        if success:
                            self.send_progress_update(
                                f"✅ Completed processing for {display_code}"
                            )
                        else:
                            self.send_progress_update(
                                f"⚠️ Completed but couldn't update markdown for {display_code}"
                            )
                else:
                    self.send_progress_update(
                        f"✅ Exported WEBP files for {display_code} (no course integration)"
                    )
            
            self.send_progress_update(f"\n✅ Finished processing: {input_file.name}")
            
        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error processing {input_file.name}: {e}"
            self.send_progress_update(f"❌ {error_message}")
            logging.exception(error_message)
    
    def process_paths(self):
        """Override to ensure at least one target language is selected."""
        # Check if we have target languages selected
        if not self.selected_target_langs and not self.target_lang.get():
            messagebox.showerror("Error", "No target languages selected.")
            return
        
        # Call parent implementation
        super().process_paths()

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