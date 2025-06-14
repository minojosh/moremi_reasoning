import os
import sys
import argparse
import yaml
from pathlib import Path
from tqdm import tqdm
sys.path.append('/home/justjosh/Turing-Test')
from dotenv import load_dotenv
from .report_processor import ReportProcessor

def load_settings(settings_path="moremi_reasoning/src/settings.yaml"):
    """Load settings from YAML file."""
    with open(settings_path, 'r') as f:
        return yaml.safe_load(f)

def process_reports(modality="chest_xray", num_reports=None, patient_ids=None, settings_path=None):
    """
    Process reports using the Gemini API
    
    Args:
        modality (str): Modality to process (e.g., chest_xray, mammogram)
        num_reports (int, optional): Number of reports to process. If None, process all.
        patient_ids (list, optional): List of specific patient IDs to process. If provided, num_reports is ignored.
        settings_path (str, optional): Path to settings file
    """
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        return
    
    # Load settings
    settings = load_settings(settings_path) if settings_path else load_settings()
    
    # Check if modality is supported
    if modality not in settings.get("modalities", {}):
        print(f"Error: Modality '{modality}' not configured in settings.yaml")
        print(f"Available modalities: {', '.join(settings.get('modalities', {}).keys())}")
        return
    
    # Configure paths based on modality
    if modality == "chest_xray":
        # Use existing paths for backward compatibility
        report_file_path = "/home/justjosh/Turing-Test/processed_data/chest_xray/Doc2Moremi/100_euracare_reports.json"
        image_base_path = "/home/justjosh/Turing-Test/processed_data/chest_xray/Image Gallery"
    else:
        # For other modalities, use paths from settings
        data_paths = settings.get("data_paths", {})
        all_matches_dir = Path(data_paths.get("all_matches_combined", "All_Matches_Combined"))
        cot_dir = Path(data_paths.get("cot", "cot"))
        image_base_path = Path(data_paths.get("images", "images"))
        report_file_path = cot_dir
    
    # Initialize processor with modality
    processor = ReportProcessor(
        api_key=api_key,
        report_file_path=report_file_path,
        image_base_path=image_base_path,
        modality=modality,
        settings=settings
    )
    
    # Process reports according to the specified filters
    if patient_ids:
        # Process only specific patient IDs
        processor.process_specific_patients(patient_ids)
    else:
        # Process all or limited number of reports
        processor.process_reports(num_reports=num_reports)
    
    # Always save the consolidated file at the end
    processor.save_consolidated_records()
    print(f"Consolidated file saved in reports/{modality}/ directory")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process medical reports with Gemini API')
    parser.add_argument('--modality', default='chest_xray', help='Medical imaging modality (e.g., chest_xray, mammogram)')
    parser.add_argument('--num', type=int, help='Number of reports to process')
    parser.add_argument('--patients', nargs='+', help='Specific patient IDs to process')
    parser.add_argument('--force', action='store_true', help='Force reprocessing of already processed records')
    parser.add_argument('--settings', help='Path to settings file (default: moremi_reasoning/src/settings.yaml)')
    
    args = parser.parse_args()
    
    process_reports(
        modality=args.modality,
        num_reports=args.num, 
        patient_ids=args.patients,
        settings_path=args.settings
    )