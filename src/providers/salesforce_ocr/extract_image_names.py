#!/usr/bin/env python3
import os
import sys
import argparse
from src.utils.pathfinder import get_project_root, get_src_dir, get_image_dir
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.append(str(PROJECT_ROOT))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.append(str(SRC_DIR))
IMAGE_DIR = os.path.join(SRC_DIR, "data", "salesforce", "salesforce_images")

def get_image_files(directory):
    # Specify common image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
    try:
        return [
            f for f in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, f)) and os.path.splitext(f)[1].lower() in image_extensions
        ]
    except FileNotFoundError:
        print(f"Directory not found: {directory}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Extract image file names from a specified directory."
    )
    parser.add_argument(
        '--dir',
        type=str,
        default=IMAGE_DIR,
        help='Directory containing images (default: src/data/salesforce/salesforce_images)'
    )
    args = parser.parse_args()

    image_dir = args.dir
    image_files = get_image_files(image_dir)

    # Save the list to "all_image_files.txt" in the same directory as this script.
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_image_files.txt")
    
    with open(output_file, "w") as f:
        for filename in image_files:
            f.write(f"{filename}\n")
    
    print(f"Found {len(image_files)} image(s). List saved to {output_file}")

if __name__ == "__main__":
    main()