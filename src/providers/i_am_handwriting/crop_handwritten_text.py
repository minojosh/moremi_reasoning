#!/usr/bin/env python3
"""
Utility script for cropping handwritten text from IAM database images.

This script extracts only the handwritten portion of the text from images,
excluding the machine-printed part at the top and signature area at the bottom.
The cropped images are saved with the same filenames in a new directory.
"""

import os
import sys
import cv2
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Crop handwritten text from IAM database images.'
    )
    parser.add_argument(
        '--source-dir',
        type=str,
        default='data/I AM/formsA-D',
        help='Directory containing the source images (default: data/I AM/formsA-D)'
    )
    parser.add_argument(
        '--xml-dir', 
        type=str,
        default='data/I AM/xml',
        help='Directory containing XML annotation files (default: data/I AM/xml)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/I AM/cropped_handwritten',
        help='Directory to save cropped images (default: data/I AM/cropped_handwritten)'
    )
    return parser.parse_args()

def get_handwritten_bounds_from_xml(xml_file):
    """
    Extract the bounding coordinates of the handwritten text from the XML file.
    
    Args:
        xml_file: Path to XML file
        
    Returns:
        tuple: (min_x, min_y, max_x, max_y) coordinates for cropping
    """
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        # Get form dimensions
        form_width = int(root.get('width'))
        form_height = int(root.get('height'))
        
        # Find all handwritten lines
        handwritten_part = root.find('handwritten-part')
        if handwritten_part is None:
            logger.warning(f"No handwritten part found in {xml_file}")
            return None
        
        lines = handwritten_part.findall('line')
        if not lines:
            logger.warning(f"No lines found in {xml_file}")
            return None
        
        # Initialize boundary values
        min_x = form_width
        min_y = form_height
        max_x = 0
        max_y = 0
        
        # Get min/max coordinates from all components in all words in all lines
        for line in lines:
            for word in line.findall('word'):
                for cmp in word.findall('cmp'):
                    x = int(cmp.get('x'))
                    y = int(cmp.get('y'))
                    width = int(cmp.get('width'))
                    height = int(cmp.get('height'))
                    
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x + width)
                    max_y = max(max_y, y + height)
        
        # Add some padding (5%)
        width = max_x - min_x
        height = max_y - min_y
        
        padding_x = int(width * 0.05)
        padding_y = int(height * 0.05)
        
        min_x = max(0, min_x - padding_x)
        min_y = max(0, min_y - padding_y)
        max_x = min(form_width, max_x + padding_x)
        max_y = min(form_height, max_y + padding_y)
        
        return (min_x, min_y, max_x, max_y)
    
    except Exception as e:
        logger.error(f"Error processing {xml_file}: {e}")
        return None

def crop_image(image_path, xml_path, output_path):
    """
    Crop the handwritten text from an image using bounds from XML file.
    
    Args:
        image_path: Path to the image file
        xml_path: Path to the corresponding XML file
        output_path: Path to save the cropped image
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get bounds from XML
        bounds = get_handwritten_bounds_from_xml(xml_path)
        if bounds is None:
            return False
        
        # Read image
        image = cv2.imread(str(image_path))
        if image is None:
            logger.error(f"Could not read image: {image_path}")
            return False
        
        # Crop image
        min_x, min_y, max_x, max_y = bounds
        cropped = image[min_y:max_y, min_x:max_x]
        
        # Save cropped image
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(str(output_path), cropped)
        return True
        
    except Exception as e:
        logger.error(f"Error cropping {image_path}: {e}")
        return False

def main():
    """Main function to process all images."""
    args = parse_args()
    
    # Set up paths
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    source_dir = script_dir / args.source_dir
    xml_dir = script_dir / args.xml_dir
    output_dir = script_dir / args.output_dir
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Find all image files
    image_files = list(source_dir.glob('*.png'))
    if not image_files:
        logger.error(f"No PNG files found in {source_dir}")
        return
    
    logger.info(f"Found {len(image_files)} image files to process")
    
    # Process each image
    success_count = 0
    for img_path in image_files:
        # Get corresponding XML file
        base_name = img_path.stem  # filename without extension
        xml_path = xml_dir / f"{base_name}.xml"
        
        # Check if XML file exists
        if not xml_path.exists():
            logger.warning(f"XML file not found for {img_path}")
            continue
        
        # Create output path
        output_path = output_dir / img_path.name
        
        # Crop and save image
        if crop_image(img_path, xml_path, output_path):
            success_count += 1
            if success_count % 20 == 0:
                logger.info(f"Processed {success_count} images")
    
    logger.info(f"Completed. Successfully cropped {success_count} out of {len(image_files)} images.")
    logger.info(f"Cropped images saved to {output_dir}")

if __name__ == "__main__":
    main()
