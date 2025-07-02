import yaml
from pathlib import Path
from typing import Dict, Any
from .path_config import get_config_path


def load_yaml_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    config_path = get_config_path() / config_file
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_modalities_config() -> Dict[str, Any]:
    """Load modalities configuration."""
    return load_yaml_config("modalities.yaml")


def load_radiopedia_config() -> Dict[str, Any]:
    """Load radiopedia pipeline configuration."""
    return load_yaml_config("radiopedia_config.yaml")


def get_modality_keywords(modality: str) -> list:
    """Get keywords for a specific modality."""
    config = load_modalities_config()
    return config.get("modalities", {}).get(modality, {}).get("keywords", [])


def get_all_modalities() -> list:
    """Get list of all available modalities."""
    config = load_modalities_config()
    return list(config.get("modalities", {}).keys())
