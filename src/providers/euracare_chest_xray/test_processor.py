import os
import sys
sys.path.append('/home/justjosh/Turing-Test')
from dotenv import load_dotenv
from .report_processor import ReportProcessor

def test_multiple_reports(num_reports=3):
    """Test processing multiple reports"""
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file")
        return
        
    processor = ReportProcessor(
        api_key=api_key,
        report_file_path="/home/justjosh/Turing-Test/processed_data/chest_xray/Doc2Moremi/100_euracare_reports.json",
        image_base_path="/home/justjosh/Turing-Test/processed_data/chest_xray/Image Gallery"
    )
    
    reports = processor.load_reports()
    if not reports:
        print("Error: Could not load reports")
        return
        
    # Process first num_reports patients
    for i, (patient_id, report_data) in enumerate(list(reports.items())[:num_reports]):
        print(f"\nProcessing patient {i+1}/{num_reports}: {patient_id}")
        
        report_info = processor.extract_report_info(report_data)
        if not report_info:
            print(f"Error: Could not extract report info for patient {patient_id}")
            continue
            
        image_path = processor.get_image_path(patient_id)
        if not os.path.exists(image_path):
            print(f"Error: Image not found at {image_path}")
            continue
            
        image = processor.encode_image(image_path)
        if not image:
            print(f"Error: Could not encode image for patient {patient_id}")
            continue
            
        reasoning_data = processor.generate_reasoning(image, report_info, image_path)
        if reasoning_data:
            print(f"Successfully generated reasoning for patient {patient_id}")
            print(f"Saved to: moremi_reasoning/reports/{patient_id}.json")
            processor.save_reasoning(patient_id, reasoning_data)
            print(f"JSON data structure:")
            print(f"- Image: {reasoning_data['image']}")
            print(f"- Reasoning: {len(reasoning_data['reasoning'])} chars")
            print(f"- Reflection: {len(reasoning_data['reflection'])} chars")
            print(f"- Answer: {len(reasoning_data['answer'])} chars")
        else:
            print(f"Error: Could not generate reasoning for patient {patient_id}")

if __name__ == "__main__":
    test_multiple_reports()