#!/usr/bin/env python3
"""
OCR Helper Functions
Clean utilities for handwriting OCR processing - uses STANDARD reasoning engine interfaces
"""
import re
from typing import Dict, List, Tuple

def extract_ocr_transcription(response_text: str) -> str:
    """
    Extract EXACT transcription from OCR response, preserving all formatting.
    Uses the standard extract_final_conclusion from reasoning engine.
    """
    if not response_text or not response_text.strip():
        return ""
    
    # Import here to avoid circular imports
    from core.reasoning_engine import extract_final_conclusion
    
    # Use the standard extraction with OCR content type
    result = extract_final_conclusion(response_text, content_type="ocr")
    
    # Additional OCR-specific cleanup while preserving exact spacing
    if result:
        # Remove only markdown formatting, preserve ALL actual content
        result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
        result = re.sub(r'\*([^*]+)\*', r'\1', result)
        # Convert newlines to spaces but preserve exact character spacing
        result = re.sub(r'\n+', ' ', result)
        return result.strip()
    
    return ""

def check_ocr_accuracy(response: str, reference: str, gpt_instance, query_history: List[str] = None, response_history: List[str] = None) -> bool:
    """
    Check OCR accuracy using the STANDARD reasoning engine verification.
    Uses the same interface as multimodal_simply.py
    """
    if query_history is None:
        query_history = []
    if response_history is None:
        response_history = []
    
    # Import here to avoid circular imports
    from core.reasoning_engine import check_answer_accuracy
    
    # Use the standard verification with OCR content type
    return check_answer_accuracy(response, reference, gpt_instance, query_history, response_history, content_type="ocr")

def calculate_confidence_score(strategies_used: List[str], verification_passed: bool, reasoning_depth: int) -> float:
    """Calculate confidence based on reasoning success and depth."""
    base_confidence = 0.3
    
    # Major boost for verification passing
    if verification_passed:
        base_confidence += 0.5
    
    # Boost for reasoning depth (more attempts = more thorough)
    depth_boost = min(reasoning_depth * 0.03, 0.15)
    base_confidence += depth_boost
    
    # Small boost for using multiple strategies
    strategy_boost = min(len(set(strategies_used)) * 0.02, 0.05)
    base_confidence += strategy_boost
    
    return min(base_confidence, 1.0)

def build_result_dict(transcription: str, confidence: float, reasoning_trace: List[str], 
                     strategies_used: List[str], verification_passed: bool) -> Dict:
    """Build simple result dictionary for OCR transcription."""
    return {
        "final_transcription": transcription,
        "confidence": confidence,
        "reasoning_trace": reasoning_trace,
        "strategies_used": strategies_used,
        "verification_passed": verification_passed,
        "error": None
    }

def build_error_result(error_msg: str, image_id: str = None) -> Dict:
    """Build error result dictionary."""
    return {
        "final_transcription": "",
        "confidence": 0.0,
        "error": error_msg,
        "reasoning_trace": [],
        "strategies_used": [],
        "verification_passed": False,
        "image_id": image_id
    }
