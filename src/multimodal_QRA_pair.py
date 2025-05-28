# %%

from tqdm import tqdm
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from dotenv import load_dotenv
from kaggle_secrets import UserSecretsClient
import os
import base64
import random
import json
import re  
import traceback
import requests
from urllib.parse import urlparse
import yaml

load_dotenv()
user_secrets = UserSecretsClient()

# Get the directory of the current script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load CONFIG from reasoning_config.yaml (located in config subdirectory)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config", "reasoning_config.yaml")
if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"reasoning_config.yaml not found. Expected at: {CONFIG_PATH}")
with open(CONFIG_PATH, 'r') as f:
    CONFIG = yaml.safe_load(f)

# Load PROMPTS from reasoning_prompts.yaml (located in config subdirectory)
PROMPTS_PATH = os.path.join(SCRIPT_DIR, "config", "reasoning_prompts.yaml")
if not os.path.exists(PROMPTS_PATH):
    raise FileNotFoundError(f"reasoning_prompts.yaml not found. Expected at: {PROMPTS_PATH}")
with open(PROMPTS_PATH, 'r') as f:
    PROMPTS = yaml.safe_load(f)

def encode_image(image_path):
    """Encode image from local file or URL to base64"""
    try:
        # Check if it's a URL
        if image_path.startswith(('http://', 'https://')):
            response = requests.get(image_path, timeout=30)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
        else:
            # Handle local file
            if not os.path.isabs(image_path):
                # If relative path, join with image_dir
                image_path = os.path.join(CONFIG["image_dir"], os.path.basename(image_path))
            
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image {image_path}: {str(e)}")
        raise

class GPT:
    def __init__(self):
        self.model_name = CONFIG["model_name"]
        self.api_url = CONFIG["api_url"]
        self.api_key = user_secrets.get_secret("OPEN_ROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY")
        return

    def call(self, content, additional_args={}, image_urls=None, url=None, model=None):
        client = OpenAI(
        base_url=url or self.api_url,
        api_key=self.api_key,
        )

        try:
            messages = [{
                "role": "user",
                "content": []
            }]
            
            # Add text content
            messages[0]["content"].append({"type": "text", "text": content})
            
            # Add multiple image content if provided
            if image_urls and isinstance(image_urls, list):
                for img_url in image_urls:
                    encoded_image = encode_image(img_url)
                    image_url_with_prefix = f"data:image/jpeg;base64,{encoded_image}"
                    messages[0]["content"].append({"type": "image_url", "image_url": {"url": image_url_with_prefix}})
            # Handle single image case for backward compatibility
            elif image_urls:
                encoded_image = encode_image(image_urls)
                image_url_with_prefix = f"data:image/jpeg;base64,{encoded_image}"
                messages[0]["content"].append({"type": "image_url", "image_url": {"url": image_url_with_prefix}})
            
            response = client.chat.completions.create(
                model=model or self.model_name,
                messages=messages,
                max_tokens=20000,
                temperature=1
            )
            
            # Extract the content from the response
            response_content = response.choices[0].message.content
            
            if not response_content:
                raise ValueError("Empty response from API")
                
            return response_content
            
        except Exception as e:
            print(f"API Error: {str(e)}")
            raise ValueError(f"API Error: {str(e)}")

    def text_only_call(self, content, additional_args={}):
        """Special method for text-only processing like verification tasks"""
        return self.call(content, additional_args, model="google/gemini-2.0-flash-001")

    def retry_call(self, content, additional_args={"max_tokens": 20000}, image_urls=None, url=None, max_attempts=2):
        """Simplified retry call with limited attempts"""
        for attempt in range(max_attempts):
            try:
                return self.call(content, additional_args, image_urls, url or self.api_url, self.model_name)
            except Exception as e:
                if attempt == max_attempts - 1:  # Last attempt
                    raise
                print(f"Retry attempt {attempt + 1}/{max_attempts} after error: {str(e)}")

# Search strategies with their corresponding prompts
# This definition needs to be AFTER PROMPTS is loaded.
search_strategies = [
    ('Backtracking', PROMPTS.get('gen_prompt_rethink_Backtracking', '')),
    ('Exploring New Paths', PROMPTS.get('gen_prompt_rethink_Exploring_New_Path', '')),
    ('Verification', PROMPTS.get('gen_prompt_rethink_Verification', '')),
    ('Correction', PROMPTS.get('gen_prompt_rethink_Correction', ''))
]

def extract_final_conclusion(text):
    """Extract what appears to be a final conclusion or answer from text"""
    # Look for common conclusion indicators
    conclusion_markers = [
        r"(?:final conclusion|in conclusion|therefore|thus|to conclude|in summary):\s*(.*?)(?:\n\n|\Z)",
        r"(?:the answer is|my answer is|i conclude that):\s*(.*?)(?:\n\n|\Z)",
        r"(?:diagnosis is|diagnosis:|final diagnosis:):\s*(.*?)(?:\n\n|\Z)",
    ]
    
    for marker in conclusion_markers:
        match = re.search(marker, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # If no markers found, try to find the last non-empty paragraph
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if paragraphs:
        return paragraphs[-1]
        
    # Fallback - just return the last 100 characters
    return text[-100:].strip() if len(text) > 100 else text.strip()

def check_answer_accuracy(response, reference, gpt_instance, query_history, response_history):
    """Check if a response is correct without requiring specific formatting"""
    query = PROMPTS['verify_prompt'].format(response, reference)
    query_history.append(query)
    
    verification = gpt_instance.text_only_call(query)
    response_history.append(verification)
    print("verification: ", verification)
    
    return 'true' in verification.lower()

def main():
    def filter_data(tmpdata):
        filtered_data = []
        process_id = 1
        for case in tmpdata:
            # Handle both old format and new OCR format
            if isinstance(case, dict):
                if "question" in case and "answer" in case:
                    # Old format
                    data_point = {
                        'process_id': process_id,
                        'Open-ended Verifiable Question': case["question"],
                        'Ground-True Answer': case["answer"],
                        'img_urls': case.get('img_urls', [])
                    }
                elif "Open-ended Verifiable Question" in case:
                    # New OCR format - already properly structured
                    data_point = case.copy()
                    data_point['process_id'] = process_id
                else:
                    # Skip malformed data
                    print(f"Warning: Skipping malformed data entry: {case}")
                    continue
            else:
                print(f"Warning: Skipping non-dict data entry: {case}")
                continue
                
            filtered_data.append(data_point)
            process_id += 1

        print(f"Original data size: {len(tmpdata)}, Filtered data size: {len(filtered_data)}")
        return filtered_data

    with open(CONFIG["data_path"], encoding='utf-8') as f:
        tmpdata = json.load(f)

    data = filter_data(tmpdata)

    if CONFIG["limit_num"]:
        data = data[:CONFIG["limit_num"]]
        
    print(f"Read data: {len(data)} items")

    task_name = f'{os.path.split(CONFIG["data_path"])[-1].replace(".json","")}_CoT_search'
    save_dir = f'reasoning_data_new/{task_name}'
    os.makedirs(save_dir, exist_ok=True)
    
    # Define progress file path
    progress_file = os.path.join(save_dir, "progress.json")
    
    # Load progress data if it exists
    progress_data = {}
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
                print(f"Loaded progress data with {len(progress_data)} processed items")
        except Exception as e:
            print(f"Error loading progress file: {str(e)}")
            progress_data = {}
    
    # Create a set of already processed keys (need a unique identifier)
    processed_keys = set(progress_data.keys())
    print(f"Found {len(processed_keys)} previously processed entries")
    
    # Filter out already processed items by creating a unique key for each entry
    def get_item_key(item):
        # Create a more unique key by combining question with process_id
        return f"{item['Open-ended Verifiable Question']}_{item['process_id']}"
    
    unprocessed_data = [item for item in data if get_item_key(item) not in processed_keys]
    print(f"Items remaining for processing: {len(unprocessed_data)} of {len(data)}")

    gpt_instance = GPT()

    def process_sample(d):
        try:
            # Initialize tracking variables
            query_history = []
            response_history = []
            reasoning_history = []
            attempt_history = []
            correct = False
            
            # Get image URLs - now using the list of images
            image_urls = d.get('img_urls', [])
            
            # Create a unique key for this item
            item_key = get_item_key(d)
            
            # Initial reasoning attempt using query_prompt_init
            query = PROMPTS['query_prompt_init'].format(d['Open-ended Verifiable Question'])
            query_history.append(query)
            
            response = gpt_instance.retry_call(query, image_urls=image_urls)
            response_history.append(response)
            reasoning_history.append(response)
            attempt_history.append('Initial Analysis')
            
            # Extract conclusion and verify if correct
            correct = check_answer_accuracy(response, d['Ground-True Answer'], 
                                          gpt_instance, query_history, response_history)
            
            # Track whether an answer was verified as correct
            found_correct_answer = correct
            
            # Try different strategic approaches if incorrect
            search_attempts = 0
            while not correct and search_attempts < CONFIG["max_search_attempts"]:
                strategy_name, gen_prompt_rethink = random.choice(search_strategies)
                attempt_history.append(strategy_name)
                
                # Format the selected rethink prompt
                query = gen_prompt_rethink.format(d['Open-ended Verifiable Question'], response)
                query_history.append(query)
                
                response = gpt_instance.retry_call(query, image_urls=image_urls)
                response_history.append(response)
                reasoning_history.append(response)
                
                correct = check_answer_accuracy(response, d['Ground-True Answer'], 
                                              gpt_instance, query_history, response_history)
                if correct:
                    found_correct_answer = True
                search_attempts += 1
            
            # If still incorrect and efficient search enabled, provide the answer
            if not correct and CONFIG["efficient_search"]:
                attempt_history.append('Guided Prompt')
                last_reasoning = reasoning_history[-1] if reasoning_history else ""
                query = PROMPTS['guided_prompt'].format(d['Open-ended Verifiable Question'], last_reasoning, d['Ground-True Answer'])
                query_history.append(query)
                
                response = gpt_instance.retry_call(query, image_urls=image_urls)
                response_history.append(response)
                reasoning_history.append(response)
                
                correct = check_answer_accuracy(response, d['Ground-True Answer'], 
                                              gpt_instance, query_history, response_history)
                if correct:
                    found_correct_answer = True
            
            # Get the final reasoning flow
            best_reasoning_text = reasoning_history[-1] if reasoning_history else ""
            
            # Convert to natural reasoning
            query = PROMPTS['natural_reasoning_prompt'].format(best_reasoning_text, d['Open-ended Verifiable Question'])
            query_history.append(query)
            
            natural_response = gpt_instance.text_only_call(query)
            response_history.append(natural_response)
            natural_reasoning = natural_response
            
            # Generate final answer
            query = PROMPTS['final_response_prompt'].format(natural_reasoning, d['Open-ended Verifiable Question'])
            query_history.append(query)
            
            final_response = gpt_instance.text_only_call(query)
            response_history.append(final_response)
            
            # Compile results
            result = {
                'img_urls': image_urls,
                'Question': d['Open-ended Verifiable Question'],
                'Complex_CoT': natural_reasoning,
                'Response': final_response,
                'Ground-True Answer': d['Ground-True Answer'],
                'query_history': query_history,
                'response_history': response_history,
                'reasoning_attempts': attempt_history,
                'found_correct_answer': found_correct_answer
            }
            
            # Update progress data
            with open(progress_file, 'r+', encoding='utf-8') as f:
                try:
                    current_progress = json.load(f)
                except json.JSONDecodeError:
                    current_progress = {}
                
                # Add the new processed item
                current_progress[item_key] = result
                
                # Write back to file
                f.seek(0)
                f.truncate()
                json.dump(current_progress, f, ensure_ascii=False, indent=2)
                
            print(f"Successfully processed item with key: {item_key}")
            return 1
            
        except Exception as e:
            print(f"Error processing item: {str(e)}")
            traceback.print_exc()
            return 0
    
    # Create empty progress file if it doesn't exist
    if not os.path.exists(progress_file):
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    
    # Process unprocessed items
    if unprocessed_data:
        with ThreadPoolExecutor(max_workers=CONFIG["num_process"]) as executor:
            results = list(tqdm(executor.map(process_sample, unprocessed_data), 
                               total=len(unprocessed_data), 
                               desc="Processing samples", 
                               unit="sample"))
        
        print(f"Completed processing {sum(results)} of {len(unprocessed_data)} items")
    else:
        print("No new items to process")
    
    # Load final progress data
    with open(progress_file, 'r', encoding='utf-8') as f:
        final_progress_data = json.load(f)
    
    # Extract values from the progress data dictionary
    final_data = list(final_progress_data.values())
    
    # Save the full output
    output_path = f"{task_name}_{len(final_data)}.json"
    print(f"Saving {len(final_data)} processed items to {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(final_data, file, ensure_ascii=False, indent=2)
    
    # Generate simplified output
    simplified_data = []
    for item in final_data:
        simplified_item = {
            'img_urls': item.get('img_urls', []),
            'question': item.get('Question', ''),
            'reasoning': item.get('Complex_CoT', ''),
            'answer': item.get('Response', ''),
            'ground_truth': item.get('Ground-True Answer', '')
        }
        simplified_data.append(simplified_item)
    
    # Save simplified output
    simplified_output_path = f"simplified_{task_name}_{len(simplified_data)}.json"
    print(f"Saving simplified output with {len(simplified_data)} items to {simplified_output_path}")
    
    with open(simplified_output_path, 'w', encoding='utf-8') as file:
        json.dump(simplified_data, file, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()