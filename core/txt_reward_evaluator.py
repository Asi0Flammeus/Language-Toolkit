import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TXTRewardEvaluator:
    def __init__(self, config_path: str = "supported_languages.yml"):
        self.config_path = config_path
        self.language_factors = self._load_language_factors()
        self.euros_per_word = 0.0006

    def _load_language_factors(self) -> Dict[str, float]:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                # Handle both formats: direct dict and nested 'language_factors' key
                if isinstance(data, dict):
                    if 'language_factors' in data:
                        return data['language_factors']
                    else:
                        # Direct format: language_code: factor
                        return data
                return {}
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_path} not found")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            return {}

    def _count_words(self, text: str) -> int:
        """Count words in text, excluding empty lines and whitespace."""
        if not text.strip():
            return 0
        
        # Split by whitespace and filter out empty strings
        words = re.findall(r'\S+', text)
        return len(words)

    def _extract_text_from_txt(self, file_path: str) -> str:
        """Extract text content from a TXT file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as file:
                    return file.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return ""
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""

    def evaluate_single_file(self, file_path: str, target_lang: str) -> Dict:
        """Evaluate reward for a single TXT file."""
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        if not file_path.lower().endswith('.txt'):
            return {"error": f"File is not a TXT file: {file_path}"}

        try:
            # Extract text content
            text_content = self._extract_text_from_txt(file_path)
            
            # Count words
            word_count = self._count_words(text_content)
            
            # Get language difficulty factor
            diff_lang = self.language_factors.get(target_lang, 1.0)
            
            # Calculate reward using the formula: reward = words * diff_lang * euros_per_word
            reward = word_count * diff_lang * self.euros_per_word
            
            return {
                "file_path": file_path,
                "word_count": word_count,
                "target_language": target_lang,
                "difficulty_factor": diff_lang,
                "euros_per_word": self.euros_per_word,
                "reward_euros": round(reward, 4),
                "reward_cents": round(reward * 100, 2)
            }
            
        except Exception as e:
            logger.error(f"Error evaluating file {file_path}: {e}")
            return {"error": f"Error evaluating file: {str(e)}"}

    def evaluate_folder(self, folder_path: str, target_lang: str, recursive: bool = False) -> List[Dict]:
        """Evaluate rewards for all TXT files in a folder."""
        results = []
        
        if not os.path.exists(folder_path):
            return [{"error": f"Folder not found: {folder_path}"}]

        pattern = "**/*.txt" if recursive else "*.txt"
        txt_files = list(Path(folder_path).glob(pattern))
        
        if not txt_files:
            return [{"error": f"No TXT files found in {folder_path}"}]

        for txt_file in txt_files:
            result = self.evaluate_single_file(str(txt_file), target_lang)
            results.append(result)

        return results

    def get_available_languages(self) -> List[str]:
        """Get list of available languages from the configuration."""
        return list(self.language_factors.keys())

    def get_summary_stats(self, results: List[Dict]) -> Dict:
        """Calculate summary statistics for a list of evaluation results."""
        if not results:
            return {}

        valid_results = [r for r in results if "error" not in r]
        if not valid_results:
            return {"error": "No valid results to summarize"}

        total_files = len(valid_results)
        total_words = sum(r["word_count"] for r in valid_results)
        total_reward_euros = sum(r["reward_euros"] for r in valid_results)
        total_reward_cents = sum(r["reward_cents"] for r in valid_results)

        return {
            "total_files": total_files,
            "total_words": total_words,
            "total_reward_euros": round(total_reward_euros, 4),
            "total_reward_cents": round(total_reward_cents, 2),
            "average_words_per_file": round(total_words / total_files, 2) if total_files > 0 else 0,
            "average_reward_per_file": round(total_reward_euros / total_files, 4) if total_files > 0 else 0
        }