"""
Dynamic Ground Truth Generation using AI
Uses Gemini 2.0 Flash to intelligently extract ground truth from case metadata.
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import requests
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class DynamicGroundTruthGenerator:
    """
    Intelligent ground truth extraction using AI rather than static templates.
    Uses Gemini 2.0 Flash with temperature 0 for consistent, deterministic results.
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPEN_ROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPEN_ROUTER_API_KEY environment variable not set")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        self.model_name = "google/gemini-2.5-flash-preview-05-20"  # Most capable model
        self.logger = logging.getLogger(__name__)
        
        # Modality-specific prompts for focused extraction
        self.modality_prompts = {
            'mammography': self._get_mammography_prompt(),
            'ct': self._get_ct_prompt(),
            'mri': self._get_mri_prompt(),
            'ultrasound': self._get_ultrasound_prompt(),
            'x-ray': self._get_xray_prompt()
        }
    
    def generate_ground_truth(self, case_data: Dict[str, Any]) -> str:
        """
        Generate a structured, human-readable ground truth text using AI analysis of case metadata.
        
        Args:
            case_data: Complete case information from Radiopaedia
        Returns:
            Raw text string containing the formatted ground truth document.
        """
        try:
            modality = self._detect_modality(case_data)
            
            # Prepare comprehensive context
            context = self._prepare_case_context(case_data)
            
            # Get modality-specific prompt
            prompt = self.modality_prompts.get(modality, self._get_universal_prompt())
            
            # Format the prompt with case context
            formatted_prompt = prompt.format(**context)
            
            # Call AI with deterministic settings
            # Call AI with deterministic settings to produce a structured, human-readable text ground truth
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert radiologist extracting ground truth from medical case information. Provide accurate, conservative assessments based on the evidence presented. Respond with a structured, human-readable text document."
                    },
                    {
                        "role": "user",
                        "content": formatted_prompt
                    }
                ],
                temperature=0.0,  # Deterministic results
                max_tokens=4000
            )

            # Return raw text as ground truth
            ground_truth_text = response.choices[0].message.content
            return ground_truth_text
            
        except Exception as e:
            self.logger.error(f"Error generating ground truth for {case_data.get('case_url', 'unknown')}: {e}")
            return self._fallback_ground_truth(case_data, str(e))
    
    def _detect_modality(self, case_data: Dict[str, Any]) -> str:
        """Detect the primary modality from case data."""
        modalities = case_data.get('modalities', [])
        if modalities:
            primary_modality = modalities[0].lower()
            
            # Normalize modality names
            modality_map = {
                'mammography': 'mammography',
                'x-ray': 'x-ray',
                'ct': 'ct',
                'mri': 'mri',
                'ultrasound': 'ultrasound'
            }
            
            return modality_map.get(primary_modality, primary_modality)
        
        return 'unknown'
    
    def _prepare_case_context(self, case_data: Dict[str, Any]) -> Dict[str, str]:
        """Prepare comprehensive case context for AI analysis."""
        
        # Extract image captions
        images = case_data.get('images', {})
        caption = images.get('caption', '') if isinstance(images, dict) else ''
        
        # Extract series information
        series_info = []
        if isinstance(images, dict) and 'series' in images:
            for series in images['series']:
                series_name = series.get('series_name', 'Unknown')
                url_count = len(series.get('urls', []))
                series_info.append(f"{series_name} ({url_count} images)")
        
        return {
            'modality': self._detect_modality(case_data),
            'patient_age': case_data.get('patient_age', 'Unknown'),
            'patient_gender': case_data.get('patient_gender', 'Unknown'),
            'presentation': case_data.get('presentation', 'No clinical information provided'),
            'case_discussion': case_data.get('case_discussion', 'No discussion provided'),
            'image_caption': caption,
            'series_information': ', '.join(series_info) if series_info else 'No series information',
            'case_url': case_data.get('case_url', '')
        }
    
    def _get_mammography_prompt(self) -> str:
        """Prompt specifically designed for mammography ground truth extraction."""
        return """
Analyze this mammography case and provide a comprehensive, human-readable ground truth assessment:

**Case Information:**
- Modality: {modality}
- Patient: {patient_age}, {patient_gender}
- Presentation: {presentation}
- Image Caption: {image_caption}
- Series: {series_information}
- Expert Discussion: {case_discussion}

**Provide a structured text assessment covering:**

FINAL DIAGNOSIS: [State the confirmed diagnosis from biopsy/follow-up]

BI-RADS CATEGORY: [State the appropriate BI-RADS category with justification]

KEY IMAGING FEATURES:
- [List the specific mammographic features that led to the diagnosis]
- [Include details about mass characteristics, margins, calcifications, etc.]

CLINICAL OUTCOME: [Describe what actually happened - biopsy results, treatment, follow-up]

BREAST DENSITY: [State the breast density category if mentioned]

ASSESSMENT RATIONALE: [Explain why this BI-RADS category was appropriate based on the imaging features]

TEACHING POINTS:
- [Key learning points from this case]
- [Important diagnostic considerations]

Format your response as clear, structured text that a radiologist could easily read and understand.
"""

    def _get_ct_prompt(self) -> str:
        """Prompt specifically designed for CT ground truth extraction."""
        return """
Analyze this CT case and provide a comprehensive, human-readable ground truth assessment:

**Case Information:**
- Modality: {modality}
- Patient: {patient_age}, {patient_gender}
- Presentation: {presentation}
- Image Caption: {image_caption}
- Series: {series_information}
- Expert Discussion: {case_discussion}

**Provide a structured text assessment covering:**

FINAL DIAGNOSIS: [State the confirmed diagnosis from histology/follow-up]

KEY IMAGING FEATURES:
- [List the specific CT features that led to the diagnosis]
- [Include details about anatomical location, enhancement patterns, etc.]

CLINICAL CORRELATION: [Explain how the imaging findings correlate with the clinical presentation]

DIFFERENTIAL DIAGNOSIS: [List any differential diagnoses considered]

TEACHING POINTS:
- [Key learning points from this case]

Format your response as clear, structured text that a radiologist could easily read and understand.
"""

    def _get_mri_prompt(self) -> str:
        """Prompt specifically designed for MRI ground truth extraction."""
        return """
Analyze this MRI case and provide a comprehensive, human-readable ground truth assessment:

**Case Information:**
- Modality: {modality}
- Patient: {patient_age}, {patient_gender}
- Presentation: {presentation}
- Image Caption: {image_caption}
- Series: {series_information}
- Expert Discussion: {case_discussion}

**Provide a structured text assessment covering:**

FINAL DIAGNOSIS: [State the confirmed diagnosis]

KEY IMAGING FEATURES:
- [List the specific MRI features, including signal characteristics on different sequences and enhancement patterns]

ANATOMICAL LOCATION: [Describe the precise anatomical location of the findings]

CLINICAL SIGNIFICANCE: [Explain the clinical impact of the findings]

DIFFERENTIAL CONSIDERATIONS: [List other diagnoses that were considered]

TEACHING POINTS:
- [Key learning points from this case]

Format your response as clear, structured text that a radiologist could easily read and understand.
"""

    def _get_ultrasound_prompt(self) -> str:
        """Prompt specifically designed for ultrasound ground truth extraction."""
        return """
Analyze this ultrasound case and provide a comprehensive, human-readable ground truth assessment:

**Case Information:**
- Modality: {modality}
- Patient: {patient_age}, {patient_gender}
- Presentation: {presentation}
- Image Caption: {image_caption}
- Series: {series_information}
- Expert Discussion: {case_discussion}

**Provide a structured text assessment covering:**

FINAL DIAGNOSIS: [State the final diagnosis or assessment]

KEY IMAGING FEATURES:
- [Describe the key sonographic findings, including echogenicity, morphology, and Doppler parameters if relevant]

CLINICAL CORRELATION: [Explain how the findings relate to the patient's symptoms]

TECHNICAL CONSIDERATIONS: [Mention any technical factors that may have influenced the study]

TEACHING POINTS:
- [Key learning points from this case]

Format your response as clear, structured text that a radiologist could easily read and understand.
"""

    def _get_xray_prompt(self) -> str:
        """Prompt specifically designed for X-ray ground truth extraction."""
        return """
Analyze this X-ray case and provide a comprehensive, human-readable ground truth assessment:

**Case Information:**
- Modality: {modality}
- Patient: {patient_age}, {patient_gender}
- Presentation: {presentation}
- Image Caption: {image_caption}
- Series: {series_information}
- Expert Discussion: {case_discussion}

**Provide a structured text assessment covering:**

FINAL DIAGNOSIS: [State the primary pathology or main abnormal finding]

KEY IMAGING FEATURES:
- [List the specific radiological signs and affected anatomical structures]

CLINICAL CORRELATION: [Explain how the findings explain the patient's symptoms]

URGENCY: [Assess whether the findings are urgent or non-urgent]

ADDITIONAL FINDINGS: [Note any secondary or incidental findings]

TEACHING POINTS:
- [Key learning points from this case]

Format your response as clear, structured text that a radiologist could easily read and understand.
"""

    def _get_universal_prompt(self) -> str:
        """Universal prompt for unknown or unsupported modalities."""
        return """
Analyze this medical imaging case and extract the ground truth information:

**Case Information:**
- Modality: {modality}
- Patient: {patient_age}, {patient_gender}
- Presentation: {presentation}
- Image Caption: {image_caption}
- Series: {series_information}
- Expert Discussion: {case_discussion}

**Extract the following ground truth elements:**

1. **Primary Diagnosis**: What was the final diagnosis?
2. **Key Findings**: Main imaging findings described
3. **Clinical Correlation**: How findings relate to presentation
4. **Diagnostic Confidence**: Level of diagnostic certainty
5. **Clinical Significance**: Impact on patient care

Provide your analysis as JSON with these exact keys:
- "final_diagnosis": confirmed diagnosis
- "key_findings": main imaging findings
- "clinical_correlation": presentation correlation
- "diagnostic_confidence": certainty level
- "clinical_significance": care impact
- "modality_specific_notes": any modality-specific observations
"""

    def _fallback_ground_truth(self, case_data: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Provide fallback ground truth when AI generation fails."""
        return {
            'error': error,
            'fallback_method': 'static_extraction',
            'case_url': case_data.get('case_url', ''),
            'modality': self._detect_modality(case_data),
            'raw_discussion': case_data.get('case_discussion', ''),
            'raw_caption': case_data.get('images', {}).get('caption', '') if isinstance(case_data.get('images', {}), dict) else '',
            'presentation': case_data.get('presentation', ''),
            'requires_manual_review': True
        }
    
    def batch_generate_ground_truth(self, cases: List[Dict[str, Any]], 
                                  limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Generate ground truth for multiple cases efficiently.
        
        Args:
            cases: List of case data dictionaries
            limit: Optional limit on number of cases to process
            
        Returns:
            List of ground truth dictionaries
        """
        if limit:
            cases = cases[:limit]
        
        results = []
        
        for i, case in enumerate(cases):
            try:
                self.logger.info(f"Processing case {i+1}/{len(cases)}: {case.get('case_url', 'unknown')}")
                ground_truth = self.generate_ground_truth(case)
                results.append(ground_truth)
                
            except Exception as e:
                self.logger.error(f"Failed to process case {i+1}: {e}")
                results.append(self._fallback_ground_truth(case, str(e)))
        
        return results
    
    def save_ground_truth_batch(self, ground_truth_data: List[Dict[str, Any]], 
                               output_file: Path) -> None:
        """Save generated ground truth to file."""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(ground_truth_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(ground_truth_data)} ground truth records to {output_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save ground truth to {output_file}: {e}")
            raise


if __name__ == "__main__":
    # Example usage
    generator = DynamicGroundTruthGenerator()
    
    # Test with a sample case
    sample_case = {
        "case_url": "https://radiopaedia.org/cases/pilomatricoma-of-the-breast?lang=us",
        "modalities": ["MAMMOGRAPHY"],
        "patient_age": "45 years",
        "patient_gender": "Male",
        "presentation": "Painless palpable lump in the upper inner quadrant of the right breast over the last 6 months.",
        "case_discussion": "Based on the imaging features, the lesion was reported as BI-RADS 4 category. Therefore, the patient underwent an ultrasound-guided core needle biopsy, obtaining a histopathological diagnosis of pilomatricoma. Pilomatricomas are benign skin tumors that arise from the hair follicles.",
        "images": {
            "caption": "Round nodule with obscured margins at the upper inner quadrant of the right breast."
        }
    }
    
    result = generator.generate_ground_truth(sample_case)
    print(json.dumps(result, indent=2))
