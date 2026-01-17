import os
from config_loader import get_config

conf = get_config()

def get_drive_path(name: str):
    return os.path.join(conf['paths']['storage_root'], name)

def exists_on_disk(name: str) -> bool:
    return os.path.exists(get_drive_path(name))

def require_drive_exists(name: str):
    if not exists_on_disk(name):
        raise FileNotFoundError(f"Drive folder '{name}' not found.")
