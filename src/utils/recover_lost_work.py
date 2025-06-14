#!/usr/bin/env python3
"""
Recovery script to help find and potentially recover lost handwriting OCR work.
This script looks for any partial results, logs, or temporary files that might contain your lost progress.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
import re

def find_potential_recovery_files(base_dir: Path):
    """Find any files that might contain partial results from the failed run."""
    
    recovery_candidates = []
    
    # Look in common result directories
    potential_dirs = [
        base_dir / "results",
        base_dir / "results" / "handwriting_qna",
        base_dir / "src" / "data",
        base_dir,  # Root directory
    ]
    
    patterns_to_check = [
        "*.json",  # Result files
        "*.log",   # Log files
        "*.tmp",   # Temporary files
        "*.backup",  # Backup files
        "*.progress",  # Progress files
    ]
    
    print("Searching for potential recovery files...")
    
    for directory in potential_dirs:
        if not directory.exists():
            continue
            
        print(f"\nChecking directory: {directory}")
        
        for pattern in patterns_to_check:
            files = list(directory.glob(pattern))
            for file_path in files:
                try:
                    # Check file modification time (files from today are likely candidates)
                    mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    today = datetime.now().date()
                    
                    if mod_time.date() == today:
                        file_info = {
                            "path": str(file_path),
                            "size": file_path.stat().st_size,
                            "modified": mod_time.isoformat(),
                            "type": "unknown"
                        }
                        
                        # Try to determine file type and content
                        if file_path.suffix == ".json":
                            file_info["type"] = analyze_json_file(file_path)
                        elif file_path.suffix == ".log":
                            file_info["type"] = "log_file"
                        elif file_path.suffix == ".progress":
                            file_info["type"] = "progress_file"
                        
                        recovery_candidates.append(file_info)
                        
                except Exception as e:
                    print(f"Error checking {file_path}: {e}")
    
    return recovery_candidates

def analyze_json_file(file_path: Path):
    """Analyze a JSON file to determine if it contains handwriting OCR results."""
    
    try:
        with open(file_path, 'r') as f:
            # Read first few KB to check structure
            content = f.read(5000)
            
        # Look for handwriting OCR specific patterns
        if any(keyword in content.lower() for keyword in [
            "handwriting", "ground_true_answer", "image_id", 
            "question", "ocr", "xml_path", "image_path"
        ]):
            # Try to load full JSON to count entries
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    
                if isinstance(data, list):
                    return f"handwriting_results_{len(data)}_entries"
                elif isinstance(data, dict):
                    if "processed_ids" in data:
                        return f"progress_file_{len(data.get('processed_ids', []))}_processed"
                    else:
                        return "handwriting_single_result"
            except json.JSONDecodeError:
                return "partial_json_file"
                
        return "unknown_json"
        
    except Exception as e:
        return f"error_reading_json: {e}"

def check_console_output_for_clues():
    """Check if there are any console logs or terminal history that might have clues."""
    
    print("\n" + "="*60)
    print("CHECKING FOR CONSOLE OUTPUT CLUES")
    print("="*60)
    
    # Check if there are any recent log files in logs directory
    logs_dir = Path("src/logs")
    if logs_dir.exists():
        recent_logs = []
        for log_file in logs_dir.glob("*.log"):
            mod_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mod_time.date() == datetime.now().date():
                recent_logs.append((log_file, mod_time))
        
        if recent_logs:
            print(f"Found {len(recent_logs)} log files from today:")
            for log_file, mod_time in sorted(recent_logs, key=lambda x: x[1], reverse=True):
                print(f"  - {log_file.name} (modified: {mod_time.strftime('%H:%M:%S')})")
        else:
            print("No recent log files found.")
    else:
        print("No logs directory found.")

def extract_partial_results_from_logs(log_files):
    """Try to extract any partial results from log files."""
    
    print("\n" + "="*60)
    print("ANALYZING LOG FILES FOR PARTIAL RESULTS")
    print("="*60)
    
    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            
            # Look for patterns that might indicate successful processing
            success_patterns = [
                r"Image ID: (\w+)",
                r"Question: (.+)",
                r"Ground Truth.*: (.+)",
                r"Model Answer: (.+)",
                r"Successful: (\d+)"
            ]
            
            findings = {}
            for pattern in success_patterns:
                matches = re.findall(pattern, content)
                if matches:
                    findings[pattern] = matches[:5]  # First 5 matches
            
            if findings:
                print(f"\nFindings in {log_file.name}:")
                for pattern, matches in findings.items():
                    print(f"  {pattern}: {matches}")
                    
        except Exception as e:
            print(f"Error reading {log_file}: {e}")

def main():
    """Main recovery function."""
    
    print("="*60)
    print("HANDWRITING OCR WORK RECOVERY TOOL")
    print("="*60)
    print("This tool will help you find any traces of your lost work.")
    print("Looking for files created today that might contain partial results...\n")
    
    base_dir = Path.cwd()
    
    # Find potential recovery files
    candidates = find_potential_recovery_files(base_dir)
    
    if not candidates:
        print("❌ No potential recovery files found from today.")
        print("\nThis suggests your work was completely lost.")
        print("However, you can now run the script with resume functionality:")
        print("  python src/providers/i_am_handwriting/handwriting_ocr_reasoning.py --limit 529")
        return
    
    print(f"✅ Found {len(candidates)} potential recovery files:")
    print("\n" + "="*60)
    print("POTENTIAL RECOVERY FILES")
    print("="*60)
    
    best_candidates = []
    
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. {candidate['path']}")
        print(f"   Type: {candidate['type']}")
        print(f"   Size: {candidate['size']:,} bytes")
        print(f"   Modified: {candidate['modified']}")
        
        # Identify best candidates
        if any(keyword in candidate['type'] for keyword in ['handwriting_results', 'progress_file']):
            best_candidates.append(candidate)
        
        print()
    
    if best_candidates:
        print("🎯 BEST RECOVERY CANDIDATES:")
        for candidate in best_candidates:
            print(f"  - {candidate['path']} ({candidate['type']})")
        
        print(f"\n✅ GOOD NEWS! Found {len(best_candidates)} files that likely contain your work!")
        print("\nRECOVERY OPTIONS:")
        print("1. Check these files manually to see if they contain your 104 processed results")
        print("2. Use the new resume functionality to continue from where you left off")
        print("3. The enhanced script now saves progress incrementally - this won't happen again!")
        
    else:
        print("❌ No clear recovery candidates found.")
        print("Your work appears to be lost, but the new system prevents this in the future.")
    
    # Check console/log clues
    check_console_output_for_clues()
    
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Run with enhanced progress tracking:")
    print("   python src/providers/i_am_handwriting/handwriting_ocr_reasoning.py --limit 529")
    print("2. The new system will:")
    print("   - Save each result immediately (no more losses)")
    print("   - Track progress and allow resuming")
    print("   - Create backups automatically")
    print("   - Show recovery options if interrupted")
    print("3. If you want to start completely fresh:")
    print("   python src/providers/i_am_handwriting/handwriting_ocr_reasoning.py --limit 529 --no-resume")

if __name__ == "__main__":
    main()
