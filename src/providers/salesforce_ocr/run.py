# Enhanced OCR Reasoning Pipeline Execution
import os
import sys
import json
import yaml
import subprocess
import time
import traceback
from pathlib import Path
from datetime import datetime
import io
import contextlib

# 1. Prepare the environment and configurations
print("=== Setting up Enhanced OCR Reasoning Pipeline ===")

# Get the current working directory and set up paths
project_root = Path(__file__).resolve().parent.parent.parent
print(f"Project root directory: {project_root}")
current_dir = Path.cwd()
src_dir = project_root / "src"
config_dir = src_dir / "config"
API_KEY = os.getenv("OPEN_ROUTER_API_KEY")
print(f"Current directory: {current_dir}")
print(f"Source directory: {src_dir}")
print(f"Config directory: {config_dir}")

# Create logs directory for tracking
logs_dir = current_dir / "logs"
logs_dir.mkdir(exist_ok=True)


# 2. Validate environment setup
def validate_environment():
    """Validate that all required components are available"""
    issues = []

    # Check API key
    api_key = API_KEY
    if not api_key:
        issues.append("API_KEY environment variable not set")
    elif len(api_key) < 20:
        issues.append("API_KEY appears to be too short")

    # Check configuration files
    config_file = config_dir / "reasoning_config.yaml"
    prompts_file = config_dir / "reasoning_prompts.yaml"

    if not config_file.exists():
        issues.append(f"Configuration file missing: {config_file}")
    if not prompts_file.exists():
        issues.append(f"Prompts file missing: {prompts_file}")

    # Check QA pairs file
    qa_pairs_file = current_dir / "ocr_test_samples_from_list.json"
    if not qa_pairs_file.exists():
        issues.append(f"QA pairs file missing: {qa_pairs_file}")

    # Check source files
    pipeline_script = src_dir / "multimodal_QRA_pair.py"
    if not pipeline_script.exists():
        issues.append(f"Pipeline script missing: {pipeline_script}")

    return issues


# 3. Enhanced configuration setup
def setup_pipeline_config():
    """Set up optimized configuration for OCR reasoning"""
    config_file = config_dir / "reasoning_config.yaml"

    if not config_file.exists():
        print("⚠️ Configuration file not found!")
        return False

    with open(config_file, "r") as f:
        reasoning_config = yaml.safe_load(f)

    # Backup original config
    backup_file = config_file.with_suffix(".yaml.backup")
    with open(backup_file, "w") as f:
        yaml.dump(reasoning_config, f, default_flow_style=False)

    # Update configuration for OCR processing
    updates = {
        "data_path": str(current_dir / "ocr_test_samples_from_list.json"),
        "image_dir": str(current_dir / "salesforce_images"),
        "limit_num": 10,  # Start with manageable size
        "max_search_attempts": 3,
        "efficient_search": True,
        "num_process": 1,
        "batch_size": 3,
        "save_progress": True,
        "verbose": True,
        "model_name": "google/gemini-2.0-flash-001",
    }

    for key, value in updates.items():
        reasoning_config[key] = value

    # Save updated configuration
    with open(config_file, "w") as f:
        yaml.dump(reasoning_config, f, default_flow_style=False)

    print("✓ Updated reasoning configuration:")
    for key, value in updates.items():
        print(f"  {key}: {value}")

    return True


# 4. Run validation
print("\n=== Environment Validation ===")
validation_issues = validate_environment()

if validation_issues:
    print("❌ Environment validation failed:")
    for issue in validation_issues:
        print(f"  - {issue}")
    print("\nPlease fix these issues before proceeding.")
else:
    print("✅ Environment validation passed!")

# 5. Set up configuration
if not validation_issues:
    config_success = setup_pipeline_config()
    if config_success:
        print("✓ Configuration setup complete")


# 6. Enhanced pipeline execution with monitoring
def run_ocr_reasoning_pipeline():
    """Run the OCR reasoning pipeline with enhanced monitoring"""

    if validation_issues:
        print("❌ Cannot run pipeline due to validation issues")
        return False

    print("\n🚀 Starting Enhanced OCR Reasoning Pipeline...")

    # Set up logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"ocr_reasoning_pipeline_{timestamp}.log"

    try:
        # Add src to Python path
        sys.path.insert(0, str(src_dir))

        # Change to src directory
        original_dir = os.getcwd()
        os.chdir(str(src_dir))

        # Start timing
        start_time = time.time()

        # Import and run the pipeline
        from multimodal_QRA_pair import main as run_reasoning_pipeline

        print("✓ Pipeline module imported successfully")
        print("📊 Processing OCR questions with Chain of Thought reasoning...")
        print(f"📝 Logs will be saved to: {log_file}")

        # Capture output for logging


        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            run_reasoning_pipeline()

        output = f.getvalue()

        # Save log
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"OCR Reasoning Pipeline Log - {timestamp}\n")
            log.write("=" * 50 + "\n\n")
            log.write(output)

        # Calculate execution time
        execution_time = time.time() - start_time

        print(f"\n✅ Pipeline completed successfully in {execution_time:.2f} seconds!")
        print(f"📊 Check the output files for reasoning results")

        return True

    except ImportError as e:
        error_msg = f"Failed to import pipeline module: {str(e)}"
        print(f"❌ {error_msg}")
        with open(log_file, "w") as log:
            log.write(f"ERROR: {error_msg}\n{traceback.format_exc()}")
        return False

    except Exception as e:
        error_msg = f"Pipeline execution failed: {str(e)}"
        print(f"❌ {error_msg}")
        print(f"💡 Check log file for details: {log_file}")
        with open(log_file, "w") as log:
            log.write(f"ERROR: {error_msg}\n{traceback.format_exc()}")
        return False

    finally:
        # Return to original directory
        os.chdir(original_dir)


# 7. Execute the pipeline
if not validation_issues:
    pipeline_success = run_ocr_reasoning_pipeline()

    if pipeline_success:
        # 8. Quick results check
        print("\n=== Quick Results Check ===")

        output_files = []
        for directory in [current_dir, src_dir]:
            output_files.extend(list(directory.glob("*ocr_qa_pairs*CoT_search*.json")))
            output_files.extend(list(directory.glob("simplified_*ocr_qa_pairs*.json")))

        if output_files:
            print(f"✓ Found {len(output_files)} output files:")
            for file in output_files[:3]:  # Show first 3
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list) and data:
                        successful = sum(
                            1
                            for item in data
                            if item.get("found_correct_answer", False)
                        )
                        print(
                            f"  📁 {file.name}: {len(data)} samples, {successful} successful"
                        )
                except:
                    print(f"  📁 {file.name}: Could not analyze")
        else:
            print("⚠️ No output files found - check logs for issues")

else:
    print("\n💡 To proceed manually:")
    print("1. Fix the validation issues listed above")
    print("2. Set API_KEY: export API_KEY='sk-or-v1-your-key'")
    print("3. Run: cd src && python multimodal_QRA_pair.py")

print("\n=== Pipeline Execution Summary ===")
if not validation_issues and "pipeline_success" in locals() and pipeline_success:
    print("🎉 OCR Reasoning Pipeline completed successfully!")
    print("📈 Proceed to quality assessment in the next cell")
elif validation_issues:
    print("🔧 Environment setup needed - address validation issues first")
else:
    print("⚠️ Pipeline execution encountered issues - check logs for details")

print("\n📋 Next Steps:")
print("1. Review quality assessment results")
print("2. Analyze reasoning strategies and success patterns")
print("3. Refine prompts based on performance")
print("4. Scale up to larger datasets if results are satisfactory")