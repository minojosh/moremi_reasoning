#!/usr/bin/env python3
import os
import yaml
import json
import base64
import logging
import asyncio
import aiohttp
import dotenv
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
dotenv.load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("modality_processor")

class ModalityProcessor:
    """Process different medical imaging modalities for reasoning data generation."""
    
    def __init__(self, settings_path: str = "settings.yaml"):
        """Initialize with settings from YAML file.
        
        Args:
            settings_path: Path to settings.yaml file
        """
        self.settings = self._load_settings(settings_path)
        self.version = self.settings.get("version", "1.0")
        self.modalities = self.settings.get("modalities", {})
        self.data_paths = self.settings.get("data_paths", {})
        self.processing = self.settings.get("processing", {})
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
        
    def _load_settings(self, settings_path: str) -> Dict[str, Any]:
        """Load settings from YAML file."""
        with open(settings_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get_modality_template(self, modality: str) -> str:
        """Get the template for a specific modality."""
        if modality not in self.modalities:
            raise ValueError(f"Modality '{modality}' not configured in settings.yaml")
        
        return self.modalities[modality].get("base_template", "")
    
    def get_patient_data(self, patient_id: str) -> Dict[str, Any]:
        """Get patient data from JSON file.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Dict containing patient data
        """
        cot_dir = Path(self.data_paths.get("cot", "cot"))
        patient_file = cot_dir / f"{patient_id}.json"
        
        if not patient_file.exists():
            raise FileNotFoundError(f"Patient file not found: {patient_file}")
        
        with open(patient_file, 'r') as f:
            return json.load(f)
    
    def find_ground_truth(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Find ground truth data for a patient.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Dict containing ground truth data or None if not found
        """
        all_matches_dir = Path(self.data_paths.get("all_matches_combined", "All_Matches_Combined"))
        
        # Look for patient directory
        for patient_dir in all_matches_dir.glob(f"Patient-{patient_id}*"):
            if patient_dir.is_dir():
                # Find docx file
                docx_files = list(patient_dir.glob("*.doc*"))
                image_files = list(patient_dir.glob(f"*{patient_id}*_collage.jpg"))
                
                if docx_files and image_files:
                    return {
                        "docx_path": str(docx_files[0]),
                        "image_path": str(image_files[0])
                    }
        
        return None
    
    def find_image(self, patient_id: str) -> Optional[str]:
        """Find image file for a patient.
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Path to image file or None if not found
        """
        images_dir = Path(self.data_paths.get("images", "images"))
        
        # Look for exact matches first
        exact_matches = list(images_dir.glob(f"*{patient_id}*.jpg"))
        if exact_matches:
            return str(exact_matches[0])
        
        # Try fuzzy matching
        patient_name_parts = patient_id.split("_")
        for image_path in images_dir.glob("*.jpg"):
            image_name = image_path.stem
            if any(part in image_name for part in patient_name_parts if part):
                return str(image_path)
        
        return None
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded image
        """
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
    async def generate_reasoning(
        self, 
        modality: str, 
        patient_id: str, 
        api_endpoint: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """Generate reasoning data for a patient.
        
        Args:
            modality: Medical imaging modality
            patient_id: Patient identifier
            api_endpoint: API endpoint for reasoning generation
            
        Returns:
            Tuple of (success, result)
        """
        try:
            # Get patient data
            patient_data = self.get_patient_data(patient_id)
            
            # Find image
            image_path = self.find_image(patient_id)
            if not image_path:
                return False, {"error": f"Image not found for patient {patient_id}"}
            
            # Find ground truth
            ground_truth = self.find_ground_truth(patient_id)
            
            # Encode image
            encoded_image = self.encode_image(image_path)
            
            # Get modality template
            template = self.get_modality_template(modality)
            
            # Prepare payload
            payload = {
                "system_prompt": template,
                "image": encoded_image,
                "context": json.dumps(patient_data),
                "modality": modality,
                "img_url": image_path,
                "ground_truth": ground_truth["docx_path"] if ground_truth else "",
                "api_key": self.api_key
            }
            
            # Call API
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_endpoint, json=payload, headers=headers) as response:
                    if response.status != 200:
                        return False, {"error": f"API error: {response.status}"}
                    
                    result = await response.json()
                    return True, result
                    
        except Exception as e:
            logger.error(f"Error generating reasoning: {e}")
            return False, {"error": str(e)}
    
    async def process_patients(
        self, 
        modality: str, 
        patient_ids: List[str], 
        api_endpoint: str,
        output_dir: str = None
    ) -> Tuple[int, int]:
        """Process a list of patients.
        
        Args:
            modality: Medical imaging modality
            patient_ids: List of patient identifiers
            api_endpoint: API endpoint for reasoning generation
            output_dir: Directory to save results
            
        Returns:
            Tuple of (processed_count, failed_count)
        """
        # Create output directory - use reports/modality_name by default
        if output_dir is None:
            output_dir = f"reports/{modality}"
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Get batch size
        batch_size = self.processing.get("batch_size", 5)
        
        # Process in batches
        processed = 0
        failed = 0
        
        for i in range(0, len(patient_ids), batch_size):
            batch = patient_ids[i:i+batch_size]
            tasks = []
            
            # Create tasks
            for patient_id in batch:
                task = asyncio.create_task(
                    self.generate_reasoning(modality, patient_id, api_endpoint)
                )
                tasks.append((patient_id, task))
            
            # Process batch
            for patient_id, task in tasks:
                success, result = await task
                
                if success:
                    # Save result
                    output_path = os.path.join(output_dir, f"{patient_id}_{modality}_reasoning.json")
                    with open(output_path, 'w') as f:
                        json.dump(result, f, indent=2)
                    
                    logger.info(f"Successfully processed {patient_id} for {modality}")
                    processed += 1
                else:
                    logger.error(f"Failed to process {patient_id} for {modality}: {result.get('error', 'Unknown error')}")
                    failed += 1
        
        return processed, failed
    
    def list_patients(self) -> List[str]:
        """List all patients in the cot directory.
        
        Returns:
            List of patient identifiers
        """
        cot_dir = Path(self.data_paths.get("cot", "cot"))
        return [f.stem for f in cot_dir.glob("*.json")]


async def main():
    """Main entry point."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Process medical imaging modalities for reasoning data generation")
    parser.add_argument("--modality", required=True, help="Medical imaging modality (e.g., chest_xray, mammogram)")
    parser.add_argument("--api-endpoint", required=True, help="API endpoint for reasoning generation")
    parser.add_argument("--output-dir", help="Directory to save results (default: reports/{modality})")
    parser.add_argument("--settings", default="settings.yaml", help="Path to settings.yaml file")
    parser.add_argument("--patient-id", help="Process a specific patient")
    parser.add_argument("--limit", type=int, help="Limit number of patients to process")
    args = parser.parse_args()
    
    # Initialize processor
    processor = ModalityProcessor(args.settings)
    
    # Get patients
    if args.patient_id:
        patient_ids = [args.patient_id]
    else:
        patient_ids = processor.list_patients()
        if args.limit:
            patient_ids = patient_ids[:args.limit]
    
    # Set output directory
    output_dir = args.output_dir or f"reports/{args.modality}"
    
    logger.info(f"Processing {len(patient_ids)} patients for {args.modality}")
    logger.info(f"Results will be saved to {output_dir}")
    
    # Process patients
    processed, failed = await processor.process_patients(
        args.modality, 
        patient_ids, 
        args.api_endpoint, 
        output_dir
    )
    
    logger.info(f"Processed: {processed}, Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(main())