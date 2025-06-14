import os  
import sys

# set up the project root and source directory as module paths for use globally
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(SRC_DIR))

def get_project_root():
    """
    Get the absolute path to the project root directory.
    This is typically two levels up from the current file's directory.
    """
    return PROJECT_ROOT

def get_src_dir():
    """
    Get the absolute path to the source directory.
    This is typically one level down from the project root.
    """
    return SRC_DIR

def get_image_dir(provider,dirname):
    """
    Args:
        provider (str): The name of the provider, e.g., 'salesforce_ocr'.
        dirname (str): The name of the directory containing images, e.g., 'salesforce_images'.
    Returns:
        str: The absolute path to the directory containing images.
    """
    if not provider or not dirname:
        raise ValueError("Both provider and dirname must be specified.")
    if not isinstance(provider, str) or not isinstance(dirname, str):
        raise TypeError("Both provider and dirname must be strings.")
    if not provider.isidentifier() or not dirname.isidentifier():
        raise ValueError("Both provider and dirname must be valid identifiers (no spaces or special characters).")
    if not os.path.exists(SRC_DIR):
        raise FileNotFoundError(f"Source directory does not exist: {SRC_DIR}")
    if not os.path.exists(os.path.join(SRC_DIR, "data", provider)):
        raise FileNotFoundError(f"Data directory for provider '{provider}' does not exist: {os.path.join(SRC_DIR, 'data', provider)}")
    if not os.path.exists(os.path.join(SRC_DIR, "data", provider, dirname)):
        raise FileNotFoundError(f"Image directory '{dirname}' for provider '{provider}' does not exist: {os.path.join(SRC_DIR, 'data', provider, dirname)}")

    return os.path.join(SRC_DIR, "data", provider, dirname)