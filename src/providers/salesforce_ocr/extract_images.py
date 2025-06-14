#!/usr/bin/env python3
import os
import re
import argparse
import sys
import json
import logging
from src.utils.pathfinder import get_project_root, get_src_dir, get_image_dir
# Set up project paths
PROJECT_ROOT = get_project_root()
SRC_DIR = get_src_dir()
IMAGE_DIR = get_image_dir('salesforce', 'salesforce_images')
JSON_L_FILE = os.path.join(SRC_DIR, 'data', 'salesforce', 'salesforce_2200.json')
OUTPUT_DIR = os.path.join(SRC_DIR, 'data', 'salesforce')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'salesforce_ocr.json')


def setup_logging(log_file):
    """Configure logging to output to both console and a log file."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def find_images(directory):
    """
    Walk through the directory and find files whose names match
    a 32-character hex UID and a supported image extension.
    Returns (matched_list, non_matched_list).
    """
    pattern = re.compile(r'^([0-9a-f]{32})\.(jpg|jpeg|png|gif)$', re.IGNORECASE)
    matched = []
    non_matched = []

    for root, _, files in os.walk(directory):
        for fname in files:
            full_path = os.path.join(root, fname)
            m = pattern.match(fname)
            if m:
                uid = m.group(1)
                matched.append({
                    'uid': uid,
                    'filename': fname,
                    'path': full_path
                })
                logging.info(f'Found matching image: {full_path}')
            else:
                non_matched.append(full_path)

    return matched, non_matched

def load_ocr_data(ocr_json_file):
    """
    Load OCR data from a JSONL file (each line is a JSON object).
    
    Returns a dictionary mapping UIDs to their OCR data.
    """
    logging.info(f'Loading OCR data from: {ocr_json_file}')
    ocr_map = {}
    try:
        with open(ocr_json_file, 'r', encoding='utf-8') as f:
            line_count = 0
            for line in f:
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                    
                try:
                    entry = json.loads(line)
                    if 'uid' in entry:
                        uid = entry['uid']
                        ocr_map[uid] = entry
                        line_count += 1
                        if line_count % 500 == 0:  # Log progress every 500 entries
                            logging.info(f'Processed {line_count} entries...')
                except json.JSONDecodeError as e:
                    logging.error(f'Error parsing JSON line: {e}')
                    continue
                    
        logging.info(f'Loaded {len(ocr_map)} OCR entries')
        return ocr_map
    except Exception as e:
        logging.error(f'Error loading OCR data: {e}')
        return {}

def match_images_with_ocr(images, ocr_data):
    """
    Match images with OCR data based on UID.
    Returns a list of images with OCR data attached.
    """
    matched_images = []
    
    for img in images:
        uid = img['uid']
        ocr_entry = ocr_data.get(uid)
        
        if ocr_entry:
            # Create a new dict with image info and OCR data
            matched_entry = img.copy()
            matched_entry['ocr_data_found'] = True
            
            # Extract relevant OCR data
            for key in ['face_bboxes', 'url', 'key', 'captions', 'metadata']:
                if key in ocr_entry:
                    matched_entry[key] = ocr_entry[key]
                    
            matched_images.append(matched_entry)
            logging.info(f'Matched image {img["filename"]} with OCR data')
        else:
            # Include image info but note that OCR data was not found
            img['ocr_data_found'] = False
            matched_images.append(img)
            logging.info(f'No OCR data found for image {img["filename"]}')
    
    return matched_images

def write_output(data, output_file):
    """Write the collected data (images and stats) to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    logging.info(f'Output written to {output_file}')

def main():
    parser = argparse.ArgumentParser(
        description='Scan a directory for UID-named images and extract their info into JSON.'
    )
    parser.add_argument('-d', '--directory',
                        default=IMAGE_DIR,
                        help='Path (absolute or relative) to the directory containing images.')
    parser.add_argument('-o', '--output',
                        default=OUTPUT_FILE,
                        help='Output JSON file (default: salesforce_ocr.json)')
    parser.add_argument('-l', '--log',
                        default='image_extractor.log',
                        help='Log file path (default: image_extractor.log)')
    parser.add_argument('-j', '--ocr-json',
                        default=JSON_L_FILE,
                        help='JSON file containing OCR data (default: salesforce_2200.json)')
    args = parser.parse_args()

    setup_logging(args.log)
    logging.info(f'Starting scan in directory: {args.directory}')

    # Find images in the specified directory
    matched, non_matched = find_images(args.directory)
    
    # Load OCR data
    ocr_data = load_ocr_data(args.ocr_json)
    
    # Match images with OCR data
    matched_with_ocr = match_images_with_ocr(matched, ocr_data)
    
    stats = {
        'total_files_scanned': len(matched) + len(non_matched),
        'matched_count': len(matched),
        'matched_with_ocr': sum(1 for img in matched_with_ocr if img.get('ocr_data_found', True)),
        'non_matched_count': len(non_matched)
    }
    logging.info(f'Scan complete. Stats: {stats}')

    output_data = {
        'images': matched_with_ocr,
        'stats': stats
    }
    write_output(output_data, args.output)

if __name__ == '__main__':
    main()