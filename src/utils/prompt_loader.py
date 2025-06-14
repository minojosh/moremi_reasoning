# prompt_loader.py
# Loads prompt templates from a YAML file
import yaml

def load_prompts(path: str) -> dict:
    """
    Load a set of prompt templates from a YAML file.
    Returns a dict where keys are prompt names and values are template strings.
    """
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return data
