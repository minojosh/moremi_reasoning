import json
import os
import sys
import argparse
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from tqdm import tqdm
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

from src.core.reasoning_engine import (
    ReasoningConfig,
    MultimodalGPT,
    ReasoningStrategies,
    extract_final_conclusion,
    synthesize_natural_reasoning
)
from src.providers.i_am_handwriting.iam_utils import (
    ProgressTracker, 
    IncrementalResultSaver,
    RecoveryManager
)

load_dotenv(project_root / ".env")

def process_salesforce_qa_pair(
    qa_item: dict,
    gpt_instance: MultimodalGPT, 
    reasoning_strategies: ReasoningStrategies, 
    prompts: dict,
    process_id: int = 0 
):
    """
    Processes a single Salesforce OCR QA pair through the reasoning pipeline.
    
    Args:
        qa_item: Dictionary containing QA pair data with keys:
                - 'Open-ended Verifiable Question': The question
                - 'Ground-True Answer': The ground truth answer
                - 'img_urls': List of image URLs/paths
                - 'process_id': Unique identifier
        gpt_instance: MultimodalGPT instance
        reasoning_strategies: ReasoningStrategies instance
        prompts: Prompts configuration
        process_id: Process identifier for tracking
    
    Returns:
        Dictionary containing processing results
    """
    query_history = []
    response_history = []
    
    try:
        # Extract data from QA item
        question = qa_item.get('Open-ended Verifiable Question', '')
        ground_truth_answer = qa_item.get('Ground-True Answer', '')
        image_urls = qa_item.get('img_urls', [])
        item_process_id = qa_item.get('process_id', process_id)
        
        if not question:
            raise ValueError("No question found in QA item")
        if not image_urls:
            raise ValueError("No image URLs found in QA item")
        
        # Verify image exists
        image_path = image_urls[0]  # Use first image
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # 1. Format the initial prompt using the pre-existing question
        qna_prompt_template_str = prompts.get('query_prompt_init', "Please answer the following question about the image: {question}")
        
        if "{question}" in qna_prompt_template_str:
            initial_prompt_content = qna_prompt_template_str.format(question=question)
        else:
            initial_prompt_content = qna_prompt_template_str.format(question)
            
        query_history.append(f"Formatted Prompt: {initial_prompt_content}")

        # 2. Initial model call
        initial_model_response = gpt_instance.call(
            content=initial_prompt_content,
            image_urls=[str(image_path)], 
            additional_args={"max_tokens": prompts.get("max_tokens", 1500)} 
        )
        response_history.append(initial_model_response)

        # 3. Apply reasoning strategies
        context_data = {
            "image_urls": [str(image_path)],
            "question": question,
            "current_response": initial_model_response,
            "ground_truth": ground_truth_answer  # Available for reference
        }
        
        strategy_result = reasoning_strategies.apply_all_strategies(
            initial_model_response,
            context_data=context_data,
            max_strategies=prompts.get('max_search_attempts', 3) 
        )
        
        final_answer_text = strategy_result["final_result"]
        query_history.extend([f"Applied strategy: {s}" for s in strategy_result["strategies_used"]])
        response_history.extend(strategy_result["reasoning_trace"])

        # 4. Synthesize Natural Reasoning
        natural_reasoning_text = synthesize_natural_reasoning(
            gpt_instance=gpt_instance, 
            reasoning_history=response_history,
            question=question,
            prompts=prompts
        )

        # 5. Generate final response
        final_response_prompt_template = prompts.get('final_response_prompt', 
            "Based on the internal thinking: {}\n\nFor the question: {}\n\nProvide a final response.")
        
        final_response_query = final_response_prompt_template.format(natural_reasoning_text, question)
        query_history.append(final_response_query)
        
        final_response = gpt_instance.text_only_call(
            content=final_response_query,
            additional_args={"max_tokens": prompts.get("final_response_max_tokens", 1000)}
        )
        response_history.append(final_response)

        # 6. Extract final conclusion
        extracted_answer = extract_final_conclusion(final_response, content_type="ocr") 

        return {
            "process_id": item_process_id,
            "image_path": str(image_path),
            "Question": question,
            "Ground_True_Answer": ground_truth_answer,
            "Complex_CoT": natural_reasoning_text,
            "Response": final_response,
            "Extracted_Answer": extracted_answer,
            "Query_History": query_history,
            "Response_History": response_history,
            "Strategies_Used": strategy_result["strategies_used"],
            "status": "success"
        }

    except Exception as e:
        return {
            "process_id": process_id,
            "image_path": qa_item.get('img_urls', ['unknown'])[0] if qa_item.get('img_urls') else 'unknown',
            "Question": qa_item.get('Open-ended Verifiable Question', 'unknown'),
            "Ground_True_Answer": qa_item.get('Ground-True Answer', ''),
            "error": str(e),
            "traceback": traceback.format_exc(),
            "status": "error"
        }

def load_qa_pairs_from_results(results_dir: Path, granularity: int = 1):
    """
    Load QA pairs from the results directory created by prepare_data.py
    
    Args:
        results_dir: Path to results directory
        granularity: Which granularity file to load (0, 1, 5, etc.)
    
    Returns:
        List of QA pair dictionaries
    """
    qa_file_pattern = f"ocr_qa_pairs_from_json_granularity_{granularity}.json"
    qa_file_path = results_dir / qa_file_pattern
    
    if not qa_file_path.exists():
        raise FileNotFoundError(f"QA pairs file not found: {qa_file_path}")
    
    with open(qa_file_path, 'r', encoding='utf-8') as f:
        qa_pairs = json.load(f)
    
    print(f"Loaded {len(qa_pairs)} QA pairs from {qa_file_path}")
    return qa_pairs

def run_salesforce_qa_reasoning(
    config_path: str = None, 
    limit: int = None, 
    resume: bool = True,
    granularity: int = 1,
    results_dir: str = None
):
    """
    Main function to run the Salesforce OCR QA reasoning pipeline.
    
    Args:
        config_path: Path to reasoning config file
        limit: Limit number of QA pairs to process
        resume: Whether to resume from previous progress
        granularity: Which granularity QA pairs to use (0, 1, 5, etc.)
        results_dir: Directory containing QA pairs from prepare_data.py
    """
    try:
        # Initialize reasoning components using Salesforce OCR config
        reasoning_config_obj = ReasoningConfig(
            config_file=config_path or "salesforce_config.yaml",  # Use Salesforce-specific config
            prompts_file="salesforce_prompts.yaml"  # Use Salesforce-specific prompts
        )
        gpt_instance = MultimodalGPT(reasoning_config_obj)
        reasoning_strategies = ReasoningStrategies(reasoning_config_obj, gpt_instance)

        pipeline_config = reasoning_config_obj.config 
        prompts_config = reasoning_config_obj.prompts

        # Load QA pairs from prepare_data.py results
        if results_dir is None:
            results_dir = project_root / "src" / "data" / "salesforce" / "qa_pairs"
        else:
            results_dir = Path(results_dir)
            
        qa_pairs = load_qa_pairs_from_results(results_dir, granularity)
        
        if not qa_pairs:
            print("No QA pairs found to process.")
            return

        if limit is not None and limit > 0:
            qa_pairs = qa_pairs[:limit]
        
        print(f"Processing {len(qa_pairs)} QA pairs (granularity {granularity})")

        # Initialize progress tracking and incremental saving
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = project_root / pipeline_config.get("results_dir", "results")
        output_dir.mkdir(parents=True, exist_ok=True)
        results_file = output_dir / f"salesforce_qa_reasoning_results_g{granularity}_{timestamp}.json"
        
        # Check for recovery options if resume is enabled
        recovery_manager = RecoveryManager(output_dir)
        if resume:
            incomplete_runs = recovery_manager.find_incomplete_runs()
            if incomplete_runs:
                print("\n" + "="*60)
                print("RECOVERY OPTIONS AVAILABLE")
                print("="*60)
                suggestions = recovery_manager.suggest_recovery_options(len(qa_pairs))
                print(suggestions)
                
                response = input("Do you want to resume from the most recent run? (y/n): ").strip().lower()
                if response == 'y' and incomplete_runs:
                    latest_run = max(incomplete_runs, key=lambda x: x['last_updated'])
                    results_file = Path(latest_run['results_file'])
                    print(f"Resuming from: {results_file}")
                    print(f"Already processed: {latest_run['processed_count']} items")
        
        # Initialize tracking components
        progress_tracker = ProgressTracker(
            results_file=str(results_file),
            progress_file=str(results_file.with_suffix('.progress'))
        )
        
        result_saver = IncrementalResultSaver(str(results_file))
        
        # Filter out already processed samples
        remaining_qa_pairs = []
        for qa_item in qa_pairs:
            item_id = qa_item.get('process_id', 'unknown')
            if not progress_tracker.is_processed(str(item_id)):
                remaining_qa_pairs.append(qa_item)
        
        if not remaining_qa_pairs:
            print("All QA pairs have already been processed!")
            print(f"Results available in: {results_file}")
            return
        
        print(f"Resuming processing: {len(remaining_qa_pairs)} remaining out of {len(qa_pairs)} total QA pairs")
        
        # Create backup of existing results
        if results_file.exists():
            backup_file = result_saver.backup_results()
            if backup_file:
                print(f"Created backup: {backup_file}")

        results = []
        num_workers = pipeline_config.get("num_processes", os.cpu_count() or 1)
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_qa = {
                executor.submit(
                    process_salesforce_qa_pair, 
                    qa_item, 
                    gpt_instance, 
                    reasoning_strategies, 
                    prompts_config,
                    qa_item.get('process_id', idx)
                ): qa_item
                for idx, qa_item in enumerate(remaining_qa_pairs)
            }
            
            # Process completed tasks and save incrementally
            with tqdm(total=len(remaining_qa_pairs), desc="Processing QA pairs") as pbar:
                for future in as_completed(future_to_qa):
                    qa_item = future_to_qa[future]
                    try:
                        result = future.result()
                        
                        # Save result immediately
                        result_saver.append_result(result)
                        results.append(result)
                        
                        # Mark as processed
                        item_id = str(qa_item.get('process_id', 'unknown'))
                        progress_tracker.mark_processed(item_id)
                        
                        # Update progress bar
                        if result.get("status") == "success":
                            pbar.set_postfix({"Status": "✓", "ID": item_id})
                        else:
                            pbar.set_postfix({"Status": "✗", "Error": result.get("error", "unknown")[:50]})
                        
                        pbar.update(1)
                        
                    except Exception as exc:
                        print(f"Critical error in future for QA item {qa_item.get('process_id', 'unknown')}: {exc}")
                        
                        item_id = str(qa_item.get('process_id', 'unknown'))
                        progress_tracker.mark_processed(item_id)
                        
                        error_result = {
                            "process_id": qa_item.get('process_id', 'unknown'),
                            "error": str(exc), 
                            "status": "error_in_future"
                        }
                        result_saver.append_result(error_result)
                        results.append(error_result)
                        pbar.update(1)

        # Final statistics
        stats = progress_tracker.get_stats()
        all_results = result_saver.get_existing_results()
        
        print("\n" + "="*60)
        print("SALESFORCE QA REASONING COMPLETE")
        print("="*60)
        print(f"Granularity processed: {granularity}")
        print(f"Total processed: {stats['processed_count']}")
        print(f"Results saved to: {results_file}")
        
        # Summary of results
        successful_count = sum(1 for r in all_results if r.get("status") == "success")
        error_count = len(all_results) - successful_count
        print(f"Successful: {successful_count}")
        print(f"Errors: {error_count}")

        # Show sample results
        for i, res in enumerate(all_results[:min(3, len(all_results))]): 
            print(f"\n--- Result {i+1} ---")
            if res.get("status") == "success":
                print(f"  Process ID: {res.get('process_id')}")
                print(f"  Question: {res['Question'][:100]}...")
                print(f"  Ground Truth: {res['Ground_True_Answer'][:100]}...")
                print(f"  Model Answer: {res['Response'][:100]}...")
                print(f"  Strategies: {res.get('Strategies_Used')}")
            else:
                print(f"  Process ID: {res.get('process_id', 'N/A')}")
                print(f"  Error: {res['error']}")

        # Generate simplified output
        simplified_results = []
        for res in all_results:
            if res.get("status") == "success":
                simplified_item = {
                    'process_id': res.get('process_id'),
                    'image_path': res.get('image_path'),
                    'question': res.get('Question'),
                    'reasoning': res.get('Complex_CoT'),
                    'answer': res.get('Response'),
                    'ground_truth': res.get('Ground_True_Answer'),
                    'strategies_used': res.get('Strategies_Used')
                }
                simplified_results.append(simplified_item)

        simplified_output_path = results_file.with_name(results_file.stem + "_simplified.json")
        with open(simplified_output_path, 'w', encoding='utf-8') as f:
            json.dump(simplified_results, f, indent=4)
        print(f"Simplified results saved to: {simplified_output_path}")

    except FileNotFoundError as fnf_error:
        print(f"Configuration Error: {fnf_error}")
        print("Please ensure Salesforce OCR config files exist or QA pairs are generated.")
    except Exception as e:
        print(f"An unexpected error occurred in the pipeline: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Salesforce OCR QA Reasoning Pipeline")
    parser.add_argument(
        "--config",
        help="Path to the reasoning config file for Salesforce OCR",
        default=None
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of QA pairs to process"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh without checking for previous progress"
    )
    parser.add_argument(
        "--granularity",
        type=int,
        default=1,
        help="Which granularity QA pairs to use (0=basic, 1=word locations, 5=bbox, etc.)"
    )
    parser.add_argument(
        "--results-dir",
        help="Directory containing QA pairs from prepare_data.py",
        default=None
    )
    
    args = parser.parse_args()
    
    run_salesforce_qa_reasoning(
        config_path=args.config, 
        limit=args.limit, 
        resume=not args.no_resume,
        granularity=args.granularity,
        results_dir=args.results_dir
    )
