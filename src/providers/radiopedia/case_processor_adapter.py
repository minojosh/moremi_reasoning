#!/usr/bin/env python3
"""
Radiopedia Case Processor Wrapper
Adapts the existing processing function to work with the actual data structure.
"""

import logging
from typing import Dict, List
from providers.radiopedia.radiopedia_report_reasoning import process_radiology_case

logger = logging.getLogger(__name__)

def adapt_case_data_for_processing(case_data: Dict) -> Dict:
    """Adapt case data to the expected format for processing."""
    
    # Check if the data already has the correct structure
    images_data = case_data.get('images', {})
    
    if 'series' in images_data and isinstance(images_data['series'], list):
        # Data already has the correct structure, no adaptation needed
        logger.info("Case data already in correct format")
        return case_data
    
    # Extract image URLs from alternative structures (study_X_series_Y_)
    image_urls = []
    
    for key, series_data in images_data.items():
        # Skip non-series keys like 'caption'
        if key == 'series' or key == 'caption':
            continue
            
        if isinstance(series_data, dict) and 'urls' in series_data:
            urls = series_data.get('urls', [])
            image_urls.extend(urls)
    
    # Create adapted structure only if we found URLs to extract
    if image_urls:
        adapted_case = case_data.copy()
        adapted_case['images'] = {
            'series': [
                {'urls': image_urls}
            ]
        }
        logger.info(f"Adapted case data with {len(image_urls)} image URLs")
        return adapted_case
    
    # If no adaptation was needed or possible, return original
    return case_data

def process_radiology_case_adapted(
    case_data: dict,
    gpt_instance,
    reasoning_strategies,
    prompts: dict,
    report_formats: dict,
    question_generator,
    process_id: int = 0
) -> Dict:
    """Process radiology case with data structure adaptation."""
    
    try:
        # Adapt the case data structure
        adapted_case = adapt_case_data_for_processing(case_data)
        
        # Call the original processing function
        result = process_radiology_case(
            case_data=adapted_case,
            gpt_instance=gpt_instance,
            reasoning_strategies=reasoning_strategies,
            prompts=prompts,
            report_formats=report_formats,
            question_generator=question_generator,
            process_id=process_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in adapted processing: {e}")
        return {
            "process_id": process_id,
            "case_url": case_data.get('case_url', case_data.get('url', 'unknown')),
            "error": str(e),
            "status": "error"
        }
