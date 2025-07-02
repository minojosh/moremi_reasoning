from pathlib import Path
from datetime import datetime


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parent.parent.parent


def get_src_path() -> Path:
    """Get the path to the src directory."""
    return get_project_root() / "src"


def get_config_path() -> Path:
    """Get the path to the config directory."""
    return get_src_path() / "config"


def get_data_path() -> Path:
    """Get the path to the data directory."""
    return get_src_path() / "data"


def get_provider_data_path(provider: str) -> Path:
    """Get the path to a provider's data directory and create it if it doesn't exist."""
    path = get_data_path() / provider
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_radiopedia_data_path() -> Path:
    """Get the path to the radiopedia data directory."""
    path = get_provider_data_path("radiopedia")
    return path


def create_timestamped_run_path(provider: str = "radiopedia") -> Path:
    """Create a timestamped directory for a new pipeline run."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S")
    
    run_path = get_provider_data_path(provider) / "runs" / date_str / time_str
    run_path.mkdir(parents=True, exist_ok=True)
    
    return run_path


def get_latest_run_path(provider: str = "radiopedia") -> Path:
    """Get the most recent run directory for a provider."""
    runs_path = get_provider_data_path(provider) / "runs"
    if not runs_path.exists():
        return None
    
    # Find the latest date directory
    date_dirs = [d for d in runs_path.iterdir() if d.is_dir()]
    if not date_dirs:
        return None
    
    latest_date = max(date_dirs, key=lambda x: x.name)
    
    # Find the latest time directory within that date
    time_dirs = [d for d in latest_date.iterdir() if d.is_dir()]
    if not time_dirs:
        return None
    
    latest_time = max(time_dirs, key=lambda x: x.name)
    return latest_time
