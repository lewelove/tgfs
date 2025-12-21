import os
from config_loader import get_config
from core import mapper

conf = get_config()

def get_drive_path(name: str):
    return os.path.join(conf['paths']['storage_root'], name)

def exists_on_disk(name: str) -> bool:
    return os.path.exists(get_drive_path(name))

def is_active_in_kernel(name: str) -> bool:
    prefix = conf['paths']['mapper_prefix']
    return mapper.is_mapped(name, prefix)

def require_drive_exists(name: str):
    """Raises error if drive does not exist on disk."""
    if not exists_on_disk(name):
        raise FileNotFoundError(f"Drive folder '{name}' not found at {get_drive_path(name)}.")

def require_drive_not_active(name: str):
    """Raises error if drive is currently mapped."""
    if is_active_in_kernel(name):
        raise RuntimeError(f"Drive '{name}' is currently active in the kernel.")
