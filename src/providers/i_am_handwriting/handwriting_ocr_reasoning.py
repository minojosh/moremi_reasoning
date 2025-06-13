import json
import os
import sys
import argparse
import random
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
    synthesize_natural_reasoning # Added import
    # check_answer_accuracy # Not used directly here as ground truth for generated Qs is complex
)
from src.providers.i_am_handwriting.iam_utils import (
    GroundTruthExtractor, 
    ProgressTracker, 
    IncrementalResultSaver,
    RecoveryManager
)
from src.providers.salesforce_ocr.ocr_question_generator import OCRQuestionGenerator

load_dotenv(project_root / ".env")

def process_sample_ocr(
    image_path: str, 
    xml_path: str, 
    gpt_instance: MultimodalGPT, 
    ground_truth_extractor: GroundTruthExtractor, 
    reasoning_strategies: ReasoningStrategies, 
    prompts: dict,
    question_generator: OCRQuestionGenerator,
    # Added process_id for consistency if ever needed for progress tracking like in multimodal_QRA_pair
    process_id: int = 0 
):
    """
    Processes a single handwriting sample for Q&A, mirroring multimodal_QRA_pair.py structure.
    1. Extracts ground truth text (full transcription) from XML.
    2. Generates a question about the image using OCRQuestionGenerator.
    3. Formats a prompt using the generated question and a template from prompts file.
    4. Gets an answer from MultimodalGPT based on the image and formatted prompt.
    5. Applies reasoning strategies for refinement.
    6. Extracts the final conclusion (answer).
    7. Tracks query and response history.
    """
    query_history = []
    response_history = []
    generated_question = "Error before question generation" # Default for error case

    try:
        image_id = Path(image_path).stem
        # Ground truth here is the full transcription from XML
        ground_truth_transcription = ground_truth_extractor.extract_text_from_xml(xml_path)
        if not ground_truth_transcription:
            ground_truth_transcription = "" # Placeholder

        # Generate a question for the image
        # You can customize difficulty and type
        question_difficulty = random.choice(["handwriting_basic", "handwriting_detailed", "handwriting_contextual"])
        # Ensure these difficulty levels exist or are handled in your OCRQuestionGenerator
        # For example, if OCRQuestionGenerator has a 'handwriting' content_type:
        generated_question = question_generator.generate_question(
            difficulty_level=question_difficulty,
            content_type="handwriting" # Assuming your generator supports this
        )
        if not generated_question:
            generated_question = prompts.get('default_ocr_question', "What does the handwritten text in this image say?")

        # 2. Format the initial prompt using a template (similar to query_prompt_init)
        # Expects a key like 'handwriting_qna_prompt_template' in handwriting_prompts.yaml
        # Example: "Based on the image, please answer: {question}"
        qna_prompt_template_str = prompts.get('query_prompt_init', "Please answer the following question about the image: {question}") # Default uses named
        
        # Make formatting robust: use named if {question} is present, else assume positional for backward compatibility or simpler templates
        if "{question}" in qna_prompt_template_str:
            initial_prompt_content = qna_prompt_template_str.format(question=generated_question)
        else:
            # Assumes the template string expects one positional argument if {question} is not found
            # This aligns with the original multimodal_QRA_pair.py if its query_prompt_init was like "Question: {}"
            initial_prompt_content = qna_prompt_template_str.format(generated_question) 
            
        query_history.append(f"Formatted Prompt: {initial_prompt_content}")

        # 3. Initial model call
        initial_model_response = gpt_instance.call(
            content=initial_prompt_content,
            image_urls=[str(image_path)], 
            additional_args={"max_tokens": prompts.get("max_tokens", 1500)} 
        )
        response_history.append(initial_model_response)

        # 4. Apply reasoning strategies
        context_data = {
            "image_urls": [str(image_path)],
            "question": generated_question, # The core question asked
            "current_response": initial_model_response 
        }
        
        strategy_result = reasoning_strategies.apply_all_strategies(
            initial_model_response, # The text to refine (model's initial answer)
            context_data=context_data,
            max_strategies=prompts.get('max_search_attempts', 3) 
        )
        
        final_answer_text = strategy_result["final_result"]
        query_history.extend([f"Applied strategy: {s}" for s in strategy_result["strategies_used"]])
        # Assuming strategy_result["reasoning_trace"] contains only the steps taken by the strategies,
        # not the initial_model_response that was passed to them.
        # initial_model_response is already in response_history.
        response_history.extend(strategy_result["reasoning_trace"])

        # 5. Synthesize Natural Reasoning (New Step)
        natural_reasoning_text = synthesize_natural_reasoning(
            gpt_instance=gpt_instance, 
            reasoning_history=response_history, # Use the full response history
            question=generated_question,
            prompts=prompts # Pass the prompts dictionary for template lookup
        )

        # 6. Generate final response using final_response_prompt (matching multimodal_simply.py pattern)
        final_response_prompt_template = prompts.get('final_response_prompt', 
            "Based on the internal thinking: {}\n\nFor the question: {}\n\nProvide a final response.")
        
        # Use positional formatting to match the YAML template
        final_response_query = final_response_prompt_template.format(natural_reasoning_text, generated_question)
        query_history.append(final_response_query)
        
        final_response = gpt_instance.text_only_call(
            content=final_response_query,
            additional_args={"max_tokens": prompts.get("final_response_max_tokens", 1000)}
        )
        response_history.append(final_response)

        # 7. Extract final conclusion (the answer) from the final response
        # The final_response should be the most refined version, similar to multimodal_simply.py
        extracted_answer = extract_final_conclusion(final_response, content_type="ocr") 

        # Note: 'Correct' field like in multimodal_QRA_pair.py is omitted 
        # because ground_truth_answer for a generated question is not available from XML.
        return {
            "process_id": process_id, # Added for consistency
            "image_id": image_id,
            "image_path": str(image_path),
            "xml_path": str(xml_path),
            "Question": generated_question, # The question posed to the model
            "Ground_True_Answer": ground_truth_transcription, # Full transcription from XML
            "Complex_CoT": natural_reasoning_text, # Store the natural reasoning summary here
            "Response": final_response, # Final response from the model (matching multimodal_simply.py)
            "Extracted_Answer": extracted_answer, # Add extracted answer as separate field
            "Query_History": query_history,
            "Response_History": response_history, # Detailed list of model responses/reasoning steps
            "Strategies_Used": strategy_result["strategies_used"],
            "status": "success"
        }

    except Exception as e:
        import traceback
        # print(f"Error processing {Path(image_path).stem if 'image_path' in locals() else 'unknown image'}: {e}\n{traceback.format_exc()}")
        return {
            "process_id": process_id,
            "image_id": Path(image_path).stem if 'image_path' in locals() else 'unknown',
            "Question": generated_question,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "status": "error"
        }

def run_handwriting_ocr_reasoning(config_path: str = None, limit: int = None, resume: bool = True):
    """
    Main function to run the handwriting OCR Q&A pipeline.
    """
    try:
        reasoning_config_obj = ReasoningConfig(
            config_file=config_path or "handwriting_config.yaml",
            prompts_file="handwriting_prompts.yaml"
        )
        gpt_instance = MultimodalGPT(reasoning_config_obj)
        reasoning_strategies = ReasoningStrategies(reasoning_config_obj, gpt_instance)
        question_generator = OCRQuestionGenerator()

        pipeline_config = reasoning_config_obj.config 
        prompts_config = reasoning_config_obj.prompts # prompts from handwriting_prompts.yaml

        ground_truth_extractor = GroundTruthExtractor()

        images_base_dir = project_root / pipeline_config.get("images_dir", "src/data/i_am_handwriting/cropped_handwritten")
        xml_base_dir = project_root / pipeline_config.get("xml_dir", "src/data/i_am_handwriting/xml")

        if not images_base_dir.is_dir():
            print(f"Error: Image directory not found: {images_base_dir}")
            return
        if not xml_base_dir.is_dir():
            print(f"Error: XML directory not found: {xml_base_dir}")
            return

        image_files = list(images_base_dir.glob("*.png")) + list(images_base_dir.glob("*.jpg")) + list(images_base_dir.glob("*.jpeg"))
        
        data_samples = []
        for idx, img_file in enumerate(image_files):
            xml_file = xml_base_dir / (img_file.stem + ".xml")
            if xml_file.exists():
                data_samples.append({"image_path": img_file, "xml_path": xml_file, "process_id": idx})
            # else:
                # print(f"Warning: XML file not found for image {img_file.name}, skipping.")
        
        if not data_samples:
            print("No image/XML pairs found to process.")
            return

        if limit is not None and limit > 0:
            data_samples = data_samples[:limit]
        
        print(f"Found {len(data_samples)} samples to process for Q&A.")

        # Initialize progress tracking and incremental saving
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = project_root / pipeline_config.get("results_dir", "results")
        output_dir.mkdir(parents=True, exist_ok=True)
        results_file = output_dir / f"handwriting_qna_results_{timestamp}.json"
        
        # Check for recovery options if resume is enabled
        recovery_manager = RecoveryManager(output_dir)
        if resume:
            incomplete_runs = recovery_manager.find_incomplete_runs()
            if incomplete_runs:
                print("\n" + "="*60)
                print("RECOVERY OPTIONS AVAILABLE")
                print("="*60)
                suggestions = recovery_manager.suggest_recovery_options(len(data_samples))
                print(suggestions)
                
                response = input("Do you want to resume from the most recent run? (y/n): ").strip().lower()
                if response == 'y' and incomplete_runs:
                    # Use the most recent incomplete run
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
        remaining_samples = []
        for sample in data_samples:
            image_id = Path(sample["image_path"]).stem
            if not progress_tracker.is_processed(image_id):
                remaining_samples.append(sample)
        
        if not remaining_samples:
            print("All samples have already been processed!")
            print(f"Results available in: {results_file}")
            return
        
        print(f"Resuming processing: {len(remaining_samples)} remaining out of {len(data_samples)} total samples")
        
        # Create backup of existing results
        if results_file.exists():
            backup_file = result_saver.backup_results()
            if backup_file:
                print(f"Created backup: {backup_file}")

        results = []
        # Process remaining samples with progress tracking
        num_workers = pipeline_config.get("num_processes", os.cpu_count() or 1)
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_sample = {
                executor.submit(
                    process_sample_ocr, 
                    sample["image_path"], 
                    sample["xml_path"], 
                    gpt_instance, 
                    ground_truth_extractor, 
                    reasoning_strategies, 
                    prompts_config,
                    question_generator,
                    sample["process_id"]
                ): sample
                for sample in remaining_samples
            }
            
            # Process completed tasks and save incrementally
            with tqdm(total=len(remaining_samples), desc="Processing samples") as pbar:
                for future in as_completed(future_to_sample):
                    sample = future_to_sample[future]
                    try:
                        result = future.result()
                        
                        # Save result immediately
                        result_saver.append_result(result)
                        results.append(result)  # Keep for backward compatibility
                        
                        # Mark as processed
                        image_id = Path(sample["image_path"]).stem
                        progress_tracker.mark_processed(image_id)
                        
                        # Update progress bar
                        if result.get("status") == "success":
                            pbar.set_postfix({"Status": "✓", "ID": result.get("image_id", "unknown")})
                        else:
                            pbar.set_postfix({"Status": "✗", "Error": result.get("error", "unknown")[:50]})
                        
                        pbar.update(1)
                        
                    except Exception as exc:
                        print(f"Critical error in future for sample {Path(sample['image_path']).name}: {exc}")
                        # Still mark as processed to avoid reprocessing
                        image_id = Path(sample["image_path"]).stem
                        progress_tracker.mark_processed(image_id)
                        
                        error_result = {
                            "process_id": sample["process_id"],
                            "image_id": image_id, 
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
        print("PROCESSING COMPLETE")
        print("="*60)
        print(f"Total processed: {stats['processed_count']}")
        print(f"Results saved to: {results_file}")
        print(f"Progress file: {results_file.with_suffix('.progress')}")
        
        # Summary of results
        successful_count = sum(1 for r in all_results if r.get("status") == "success")
        error_count = len(all_results) - successful_count
        print(f"Successful: {successful_count}")
        print(f"Errors: {error_count}")

        # Prepare for simplified output
        simplified_results = []

        # More detailed print for first few results
        for i, res in enumerate(all_results[:min(5, len(all_results))]): 
            print(f"\n--- Result {i+1} ---")
            if res.get("status") == "success":
                print(f"  Image ID: {res['image_id']}")
                print(f"  Question: {res['Question']}")
                print(f"  Ground Truth (Transcription): {res['Ground_True_Answer'][:150]}...")
                print(f"  Model Answer: {res['Response'][:150]}...")
                # print(f"  Query History: {res.get('Query_History')}")
                # print(f"  Strategies: {res.get('Strategies_Used')}")
            else:
                print(f"  Image ID: {res.get('image_id', 'N/A')}")
                print(f"  Question: {res.get('Question', 'N/A')}")
                print(f"  Error: {res['error']}")
                if "traceback" in res: print(f"  Traceback: {res['traceback'][:300]}...")

        # Note: Results are already saved incrementally, no need to save again
        print(f"\nQ&A Results already saved incrementally to: {results_file}")

        # Generate and save simplified output
        for res in all_results:
            if res.get("status") == "success":
                simplified_item = {
                    'image_path': res.get('image_path'), # Keep image_path for reference
                    'image_id': res.get('image_id'),
                    'question': res.get('Question'),
                    'reasoning': res.get('Complex_CoT'), # This is now the natural reasoning
                    'answer': res.get('Response'),
                    'ground_truth': res.get('Ground_True_Answer'), # Full transcription
                    'strategies_used': res.get('Strategies_Used')
                }
                simplified_results.append(simplified_item)

        simplified_output_path = results_file.with_name(results_file.stem + "_simplified.json")
        with open(simplified_output_path, 'w', encoding='utf-8') as f:
            json.dump(simplified_results, f, indent=4)
        print(f"Simplified Q&A Results saved to: {simplified_output_path}")

    except FileNotFoundError as fnf_error:
        print(f"Configuration Error: {fnf_error}")
        print("Please ensure 'handwriting_config.yaml' and 'handwriting_prompts.yaml' exist in 'src/config/'.")
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred in the pipeline: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Handwriting OCR Q&A Pipeline with Progress Tracking")
    parser.add_argument(
        "--config",
        help="Path to the specific reasoning_config.yaml for handwriting (e.g., src/config/handwriting_config.yaml). If not provided, 'handwriting_config.yaml' in the default config directory will be used.",
        default=None # Default is handled by ReasoningConfig class now
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of images to process."
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh without checking for previous progress (default: resume enabled)"
    )
    
    args = parser.parse_args()
    
    run_handwriting_ocr_reasoning(
        config_path=args.config, 
        limit=args.limit, 
        resume=not args.no_resume
    )
