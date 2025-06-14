import os
import json
import base64
import requests
import logging
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from tenacity import retry, stop_after_attempt, wait_exponential

class ReportProcessor:
    """Process medical reports for various modalities using the Gemini API."""
    
    def __init__(
        self, 
        api_key: str, 
        report_file_path: Union[str, Path], 
        image_base_path: Union[str, Path],
        modality: str = "chest_xray",
        settings: Optional[Dict] = None
    ):
        """
        Initialize the report processor.
        
        Args:
            api_key: Gemini API key
            report_file_path: Path to report file or directory containing reports
            image_base_path: Base path for images
            modality: Medical imaging modality (e.g., chest_xray, mammogram)
            settings: Settings from settings.yaml
        """
        self.api_key = api_key
        self.report_file_path = Path(report_file_path)
        self.image_base_path = Path(image_base_path)
        self.modality = modality
        self.settings = settings or {}
        
        # Set up API endpoint
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"
        
        # Set up output directory
        self.output_dir = Path(f"reports/{modality}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up logging
        self._setup_logging()
        
        # Load processed records
        self.consolidated_file = self.output_dir / f"{modality}_reasoning_consolidated.json"
        self.processed_records = self._load_processed_records()
        
        # Get modality template
        self.template = self._get_modality_template()
        
        # Initialize records list
        self.records = self._load_records()
        
        self.logger.info(f"Initialized ReportProcessor for {modality}")
        self.logger.info(f"Found {len(self.records)} total records")
        self.logger.info(f"Found {len(self.processed_records)} already processed records")
    
    def _setup_logging(self):
        """Set up logging configuration."""
        self.logger = logging.getLogger(f"{self.modality}_processor")
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        log_file = f"logs/report_processor_{datetime.now().strftime('%Y-%m-%d_%Hh%Mm%Ss')}.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
    
    def _get_modality_template(self) -> str:
        """Get the template for the current modality."""
        if self.settings and "modalities" in self.settings:
            modality_config = self.settings.get("modalities", {}).get(self.modality, {})
            return modality_config.get("base_template", "")
        return ""
    
    def _load_processed_records(self) -> Dict[str, Any]:
        """Load previously processed records."""
        if self.consolidated_file.exists():
            try:
                with open(self.consolidated_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.error(f"Error loading consolidated file: {self.consolidated_file}")
                return {}
        return {}
    
    def _load_records(self) -> List[Dict[str, Any]]:
        """Load records to process based on modality."""
        if self.modality == "chest_xray":
            # Chest X-ray specific logic - load from JSON file
            try:
                with open(self.report_file_path, 'r') as f:
                    data = json.load(f)
                return data.get("reports", [])
            except (json.JSONDecodeError, FileNotFoundError) as e:
                self.logger.error(f"Error loading chest X-ray reports: {e}")
                return []
        else:
            # For other modalities - load from individual JSON files in directory
            records = []
            try:
                if self.report_file_path.is_dir():
                    for json_file in self.report_file_path.glob("*.json"):
                        try:
                            with open(json_file, 'r') as f:
                                patient_data = json.load(f)
                                # Add patient_id based on filename
                                patient_data["patient_id"] = json_file.stem
                                records.append(patient_data)
                        except json.JSONDecodeError:
                            self.logger.error(f"Error loading patient file: {json_file}")
                            continue
                return records
            except Exception as e:
                self.logger.error(f"Error loading records for {self.modality}: {e}")
                return []
    
    def _get_image_path(self, record: Dict[str, Any]) -> Optional[str]:
        """Get image path for a record based on modality."""
        if self.modality == "chest_xray":
            # Chest X-ray specific logic
            case_id = record.get("case_id")
            if not case_id:
                return None
            
            # Standardized image path pattern for chest X-rays
            image_path = self.image_base_path / f"{case_id}.jpg"
            if image_path.exists():
                return str(image_path)
            
            # Try alternate formats
            for ext in [".jpeg", ".png"]:
                alt_path = self.image_base_path / f"{case_id}{ext}"
                if alt_path.exists():
                    return str(alt_path)
            
            return None
        else:
            # For other modalities
            patient_id = record.get("patient_id")
            if not patient_id:
                return None
            
            # Check for direct match
            for ext in [".jpg", ".jpeg", ".png"]:
                image_path = self.image_base_path / f"{patient_id}{ext}"
                if image_path.exists():
                    return str(image_path)
            
            # Try fuzzy matching
            for img_file in self.image_base_path.glob("*.jpg"):
                if patient_id in img_file.stem:
                    return str(img_file)
            
            return None
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def _find_ground_truth(self, patient_id: str) -> Optional[Dict[str, str]]:
        """Find ground truth data based on modality."""
        if self.modality == "chest_xray":
            # No special handling for chest X-rays
            return None
        else:
            # For other modalities, look in All_Matches_Combined directory
            all_matches_dir = Path(self.settings.get("data_paths", {}).get("all_matches_combined", "All_Matches_Combined"))
            
            # Look for patient directory
            for patient_dir in all_matches_dir.glob(f"Patient-{patient_id}*"):
                if patient_dir.is_dir():
                    # Find docx and image files
                    docx_files = list(patient_dir.glob("*.doc*"))
                    image_files = list(patient_dir.glob(f"*{patient_id}*_collage.jpg"))
                    
                    if docx_files and image_files:
                        return {
                            "docx_path": str(docx_files[0]),
                            "image_path": str(image_files[0])
                        }
            
            return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
    def _call_gemini_api(self, image_path: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Call Gemini API to generate reasoning for an image."""
        # Encode image
        encoded_image = self._encode_image(image_path)
        
        # Prepare request payload
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        # Check for existing ground truth
        patient_id = record.get("patient_id") or record.get("case_id")
        ground_truth = self._find_ground_truth(patient_id) if patient_id else None
        
        # Prepare content parts
        content_parts = [
            {
                "text": self.template
            },
            {
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": encoded_image
                }
            }
        ]
        
        # Add context from record
        context = json.dumps(record, indent=2)
        content_parts.append({"text": f"Patient Context: {context}"})
        
        # Prepare request data
        request_data = {
            "contents": [
                {
                    "role": "user",
                    "parts": content_parts
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 8192
            }
        }
        
        # Make API request
        response = requests.post(
            f"{self.api_url}?key={self.api_key}",
            headers=headers,
            json=request_data
        )
        
        # Check response
        if response.status_code != 200:
            error_message = f"API error: {response.status_code} - {response.text}"
            self.logger.error(error_message)
            raise Exception(error_message)
        
        # Parse response
        response_data = response.json()
        
        # Extract text response
        text_response = response_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        try:
            # Extract JSON from text
            start_idx = text_response.find("{")
            end_idx = text_response.rfind("}")
            
            if start_idx != -1 and end_idx != -1:
                json_str = text_response[start_idx:end_idx+1]
                reasoning_data = json.loads(json_str)
                
                # Add image URL and ground truth
                reasoning_data["img_url"] = image_path
                reasoning_data["ground_truth"] = ground_truth["docx_path"] if ground_truth else ""
                
                return reasoning_data
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Error parsing API response: {e}")
            # Try to create a structured response from unstructured text
            return {
                "img_url": image_path,
                "question": "Error parsing response",
                "complex_cot": text_response[:1000],  # Truncate to avoid huge error responses
                "final_answer": "Error: Couldn't parse structured response",
                "ground_truth": ground_truth["docx_path"] if ground_truth else ""
            }
    
    def process_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single record."""
        # Extract patient or case ID
        patient_id = record.get("patient_id") or record.get("case_id")
        if not patient_id:
            self.logger.error("Record missing patient_id or case_id")
            return None
        
        # Skip if already processed
        if patient_id in self.processed_records:
            self.logger.info(f"Skipping already processed record: {patient_id}")
            return self.processed_records[patient_id]
        
        # Get image path
        image_path = self._get_image_path(record)
        if not image_path:
            self.logger.error(f"Image not found for record: {patient_id}")
            return None
        
        try:
            # Call Gemini API
            self.logger.info(f"Processing record: {patient_id}")
            result = self._call_gemini_api(image_path, record)
            
            # Save individual result
            output_file = self.output_dir / f"{patient_id}_{self.modality}_reasoning.json"
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            
            # Update processed records
            self.processed_records[patient_id] = result
            
            return result
        except Exception as e:
            self.logger.error(f"Error processing record {patient_id}: {e}")
            return None
    
    def process_reports(self, num_reports: Optional[int] = None):
        """Process all or a limited number of reports."""
        # Limit records if specified
        records_to_process = self.records
        if num_reports is not None:
            records_to_process = records_to_process[:num_reports]
        
        # Process records
        for record in tqdm(records_to_process, desc=f"Processing {self.modality} records"):
            self.process_record(record)
            # Save after each record to maintain progress
            self.save_consolidated_records()
    
    def process_specific_patients(self, patient_ids: List[str]):
        """Process specific patients by ID."""
        for record in self.records:
            patient_id = record.get("patient_id") or record.get("case_id")
            if patient_id in patient_ids:
                self.process_record(record)
                # Save after each record to maintain progress
                self.save_consolidated_records()
    
    def save_consolidated_records(self):
        """Save all processed records to a consolidated file."""
        with open(self.consolidated_file, "w") as f:
            json.dump(self.processed_records, f, indent=2)
        
        self.logger.info(f"Saved {len(self.processed_records)} records to {self.consolidated_file}")
