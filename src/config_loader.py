import toml
import os
import pwd

def resolve_path(path):
    if path.startswith("~"):
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            home = pwd.getpwnam(sudo_user).pw_dir
        else:
            home = os.path.expanduser("~")
        return os.path.abspath(path.replace("~", home))
    
    if not os.path.isabs(path):
        raise ValueError(f"Path must be absolute or start with ~: {path}")
    return os.path.abspath(path)

def get_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.toml")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found at {config_path}")
        
    conf = toml.load(config_path)
    conf['paths']['storage_root'] = resolve_path(conf['paths']['storage_root'])
    conf['paths']['mount_root'] = resolve_path(conf['paths']['mount_root'])
    return conf
