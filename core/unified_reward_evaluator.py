import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.pptx_reward_evaluator import PPTXRewardEvaluator
from core.txt_reward_evaluator import TXTRewardEvaluator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnifiedRewardEvaluator:
    """
    Unified reward evaluator that handles both PPTX and TXT files
    with different reward calculation modes.
    """
    
    def __init__(self, config_path: str = "supported_languages.yml"):
        self.config_path = config_path
        self.pptx_evaluator = PPTXRewardEvaluator(config_path)
        self.txt_evaluator = TXTRewardEvaluator(config_path)
        self.language_factors = self.txt_evaluator.language_factors

    def evaluate_file(self, file_path: str, target_lang: str, reward_mode: str) -> Dict:
        """
        Evaluate reward for a single file based on the reward mode.
        
        Args:
            file_path: Path to the file
            target_lang: Target language code
            reward_mode: One of 'image', 'video', 'txt'
            
        Returns:
            Dictionary containing evaluation results
        """
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        file_ext = Path(file_path).suffix.lower()
        
        if reward_mode == 'txt':
            if file_ext != '.txt':
                return {"error": f"TXT mode selected but file is not a .txt file: {file_path}"}
            return self.txt_evaluator.evaluate_single_file(file_path, target_lang)
        
        elif reward_mode in ['image', 'video']:
            if file_ext not in ['.pptx', '.ppt']:
                return {"error": f"PPTX mode selected but file is not a PowerPoint file: {file_path}"}
            return self.pptx_evaluator.evaluate_pptx(file_path, target_lang, reward_mode)
        
        else:
            return {"error": f"Invalid reward mode: {reward_mode}"}

    def evaluate_folder(self, folder_path: str, target_lang: str, reward_mode: str, recursive: bool = False) -> List[Dict]:
        """
        Evaluate rewards for files in a folder based on the reward mode.
        
        Args:
            folder_path: Path to the folder
            target_lang: Target language code
            reward_mode: One of 'image', 'video', 'txt'
            recursive: Whether to search recursively
            
        Returns:
            List of evaluation results
        """
        results = []
        
        if not os.path.exists(folder_path):
            return [{"error": f"Folder not found: {folder_path}"}]

        if reward_mode == 'txt':
            pattern = "**/*.txt" if recursive else "*.txt"
            files = list(Path(folder_path).glob(pattern))
        elif reward_mode in ['image', 'video']:
            pattern1 = "**/*.pptx" if recursive else "*.pptx"
            pattern2 = "**/*.ppt" if recursive else "*.ppt"
            files = list(Path(folder_path).glob(pattern1)) + list(Path(folder_path).glob(pattern2))
        else:
            return [{"error": f"Invalid reward mode: {reward_mode}"}]
        
        if not files:
            file_type = "TXT" if reward_mode == 'txt' else "PowerPoint"
            return [{"error": f"No {file_type} files found in {folder_path}"}]

        for file_path in files:
            result = self.evaluate_file(str(file_path), target_lang, reward_mode)
            results.append(result)

        return results

    def get_available_languages(self) -> List[str]:
        """Get list of available languages from the configuration."""
        return list(self.language_factors.keys())

    def get_summary_stats(self, results: List[Dict]) -> Dict:
        """
        Calculate summary statistics for a list of evaluation results.
        
        Args:
            results: List of evaluation results
            
        Returns:
            Dictionary containing summary statistics
        """
        if not results:
            return {}

        valid_results = [r for r in results if "error" not in r]
        if not valid_results:
            return {"error": "No valid results to summarize"}

        # Determine if results are from PPTX or TXT evaluation
        first_result = valid_results[0]
        is_pptx = 'total_slides' in first_result
        is_txt = 'word_count' in first_result and 'total_slides' not in first_result

        total_files = len(valid_results)
        
        if is_pptx:
            total_reward = sum(r["total_reward"] for r in valid_results)
            total_slides = sum(r["total_slides"] for r in valid_results)
            total_text_boxes = sum(r["total_text_boxes"] for r in valid_results)
            total_words = sum(r["total_words"] for r in valid_results)
            
            return {
                "total_files": total_files,
                "total_slides": total_slides,
                "total_text_boxes": total_text_boxes,
                "total_words": total_words,
                "total_reward_euros": round(total_reward, 4),
                "total_reward_cents": round(total_reward * 100, 2),
                "average_reward_per_file": round(total_reward / total_files, 4) if total_files > 0 else 0,
                "file_type": "PPTX"
            }
        
        elif is_txt:
            total_reward = sum(r["reward_euros"] for r in valid_results)
            total_words = sum(r["word_count"] for r in valid_results)
            
            return {
                "total_files": total_files,
                "total_words": total_words,
                "total_reward_euros": round(total_reward, 4),
                "total_reward_cents": round(total_reward * 100, 2),
                "average_words_per_file": round(total_words / total_files, 2) if total_files > 0 else 0,
                "average_reward_per_file": round(total_reward / total_files, 4) if total_files > 0 else 0,
                "file_type": "TXT"
            }
        
        else:
            return {"error": "Unable to determine file type for summary"}

    def get_supported_extensions(self, reward_mode: str) -> List[str]:
        """Get supported file extensions for a given reward mode."""
        if reward_mode == 'txt':
            return ['.txt']
        elif reward_mode in ['image', 'video']:
            return ['.pptx', '.ppt']
        else:
            return []