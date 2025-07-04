#!/usr/bin/env python3
"""
Unified Radiopedia Pipeline
A command-line tool for scraping and processing Radiopaedia case data.
"""

import sys
import argparse
import multiprocessing as mp
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.utils.config_loader import get_all_modalities, load_radiopedia_config
from src.utils.path_config import create_timestamped_run_path, get_latest_run_path
from src.utils.logger import setup_logger
from src.providers.radiopedia.url_scraper import RadiopaediaURLScraper
from src.providers.radiopedia.case_scraper import RadiopaediaCaseScraper
from src.utils.preprocess_radiopedia_data import RadiopaediaDataProcessor

logger = setup_logger('radiopedia_pipeline')


def scrape_urls_step(modality: str, limit: int, run_path: Path) -> int:
    """Scrape URLs for a specific modality."""
    logger.info(f"Starting URL scraping for {modality} (limit: {limit})")
    scraper = RadiopaediaURLScraper(run_path)
    urls = scraper.scrape_modality_urls(modality, limit)
    return len(urls)


def scrape_cases_step(modality: str, limit: int, run_path: Path) -> int:
    """Scrape case data for a specific modality."""
    logger.info(f"Starting case scraping for {modality} (limit: {limit})")
    scraper = RadiopaediaCaseScraper(run_path)
    total_cases = scraper.scrape_modality_cases(modality, limit)
    return total_cases


def process_data_step(modality: str, run_path: Path) -> dict:
    """Process and filter case data for a specific modality."""
    logger.info(f"Starting data processing for {modality}")
    processor = RadiopaediaDataProcessor(run_path)
    result = processor.process_modality(modality)
    return result


def run_single_modality(modality: str, limit: int, steps: list, run_path: Path) -> dict:
    """Run the complete pipeline for a single modality."""
    results = {"modality": modality, "run_path": str(run_path)}
    
    try:
        if "scrape-urls" in steps:
            url_count = scrape_urls_step(modality, limit, run_path)
            results["urls_scraped"] = url_count
        
        if "scrape-cases" in steps:
            case_count = scrape_cases_step(modality, limit, run_path)
            results["cases_scraped"] = case_count
        
        if "process-data" in steps:
            process_result = process_data_step(modality, run_path)
            results.update(process_result)
        
        logger.info(f"Completed pipeline for {modality}: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error processing {modality}: {str(e)}")
        results["error"] = str(e)
        return results


def run_parallel_modalities(modalities: list, limit: int, steps: list) -> list:
    """Run the pipeline for multiple modalities in parallel."""
    logger.info(f"Starting parallel processing for modalities: {modalities}")
    
    # Create separate timestamped runs for each modality when running in parallel
    results = []
    with mp.Pool(processes=min(len(modalities), mp.cpu_count())) as pool:
        futures = []
        for modality in modalities:
            run_path = create_timestamped_run_path()
            futures.append(pool.apply_async(run_single_modality, (modality, limit, steps, run_path)))
        
        for future in futures:
            results.append(future.get())
    
    return results


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Radiopedia Pipeline for scraping and processing medical case data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s mammography                           # Process mammography with default settings (all steps)
  %(prog)s mammography --limit 100               # Process 100 mammography cases
  %(prog)s all --limit 50                        # Process all modalities with 50 cases each
  %(prog)s ct --steps scrape-urls                # Only scrape URLs for CT
  %(prog)s mammography --steps scrape-urls scrape-cases  # Only scrape URLs and cases (skip processing)
        """
    )
    
    parser.add_argument(
        'modality',
        help='Medical modality to process (e.g., mammography, ct, x-ray) or "all" for all modalities'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum number of cases to process (default: 50)'
    )
    
    parser.add_argument(
        '--steps',
        nargs='+',
        choices=['scrape-urls', 'scrape-cases', 'process-data'],
        default=['scrape-urls', 'scrape-cases', 'process-data'],
        help='Pipeline steps to execute (default: all steps)'
    )
    
    args = parser.parse_args()
    
    # Validate modality
    available_modalities = get_all_modalities()
    
    if args.modality == "all":
        modalities = available_modalities
        logger.info(f"Processing all modalities: {modalities}")
        
        if len(modalities) > 1:
            # Run in parallel with separate timestamped directories
            results = run_parallel_modalities(modalities, args.limit, args.steps)
        else:
            # Single modality with timestamped directory
            run_path = create_timestamped_run_path()
            logger.info(f"Created run directory: {run_path}")
            results = [run_single_modality(modalities[0], args.limit, args.steps, run_path)]
    
    elif args.modality in available_modalities:
        modalities = [args.modality]
        
        # Create new run directory for URL scraping or reuse latest for case-only scraping
        if 'scrape-urls' in args.steps:
            run_path = create_timestamped_run_path()
            logger.info(f"Created run directory: {run_path}")
        else:
            # For case scraping only, try to use the latest run directory
            try:
                run_path = get_latest_run_path()
                logger.info(f"Using latest run directory: {run_path}")
            except FileNotFoundError:
                logger.error("No existing run directory found. Please run URL scraping first.")
                sys.exit(1)
        
        logger.info(f"Processing single modality: {args.modality}")
        results = [run_single_modality(args.modality, args.limit, args.steps, run_path)]
    
    else:
        logger.error(f"Invalid modality: {args.modality}")
        logger.error(f"Available modalities: {available_modalities}")
        sys.exit(1)
    
    # Print summary
    print("\n" + "="*60)
    print("PIPELINE SUMMARY")
    print("="*60)
    
    for result in results:
        modality = result.get("modality", "Unknown")
        run_path = result.get("run_path", "Unknown")
        print(f"\nModality: {modality}")
        print(f"  📁 Run directory: {run_path}")
        
        if "error" in result:
            print(f"  ❌ Error: {result['error']}")
        else:
            if "urls_scraped" in result:
                print(f"  📋 URLs scraped: {result['urls_scraped']}")
            if "cases_scraped" in result:
                print(f"  🔍 Cases scraped: {result['cases_scraped']}")
            if "processed" in result:
                print(f"  📊 Cases processed: {result['processed']}")
            if "filtered" in result:
                print(f"  ✅ Cases filtered: {result['filtered']}")
            if "failed" in result:
                print(f"  ❌ Cases failed: {result['failed']}")
    
    print("\n" + "="*60)
    logger.info("Pipeline execution completed")


if __name__ == "__main__":
    main()
