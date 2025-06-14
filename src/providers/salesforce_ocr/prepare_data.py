# get all file names from the `salesforce_test` directory
import os
import sys
import json # Ensure json is imported
import random
import pandas as pd # Added pandas import

# sys.path.append("../src")
from src.providers.salesforce_ocr.ocr_data_bridge import OCRDataBridge
# Import the string paths from pathfinder
from src.utils.pathfinder import PROJECT_ROOT, SRC_DIR

# Initialize the bridge
bridge = OCRDataBridge()

# PROJECT_ROOT # This line is redundant as PROJECT_ROOT is imported
# Use os.path.join for consistency with pathfinder.py
IMAGE_DIR = os.path.join(SRC_DIR, "data", "salesforce_ocr", "salesforce_images")
SAMPLE_IMAGE_LIST_FILE = os.path.join(SRC_DIR, "data", "salesforce", "all_image_files.txt")
SALESFORCE_OCR_JSON_FILE = os.path.join(SRC_DIR, "data", "salesforce", "salesforce_ocr.json") # Path to the JSONL file
RESULTS_DIR = os.path.join(SRC_DIR, "data","salesforce","qa_pairs") # Define a results directory
os.makedirs(RESULTS_DIR, exist_ok=True) # Ensure the results directory exists

all_image_files = []
# Use os.path.exists for string paths
if os.path.exists(SAMPLE_IMAGE_LIST_FILE):
    with open(SAMPLE_IMAGE_LIST_FILE, "r") as f:
        all_image_files = [line.strip() for line in f.readlines() if line.strip()]
else:
    print(f"Warning: Sample image list file not found at {SAMPLE_IMAGE_LIST_FILE}")

# Create a mapping from UID to filename for URL construction
uid_to_filename = {fn.split('.')[0]: fn for fn in all_image_files}

# Load data from salesforce_ocr.json
salesforce_data = []
if os.path.exists(SALESFORCE_OCR_JSON_FILE):
    with open(SALESFORCE_OCR_JSON_FILE, 'r') as f:
        try:
            salesforce_data = json.load(f) # Assuming it's a JSON array
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {SALESFORCE_OCR_JSON_FILE}: {e}")
else:
    print(f"Warning: Salesforce OCR JSON file not found at {SALESFORCE_OCR_JSON_FILE}")


# Print the number of files found
files_found = len(all_image_files)
print(f"Found {files_found} image files listed in {SAMPLE_IMAGE_LIST_FILE}")
# sample_size = files_found # This variable was defined but not clearly used later, can be removed if not needed.


def get_caption_text_by_granularity(sample_row, desired_granularity=1, prefer_no_raw_datacomp=True):
    """
    Extracts caption text for a specific granularity from salesforce_ocr.json entry.
    Uses the existing 'captions' field which contains rich OCR data with different granularities.
    """
    if sample_row is None:
        return None
    
    captions_str = sample_row.get("captions")
    if not captions_str:
        print(f"Warning: Missing 'captions' for UID: {sample_row.get('uid')}")
        return None
        
    try:
        captions_list = json.loads(captions_str)
        
        # Try to find the exact granularity, optionally filtering by include_datacomp_raw_cap
        for cap_obj in captions_list:
            if cap_obj.get("granularity") == desired_granularity:
                if prefer_no_raw_datacomp and cap_obj.get("include_datacomp_raw_cap") == True:
                    continue # Skip raw datacomp if preferred
                return cap_obj.get("text")

        # Fallback: if exact granularity with preference not found, try without preference
        if prefer_no_raw_datacomp:
            for cap_obj in captions_list:
                if cap_obj.get("granularity") == desired_granularity:
                    return cap_obj.get("text")
        
        # If still not found, return None
        return None
        
    except json.JSONDecodeError:
        print(f"Error decoding captions JSON for UID: {sample_row.get('uid')}")
        return None
    except Exception as e:
        print(f"Error processing captions for UID: {sample_row.get('uid')}: {e}")
        return None

def get_ocr_text_from_salesforce_json_entry(sample_row):
    """
    DEPRECATED: This function extracts from metadata field.
    Use get_caption_text_by_granularity() instead to use the rich captions data.
    """
    if sample_row is None:
        return None
    
    metadata_str = sample_row.get("metadata")
    if not metadata_str:
        print(f"Warning: Missing 'metadata' for UID: {sample_row.get('uid')}")
        return None
        
    try:
        metadata = json.loads(metadata_str)
        entries = metadata.get("entries")
        if not entries:
            print(f"Warning: Missing 'entries' in metadata for UID: {sample_row.get('uid')}")
            return None
        
        all_text = " ".join([entry.get("text", "").strip() for entry in entries if entry.get("text")]).strip()
        return all_text if all_text else None
    except json.JSONDecodeError:
        print(f"Error decoding metadata JSON for UID: {sample_row.get('uid')}")
        return None
    except AttributeError:
        print(f"Attribute error processing metadata for UID: {sample_row.get('uid')}")
        return None

# This is the old get_ocr_text_for_qna, which might be needed if OCRDataBridge relies on it internally
# or if some parts of the script still expect the old "captions" structure with granularities.
# For now, we assume the bridge's create_ocr_qa_pairs will use the 'granularity' argument
# to pick from the 'captions' we construct.
def get_ocr_text_for_qna(
    sample_row, desired_granularity=0, prefer_no_raw_datacomp=True
):
    # This function's logic for choosing based on granularity might still be relevant
    # for how OCRDataBridge consumes the 'captions' field we will prepare.
    if sample_row is None:
        return None

    captions_str = sample_row.get("captions") # This will be the field we construct for the DataFrame
    if not captions_str:
        return None

    try:
        captions_list = json.loads(captions_str)
        # Try to find the exact granularity
        for cap_obj in captions_list:
            if cap_obj.get("granularity") == desired_granularity:
                if prefer_no_raw_datacomp and cap_obj.get("include_datacomp_raw_cap") == True:
                    continue # Skip raw datacomp if preferred
                return cap_obj.get("text")

        # Fallback: if exact granularity with preference not found, try without preference
        if prefer_no_raw_datacomp:
            for cap_obj in captions_list:
                if cap_obj.get("granularity") == desired_granularity:
                    return cap_obj.get("text")
        
        # Fallback: if desired_granularity not found at all, try to get any text from granularity 0 or 5
        for default_granularity in [0, 5]: # Check common defaults
            for cap_obj in captions_list:
                if cap_obj.get("granularity") == default_granularity:
                    return cap_obj.get("text")

        # Final fallback: return the first caption's text if any
        if captions_list:
            return captions_list[0].get("text")

    except json.JSONDecodeError:
        print(f"Error decoding captions JSON in get_ocr_text_for_qna for UID: {sample_row.get('uid')}")
        return None
    return None


if salesforce_data:
    sample_for_qna_from_json = salesforce_data[0]

    # --- Configuration for Q&A Generation (using granularity 1 for word-based locations) ---
    CHOSEN_GRANULARITY = 1 # Granularity 1 has locations in words (above center, below center, etc.)
    
    ground_truth_ocr_text = get_caption_text_by_granularity(sample_for_qna_from_json, CHOSEN_GRANULARITY)

    if ground_truth_ocr_text:
        question = "What is all the text visible in this image?"
        image_uid = sample_for_qna_from_json.get("uid")
        
        image_filename = uid_to_filename.get(image_uid)
        # Ensure IMAGE_DIR is a string for os.path.join
        image_url_for_qna = os.path.join(str(IMAGE_DIR), image_filename) if image_filename else f"URL_NOT_FOUND_FOR_{image_uid}"
        
        print(f"--- Generated Q&A for Image UID: {image_uid} (using granularity {CHOSEN_GRANULARITY}) ---")
        print(f"Image URL: {image_url_for_qna}")
        print(f"Question: {question}")
        print(f"Ground-Truth Answer (granularity {CHOSEN_GRANULARITY} - word-based locations):")
        print(f"{ground_truth_ocr_text}")

        prepared_data_item = {
            "process_id": image_uid,
            "Open-ended Verifiable Question": question,
            "Ground-True Answer": ground_truth_ocr_text,
            "img_urls": [image_url_for_qna] if image_url_for_qna and "NOT_FOUND" not in image_url_for_qna else [],
        }
        print("\nPrepared data item structure for the reasoning script (from first JSON entry):")
        print(json.dumps(prepared_data_item, indent=2))
    else:
        print(
            f"Could not extract granularity {CHOSEN_GRANULARITY} caption text from the first sample in salesforce_ocr.json (UID: {sample_for_qna_from_json.get('uid')})."
        )
else:
    print("Salesforce OCR JSON data not loaded or empty, skipping Q&A formulation for the first sample.")

# Make sure re is imported if not already (re is not used in the visible snippet, but good to keep if used elsewhere)
# import re 

# Since we have the file names in all_image_files, let's randomly sample one
random_file = random.choice(all_image_files) if all_image_files else None

if random_file:
    uid = random_file.split(".")[0]

    print(f"\n--- Generating Q&A for a randomly selected image file: {random_file} ---")
    print(f"Extracted UID: {uid}")

    # Create a mock sample row similar to salesforce_ocr.json structure
    # This requires finding the corresponding entry in salesforce_data or creating a pure mock
    # For simplicity, let's try to find it in loaded data, or make a simpler mock if not found.
    corresponding_json_entry = next((item for item in salesforce_data if item.get("uid") == uid), None)
    
    ocr_text_for_random_sample = None
    if corresponding_json_entry:
        # Use granularity 1 for word-based locations
        ocr_text_for_random_sample = get_caption_text_by_granularity(corresponding_json_entry, 1)
    else:
        # Fallback to a very basic mock if UID not in salesforce_ocr.json (e.g., if all_image_files is broader)
        print(f"UID {uid} from random file not found in salesforce_ocr.json, using basic mock text.")
        ocr_text_for_random_sample = f"Mock OCR text for image {uid}"

    # Ensure IMAGE_DIR is a string for os.path.join
    image_url_for_random_qna = os.path.join(str(IMAGE_DIR), random_file)

    question = "What is all the text visible in this image?"
    prepared_data_item_random = {
        "process_id": uid,
        "Open-ended Verifiable Question": question,
        "Ground-True Answer": ocr_text_for_random_sample if ocr_text_for_random_sample else "OCR text not available for random sample",
        "img_urls": [image_url_for_random_qna],
    }

    print("\nGenerated sample Q&A (from random file):")
    print(json.dumps(prepared_data_item_random, indent=2))
else:
    print("\nNo image files found in the list to sample for random Q&A generation.")

# Create QA pairs from our Salesforce data (loaded from salesforce_ocr.json)
print("\n=== Generating OCR QA Pairs from salesforce_ocr.json ===")

reformatted_data_for_bridge = []
for item in salesforce_data:
    uid = item.get("uid")
    if not uid:
        continue

    # Extract caption text for different granularities from the existing captions field
    # This uses the rich OCR data that already exists in salesforce_ocr.json
    granularity_texts = {}
    for granularity in [0, 1, 2, 3, 4, 5]:
        text = get_caption_text_by_granularity(item, granularity, prefer_no_raw_datacomp=True)
        if text:
            granularity_texts[granularity] = text

    # If no caption texts found, skip this item
    if not granularity_texts:
        print(f"Warning: No caption text found for any granularity for UID {uid}")
        continue

    # Construct the 'captions' field using the actual caption texts from the JSON
    # This preserves the rich OCR data with different levels of detail
    captions_list = []
    for granularity, text in granularity_texts.items():
        captions_list.append({
            "granularity": granularity, 
            "text": text, 
            "include_datacomp_raw_cap": False
        })
    
    captions_json_string = json.dumps(captions_list)

    image_filename = uid_to_filename.get(uid)
    # Ensure IMAGE_DIR is a string for os.path.join
    image_url = os.path.join(str(IMAGE_DIR), image_filename) if image_filename else None
    
    if image_url:
        reformatted_data_for_bridge.append({
            "uid": uid,
            "url": image_url,
            "captions": captions_json_string # This now contains the actual rich caption data
        })
    # else:
        # print(f"Skipping UID {uid} due to missing image file for bridge preparation.")

salesforce_df_for_bridge = pd.DataFrame()
if reformatted_data_for_bridge:
    salesforce_df_for_bridge = pd.DataFrame(reformatted_data_for_bridge)
    print(f"Prepared {len(salesforce_df_for_bridge)} rows of data for the OCRDataBridge.")
else:
    print("No data prepared for OCRDataBridge (possibly due to missing UIDs, metadata, or image files).")


# Generate QA pairs using different granularities
# The bridge.create_ocr_qa_pairs will use the 'granularity' argument to pick from the 'captions'
# field of the salesforce_df_for_bridge.
if not salesforce_df_for_bridge.empty:
    # Focus on granularity 1 (word-based locations) as requested by the user
    # But also include 0 and 5 for comparison
    for granularity_to_request in [0, 1, 5]:  # 1 is the main focus (word-based locations)
        print(f"\n--- Processing for Granularity {granularity_to_request} to be requested from bridge ---")
        
        if granularity_to_request == 1:
            print("*** This is the granularity with word-based locations (above center, below center, etc.) ***")

        # Note: num_samples might be more than available data, pandas sample handles this.
        # Ensure image_dir is correctly used by the bridge if URLs are not absolute or if it needs it.
        qa_pairs = bridge.create_ocr_qa_pairs(
            salesforce_df=salesforce_df_for_bridge, 
            image_dir=str(IMAGE_DIR), # Passed for consistency, though URLs in df are absolute
            num_samples=len(salesforce_df_for_bridge), # Process all samples in the DataFrame
            granularity=granularity_to_request, # This is the key argument for the bridge
            seed=42, # Seed can remain for reproducibility if sampling were still used
        )

        print(f"Generated {len(qa_pairs)} QA pairs for requested granularity {granularity_to_request}")

        if qa_pairs:
            validation = bridge.validate_qa_pairs(qa_pairs)
            print(f"Validation Results:")
            print(f"  Total pairs: {validation['total_pairs']}")
            print(f"  Valid pairs: {validation['valid_pairs']}")
            print(f"  Issues found: {len(validation['issues'])}")

            if validation["issues"]:
                print("\nFirst few issues:")
                for issue in validation["issues"][:3]:
                    print(f"  - Pair {issue['pair_index']}: {issue['issues']}")

            output_file_name = f"ocr_qa_pairs_from_json_granularity_{granularity_to_request}.json"
            output_file = os.path.join(RESULTS_DIR, output_file_name) # Save in the results directory
            bridge.save_for_reasoning_pipeline(qa_pairs, output_file)

            if qa_pairs: # Show sample from this batch
                print(f"\nSample QA Pair (Requested Granularity {granularity_to_request}):")
                sample = qa_pairs[0]
                print(f"  Question: {sample['Open-ended Verifiable Question']}")
                answer_snippet = sample['Ground-True Answer']
                print(
                    f"  Answer: {answer_snippet[:200]}{'...' if len(answer_snippet) > 200 else ''}"
                )
                print(f"  Image URLs: {sample['img_urls']}")
                print(f"  Process ID: {sample['process_id']}")
        else:
            print(f"No QA pairs generated for requested granularity {granularity_to_request}.")
else:
    print("Skipping OCR QA Pair generation as the DataFrame for the bridge is empty.")

print("\n=== OCR QA Pair Generation from salesforce_ocr.json Complete ===")
if not salesforce_df_for_bridge.empty:
    print("Files generated (if QA pairs were created):")
    for g in [0, 7]:
        # Update the path to show where files are saved
        print(f"- {os.path.join(RESULTS_DIR, f'ocr_qa_pairs_from_json_granularity_{g}.json')}")
    print("\nThese files are now ready for the reasoning pipeline!")
else:
    print("No files generated as no data was processed by the bridge.")
