#!/usr/bin/env python3
"""
Unified entry point for running reasoning pipelines.
This script allows you to run any reasoning pipeline from the root directory.

Usage:
    python run_reasoning_pipeline.py handwriting [options]
    python run_reasoning_pipeline.py salesforce [options] 
    python run_reasoning_pipeline.py radiopedia [options]
    python run_reasoning_pipeline.py --help

Examples:
    python run_reasoning_pipeline.py handwriting --limit 50
    python run_reasoning_pipeline.py salesforce --granularity 1 --limit 100
    python run_reasoning_pipeline.py radiopedia --modality mammography --limit 10
    python run_reasoning_pipeline.py radiopedia --limit 5
    python run_reasoning_pipeline.py handwriting --no-resume
"""

import sys
import argparse
import subprocess
from pathlib import Path

# Project root setup
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

# Pipeline definitions
PIPELINES = {
    "handwriting": {
        "script": "src/providers/i_am_handwriting/handwriting_ocr_reasoning.py",
        "description": "Handwriting OCR Q&A Pipeline with Progress Tracking",
        "specific_args": []
    },
    "salesforce": {
        "script": "src/providers/salesforce_ocr/salesforce_qa_reasoning.py", 
        "description": "Salesforce OCR QA Reasoning Pipeline",
        "specific_args": [
            ("--granularity", "int", "Which granularity QA pairs to use (0=basic, 1=word locations, 5=bbox, etc.)", 1),
            ("--results-dir", "str", "Directory containing QA pairs from prepare_data.py", None)
        ]
    },
    "radiopedia": {
        "script": "src/providers/radiopedia/radiopedia_report_reasoning.py",
        "description": "Radiopedia Medical Imaging Q&A Reasoning Pipeline",
        "specific_args": [
            ("--modality", "str", "Specific modality to process (mammography, x-ray, ct, mri, ultrasound)", None)
        ]
    }
}

def create_parser():
    """Create the main argument parser with subcommands for each pipeline."""
    parser = argparse.ArgumentParser(
        description="Unified entry point for reasoning pipelines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Add pipeline subcommands
    subparsers = parser.add_subparsers(
        dest="pipeline",
        help="Available reasoning pipelines",
        metavar="PIPELINE"
    )
    
    # Common arguments that all pipelines share
    common_args = [
        ("--config", "str", "Path to the reasoning config file", None),
        ("--limit", "int", "Limit the number of items to process", None),
        ("--no-resume", "store_true", "Start fresh without checking for previous progress", False)
    ]
    
    # Create subparser for each pipeline
    for pipeline_name, pipeline_info in PIPELINES.items():
        subparser = subparsers.add_parser(
            pipeline_name,
            help=pipeline_info["description"],
            description=pipeline_info["description"]
        )
        
        # Add common arguments
        for arg_name, arg_type, arg_help, arg_default in common_args:
            if arg_type == "store_true":
                subparser.add_argument(arg_name, action="store_true", help=arg_help)
            elif arg_type == "int":
                subparser.add_argument(arg_name, type=int, help=arg_help, default=arg_default)
            else:
                subparser.add_argument(arg_name, help=arg_help, default=arg_default)
        
        # Add pipeline-specific arguments
        for arg_name, arg_type, arg_help, arg_default in pipeline_info["specific_args"]:
            if arg_type == "int":
                subparser.add_argument(arg_name, type=int, help=arg_help, default=arg_default)
            else:
                subparser.add_argument(arg_name, help=arg_help, default=arg_default)
    
    return parser

def build_command_args(pipeline_name, args):
    """Build the command arguments for the specific pipeline script."""
    cmd_args = []
    
    # Add common arguments
    if args.config:
        cmd_args.extend(["--config", args.config])
    if args.limit:
        cmd_args.extend(["--limit", str(args.limit)])
    if args.no_resume:
        cmd_args.append("--no-resume")
    
    # Add pipeline-specific arguments
    if pipeline_name == "salesforce":
        if hasattr(args, 'granularity') and args.granularity is not None:
            cmd_args.extend(["--granularity", str(args.granularity)])
        if hasattr(args, 'results_dir') and args.results_dir:
            cmd_args.extend(["--results-dir", args.results_dir])
    elif pipeline_name == "radiopedia":
        if hasattr(args, 'modality') and args.modality:
            cmd_args.extend(["--modality", args.modality])
    
    return cmd_args

def run_pipeline(pipeline_name, args):
    """Execute the specified pipeline with the given arguments."""
    if pipeline_name not in PIPELINES:
        print(f"Error: Unknown pipeline '{pipeline_name}'")
        print(f"Available pipelines: {', '.join(PIPELINES.keys())}")
        return 1
    
    pipeline_info = PIPELINES[pipeline_name]
    script_path = project_root / pipeline_info["script"]
    
    if not script_path.exists():
        print(f"Error: Pipeline script not found: {script_path}")
        return 1
    
    # Build command
    cmd = [sys.executable, str(script_path)]
    cmd.extend(build_command_args(pipeline_name, args))
    
    print("="*60)
    print(f"RUNNING {pipeline_name.upper()} REASONING PIPELINE")
    print("="*60)
    print(f"Script: {script_path}")
    print(f"Command: {' '.join(cmd)}")
    print("="*60)
    
    try:
        # Execute the pipeline script
        result = subprocess.run(cmd, cwd=project_root)
        return result.returncode
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user")
        return 130
    except Exception as e:
        print(f"Error executing pipeline: {e}")
        return 1

def main():
    """Main entry point."""
    parser = create_parser()
    
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    args = parser.parse_args()
    
    if not args.pipeline:
        print("Error: Please specify a pipeline to run")
        parser.print_help()
        return 1
    
    return run_pipeline(args.pipeline, args)

if __name__ == "__main__":
    sys.exit(main())
