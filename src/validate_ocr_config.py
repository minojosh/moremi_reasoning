"""
Configuration Validator for OCR Pipeline
Validates that all prompts and configurations are properly set for OCR tasks
"""

import yaml
import os
import json
from pathlib import Path

class OCRConfigValidator:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)
        self.config_path = self.base_path / "src/config/reasoning_config.yaml"
        self.prompts_path = self.base_path / "src/config/reasoning_prompts.yaml"
        
    def validate_config_file(self) -> dict:
        """Validate the reasoning configuration file."""
        results = {"config_file": {"status": "PASS", "issues": []}}
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check required fields
            required_fields = [
                "data_path", "model_name", "api_url", "max_search_attempts",
                "efficient_search", "num_process", "image_dir", "batch_size"
            ]
            
            for field in required_fields:
                if field not in config:
                    results["config_file"]["issues"].append(f"Missing required field: {field}")
                    results["config_file"]["status"] = "FAIL"
            
            # Check OCR-specific recommendations
            if config.get("max_search_attempts", 0) < 2:
                results["config_file"]["issues"].append("Recommend max_search_attempts >= 2 for OCR tasks")
                results["config_file"]["status"] = "WARN"
                
            if config.get("num_process", 0) > 4:
                results["config_file"]["issues"].append("High num_process may cause API rate limiting")
                results["config_file"]["status"] = "WARN"
                
            # Check model compatibility
            model_name = config.get("model_name", "")
            if "gemini" not in model_name.lower() and "gpt" not in model_name.lower():
                results["config_file"]["issues"].append("Consider using Gemini or GPT models for better OCR performance")
                results["config_file"]["status"] = "WARN"
                
        except Exception as e:
            results["config_file"]["status"] = "FAIL"
            results["config_file"]["issues"].append(f"Error reading config file: {str(e)}")
            
        return results
    
    def validate_prompts_file(self) -> dict:
        """Validate the prompts configuration file."""
        results = {"prompts_file": {"status": "PASS", "issues": []}}
        
        try:
            with open(self.prompts_path, 'r') as f:
                prompts = yaml.safe_load(f)
            
            # Check required prompts
            required_prompts = [
                "query_prompt_init", "gen_prompt_rethink_Backtracking",
                "gen_prompt_rethink_Exploring_New_Path", "gen_prompt_rethink_Verification",
                "gen_prompt_rethink_Correction", "guided_prompt", "verify_prompt",
                "natural_reasoning_prompt", "final_response_prompt"
            ]
            
            for prompt in required_prompts:
                if prompt not in prompts:
                    results["prompts_file"]["issues"].append(f"Missing required prompt: {prompt}")
                    results["prompts_file"]["status"] = "FAIL"
                elif not prompts[prompt] or prompts[prompt].strip() == "":
                    results["prompts_file"]["issues"].append(f"Empty prompt: {prompt}")
                    results["prompts_file"]["status"] = "FAIL"
            
            # Check OCR-specific content in prompts
            ocr_keywords = ["OCR", "text", "character", "extract", "transcribe", "recognition"]
            
            init_prompt = prompts.get("query_prompt_init", "")
            if not any(keyword in init_prompt for keyword in ocr_keywords):
                results["prompts_file"]["issues"].append("query_prompt_init should contain OCR-specific instructions")
                results["prompts_file"]["status"] = "WARN"
            
            # Check verification prompt has OCR guidelines
            verify_prompt = prompts.get("verify_prompt", "")
            if "character matches" not in verify_prompt and "text content" not in verify_prompt:
                results["prompts_file"]["issues"].append("verify_prompt should include OCR-specific evaluation criteria")
                results["prompts_file"]["status"] = "WARN"
                
        except Exception as e:
            results["prompts_file"]["status"] = "FAIL"
            results["prompts_file"]["issues"].append(f"Error reading prompts file: {str(e)}")
            
        return results
    
    def validate_data_structure(self) -> dict:
        """Validate the expected data structure."""
        results = {"data_structure": {"status": "PASS", "issues": []}}
        
        # Check if required directories exist
        required_dirs = ["src", "src/config", "salesforce_ocr"]
        
        for dir_path in required_dirs:
            full_path = self.base_path / dir_path
            if not full_path.exists():
                results["data_structure"]["issues"].append(f"Missing directory: {dir_path}")
                results["data_structure"]["status"] = "FAIL"
        
        # Check if OCR question generator exists
        ocr_gen_path = self.base_path / "src/ocr_question_generator.py"
        if not ocr_gen_path.exists():
            results["data_structure"]["issues"].append("Missing OCR question generator")
            results["data_structure"]["status"] = "FAIL"
            
        return results
    
    def validate_multimodal_script(self) -> dict:
        """Validate the multimodal QRA pair script compatibility."""
        results = {"multimodal_script": {"status": "PASS", "issues": []}}
        
        script_path = self.base_path / "src/multimodal_QRA_pair.py"
        
        if not script_path.exists():
            results["multimodal_script"]["status"] = "FAIL"
            results["multimodal_script"]["issues"].append("multimodal_QRA_pair.py not found")
            return results
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for OCR-compatible features
            required_features = [
                "img_urls", "encode_image", "retry_call", "check_answer_accuracy"
            ]
            
            for feature in required_features:
                if feature not in content:
                    results["multimodal_script"]["issues"].append(f"Missing feature: {feature}")
                    results["multimodal_script"]["status"] = "WARN"
            
            # Check for proper error handling
            if "except Exception" not in content:
                results["multimodal_script"]["issues"].append("Consider adding more robust error handling")
                results["multimodal_script"]["status"] = "WARN"
                
        except Exception as e:
            results["multimodal_script"]["status"] = "FAIL"
            results["multimodal_script"]["issues"].append(f"Error reading script: {str(e)}")
            
        return results
    
    def run_full_validation(self) -> dict:
        """Run complete validation of OCR pipeline configuration."""
        print("🔍 Running OCR Pipeline Configuration Validation...")
        print("=" * 60)
        
        results = {}
        
        # Run all validations
        results.update(self.validate_config_file())
        results.update(self.validate_prompts_file())
        results.update(self.validate_data_structure())
        results.update(self.validate_multimodal_script())
        
        # Generate summary
        overall_status = "PASS"
        total_issues = 0
        
        for component, data in results.items():
            status = data["status"]
            issues_count = len(data["issues"])
            total_issues += issues_count
            
            status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "❓")
            
            print(f"{status_icon} {component.replace('_', ' ').title()}: {status}")
            
            if issues_count > 0:
                for issue in data["issues"]:
                    print(f"   • {issue}")
                print()
            
            if status == "FAIL":
                overall_status = "FAIL"
            elif status == "WARN" and overall_status == "PASS":
                overall_status = "WARN"
        
        print("=" * 60)
        print(f"📊 Overall Status: {overall_status}")
        print(f"📋 Total Issues Found: {total_issues}")
        
        if overall_status == "PASS":
            print("🎉 Configuration is ready for OCR testing!")
        elif overall_status == "WARN":
            print("⚠️  Configuration has warnings but should work for testing")
        else:
            print("❌ Configuration has critical issues that need to be fixed")
        
        return {
            "overall_status": overall_status,
            "total_issues": total_issues,
            "detailed_results": results
        }
    
    def generate_recommendations(self) -> list:
        """Generate OCR-specific recommendations."""
        recommendations = [
            "🎯 Use questions that test different OCR challenges (rotated text, multiple fonts, etc.)",
            "📊 Include both simple and complex text layouts in your test data",
            "🔄 Test with different image qualities and resolutions",
            "📝 Validate character-level accuracy for critical applications",
            "🌐 Test with multilingual content if applicable",
            "⚡ Monitor API response times for batch processing",
            "💾 Keep backup copies of successful reasoning traces",
            "🔍 Review verification prompt effectiveness regularly",
        ]
        
        print("\\n🚀 OCR Testing Recommendations:")
        print("=" * 40)
        for rec in recommendations:
            print(rec)
        
        return recommendations

def main():
    """Main function to run validation."""
    validator = OCRConfigValidator()
    results = validator.run_full_validation()
    validator.generate_recommendations()
    
    return results

if __name__ == "__main__":
    main()
