"""
Multimodal QRA Pair Processing - Refactored Version
Now uses the centralized reasoning engine for cleaner architecture.
"""

import os
import json
import yaml
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Import the reasoning engine
from core.reasoning_engine import (
    ReasoningConfig, 
    MultimodalGPT, 
    ReasoningStrategies,
    extract_final_conclusion,
    check_answer_accuracy
)

load_dotenv()

def filter_data(tmpdata):
    """Filter and prepare data for processing."""
    filtered_data = []
    process_id = 1
    for case in tmpdata:
        if case.get('Open-ended Verifiable Question') and case.get('img_urls'):
            case['process_id'] = process_id
            filtered_data.append(case)
            process_id += 1
    
    print(f"Original data size: {len(tmpdata)}, Filtered data size: {len(filtered_data)}")
    return filtered_data

def process_sample(d, gpt_instance, strategies, config, prompts):
    """Process a single data sample with advanced reasoning."""
    try:
        query_history = []
        response_history = []
        
        # Extract question and context
        question = d['Open-ended Verifiable Question']
        img_urls = d.get('img_urls', [])
        ground_truth = d.get('Ground-True Answer', '')
        
        # Step 1: Initial reasoning
        initial_prompt = prompts.get('query_prompt_init', '').format(question)
        query_history.append(initial_prompt)
        
        initial_response = gpt_instance.call(
            content=initial_prompt,
            image_urls=img_urls,
            additional_args={"max_tokens": 2000}
        )
        response_history.append(initial_response)
        
        # Step 2: Apply reasoning strategies
        context_data = {
            "image_urls": img_urls,
            "question": question,
            "current_response": initial_response
        }
        
        strategy_result = strategies.apply_all_strategies(
            initial_response,
            context_data=context_data,
            max_strategies=3
        )
        
        final_response = strategy_result["final_result"]
        query_history.extend([f"Applied strategy: {s}" for s in strategy_result["strategies_used"]])
        response_history.extend(strategy_result["reasoning_trace"])
        
        # Step 3: Verification
        is_correct = check_answer_accuracy(
            final_response, ground_truth, gpt_instance, query_history, response_history, content_type="medical"
        )
        
        # Compile results
        result = {
            'process_id': d['process_id'],
            'img_urls': img_urls,
            'Question': question,
            'Complex_CoT': '\n'.join(response_history),
            'Response': final_response,
            'Ground-True Answer': ground_truth,
            'Correct': is_correct,
            'Query_History': query_history,
            'Response_History': response_history,
            'Strategies_Used': strategy_result["strategies_used"]
        }
        
        print(f"Processed item {d['process_id']}: {'Correct' if is_correct else 'Incorrect'}")
        return True, result
        
    except Exception as e:
        print(f"Error processing item {d.get('process_id', 'unknown')}: {str(e)}")
        return False, None

def main():
    """Main processing function."""
    
    # Initialize reasoning components
    reasoning_config = ReasoningConfig()
    gpt_instance = MultimodalGPT(reasoning_config)
    strategies = ReasoningStrategies(reasoning_config, gpt_instance)
    
    config = reasoning_config.config
    prompts = reasoning_config.prompts
    
    # Load and filter data
    with open(config["data_path"], encoding='utf-8') as f:
        tmpdata = json.load(f)

    data = filter_data(tmpdata)

    if config.get("limit_num"):
        data = data[:config["limit_num"]]
        
    print(f"Read data: {len(data)} items")

    # Set up output directory
    task_name = f'{os.path.split(config["data_path"])[-1].replace(".json","")}_CoT_search'
    save_dir = f'reasoning_data_new/{task_name}'
    os.makedirs(save_dir, exist_ok=True)
    
    # Progress tracking
    progress_file = os.path.join(save_dir, "progress.json")
    progress_data = {}
    
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
        except Exception as e:
            print(f"Error loading progress: {e}")
            progress_data = {}
    
    # Filter unprocessed items
    def get_item_key(item):
        return f"{item['Open-ended Verifiable Question']}_{item['process_id']}"
    
    processed_keys = set(progress_data.keys())
    unprocessed_data = [item for item in data if get_item_key(item) not in processed_keys]
    print(f"Items remaining for processing: {len(unprocessed_data)} of {len(data)}")

    # Process items
    def process_wrapper(d):
        success, result = process_sample(d, gpt_instance, strategies, config, prompts)
        if success:
            # Save progress immediately
            key = get_item_key(d)
            progress_data[key] = result
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
        return success
    
    # Create progress file if needed
    if not os.path.exists(progress_file):
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    
    # Process unprocessed items
    if unprocessed_data:
        with ThreadPoolExecutor(max_workers=config.get("num_process", 4)) as executor:
            results = list(executor.map(process_wrapper, unprocessed_data))
        
        print(f"Completed processing {sum(results)} of {len(unprocessed_data)} items")
    else:
        print("No new items to process")
    
    # Load final results and save
    with open(progress_file, 'r', encoding='utf-8') as f:
        final_progress_data = json.load(f)
    
    final_data = list(final_progress_data.values())
    
    # Save full output
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
            'ground_truth': item.get('Ground-True Answer', ''),
            'correct': item.get('Correct', False),
            'strategies_used': item.get('Strategies_Used', [])
        }
        simplified_data.append(simplified_item)
    
    # Save simplified output
    simplified_output_path = f"simplified_{task_name}_{len(simplified_data)}.json"
    print(f"Saving simplified output with {len(simplified_data)} items to {simplified_output_path}")
    
    with open(simplified_output_path, 'w', encoding='utf-8') as file:
        json.dump(simplified_data, file, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
