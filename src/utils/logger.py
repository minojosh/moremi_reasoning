import logging
import os
from datetime import datetime
from pathlib import Path

def setup_logger(name='moremi_reasoning'):
    """Set up logging with timestamp and proper directory structure"""
    # Get the project root (src is where this utils folder lives)
    project_root = Path(__file__).parent.parent
    logs_dir = project_root / 'logs'
    
    # Create process-specific subdirectory
    process_logs_dir = logs_dir / name
    process_logs_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d_%Hh%Mm%Ss')
    log_filename = process_logs_dir / f'{name}_{timestamp}.log'
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File handler
    fh = logging.FileHandler(log_filename)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger