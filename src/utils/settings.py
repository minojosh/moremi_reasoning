#!/usr/bin/env python3
"""
Simple settings loader for reasoning applications.
One file to rule them all.
"""
import yaml
from pathlib import Path
from typing import Dict, Any

class ReasoningSettings:
    """Simple, centralized settings management."""
    
    _instance = None
    _settings = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._settings is None:
            self.load_settings()
    
    def load_settings(self):
        """Load settings from reasoning_settings.yaml"""
        settings_path = self._find_settings_file()
        
        with open(settings_path, 'r') as f:
            self._settings = yaml.safe_load(f)
    
    def _find_settings_file(self) -> Path:
        """Find the reasoning_settings.yaml file"""
        possible_paths = [
            Path("src/config/reasoning_settings.yaml"),
            Path("config/reasoning_settings.yaml"),
            Path("reasoning_settings.yaml")
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        raise FileNotFoundError("reasoning_settings.yaml not found in expected locations")
    
    def get(self, key: str, default=None) -> Any:
        """Get a setting by key (supports dot notation)"""
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_config_path(self, app_name: str) -> str:
        """Get config path for a specific application"""
        config_file = self.get(f'{app_name}_config')
        if config_file:
            return f"src/config/{config_file}"
        return None
    
    def get_data_dir(self, app_name: str, data_type: str) -> str:
        """Get data directory for an application"""
        return self.get(f'data_dirs.{app_name}.{data_type}')

# Global instance
settings = ReasoningSettings()
