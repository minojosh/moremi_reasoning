import Levenshtein
from typing import Dict

class OCRMetrics:
    """Calculate OCR accuracy metrics."""
    
    @staticmethod
    def character_accuracy(predicted: str, ground_truth: str) -> float:
        """Calculate character-level accuracy using edit distance."""
        if not ground_truth:
            return 1.0 if not predicted else 0.0
        
        distance = Levenshtein.distance(predicted, ground_truth)
        accuracy = 1 - (distance / max(len(predicted), len(ground_truth)))
        return max(0.0, accuracy)
    
    @staticmethod
    def word_accuracy(predicted: str, ground_truth: str) -> float:
        """Calculate word-level accuracy."""
        pred_words = predicted.strip().split()
        gt_words = ground_truth.strip().split()
        
        if not gt_words:
            return 1.0 if not pred_words else 0.0
        
        # Use word-level edit distance
        distance = Levenshtein.distance(pred_words, gt_words)
        accuracy = 1 - (distance / max(len(pred_words), len(gt_words)))
        return max(0.0, accuracy)
    
    @staticmethod
    def exact_match(predicted: str, ground_truth: str) -> bool:
        """Check for exact string match."""
        return predicted.strip().lower() == ground_truth.strip().lower()
    
    @staticmethod
    def calculate_all_metrics(predicted: str, ground_truth: str) -> Dict[str, float]:
        """Calculate comprehensive metrics."""
        return {
            "character_accuracy": OCRMetrics.character_accuracy(predicted, ground_truth),
            "word_accuracy": OCRMetrics.word_accuracy(predicted, ground_truth),
            "exact_match": float(OCRMetrics.exact_match(predicted, ground_truth)),
            "edit_distance": float(Levenshtein.distance(predicted, ground_truth))
        }