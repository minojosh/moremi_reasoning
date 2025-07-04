"""
Radiology Question Generator
Generates diverse, realistic clinical questions for radiology cases.
"""

import random
from typing import Dict, List, Any

class RadiologyQuestionGenerator:
    """Generate diverse clinical questions for radiology cases."""
    
    def __init__(self):
        self.question_templates = {
            'diagnostic': [
                "What are the key findings in this {modality} study?",
                "Describe the abnormalities visible on this {modality} examination.",
                "What is your radiological diagnosis based on this {modality}?",
                "Analyze this {modality} and provide a differential diagnosis.",
                "What pathological findings can you identify in this {modality} study?"
            ],
            'screening': [
                "Review this screening {modality} for any abnormalities.",
                "Is this {modality} study normal or abnormal? Explain your findings.",
                "Perform a systematic review of this {modality} examination.",
                "What would you report for this routine {modality} screening?",
                "Assess this {modality} for any significant findings."
            ],
            'followup': [
                "Compare and assess any changes in this follow-up {modality}.",
                "How would you interpret this {modality} in the context of {presentation}?",
                "What is the current status based on this {modality} examination?",
                "Evaluate the progression or resolution shown in this {modality}.",
                "Review this {modality} for treatment response or disease progression."
            ],
            'emergency': [
                "Urgent {modality} interpretation needed - what are your findings?",
                "This {modality} was obtained emergently for {presentation} - what do you see?",
                "Rapid review required: analyze this emergency {modality} study.",
                "What immediate findings require attention on this {modality}?",
                "Emergency department {modality} - provide critical findings."
            ],
            'detailed_analysis': [
                "Provide a comprehensive analysis of all structures visible in this {modality}.",
                "Systematically evaluate each anatomical region in this {modality} study.",
                "Give a detailed radiological report for this {modality} examination.",
                "Perform a thorough interpretation of this {modality} with clinical correlation.",
                "Analyze this {modality} using standard reporting protocols."
            ]
        }
        
        self.modality_specific_questions = {
            'mammography': [
                "Assess this mammogram for masses, calcifications, and architectural distortion.",
                "Provide a BI-RADS assessment for this mammographic examination.",
                "Evaluate breast density and any suspicious findings on this mammogram.",
                "What are the mammographic findings and recommended follow-up?",
                "Interpret this mammogram in the context of breast cancer screening."
            ],
            'chest x-ray': [
                "Systematically review this chest X-ray for cardiopulmonary abnormalities.",
                "Evaluate the lungs, heart, and mediastinum on this chest radiograph.",
                "What pulmonary or cardiac findings are present on this chest X-ray?",
                "Assess this chest X-ray for acute pathology.",
                "Review this chest radiograph for any abnormal findings."
            ],
            'ct': [
                "Interpret this CT scan with attention to all visible structures.",
                "What are the key CT findings and their clinical significance?",
                "Provide a comprehensive CT interpretation including any pathology.",
                "Analyze this contrast-enhanced CT for abnormal findings.",
                "Review this CT study for diagnostic findings."
            ],
            'mri': [
                "Interpret this MRI examination across all sequences provided.",
                "What are the MRI findings and their diagnostic implications?",
                "Analyze the signal characteristics and enhancement patterns on this MRI.",
                "Provide a comprehensive MRI interpretation with differential diagnosis.",
                "Review this MRI study for pathological findings."
            ],
            'ultrasound': [
                "Interpret the sonographic findings in this ultrasound study.",
                "What are the ultrasound characteristics of any abnormalities seen?",
                "Provide Doppler interpretation if vascular assessment is included.",
                "Analyze the echogenicity and morphology of structures on this ultrasound.",
                "What are the key sonographic findings and recommendations?"
            ]
        }
        
        self.clinical_contexts = [
            "screening examination",
            "follow-up imaging",
            "symptom evaluation", 
            "emergency presentation",
            "preoperative assessment",
            "post-treatment monitoring",
            "routine surveillance",
            "diagnostic workup"
        ]

    def generate_question(self, case_data: Dict[str, Any]) -> str:
        """
        Generate a clinical question for a radiology case.
        
        Args:
            case_data: Dictionary containing case information
            
        Returns:
            Generated clinical question string
        """
        modality = case_data.get('modalities', ['unknown'])[0].lower()
        presentation = case_data.get('presentation', '')
        patient_age = case_data.get('patient_age', 'adult')
        patient_gender = case_data.get('patient_gender', 'patient')
        
        # Normalize modality name
        modality_map = {
            'mammography': 'mammography',
            'x-ray': 'chest x-ray' if 'chest' in presentation.lower() else 'x-ray',
            'ct': 'ct',
            'mri': 'mri', 
            'ultrasound': 'ultrasound'
        }
        
        normalized_modality = modality_map.get(modality, modality)
        
        # Choose question type based on clinical context
        question_type = self._determine_question_type(presentation, patient_age)
        
        # Generate base question with more variety
        if normalized_modality in self.modality_specific_questions and random.random() < 0.5:
            # 50% chance to use modality-specific question for better diversity
            question = random.choice(self.modality_specific_questions[normalized_modality])
        else:
            # Use general template
            template = random.choice(self.question_templates[question_type])
            question = template.format(modality=normalized_modality)
        
        # Add clinical context for more realistic questions
        if random.random() < 0.7:  # 70% chance to add clinical context for better diversity
            context = self._generate_clinical_context(presentation, patient_age, patient_gender)
            if context:
                question = f"{question} {context}"
        
        return question

    def _determine_question_type(self, presentation: str, patient_age: str) -> str:
        """Determine the appropriate question type based on clinical context."""
        presentation_lower = presentation.lower()
        
        # Emergency indicators
        if any(word in presentation_lower for word in ['acute', 'emergency', 'urgent', 'trauma', 'pain']):
            return 'emergency'
        
        # Screening indicators  
        if any(word in presentation_lower for word in ['screening', 'routine', 'asymptomatic']):
            return 'screening'
            
        # Follow-up indicators
        if any(word in presentation_lower for word in ['follow', 'monitoring', 'surveillance', 'post']):
            return 'followup'
            
        # Default to diagnostic for specific symptoms
        if any(word in presentation_lower for word in ['presents', 'complaint', 'history', 'symptoms']):
            return 'diagnostic'
            
        # Random choice for unclear cases
        return random.choice(['diagnostic', 'detailed_analysis'])

    def _generate_clinical_context(self, presentation: str, patient_age: str, patient_gender: str) -> str:
        """Generate additional clinical context for the question."""
        contexts = []
        
        # Age context
        if 'neonate' in patient_age.lower() or 'newborn' in patient_age.lower():
            contexts.append("in this neonatal patient")
        elif any(age in patient_age.lower() for age in ['pediatric', 'child', 'infant']):
            contexts.append("in this pediatric patient")
        elif any(age in patient_age.lower() for age in ['elderly', '70', '80', '90']):
            contexts.append("in this elderly patient")
        
        # Clinical presentation context
        if presentation and len(presentation) > 10:
            if random.random() < 0.3:  # 30% chance to reference presentation
                contexts.append(f"given the clinical presentation of {presentation.lower()}")
        
        # Gender-specific context for certain modalities
        if patient_gender.lower() == 'female' and random.random() < 0.2:
            contexts.append("with attention to gender-specific considerations")
        
        return random.choice(contexts) if contexts else ""

    def generate_diverse_questions(self, cases: List[Dict[str, Any]], num_variations: int = 1) -> List[Dict[str, Any]]:
        """
        Generate diverse questions for a list of cases.
        
        Args:
            cases: List of case dictionaries
            num_variations: Number of question variations per case
            
        Returns:
            List of cases with generated questions
        """
        enhanced_cases = []
        
        for case in cases:
            for variation in range(num_variations):
                case_copy = case.copy()
                case_copy['generated_question'] = self.generate_question(case)
                
                # Add variation identifier if multiple variations
                if num_variations > 1:
                    case_copy['question_variation'] = variation + 1
                    case_copy['process_id'] = f"{case.get('process_id', 0)}_{variation}"
                
                enhanced_cases.append(case_copy)
        
        return enhanced_cases
