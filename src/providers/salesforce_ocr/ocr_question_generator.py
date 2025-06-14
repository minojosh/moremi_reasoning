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
            "What is all the text visible in this image? Please provide a complete transcription.",
            "Please extract all readable text from this image and return the full text.",
            "Transcribe all text content shown in the image, ensuring no text is omitted.",
            "What text can you see in this image? Make sure to include every word."
            ],
            "specific_elements": [
            "What are the main headings or titles visible in this image? Also, extract all other visible text.",
            "List all numbers or numerical values shown in the image and include the complete text content.",
            "What labels or captions are present in this image? Additionally, provide a full transcription of any other text.",
            "Identify any website URLs, email addresses, or contact information in the image and also return all visible text.",
            "What brand names, logos, or company names are visible? Return all accompanying text as well."
            ],
            "structural_analysis": [
            "Describe the layout and organization of text in this image and transcribe the entire visible text.",
            "What is the reading order of the text elements in this image? Also, provide all the text you can see.",
            "How is the text structured or formatted in this image? Ensure that you extract all text present.",
            "What different text styles or fonts are used in this image? Along with the analysis, return full text content."
            ],
            "contextual_understanding": [
            "What type of document or content does this image appear to show? Please also return all visible text.",
            "Based on the text visible, what is this image primarily about? Ensure you provide the complete text transcription.",
            "What key information can be extracted from the text in this image? Include every bit of text in your answer.",
            "Summarize the main content based on the visible text and make sure to transcribe all text present."
            ],
            "detailed_analysis": [
            "Provide a detailed transcription preserving the original text layout and include all visible text in the image.",
            "Extract all text while maintaining the spatial relationships between elements; make sure nothing is missed.",
            "Transcribe the text and describe its visual presentation, returning all extracted text.",
            "What text is present and how is it visually organized? Also, extract and return every piece of visible text."
            ],
            "challenging_scenarios": [
            "What text is visible, including any that might be partially obscured or difficult to read? Ensure you return all transcribed text.",
            "Identify all text elements, including watermarks, stamps, or background text, and include the full text transcription.",
            "Extract text from all areas of the image, including margins and corners, reporting every visible text element.",
            "What text can you detect, even if it's small, faded, or at unusual angles? Provide a complete transcription along with your analysis."
            ],
            # New handwriting-specific questions
            "handwriting_basic": [
            "Transcribe all handwritten text visible in this image and include all other visible text as well.",
            "What handwritten words or phrases can you read in this image? Also, extract the complete text content.",
            "Please read and transcribe the handwriting shown in this image and return all visible text.",
            "Convert the handwritten text in this image to typed text and include every other visible text element."
            ],
            "handwriting_detailed": [
            "Carefully transcribe each handwritten word, preserving spelling and punctuation, and extract all visible text in the image.",
            "Read the handwriting character by character and provide the complete transcription along with full text extraction.",
            "Transcribe the handwritten text exactly as written, including any abbreviations or symbols, and include all other visible text.",
            "What is the complete handwritten message in this image? Also, return a full transcript of all visual text."
            ],
            "handwriting_challenging": [
            "Transcribe all including any difficult-to-read or unclear handwritten text in this image and also provide all visible text.",
            "What handwritten text can you decipher, even if some characters are unclear? Ensure you return the complete text transcription.",
            "Read the handwriting in this image, making your best interpretation of unclear parts, and extract all additional visible text.",
            "Transcribe all handwritten content, including any faded or partially legible text, and also include every piece of visible text."
            ]
        }
        
        # Add handwriting categories to difficulty mapping
        self.handwriting_categories = ["handwriting_basic", "handwriting_detailed", "handwriting_challenging"]
    
    def generate_question(self, difficulty_level: str = "basic", question_type: str = None, content_type: str = "general") -> str:
        """
        Generate an OCR question based on difficulty and type.
        
        Args:
            difficulty_level: "basic", "intermediate", "advanced"
            question_type: specific category or None for random
            content_type: "general", "handwriting" to focus on specific content types
        
        Returns:
            Generated question string
        """
        if question_type and question_type in self.question_templates:
            return random.choice(self.question_templates[question_type])
        
        # Select categories based on content type and difficulty level
        if content_type == "handwriting":
            if difficulty_level == "basic":
                categories = ["handwriting_basic"]
            elif difficulty_level == "intermediate":
                categories = ["handwriting_detailed", "structural_analysis"]
            else:  # advanced
                categories = ["handwriting_challenging", "detailed_analysis"]
        else:
            # Original general OCR categories
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
        
        # Check for handwriting-specific patterns first
        if any(word in question_lower for word in ["handwritten", "handwriting"]):
            if any(word in question_lower for word in ["difficult", "unclear", "decipher", "faded"]):
                return "handwriting_challenging"
            elif any(word in question_lower for word in ["carefully", "character by character", "exactly"]):
                return "handwriting_detailed"
            else:
                return "handwriting_basic"
        
        # Original categorization
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
        
        complex_indicators = [
            "detailed", "preserving", "spatial", "organization", "summarize", 
            "type of document", "character by character", "decipher", "unclear", 
            "difficult", "faded", "partially legible"
        ]
        basic_indicators = [
            "what text", "extract all", "transcribe", "handwritten text", 
            "visible", "readable"
        ]
        
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
