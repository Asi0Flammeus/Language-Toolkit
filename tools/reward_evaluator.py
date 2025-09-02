"""Reward evaluator tool for calculating translation rewards."""

import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
from pathlib import Path

from ui.base_tool import ToolBase
from core.unified_reward_evaluator import UnifiedRewardEvaluator


class RewardEvaluatorTool(ToolBase):
    """
    Unified reward evaluator for both PPTX and TXT files.
    Supports different reward modes: Image PPTX, Video PPTX, and TXT.
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx', '.ppt', '.txt'}
        
        # Additional variables specific to this tool
        self.reward_mode = tk.StringVar(value="image")  # image, video, txt
        self.target_language = tk.StringVar(value="en")
        self.results = []
        
        # Initialize the unified evaluator
        self.evaluator = UnifiedRewardEvaluator()

    def create_specific_controls(self, parent_frame):
        """Creates UI elements specific to this tool."""
        
        # Language selection
        lang_frame = ttk.LabelFrame(parent_frame, text="Language Selection")
        lang_frame.pack(fill='x', padx=5, pady=5)
        
        # Target language
        target_label = ttk.Label(lang_frame, text="Target Language:")
        target_label.pack(side=tk.LEFT, padx=5)
        
        languages = list(self.evaluator.language_factors.keys())
        target_combo = ttk.Combobox(lang_frame, textvariable=self.target_language, 
                                   values=languages, state="readonly")
        target_combo.pack(side=tk.LEFT, padx=5)
        
        # Reward mode selection
        mode_frame = ttk.LabelFrame(parent_frame, text="Reward Mode")
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Radiobutton(mode_frame, text="Image PPTX (factor 1.5)", 
                       variable=self.reward_mode, 
                       value="image").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="Video PPTX (factor 1.0)", 
                       variable=self.reward_mode, 
                       value="video").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(mode_frame, text="TXT Files", 
                       variable=self.reward_mode, 
                       value="txt").pack(side=tk.LEFT, padx=10)
        
        # CSV export button
        export_frame = ttk.Frame(parent_frame)
        export_frame.pack(fill='x', padx=5, pady=5)
        
        self.export_button = ttk.Button(export_frame, text="Export Results to CSV", 
                                       command=self.export_to_csv, state=tk.DISABLED)
        self.export_button.pack(side=tk.LEFT, padx=5)



    def before_processing(self):
        """Setup before processing starts."""
        self.results = []
        self.export_button.configure(state=tk.DISABLED)

    def process_file(self, input_file: Path, output_dir: Path):
        """Process a single file for reward evaluation."""
        try:
            self.send_progress_update(f"Evaluating {input_file.name}...")
            
            # Evaluate the file
            result = self.evaluator.evaluate_file(
                str(input_file), 
                self.target_language.get(),
                self.reward_mode.get()
            )
            
            self.results.append(result)
            
            # Display results
            if 'error' in result:
                self.send_progress_update(f"ERROR: {result['error']}")
                # Results display will be shown in after_processing()
                return False
            else:
                # Handle different result formats
                if self.reward_mode.get() == 'txt':
                    reward_euros = result['reward_euros']
                    word_count = result['word_count']
                    self.send_progress_update(f"✅ {input_file.name}")
                    self.send_progress_update(f"   Reward: €{reward_euros:.4f}")
                    self.send_progress_update(f"   Words: {word_count}")
                else:
                    # PPTX mode
                    total_reward = result['total_reward']
                    total_slides = result['total_slides']
                    total_text_boxes = result['total_text_boxes']
                    total_words = result['total_words']
                    self.send_progress_update(f"✅ {input_file.name}")
                    self.send_progress_update(f"   Reward: €{total_reward:.4f}")
                    self.send_progress_update(f"   Slides: {total_slides}, Text boxes: {total_text_boxes}, Words: {total_words}")
                
                # Results display will be shown in after_processing()
                return True
                
        except Exception as e:
            error_msg = f"Failed to evaluate {input_file.name}: {str(e)}"
            self.send_progress_update(f"ERROR: {error_msg}")
            logging.error(error_msg, exc_info=True)
            return False

    def update_results_display(self):
        """Update the results display - now just logs to progress."""
        if not self.results:
            self.send_progress_update("No results yet...")
            return
        
        # Calculate summary statistics
        summary = self.evaluator.get_summary_stats(self.results)
        
        if 'error' in summary:
            self.send_progress_update(f"Error generating summary: {summary['error']}")
            return
        
        # Display summary in progress
        file_type = "TXT" if self.reward_mode.get() == 'txt' else "PPTX"
        
        self.send_progress_update(f"\n{file_type} Reward Evaluation Results")
        self.send_progress_update("="*50)
        self.send_progress_update(f"Total Files: {summary['total_files']}")
        
        if file_type == "PPTX":
            self.send_progress_update(f"Total Slides: {summary['total_slides']}")
            self.send_progress_update(f"Total Text Boxes: {summary['total_text_boxes']}")
            self.send_progress_update(f"Total Words: {summary['total_words']}")
        else:
            self.send_progress_update(f"Total Words: {summary['total_words']}")
            self.send_progress_update(f"Avg Words/File: {summary['average_words_per_file']}")
        
        self.send_progress_update(f"Total Reward: €{summary['total_reward_euros']:.4f}")
        self.send_progress_update(f"Avg Reward/File: €{summary['average_reward_per_file']:.4f}")
        
        # Display individual file results in progress
        self.send_progress_update("\nIndividual File Results:")
        self.send_progress_update("-"*30)
        
        for result in self.results:
            if 'error' in result:
                filename = result.get('filename', result.get('file_path', 'Unknown'))
                self.send_progress_update(f"❌ {filename}: {result['error']}")
            else:
                if self.reward_mode.get() == 'txt':
                    filename = result.get('file_path', 'Unknown')
                    reward = result.get('reward_euros', 0)
                    words = result.get('word_count', 0)
                    target_lang = result.get('target_language', 'N/A')
                    difficulty = result.get('difficulty_factor', 0)
                    
                    self.send_progress_update(f"✅ {filename}")
                    self.send_progress_update(f"   Reward: €{reward:.4f}")
                    self.send_progress_update(f"   Words: {words}")
                    self.send_progress_update(f"   Target Language: {target_lang}")
                    self.send_progress_update(f"   Difficulty Factor: {difficulty}")
                else:
                    filename = result.get('filename', 'Unknown')
                    reward = result.get('total_reward', 0)
                    slides = result.get('total_slides', 0)
                    text_boxes = result.get('total_text_boxes', 0)
                    words = result.get('total_words', 0)
                    mode = result.get('mode', 'unknown')
                    
                    self.send_progress_update(f"✅ {filename}")
                    self.send_progress_update(f"   Reward: €{reward:.4f}")
                    self.send_progress_update(f"   Slides: {slides}, Text boxes: {text_boxes}, Words: {words}")
                    self.send_progress_update(f"   Mode: {mode}")
        
        # Enable export button if we have results
        if self.results:
            self.export_button.configure(state=tk.NORMAL)

    def export_to_csv(self):
        """Export results to CSV file."""
        if not self.results:
            messagebox.showwarning("No Results", "No results to export.")
            return
        
        # Ask user for CSV file location
        csv_file = filedialog.asksaveasfilename(
            title="Save Results as CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if csv_file:
            try:
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    
                    if self.reward_mode.get() == 'txt':
                        # TXT CSV format
                        writer.writerow(['File Path', 'Word Count', 'Target Language', 
                                       'Difficulty Factor', 'Euros per Word', 'Reward (Euros)', 'Reward (Cents)', 'Error'])
                        
                        for result in self.results:
                            if 'error' in result:
                                writer.writerow([result.get('file_path', ''), '', '', '', '', '', '', result['error']])
                            else:
                                writer.writerow([
                                    result.get('file_path', ''),
                                    result.get('word_count', 0),
                                    result.get('target_language', ''),
                                    result.get('difficulty_factor', 0),
                                    result.get('euros_per_word', 0),
                                    result.get('reward_euros', 0),
                                    result.get('reward_cents', 0),
                                    ''
                                ])
                    else:
                        # PPTX CSV format
                        writer.writerow(['Filename', 'Total Slides', 'Total Text Boxes', 'Total Words', 
                                       'Mode', 'Total Reward (Euros)', 'Language', 'Error'])
                        
                        for result in self.results:
                            if 'error' in result:
                                writer.writerow([result.get('filename', ''), '', '', '', '', '', '', result['error']])
                            else:
                                writer.writerow([
                                    result.get('filename', ''),
                                    result.get('total_slides', 0),
                                    result.get('total_text_boxes', 0),
                                    result.get('total_words', 0),
                                    result.get('mode', ''),
                                    result.get('total_reward', 0),
                                    result.get('language', ''),
                                    ''
                                ])
                
                self.send_progress_update(f"Results exported to: {csv_file}")
                messagebox.showinfo("Export Successful", f"Results exported to:\n{csv_file}")
            except Exception as e:
                error_msg = f"Failed to export CSV: {str(e)}"
                self.send_progress_update(f"ERROR: {error_msg}")
                messagebox.showerror("Export Error", error_msg)

    def after_processing(self):
        """Cleanup after processing is complete."""
        self.send_progress_update("Reward evaluation completed.")
        self.update_results_display()

    def get_all_files_recursive(self, directory: Path):
        """Get all supported files from directory recursively."""
        files = []
        supported_exts = self.evaluator.get_supported_extensions(self.reward_mode.get())
        for ext in supported_exts:
            files.extend(directory.rglob(f"*{ext}"))
        return files