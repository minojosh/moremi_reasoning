"""
Radiology Report Generation with Multi-Step Reasoning
Leverages existing reasoning engine for diagnostic report generation.
"""

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
sys.path.append(str(project_root / "src"))

from core.reasoning_engine import (
    ReasoningConfig,
    MultimodalGPT,
    ReasoningStrategies,
    synthesize_natural_reasoning,
)
from providers.radiopedia.radiology_question_generator import RadiologyQuestionGenerator
from providers.i_am_handwriting.iam_utils import (
    ProgressTracker,
    IncrementalResultSaver,
    RecoveryManager,
)
from providers.radiopedia.dynamic_ground_truth_generator import (
    DynamicGroundTruthGenerator,
)

load_dotenv(project_root / ".env")


def process_radiology_case(
    case_data: dict,
    gpt_instance: MultimodalGPT,
    reasoning_strategies: ReasoningStrategies,
    prompts: dict,
    report_formats: dict,
    question_generator: RadiologyQuestionGenerator,
    process_id: int = 0,
):
    """
    Process a single radiology case for report generation.

    Args:
        case_data: Dictionary containing case information from Radiopaedia
        gpt_instance: MultimodalGPT instance for reasoning
        reasoning_strategies: ReasoningStrategies instance
        prompts: Prompts configuration
        report_formats: Report format templates from reports_prompts.json
        question_generator: RadiologyQuestionGenerator instance for generating diverse questions
        process_id: Process identifier for tracking

    Returns:
        Dictionary with processing results following consistent key naming
    """
    try:
        query_history = []
        response_history = []
        # Generate text-based ground truth using the updated generator
        gt_generator = DynamicGroundTruthGenerator()
        ground_truth_text = gt_generator.generate_ground_truth(case_data)

        # Extract case information
        modality = case_data.get("modalities", ["unknown"])[0].lower()
        patient_age = case_data.get("patient_age", "Unknown")
        patient_gender = case_data.get("patient_gender", "Unknown")
        presentation = case_data.get("presentation", "No clinical information provided")
        case_discussion = case_data.get("case_discussion", "")
        case_url = case_data.get("case_url", "")
        caption = case_data.get("caption", "")

        # Get image URLs from the structured format
        image_urls = []
        images_data = case_data.get("images", {})
        if isinstance(images_data, dict) and "series" in images_data:
            for series in images_data["series"]:
                urls = series.get("urls", [])
                image_urls.extend(urls)

        if not image_urls:
            return {
                "process_id": process_id,
                "case_url": case_url,
                "error": "No valid images found in case data",
                "status": "error",
            }

        # Get report format for this modality
        modality_key = modality.replace("-", " ").replace("_", " ")
        report_format = report_formats.get(
            modality_key, report_formats.get("chest x-ray", {})
        )

        # Generate diverse clinical question using the question generator
        generated_question = question_generator.generate_question(case_data)

        # Build comprehensive clinical question with report structure guidance
        if report_format.get("structure"):
            structure_guidance = f"\n\nStructure your report according to this format: {report_format['structure']}"
        else:
            structure_guidance = ""

        question = f"""{generated_question}

Patient Information:
- Age: {patient_age}
- Gender: {patient_gender}
- Clinical Presentation: {presentation}

Follow the structured reporting format for {modality} studies and provide detailed analysis of all visible structures and any pathological findings.{structure_guidance}"""

        # 1. Initial prompt for report generation
        initial_prompt_template = prompts.get(
            "radiology_report_init", prompts.get("query_prompt_init", "{}")
        )
        if "{question}" in initial_prompt_template:
            initial_prompt_content = initial_prompt_template.format(question=question)
        else:
            initial_prompt_content = initial_prompt_template.format(question)

        query_history.append(f"Clinical Question: {question}")
        query_history.append(f"Formatted Prompt: {initial_prompt_content}")

        # 2. Initial model call for diagnostic reasoning
        initial_model_response = gpt_instance.call(
            content=initial_prompt_content,
            image_urls=image_urls,  # Limit to first 3 images to avoid token limits
            additional_args={"max_tokens": prompts.get("max_tokens", 25000)},
        )
        response_history.append(initial_model_response)

        # 3. Apply reasoning strategies for clinical verification
        context_data = {
            "image_urls": image_urls,
            "question": question,
            "ground_truth": ground_truth_text,
            "current_response": initial_model_response,
            "query_history": query_history,
            "response_history": response_history,
            "content_type": "radiology",
        }

        strategy_result = reasoning_strategies.apply_all_strategies(
            initial_model_response,
            context_data=context_data,
            max_strategies=prompts.get("max_search_attempts", 4),
        )

        final_report = strategy_result["final_result"]
        found_accurate_diagnosis = strategy_result.get("found_correct_answer", False)
        query_history.extend(
            [f"Applied strategy: {s}" for s in strategy_result["strategies_used"]]
        )
        response_history.extend(strategy_result["reasoning_trace"])

        # Update query/response history from strategy results
        query_history.extend(strategy_result.get("query_history", []))
        response_history.extend(strategy_result.get("response_history", []))

        # 4. Synthesize clinical reasoning
        natural_reasoning_text = synthesize_natural_reasoning(
            gpt_instance=gpt_instance,
            reasoning_history=response_history,
            question=question,
            prompts=prompts,
        )

        # 5. Generate structured final report
        final_report_prompt_template = prompts.get(
            "final_report_prompt",
            "Based on the clinical reasoning: {}\n\nFor the diagnostic question: {}\n\nProvide a structured radiology report.",
        )

        # Use positional arguments to avoid conflicts with JSON braces
        final_report_query = final_report_prompt_template.format(
            natural_reasoning_text, question
        )

        query_history.append(final_report_query)

        final_structured_report = gpt_instance.text_only_call(
            content=final_report_query,
            additional_args={
                "max_tokens": prompts.get("final_response_max_tokens", 20000)
            },
        )
        response_history.append(final_structured_report)

        # 7. Perform simplified validation
        validation_result = None
        if "verify_prompt" in prompts:
            try:
                # We will take the final_structured_report as the model response to compare with ground_truth
                validation_prompt = prompts["verify_prompt"].format(
                    final_structured_report, ground_truth_text
                )

                validation_response = gpt_instance.text_only_call(
                    content=validation_prompt,
                    additional_args={"max_tokens": 20000, "temperature": 0.0},
                )
                
                # The response should be "True" or "False"
                if "true" in validation_response.lower():
                    found_accurate_diagnosis = True
                
                validation_result = {"result": validation_response}


            except Exception as e:
                validation_result = {
                    "error": f"Validation failed: {str(e)}",
                    "full_traceback": traceback.format_exc(),
                }

        return {
            "process_id": process_id,
            "case_url": case_url,
            "modality": modality,
            "image_urls": image_urls,
            "Question": question,  # Using consistent key name
            "Ground_True_Answer": ground_truth_text,  # Using generated text-based ground truth
            "Complex_CoT": natural_reasoning_text,  # Using consistent key name
            "Response": final_structured_report,  # Using consistent key name
            "Found_Correct_Answer": found_accurate_diagnosis,  # Using consistent key name
            "Query_History": query_history,  # Using consistent key name
            "Response_History": response_history,  # Using consistent key name
            "Strategies_Used": strategy_result[
                "strategies_used"
            ],  # Using consistent key name
            "Validation_Result": validation_result,
            "status": "success",
        }

    except Exception as e:
        return {
            "process_id": process_id,
            "case_url": case_data.get("case_url", "unknown"),
            "modality": case_data.get("modalities", ["unknown"])[0],
            "error": str(e),
            "traceback": traceback.format_exc(),
            "status": "error",
        }


def load_modality_cases(modality: str, data_dir: Path, limit: int = None):
    """Load cases for a specific modality."""
    modality_file = data_dir / f"{modality}_only_cases.json"

    if not modality_file.exists():
        raise FileNotFoundError(f"No cases found for modality: {modality}")

    with open(modality_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if limit:
        cases = cases[:limit]

    # Add process IDs
    for idx, case in enumerate(cases):
        case["process_id"] = idx

    return cases


def load_report_formats(config_dir: Path):
    """Load report format templates."""
    reports_file = config_dir / "reports prompts.json"

    if not reports_file.exists():
        raise FileNotFoundError(f"Report formats not found: {reports_file}")

    with open(reports_file, "r", encoding="utf-8") as f:
        return json.load(f)


def run_radiopedia_report_reasoning(
    modality: str = None,
    config_path: str = None,
    limit: int = None,
    resume: bool = True,
):
    """
    Main function to run the Radiopaedia report generation pipeline.

    Args:
        modality: Specific modality to process (e.g., 'mammography', 'x-ray', 'ct')
        config_path: Path to reasoning config file
        limit: Limit number of cases to process
        resume: Whether to resume from previous progress
    """
    try:
        # Initialize reasoning components
        reasoning_config_obj = ReasoningConfig(
            config_dir=project_root / "src" / "config",
            config_file="radiopedia_config.yaml",
            prompts_file="radiopedia_prompts.yaml",
        )
        gpt_instance = MultimodalGPT(reasoning_config_obj)
        reasoning_strategies = ReasoningStrategies(reasoning_config_obj, gpt_instance)

        pipeline_config = reasoning_config_obj.config
        prompts_config = reasoning_config_obj.prompts

        # Initialize question generator
        question_generator = RadiologyQuestionGenerator()

        # Load report formats
        report_formats = load_report_formats(reasoning_config_obj.config_dir)

        # Initialize question generator for diverse questions
        question_generator = RadiologyQuestionGenerator()

        # Load modality cases
        data_dir = (
            project_root / "src" / "data" / "radiopedia" / "modality_specific_cases"
        )

        if modality:
            cases = load_modality_cases(modality, data_dir, limit)
            print(f"Processing {len(cases)} {modality} cases")
        else:
            # Process all modalities
            all_cases = []
            available_modalities = ["mammography", "x-ray", "ct", "mri", "ultrasound"]
            for mod in available_modalities:
                try:
                    mod_cases = load_modality_cases(mod, data_dir, limit)
                    all_cases.extend(mod_cases)
                except FileNotFoundError:
                    print(f"No cases found for {mod}, skipping...")
            cases = all_cases
            print(f"Processing {len(cases)} cases across all modalities")

        if not cases:
            print("No cases found to process.")
            return

        # Create output directory with correct naming convention
        output_dir = project_root / "src" / "data" / "radiopedia" / "reasoning_samples"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize progress tracking with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        modality_suffix = f"_{modality}" if modality else "_all_modalities"
        results_file = (
            output_dir
            / f"radiopedia_report_reasoning{modality_suffix}_{timestamp}.json"
        )

        # Check for recovery options if resume is enabled
        recovery_manager = RecoveryManager(output_dir)
        if resume:
            incomplete_runs = recovery_manager.find_incomplete_runs()
            if incomplete_runs:
                print("\n" + "=" * 60)
                print("RECOVERY OPTIONS AVAILABLE")
                print("=" * 60)
                suggestions = recovery_manager.suggest_recovery_options(len(cases))
                print(suggestions)

                response = (
                    input("Do you want to resume from the most recent run? (y/n): ")
                    .strip()
                    .lower()
                )
                if response == "y" and incomplete_runs:
                    latest_run = max(incomplete_runs, key=lambda x: x["last_updated"])
                    results_file = Path(latest_run["results_file"])
                    print(f"Resuming from: {results_file}")
                    print(f"Already processed: {latest_run['processed_count']} items")

        # Initialize tracking components
        progress_tracker = ProgressTracker(
            results_file=str(results_file),
            progress_file=str(results_file.with_suffix(".progress")),
        )

        result_saver = IncrementalResultSaver(str(results_file))

        # Filter out already processed samples
        remaining_cases = []
        for case in cases:
            item_id = case.get("process_id", "unknown")
            if not progress_tracker.is_processed(str(item_id)):
                remaining_cases.append(case)

        if not remaining_cases:
            print("All cases have already been processed!")
            print(f"Results available in: {results_file}")
            return

        print(
            f"Resuming processing: {len(remaining_cases)} remaining out of {len(cases)} total cases"
        )

        # Create backup of existing results
        if results_file.exists():
            backup_file = result_saver.backup_results()
            if backup_file:
                print(f"Created backup: {backup_file}")

        results = []
        num_workers = pipeline_config.get("num_processes", os.cpu_count() or 1)

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_case = {
                executor.submit(
                    process_radiology_case,
                    case,
                    gpt_instance,
                    reasoning_strategies,
                    prompts_config,
                    report_formats,
                    question_generator,
                    case.get("process_id", idx),
                ): case
                for idx, case in enumerate(remaining_cases)
            }

            # Process completed tasks and save incrementally
            with tqdm(
                total=len(remaining_cases), desc="Processing radiology cases"
            ) as pbar:
                for future in as_completed(future_to_case):
                    case = future_to_case[future]
                    try:
                        result = future.result()

                        # Save result immediately
                        result_saver.append_result(result)
                        results.append(result)

                        # Mark as processed
                        item_id = str(case.get("process_id", "unknown"))
                        progress_tracker.mark_processed(item_id)

                        # Update progress bar
                        if result.get("status") == "success":
                            pbar.set_postfix(
                                {
                                    "Status": "✓",
                                    "Modality": result.get("modality", "unknown"),
                                }
                            )
                        else:
                            pbar.set_postfix(
                                {
                                    "Status": "✗",
                                    "Error": result.get("error", "unknown")[:50],
                                }
                            )

                        pbar.update(1)

                    except Exception as exc:
                        print(
                            f"Critical error in future for case {case.get('process_id', 'unknown')}: {exc}"
                        )
                        item_id = str(case.get("process_id", "unknown"))
                        progress_tracker.mark_processed(item_id)

                        error_result = {
                            "process_id": case.get("process_id", "unknown"),
                            "error": str(exc),
                            "status": "error_in_future",
                        }
                        result_saver.append_result(error_result)
                        results.append(error_result)
                        pbar.update(1)

        # Final statistics
        stats = progress_tracker.get_stats()
        all_results = result_saver.get_existing_results()

        print("\n" + "=" * 60)
        print("RADIOPEDIA REPORT REASONING COMPLETE")
        print("=" * 60)
        if modality:
            print(f"Modality processed: {modality}")
        print(f"Total processed: {stats['processed_count']}")
        print(f"Results saved to: {results_file}")

        # Summary of results
        successful_count = sum(1 for r in all_results if r.get("status") == "success")
        error_count = len(all_results) - successful_count
        print(f"Successful: {successful_count}")
        print(f"Errors: {error_count}")

        # Show sample results
        for i, res in enumerate(all_results[: min(3, len(all_results))]):
            print(f"\n--- Result {i+1} ---")
            if res.get("status") == "success":
                print(f"  Case URL: {res.get('case_url', 'N/A')}")
                print(f"  Modality: {res.get('modality', 'N/A')}")
                print(f"  Question: {res.get('Question', 'N/A')[:100]}...")
                print(
                    f"  Presentation: {res.get('patient_info', {}).get('presentation', 'N/A')[:100]}..."
                )
                print(f"  Diagnostic Report: {res.get('Response', 'N/A')[:100]}...")
                print(f"  Strategies: {res.get('Strategies_Used')}")
            else:
                print(f"  Case URL: {res.get('case_url', 'N/A')}")
                print(f"  Error: {res['error']}")

        # Generate simplified output with consistent structure
        simplified_results = []
        for res in all_results:
            if res.get("status") == "success":
                simplified_item = {
                    "process_id": res.get("process_id"),
                    "case_url": res.get("case_url"),
                    "modality": res.get("modality"),
                    "image_urls": res.get("image_urls"),
                    "question": res.get("Question"),  # Using consistent key names
                    "reasoning": res.get("Complex_CoT"),  # Using consistent key names
                    "answer": res.get("Response"),  # Using consistent key names
                    "ground_truth": res.get(
                        "Ground_True_Answer"
                    ),  # Using consistent key names
                    # "extracted_answer": res.get(
                    #     "Extracted_Answer"
                    # ),  # Using consistent key names
                    "found_correct_answer": res.get(
                        "Found_Correct_Answer"
                    ),  # Using consistent key names
                    "strategies_used": res.get(
                        "Strategies_Used"
                    ),  # Using consistent key names
                    # "patient_presentation": res.get("patient_info", {}).get(
                    #     "presentation"
                    # ),
                }
                simplified_results.append(simplified_item)

        simplified_output_path = results_file.with_name(
            results_file.stem + "_simplified.json"
        )
        with open(simplified_output_path, "w", encoding="utf-8") as f:
            json.dump(simplified_results, f, indent=4)
        print(f"Simplified results saved to: {simplified_output_path}")

    except FileNotFoundError as fnf_error:
        print(f"Configuration Error: {fnf_error}")
        print("Please ensure configuration files exist and modality data is available.")
    except Exception as e:
        print(f"An unexpected error occurred in the pipeline: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Radiopaedia Report Generation Reasoning Pipeline"
    )
    parser.add_argument(
        "--modality",
        choices=["mammography", "x-ray", "ct", "mri", "ultrasound"],
        help="Specific modality to process (if not provided, processes all modalities)",
    )
    parser.add_argument(
        "--config", help="Path to the reasoning config file", default=None
    )
    parser.add_argument(
        "--limit", type=int, help="Limit the number of cases to process"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh without checking for previous progress",
    )

    args = parser.parse_args()

    run_radiopedia_report_reasoning(
        modality=args.modality,
        config_path=args.config,
        limit=args.limit,
        resume=not args.no_resume,
    )
