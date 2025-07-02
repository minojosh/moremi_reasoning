import json
import os
from collections import defaultdict
from typing import Dict, List, Any
from .config_loader import load_radiopedia_config
from .path_config import get_radiopedia_data_path
from .logger import setup_logger

logger = setup_logger('preprocess_radiopedia')


class RadiopaediaDataProcessor:
    """Processor for restructuring and filtering Radiopaedia case data."""
    
    def __init__(self, run_path=None):
        self.config = load_radiopedia_config()
        self.run_path = run_path or get_radiopedia_data_path()  # Use timestamped path if provided
    
    def restructure_medical_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Restructure medical case data to group images by study."""
        restructured = {
            "url": data["url"],
            "title": data["title"],
            "modalities": data["modalities"],
            "patient_age": data["patient_age"],
            "patient_gender": data["patient_gender"],
            "presentation": data["presentation"],
            "case_discussion": data["case_discussion"],
            "images": {},
        }
        
        # Group series by study
        studies = defaultdict(list)
        study_captions = {}
        
        for series_key, series_data in data["images"].items():
            study_title = series_data["study_title"]
            
            if study_title not in study_captions:
                study_captions[study_title] = series_data["caption"]
            
            studies[study_title].append({
                "series_name": series_data["series_name"], 
                "urls": series_data["urls"]
            })
        
        # Create final structure
        for i, (study_title, series_list) in enumerate(studies.items(), 1):
            group_name = f"group{i}"
            restructured["images"][group_name] = {
                "series": series_list,
                "caption": study_captions[study_title],
            }
        
        return restructured
    
    def filter_by_modality(self, cases: List[Dict], modality: str) -> tuple[List[Dict], List[str]]:
        """Filter cases by specific modality and return valid cases and failed URLs."""
        modality_upper = modality.upper()
        filtered_cases = []
        failed_cases = []
        
        for case in cases:
            try:
                case_modalities = case.get("modalities", [])
                
                if modality_upper in case_modalities:
                    index = case_modalities.index(modality_upper)
                    image_group_key = f"group{index + 1}"
                    
                    images_dict = case.get("images", {})
                    image_group = images_dict.get(image_group_key)
                    
                    if image_group:
                        caption = image_group.get("caption", "").strip()
                        if not caption or caption == "Caption not available":
                            failed_cases.append(case["url"])
                        else:
                            filtered_case_data = {
                                "case_url": case["url"],
                                "modalities": [modality_upper],
                                "patient_age": case.get("patient_age"),
                                "patient_gender": case.get("patient_gender"),
                                "presentation": case.get("presentation"),
                                "case_discussion": case.get("case_discussion"),
                                "images": image_group,
                            }
                            filtered_cases.append(filtered_case_data)
                    else:
                        failed_cases.append(case["url"])
            
            except Exception as e:
                logger.error(f"Error processing case {case.get('url', 'N/A')}: {e}")
                if case.get("url"):
                    failed_cases.append(case["url"])
        
        return filtered_cases, failed_cases
    
    def process_modality(self, modality: str) -> Dict[str, int]:
        """Process a single modality through restructuring and filtering."""
        logger.info(f"Processing modality: {modality}")
        
        # Load raw case data
        cases_filename = f"{modality}{self.config['output']['cases_file_suffix']}"
        cases_dir = self.run_path / self.config['output']['directories']['scraped_cases']
        cases_file = cases_dir / cases_filename
        
        if not cases_file.exists():
            logger.warning(f"Cases file not found: {cases_file}")
            return {"processed": 0, "filtered": 0, "failed": 0}
        
        with open(cases_file, 'r', encoding='utf-8') as f:
            cases = json.load(f)
        
        # Restructure data
        restructured_cases = []
        for case in cases:
            try:
                restructured_data = self.restructure_medical_data(case)
                restructured_cases.append(restructured_data)
            except Exception as e:
                logger.error(f"Error restructuring case {case.get('url', 'N/A')}: {e}")
        
        # Save restructured data
        restructured_dir = self.run_path / self.config['output']['directories']['restructured_data']
        restructured_dir.mkdir(exist_ok=True)
        
        restructured_filename = f"{modality}{self.config['output']['restructured_suffix']}"
        restructured_file = restructured_dir / restructured_filename
        
        with open(restructured_file, 'w', encoding='utf-8') as f:
            json.dump(restructured_cases, f, indent=2)
        
        logger.info(f"Saved {len(restructured_cases)} restructured cases to {restructured_file}")
        
        # Filter by modality
        filtered_cases, failed_cases = self.filter_by_modality(restructured_cases, modality)
        
        # Save filtered data
        processed_dir = self.run_path / self.config['output']['directories']['processed_data']
        processed_dir.mkdir(exist_ok=True)
        
        filtered_filename = f"{modality}{self.config['output']['filtered_suffix']}"
        failed_filename = f"{modality}{self.config['output']['failed_suffix']}"
        
        filtered_file = processed_dir / filtered_filename
        failed_file = processed_dir / failed_filename
        
        with open(filtered_file, 'w', encoding='utf-8') as f:
            json.dump(filtered_cases, f, indent=2)
        
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_cases, f, indent=2)
        
        logger.info(f"Saved {len(filtered_cases)} filtered cases to {filtered_file}")
        logger.info(f"Saved {len(failed_cases)} failed cases to {failed_file}")
        
        return {
            "processed": len(restructured_cases),
            "filtered": len(filtered_cases),
            "failed": len(failed_cases)
        }
