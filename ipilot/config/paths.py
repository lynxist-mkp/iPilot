from pathlib import Path

def get_data_dir() -> Path:
    """Get the path to the data directory."""
    return Path("~/.ipilot").expanduser()

def get_config_path() -> Path:
    return get_data_dir() / "config.json"
