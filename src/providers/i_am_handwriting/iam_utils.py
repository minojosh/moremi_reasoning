import logging
import xml.etree.ElementTree as ET
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Optional
import fcntl

class ProgressTracker:
    """Track processing progress and enable resuming from failures."""
    
    def __init__(self, results_file: str, progress_file: str = None):
        self.results_file = Path(results_file)
        self.progress_file = Path(progress_file) if progress_file else self.results_file.with_suffix('.progress')
        self.processed_ids: Set[str] = set()
        self.logger = logging.getLogger("progress_tracker")
        
        # Ensure directories exist
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing progress
        self._load_progress()
    
    def _load_progress(self):
        """Load previously processed image IDs from progress file."""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    data = json.load(f)
                    self.processed_ids = set(data.get('processed_ids', []))
                    self.logger.info(f"Loaded progress: {len(self.processed_ids)} items already processed")
            else:
                self.logger.info("No existing progress file found, starting fresh")
        except Exception as e:
            self.logger.error(f"Error loading progress: {e}")
            self.processed_ids = set()
    
    def is_processed(self, image_id: str) -> bool:
        """Check if an image has already been processed."""
        return image_id in self.processed_ids
    
    def mark_processed(self, image_id: str):
        """Mark an image as processed and save progress."""
        self.processed_ids.add(image_id)
        self._save_progress()
    
    def _save_progress(self):
        """Save current progress to disk."""
        try:
            progress_data = {
                'processed_ids': list(self.processed_ids),
                'last_updated': datetime.now().isoformat(),
                'total_processed': len(self.processed_ids)
            }
            
            # Atomic write using temporary file
            temp_file = self.progress_file.with_suffix('.progress.tmp')
            with open(temp_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            
            # Atomic move
            temp_file.replace(self.progress_file)
            
        except Exception as e:
            self.logger.error(f"Error saving progress: {e}")
    
    def get_stats(self) -> Dict:
        """Get processing statistics."""
        return {
            'processed_count': len(self.processed_ids),
            'processed_ids': list(self.processed_ids)
        }

class IncrementalResultSaver:
    """Save results incrementally with file locking for thread safety."""
    
    def __init__(self, results_file: str):
        self.results_file = Path(results_file)
        self.logger = logging.getLogger("incremental_saver")
        
        # Ensure directory exists
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize file if it doesn't exist
        if not self.results_file.exists():
            self._initialize_results_file()
    
    def _initialize_results_file(self):
        """Initialize the results file as an empty JSON array."""
        try:
            with open(self.results_file, 'w') as f:
                json.dump([], f)
            self.logger.info(f"Initialized results file: {self.results_file}")
        except Exception as e:
            self.logger.error(f"Error initializing results file: {e}")
            raise
    
    def append_result(self, result: Dict):
        """Append a single result to the file with file locking."""
        try:
            # Read existing results
            with open(self.results_file, 'r+') as f:
                # Lock the file for exclusive access
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                try:
                    f.seek(0)
                    data = json.load(f)
                except json.JSONDecodeError:
                    # If file is corrupted, start fresh
                    data = []
                
                # Append new result
                data.append(result)
                
                # Write back to file
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
                
                # Unlock will happen automatically when file is closed
            
            self.logger.debug(f"Appended result for image_id: {result.get('image_id', 'unknown')}")
            
        except Exception as e:
            self.logger.error(f"Error appending result: {e}")
            # Don't raise - we don't want to stop processing for save errors
    
    def get_existing_results(self) -> List[Dict]:
        """Get all existing results from the file."""
        try:
            if self.results_file.exists():
                with open(self.results_file, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            self.logger.error(f"Error reading existing results: {e}")
            return []
    
    def backup_results(self, backup_suffix: str = None):
        """Create a backup of the current results file."""
        if not self.results_file.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_suffix = backup_suffix or f"backup_{timestamp}"
        backup_file = self.results_file.with_suffix(f'.{backup_suffix}.json')
        
        try:
            import shutil
            shutil.copy2(self.results_file, backup_file)
            self.logger.info(f"Created backup: {backup_file}")
            return backup_file
        except Exception as e:
            self.logger.error(f"Error creating backup: {e}")
            return None

class RecoveryManager:
    """Manage recovery from failed processing runs."""
    
    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        self.logger = logging.getLogger("recovery_manager")
    
    def find_incomplete_runs(self) -> List[Dict]:
        """Find incomplete processing runs that can be resumed."""
        incomplete_runs = []
        
        try:
            if not self.results_dir.exists():
                return incomplete_runs
            
            # Look for progress files
            for progress_file in self.results_dir.glob("*.progress"):
                results_file = progress_file.with_suffix('.json')
                
                if progress_file.exists():
                    with open(progress_file, 'r') as f:
                        progress_data = json.load(f)
                    
                    run_info = {
                        'progress_file': str(progress_file),
                        'results_file': str(results_file),
                        'processed_count': progress_data.get('total_processed', 0),
                        'last_updated': progress_data.get('last_updated', 'unknown'),
                        'can_resume': True
                    }
                    incomplete_runs.append(run_info)
            
        except Exception as e:
            self.logger.error(f"Error finding incomplete runs: {e}")
        
        return incomplete_runs
    
    def suggest_recovery_options(self, total_samples: int) -> str:
        """Suggest recovery options for the user."""
        incomplete_runs = self.find_incomplete_runs()
        
        if not incomplete_runs:
            return "No incomplete runs found. Starting fresh is the only option."
        
        suggestions = ["Recovery Options Found:\n"]
        
        for i, run in enumerate(incomplete_runs, 1):
            suggestions.append(f"{i}. Resume from: {run['results_file']}")
            suggestions.append(f"   - Processed: {run['processed_count']} items")
            suggestions.append(f"   - Last updated: {run['last_updated']}")
            suggestions.append(f"   - Remaining: {total_samples - run['processed_count']} items")
            suggestions.append("")
        
        return "\n".join(suggestions)

class GroundTruthExtractor:
    """Extract ground truth text from IAM database XML files."""
    
    def __init__(self):
        self.logger = logging.getLogger("ground_truth_extractor")
    
    def extract_text_from_xml(self, xml_path: str) -> str:
        """Extract ground truth text from XML file."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Extract all text elements
            text_parts = []
            for word in root.findall('.//word'):
                text = word.get('text', '').strip()
                if text:
                    text_parts.append(text)
            
            # Join with spaces
            ground_truth = ' '.join(text_parts)
            
            if not ground_truth:
                # Fallback: try to get from line elements
                for line in root.findall('.//line'):
                    text = line.get('text', '').strip()
                    if text:
                        text_parts.append(text)
                ground_truth = ' '.join(text_parts)
            
            return ground_truth.strip()
            
        except Exception as e:
            self.logger.error(f"Error extracting text from {xml_path}: {str(e)}")
            return ""