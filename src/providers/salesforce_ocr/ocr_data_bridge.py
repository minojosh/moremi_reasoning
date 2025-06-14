"""
OCR Data Bridge: Connects Salesforce OCR data processing with multimodal QRA reasoning pipeline
"""

import os
import json
import pandas as pd
import random
import re
from pathlib import Path
from typing import List, Dict, Any
import yaml
from src.utils.pathfinder import get_src_dir
SRC_DIR = get_src_dir()
CONFIG_DIR = Path(SRC_DIR) / "config"

class OCRDataBridge:
    def __init__(self, config_path: str = None):
        """Initialize OCR Data Bridge with configuration"""
        if config_path is None:
            config_path = CONFIG_DIR / "reasoning_config.yaml"

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.ocr_questions = [
            "What is all the text visible in this image?",
            "Extract and transcribe all readable text from this image.",
            "What text content can you identify in this image?",
            "Please read and provide all the text shown in this image.",
            "Transcribe any visible text, labels, or written content in this image.",
            "What written information is displayed in this image?",
            "Extract all textual elements visible in this image.",
            "Please identify and transcribe all text content in this image."
        ]
    
    def clean_ocr_text(self, text: str, granularity: int = 7) -> str:
        """Clean OCR text based on granularity level"""
        if not text:
            return ""
        
        if granularity == 5:
            # Remove OCR XML tags and bbox information for cleaner output
            text = re.sub(r'<ocr>([^<]+)</ocr><bbox>[^<]+</bbox>', r'\1', text)
            text = re.sub(r'<[^>]+>', '', text)  # Remove any remaining tags
        
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def extract_ocr_from_salesforce_row(self, row: pd.Series, preferred_granularity: int = 0) -> str:
        """Extract OCR text from a Salesforce dataset row"""
        captions_str = row.get('captions', '')
        if not captions_str:
            return ""
        
        try:
            captions_list = json.loads(captions_str)
            
            # Try to find preferred granularity
            for cap_obj in captions_list:
                if cap_obj.get('granularity') == preferred_granularity:
                    if not cap_obj.get('include_datacomp_raw_cap', True):
                        text = cap_obj.get('text', '')
                        return self.clean_ocr_text(text, preferred_granularity)
            
            # Fallback to any text from preferred granularity
            for cap_obj in captions_list:
                if cap_obj.get('granularity') == preferred_granularity:
                    text = cap_obj.get('text', '')
                    return self.clean_ocr_text(text, preferred_granularity)
            
            # Final fallback - use granularity 0 or 5
            for fallback_granularity in [0, 5]:
                for cap_obj in captions_list:
                    if cap_obj.get('granularity') == fallback_granularity:
                        text = cap_obj.get('text', '')
                        return self.clean_ocr_text(text, fallback_granularity)
            
            # Very last resort - first caption
            if captions_list:
                text = captions_list[0].get('text', '')
                return self.clean_ocr_text(text, 0)
                
        except json.JSONDecodeError as e:
            print(f"Error parsing captions JSON: {e}")
            return ""
        
        return ""
    
    def create_ocr_qa_pairs(self, 
                           salesforce_df: pd.DataFrame, 
                           image_dir: str,
                           num_samples: int = None,
                           granularity: int = 0,
                           seed: int = 42) -> List[Dict[str, Any]]:
        """Create Q&A pairs from Salesforce OCR data"""
        
        random.seed(seed)
        
        if num_samples and num_samples < len(salesforce_df):
            sample_df = salesforce_df.sample(n=num_samples, random_state=seed)
        else:
            sample_df = salesforce_df
        
        qa_pairs = []
        
        for idx, row in sample_df.iterrows():
            uid = row.get('uid', f'unknown_{idx}')
            image_url = row.get('url', '')
            
            # Extract OCR text
            ocr_text = self.extract_ocr_from_salesforce_row(row, granularity)
            
            if not ocr_text:
                print(f"Warning: No OCR text found for UID {uid}, skipping...")
                continue
            
            # Generate question
            question = random.choice(self.ocr_questions)
            
            # Determine image path/URL
            local_image_path = os.path.join(image_dir, f"{uid}.jpg")
            if os.path.exists(local_image_path):
                img_urls = [local_image_path]
            elif image_url:
                img_urls = [image_url]
            else:
                print(f"Warning: No image found for UID {uid}, skipping...")
                continue
            
            qa_pair = {
                "process_id": uid,
                "Open-ended Verifiable Question": question,
                "Ground-True Answer": ocr_text,
                "img_urls": img_urls,
                "metadata": {
                    "granularity": granularity,
                    "original_url": image_url,
                    "uid": uid
                }
            }
            
            qa_pairs.append(qa_pair)
        
        return qa_pairs
    
    def save_for_reasoning_pipeline(self, 
                                  qa_pairs: List[Dict[str, Any]], 
                                  output_path: str) -> str:
        """Save QA pairs in format expected by multimodal_QRA_pair.py"""
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        
        print(f"Saved {len(qa_pairs)} QA pairs to {output_path}")
        return output_path
    
    def validate_qa_pairs(self, qa_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate QA pairs for compatibility with reasoning pipeline"""
        validation_results = {
            "total_pairs": len(qa_pairs),
            "valid_pairs": 0,
            "issues": []
        }
        
        required_fields = ["process_id", "Open-ended Verifiable Question", "Ground-True Answer", "img_urls"]
        
        for i, pair in enumerate(qa_pairs):
            pair_issues = []
            
            # Check required fields
            for field in required_fields:
                if field not in pair:
                    pair_issues.append(f"Missing field: {field}")
                elif not pair[field]:
                    pair_issues.append(f"Empty field: {field}")
            
            # Check img_urls format
            if "img_urls" in pair:
                if not isinstance(pair["img_urls"], list):
                    pair_issues.append("img_urls should be a list")
                elif len(pair["img_urls"]) == 0:
                    pair_issues.append("img_urls list is empty")
            
            # Check text length
            if "Ground-True Answer" in pair:
                if len(pair["Ground-True Answer"]) < 10:
                    pair_issues.append("OCR text too short (< 10 characters)")
                elif len(pair["Ground-True Answer"]) > 5000:
                    pair_issues.append("OCR text very long (> 5000 characters)")
            
            if pair_issues:
                validation_results["issues"].append({
                    "pair_index": i,
                    "process_id": pair.get("process_id", "unknown"),
                    "issues": pair_issues
                })
            else:
                validation_results["valid_pairs"] += 1
        
        return validation_results

def main():
    """Example usage of OCR Data Bridge"""
    bridge = OCRDataBridge()
    
    # Example: Load Salesforce data and create QA pairs
    # This assumes you have salesforce data loaded as a DataFrame
    
    print("OCR Data Bridge - Example Usage")
    print("=" * 50)
    
    # Load sample data (you would replace this with your actual data loading)
    sample_data = {
        'uid': ['sample1', 'sample2'],
        'url': ['http://example.com/img1.jpg', 'http://example.com/img2.jpg'],
        'captions': [
            json.dumps([{"granularity": 0, "text": "Sample text 1", "include_datacomp_raw_cap": False}]),
            json.dumps([{"granularity": 0, "text": "Sample text 2", "include_datacomp_raw_cap": False}])
        ]
    }
    
    df = pd.DataFrame(sample_data)
    
    # Create QA pairs
    qa_pairs = bridge.create_ocr_qa_pairs(
        salesforce_df=df,
        image_dir="./salesforce_images",
        num_samples=2,
        granularity=7
    )
    
    # Validate QA pairs
    validation = bridge.validate_qa_pairs(qa_pairs)
    print(f"Validation Results: {validation}")
    
    # Save for reasoning pipeline
    output_path = "ocr_qa_pairs.json"
    bridge.save_for_reasoning_pipeline(qa_pairs, output_path)
    
    print(f"Created {len(qa_pairs)} QA pairs ready for reasoning pipeline")

if __name__ == "__main__":
    main()
