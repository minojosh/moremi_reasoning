"""
OCR Question Generator for Salesforce BLIP3-OCR-200M Dataset
Generates diverse, challenging OCR questions for testing reasoning capabilities
"""

import random
import json
from typing import List, Dict, Any

class OCRQuestionGenerator:
    def __init__(self):
        self.question_templates = {
            "basic_extraction": [
                "What is all the text visible in this image?",
                "Please extract all readable text from this image.",
                "Transcribe all text content shown in the image.",
                "What text can you see in this image?",
            ],
            "specific_elements": [
                "What are the main headings or titles visible in this image?",
                "List all numbers or numerical values shown in the image.",
                "What labels or captions are present in this image?",
                "Identify any website URLs, email addresses, or contact information in the image.",
                "What brand names, logos, or company names are visible?",
            ],
            "structural_analysis": [
                "Describe the layout and organization of text in this image.",
                "What is the reading order of the text elements in this image?",
                "How is the text structured or formatted in this image?",
                "What different text styles or fonts are used in this image?",
            ],
            "contextual_understanding": [
                "What type of document or content does this image appear to show?",
                "Based on the text visible, what is this image primarily about?",
                "What key information can be extracted from the text in this image?",
                "Summarize the main content based on the visible text.",
            ],
            "detailed_analysis": [
                "Provide a detailed transcription preserving the original text layout.",
                "Extract all text while maintaining the spatial relationships between elements.",
                "Transcribe the text and describe its visual presentation.",
                "What text is present and how is it visually organized?",
            ],
            "challenging_scenarios": [
                "What text is visible, including any that might be partially obscured or difficult to read?",
                "Identify all text elements, including watermarks, stamps, or background text.",
                "Extract text from all areas of the image, including margins and corners.",
                "What text can you detect, even if it's small, faded, or at unusual angles?",
            ]
        }
    
    def generate_question(self, difficulty_level: str = "basic", question_type: str = None) -> str:
        """
        Generate an OCR question based on difficulty and type.
        
        Args:
            difficulty_level: "basic", "intermediate", "advanced"
            question_type: specific category or None for random
        
        Returns:
            Generated question string
        """
        if question_type and question_type in self.question_templates:
            return random.choice(self.question_templates[question_type])
        
        # Select based on difficulty level
        if difficulty_level == "basic":
            categories = ["basic_extraction"]
        elif difficulty_level == "intermediate":
            categories = ["specific_elements", "structural_analysis"]
        else:  # advanced
            categories = ["contextual_understanding", "detailed_analysis", "challenging_scenarios"]
        
        category = random.choice(categories)
        return random.choice(self.question_templates[category])
    
    def generate_diverse_questions(self, count: int = 5) -> List[str]:
        """Generate a diverse set of OCR questions."""
        questions = []
        categories = list(self.question_templates.keys())
        
        for i in range(count):
            category = categories[i % len(categories)]
            question = random.choice(self.question_templates[category])
            questions.append(question)
        
        return questions
    
    def create_ocr_test_data(self, salesforce_data: List[Dict], num_samples: int = 10) -> List[Dict]:
        """
        Create OCR test data from Salesforce dataset with diverse questions.
        
        Args:
            salesforce_data: List of processed Salesforce data items
            num_samples: Number of test samples to create
        
        Returns:
            List of test data items with OCR questions
        """
        test_data = []
        
        for i in range(min(num_samples, len(salesforce_data))):
            item = salesforce_data[i]
            
            # Generate a diverse question
            if i % 6 == 0:
                question = self.generate_question("basic")
            elif i % 6 == 1:
                question = self.generate_question("intermediate")
            else:
                question = self.generate_question("advanced")
            
            # Extract OCR text from captions (assuming structure from notebook)
            ground_truth = self.extract_ocr_text(item)
            
            test_item = {
                "process_id": item.get("uid", f"test_{i}"),
                "question": question,
                "answer": ground_truth,
                "img_urls": [item.get("url", "")],
                "metadata": {
                    "original_uid": item.get("uid"),
                    "question_type": self.categorize_question(question),
                    "difficulty": self.assess_difficulty(question)
                }
            }
            
            test_data.append(test_item)
        
        return test_data
    
    def extract_ocr_text(self, item: Dict, preferred_granularity: int = 0) -> str:
        """Extract OCR text from Salesforce data item."""
        captions_str = item.get("captions", "")
        if not captions_str:
            return "No text available"
        
        try:
            captions_list = json.loads(captions_str)
            
            # Try to find the preferred granularity
            for cap_obj in captions_list:
                if cap_obj.get("granularity") == preferred_granularity:
                    if not cap_obj.get("include_datacomp_raw_cap", False):
                        return cap_obj.get("text", "")
            
            # Fallback to any available text
            for cap_obj in captions_list:
                text = cap_obj.get("text", "")
                if text:
                    return text
                    
        except json.JSONDecodeError:
            pass
        
        return "Text extraction failed"
    
    def categorize_question(self, question: str) -> str:
        """Categorize a question based on its content."""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ["all text", "extract all", "transcribe all"]):
            return "basic_extraction"
        elif any(word in question_lower for word in ["headings", "numbers", "labels", "urls"]):
            return "specific_elements"
        elif any(word in question_lower for word in ["layout", "structure", "organization", "reading order"]):
            return "structural_analysis"
        elif any(word in question_lower for word in ["type of document", "about", "summarize"]):
            return "contextual_understanding"
        elif any(word in question_lower for word in ["detailed", "preserving", "spatial"]):
            return "detailed_analysis"
        else:
            return "challenging_scenarios"
    
    def assess_difficulty(self, question: str) -> str:
        """Assess question difficulty based on complexity."""
        question_lower = question.lower()
        
        complex_indicators = ["detailed", "preserving", "spatial", "organization", "summarize", "type of document"]
        basic_indicators = ["what text", "extract all", "transcribe"]
        
        if any(indicator in question_lower for indicator in complex_indicators):
            return "advanced"
        elif any(indicator in question_lower for indicator in basic_indicators):
            return "basic"
        else:
            return "intermediate"

# Example usage function
def create_test_dataset_from_notebook_data():
    """Function to be called from the notebook to create test data."""
    generator = OCRQuestionGenerator()
    
    # This would be called with actual data from the notebook
    sample_questions = generator.generate_diverse_questions(10)
    
    print("Generated OCR Test Questions:")
    for i, question in enumerate(sample_questions, 1):
        difficulty = generator.assess_difficulty(question)
        category = generator.categorize_question(question)
        print(f"{i}. [{difficulty.upper()}] [{category}] {question}")
    
    return sample_questions

if __name__ == "__main__":
    create_test_dataset_from_notebook_data()
