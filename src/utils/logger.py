import logging
import os
from datetime import datetime

def setup_logger(name='moremi_reasoning'):
    """Set up logging with timestamp and proper directory structure"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%Hh%Mm%Ss')
    log_filename = os.path.join('moremi_reasoning/logs', f'{name}_{timestamp}.log')
    os.makedirs('moremi_reasoning/logs', exist_ok=True)
    
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