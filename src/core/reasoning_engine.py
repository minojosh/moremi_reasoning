"""
Reusable Reasoning Engine Module
Extracted from multimodal_QRA_pair.py for use across different applications.
"""

import os
import base64
import requests
import yaml
import re
import logging
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

class ReasoningConfig:
    """Centralized configuration management."""
    
    def __init__(self, config_dir: str = None, config_file: str = None, prompts_file: str = None):
        if config_dir is None:
            # Default to src/config directory
            script_dir = Path(__file__).parent.parent
            config_dir = script_dir / "config"
        
        self.config_dir = Path(config_dir)
        self.config_file = config_file or "salesforce_config.yaml"
        self.prompts_file = prompts_file or "salesforce_prompts.yaml"
        self._load_configs()
    
    def _load_configs(self):
        """Load all configuration files."""
        # Load reasoning config
        config_path = self.config_dir / self.config_file
        if not config_path.exists():
            raise FileNotFoundError(f"{self.config_file} not found at: {config_path}")
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load prompts
        prompts_path = self.config_dir / self.prompts_file
        if not prompts_path.exists():
            raise FileNotFoundError(f"{self.prompts_file} not found at: {prompts_path}")
        
        with open(prompts_path, 'r') as f:
            self.prompts = yaml.safe_load(f)

def encode_image(image_path, image_dir=None):
    """Encode image from local file or URL to base64"""
    try:
        # Check if it's a URL
        if image_path.startswith(('http://', 'https://')):
            response = requests.get(image_path, timeout=30)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("utf-8")
        else:
            # Handle local file
            if not os.path.isabs(image_path) and image_dir:
                image_path = os.path.join(image_dir, os.path.basename(image_path))
            
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image {image_path}: {str(e)}")
        raise

class MultimodalGPT:
    """Reusable GPT client for multimodal reasoning tasks."""
    
    def __init__(self, config: ReasoningConfig):
        self.config = config
        self.model_name = config.config["model_name"]
        self.api_url = config.config["api_url"]
        self.api_key = os.getenv("OPEN_ROUTER_API_KEY")
        
        if not self.api_key:
            raise ValueError("OPEN_ROUTER_API_KEY environment variable not set")
    
    def call(self, content, additional_args=None, image_urls=None, url=None, model=None):
        """Main API call method."""
        if additional_args is None:
            additional_args = {}
        
        client = OpenAI(
            base_url=url or self.api_url,
            api_key=self.api_key,
        )

        try:
            messages = [{
                "role": "user",
                "content": []
            }]
            
            # Add text content
            messages[0]["content"].append({"type": "text", "text": content})
            
            # Add image content
            if image_urls:
                if isinstance(image_urls, list):
                    for img_url in image_urls:
                        encoded_image = encode_image(img_url, self.config.config.get("images_dir"))
                        image_url_with_prefix = f"data:image/jpeg;base64,{encoded_image}"
                        messages[0]["content"].append({
                            "type": "image_url", 
                            "image_url": {"url": image_url_with_prefix}
                        })
                else:
                    # Single image case
                    encoded_image = encode_image(image_urls, self.config.config.get("images_dir"))
                    image_url_with_prefix = f"data:image/jpeg;base64,{encoded_image}"
                    messages[0]["content"].append({
                        "type": "image_url", 
                        "image_url": {"url": image_url_with_prefix}
                    })
            
            # Set default parameters
            api_params = {
                "model": model or self.model_name,
                "messages": messages,
                "max_tokens": additional_args.get("max_tokens", 20000),
                "temperature": additional_args.get("temperature", 1.0)
            }
            
            response = client.chat.completions.create(**api_params)
            
            response_content = response.choices[0].message.content
            if not response_content:
                raise ValueError("Empty response from API")
                
            return response_content
            
        except Exception as e:
            print(f"API Error: {str(e)}")
            raise ValueError(f"API Error: {str(e)}")

    def text_only_call(self, content, additional_args=None):
        """Text-only processing for verification tasks."""
        if additional_args is None:
            additional_args = {}
        return self.call(content, additional_args, model="google/gemini-2.0-flash-001")

    def retry_call(self, content, additional_args=None, image_urls=None, url=None, max_attempts=2):
        """Retry call with limited attempts."""
        if additional_args is None:
            additional_args = {"max_tokens": 20000}
        
        for attempt in range(max_attempts):
            try:
                return self.call(content, additional_args, image_urls, url)
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                print(f"Attempt {attempt + 1} failed: {e}. Retrying...")

def extract_final_conclusion(text, content_type="general"):
    """Extract what appears to be a final conclusion or answer from text."""
    import re
    
    if not text or not text.strip():
        return ""
    
    # Clean text first
    text = text.strip()
    
    # Handle structured reasoning format (like handwriting OCR)
    if "**'Final Conclusion'**" in text or "**Final Conclusion**" in text:
        conclusion_patterns = [
            r"\*\*'?Final Conclusion'?\*\*:?\s*(.*?)(?:\n\n\*\*'?Verification'?\*\*|\*\*'?Verification'?\*\*|$)",
            r"\*\*'?Final Conclusion'?\*\*\s*(.*?)(?:\n\n\*\*|\*\*(?!'?Final)|$)"
        ]
        
        for pattern in conclusion_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result = match.group(1).strip()
                
                # For OCR content, handle the "transcribed text follows" pattern
                if content_type.lower() == "ocr":
                    # Check if it starts with introductory text
                    intro_match = re.match(r'^The transcribed text.*?(?:is|are).*?(?:as )?follows?:\s*\n*(.*)', result, re.IGNORECASE | re.DOTALL)
                    if intro_match:
                        actual_content = intro_match.group(1).strip()
                        if actual_content:
                            return actual_content
                
                # Clean up formatting
                result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
                result = re.sub(r'\*([^*]+)\*', r'\1', result)
                if result and len(result) > 10:
                    return result
    
    # Handle OCR-specific patterns
    if content_type == "ocr":
        ocr_patterns = [
            r"(?:transcription|transcribed text|extracted text|final transcription):\s*(.*?)(?:\n\n|\Z)",
            r"(?:the text (?:in the image )?(?:reads?|says?)):\s*(.*?)(?:\n\n|\Z)",
            r"(?:handwritten text|visible text|text content):\s*(.*?)(?:\n\n|\Z)"
        ]
        
        for pattern in ocr_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result = match.group(1).strip()
                if result and len(result) > 10:
                    return result
    
    # Handle medical/diagnostic patterns
    if content_type == "medical":
        medical_patterns = [
            r"(?:final diagnosis|diagnosis:|findings?:|conclusion:)\s*(.*?)(?:\n\n|\Z)",
            r"(?:the patient.*?has|consistent with|diagnosis.*?is)\s+(.*?)(?:\.|$)",
            r"(?:therefore|thus|in conclusion),?\s*(.*?)(?:\n\n|\Z)"
        ]
        
        for pattern in medical_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result = match.group(1).strip()
                if result and len(result) > 10:
                    return result
    
    # General conclusion indicators
    general_patterns = [
        r"(?:final conclusion|in conclusion|therefore|thus|to conclude|in summary):\s*(.*?)(?:\n\n|\Z)",
        r"(?:the answer is|my answer is|i conclude that):\s*(.*?)(?:\n\n|\Z)",
        r"(?:so|therefore|thus),?\s+(.+?)(?:\.|$)"
    ]
    
    for pattern in general_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            result = match.group(1).strip()
            if result and len(result) > 10:
                return result
    
    # Look for quoted content (common in structured responses)
    quote_pattern = r'"([^"]+)"'
    quotes = re.findall(quote_pattern, text)
    if quotes:
        longest_quote = max(quotes, key=len)
        if len(longest_quote) > 20:
            return longest_quote
    
    # Smart paragraph extraction - prefer substantive content
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    if paragraphs:
        # Filter out meta-commentary and reasoning steps
        content_paragraphs = []
        for p in paragraphs:
            lower_p = p.lower()
            # Skip reasoning metadata
            if not any(meta in lower_p for meta in [
                'inner thinking', 'verification', 'let me', 'okay', 'now', 
                'wait', 'hmm', 'alright', 'putting it all together'
            ]):
                content_paragraphs.append(p)
        
        if content_paragraphs:
            # Return the longest substantive paragraph
            return max(content_paragraphs, key=len)
        else:
            # Fallback to last paragraph if all contain reasoning language
            return paragraphs[-1]
    
    # Ultimate fallback
    return text[-200:].strip() if len(text) > 200 else text

def check_answer_accuracy(response, reference, gpt_instance, query_history=None, response_history=None, content_type="general"):
    """Check if a response is correct without requiring specific formatting."""
    if query_history is None:
        query_history = []
    if response_history is None:
        response_history = []
    
    # Extract the actual content to compare
    extracted_response = extract_final_conclusion(response, content_type)
    
    verify_prompt = gpt_instance.config.prompts.get('verify_prompt', 
        'Compare the following response with the reference answer. Answer "True" if they match, "False" otherwise.\n\nResponse: {}\nReference: {}')
    
    query = verify_prompt.format(extracted_response, reference)
    query_history.append(query)
    
    verification = gpt_instance.text_only_call(query)
    response_history.append(verification)
    print("verification: ", verification)
    
    return 'true' in verification.lower()

class ReasoningStrategies:
    """Reusable reasoning strategies for different applications."""
    
    def __init__(self, config: ReasoningConfig, gpt_instance: MultimodalGPT = None):
        self.config = config
        self.gpt = gpt_instance
        self.strategies = self._load_strategies()
    
    def _load_strategies(self):
        """Load search strategies from prompts."""
        prompts = self.config.prompts
        return [
            ('Backtracking', prompts.get('gen_prompt_rethink_Backtracking', '')),
            ('Exploring New Paths', prompts.get('gen_prompt_rethink_Exploring_New_Path', '')),
            ('Verification', prompts.get('gen_prompt_rethink_Verification', '')),
            ('Correction', prompts.get('gen_prompt_rethink_Correction', ''))
        ]
    
    def apply_strategy(self, strategy_name, strategy_prompt, current_result, context_data=None):
        """Apply a specific reasoning strategy."""
        if not strategy_prompt:
            return current_result
        
        # Format the prompt based on context
        if context_data:
            # Strategy prompts expect two positional arguments: question and previous reasoning
            question = context_data.get('question', 'Please improve this transcription')
            previous_reasoning = current_result if isinstance(current_result, str) else str(current_result)
            formatted_prompt = strategy_prompt.format(question, previous_reasoning)
        else:
            formatted_prompt = strategy_prompt
        
        try:
            # Apply strategy with multimodal context if available
            image_urls = context_data.get('image_urls') if context_data else None
            strategy_response = self.gpt.call(
                content=formatted_prompt,
                image_urls=image_urls,
                additional_args={"max_tokens": 1000, "temperature": 0.7}
            )
            
            # Extract improved result
            improved_result = extract_final_conclusion(strategy_response)
            
            return {
                "result": improved_result,
                "strategy_used": strategy_name,
                "reasoning": strategy_response
            }
        except Exception as e:
            print(f"Strategy {strategy_name} failed: {e}")
            return current_result
    
    def apply_all_strategies(self, initial_result, context_data=None, max_strategies=3):
        """Apply multiple reasoning strategies sequentially."""
        current_result = initial_result
        strategies_used = []
        reasoning_trace = []
        
        for strategy_name, strategy_prompt in self.strategies[:max_strategies]:
            if not strategy_prompt:
                continue
                
            improved = self.apply_strategy(strategy_name, strategy_prompt, current_result, context_data)
            
            if improved != current_result:
                current_result = improved["result"]
                strategies_used.append(strategy_name)
                reasoning_trace.append(improved["reasoning"])
        
        return {
            "final_result": current_result,
            "strategies_used": strategies_used,
            "reasoning_trace": reasoning_trace
        }

def synthesize_natural_reasoning(gpt_instance: MultimodalGPT, reasoning_history: list[str], question: str, prompts: dict) -> str:
    """
    Converts a list of reasoning steps (response_history) into a natural language summary.
    """
    if not reasoning_history:
        return "No reasoning steps provided."

    natural_reasoning_prompt_template = prompts.get(
        'natural_reasoning_prompt', 
        "Based on the following reasoning steps: {reasoning_steps}\\n\\nAnd the original question: {question}\\n\\nPlease synthesize a coherent, natural language explanation of the thought process."
    )
    
    # Join the history into a single string for the prompt
    formatted_reasoning_steps = "\\n---\\n".join(reasoning_history)
    
    # Check if template uses positional placeholders (like in handwriting_prompts.yaml) or named placeholders
    if "{reasoning_steps}" in natural_reasoning_prompt_template and "{question}" in natural_reasoning_prompt_template:
        # Named placeholders
        prompt_content = natural_reasoning_prompt_template.format(
            reasoning_steps=formatted_reasoning_steps,
            question=question
        )
    else:
        # Positional placeholders - match the order used in multimodal_simply.py
        # The YAML template expects: reasoning_steps first, then question
        prompt_content = natural_reasoning_prompt_template.format(
            formatted_reasoning_steps,
            question
        )
    
    try:
        natural_response = gpt_instance.text_only_call(
            content=prompt_content,
            additional_args={"max_tokens": prompts.get("natural_reasoning_max_tokens", 1000)}
        )
        return natural_response
    except Exception as e:
        print(f"Error during natural reasoning synthesis: {e}")
        return f"Could not synthesize natural reasoning. Raw history: {formatted_reasoning_steps}"

def synthesize_final_response(natural_reasoning: str, question: str, gpt_instance) -> str:
    """
    Generate final response from natural reasoning and question.
    Uses the final_response_prompt template with positional formatting.
    """
    try:
        # Load prompts configuration
        prompts_path = Path(__file__).parent.parent / "config" / "handwriting_prompts.yaml"
        with open(prompts_path, 'r', encoding='utf-8') as file:
            prompts = yaml.safe_load(file)
        
        # Get the final response prompt template
        final_response_template = prompts.get('final_response_prompt', '')
        if not final_response_template:
            raise ValueError("final_response_prompt not found in handwriting_prompts.yaml")
        
        # Format the prompt with positional arguments (natural_reasoning, question)
        formatted_prompt = final_response_template.format(natural_reasoning, question)
        
        # Generate final response using text-only call
        final_response = gpt_instance.text_only_call(formatted_prompt)
        
        return final_response
        
    except Exception as e:
        logger.error(f"Error in synthesize_final_response: {str(e)}")
        raise
