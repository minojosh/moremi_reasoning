# pipeline.py
"""
Main entrypoint for QRA report generation pipeline
"""
import argparse
import logging
import yaml
import os
from utils.utils import load_json, save_json
from utils.prompt_loader import load_prompts
from utils.openai_client import OpenAIClient
from utils.dataset import MedPixDataset

def main():
    # Initialize logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    # Load config and prompts
    config = yaml.safe_loDad(open("config.yaml"))
    prompts = load_prompts("src/prompts.yaml")
    # Command-line overrides for start index and batch size
    parser = argparse.ArgumentParser(description="QRA report generation pipeline")
    parser.add_argument("--start", type=int, default=config.get("start_index", 0), help="Starting record index to process")
    parser.add_argument("--batch", type=int, default=config.get("batch_size", 0), help="Number of records to process in this batch")
    args = parser.parse_args()
    start = args.start
    batch_size = args.batch
    logging.info(f"Pipeline starting at index {start} with batch size {batch_size}")

    # Initialize dataset with modality definitions
    ds = MedPixDataset(
        data_path=config["data_path"],
        prompts_path=config.get("reports_prompts_path")
    )
    # Get next stratified batch
    batch = ds.get_stratified_batch(start=start, size=batch_size)
    if not batch:
        logging.info("No records to process. Exiting.")
        return

    client = OpenAIClient(api_url=config["api_url"], model_name=config["model_name"])
    results = []

    for rec in batch:
        modality = rec.get("modality", "unknown")
        rec_id = rec.get("id", "N/A")
        logging.info(f"Processing record id={rec_id}, modality={modality}")
        q = f"Generate a report for modality {modality}: {rec.get('report_text', '')}"
        prompt = prompts.get("query_prompt_init", "").format(q)
        response = client.send(prompt, image_urls=rec.get("img_urls"))
        results.append({"id": rec_id, "modality": modality, "response": response})

    # Save results and update start index
    # Save results and update start index in config
    output_file = f"outputs/batch_{start}.json"
    save_json(results, output_file)
    logging.info(f"Saved results to {output_file}")
    new_index = start + len(batch)
    config["start_index"] = new_index
    yaml.safe_dump(config, open("config.yaml", "w"))
    logging.info(f"Updated config start_index to {new_index}")

if __name__ == "__main__":
    main()
