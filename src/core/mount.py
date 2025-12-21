import os
from utils import shell

def mount_vdev(vdev_path, mount_root, drive_name, fs_type):
    target = os.path.join(mount_root, drive_name)
    os.makedirs(target, exist_ok=True)
    
    opts = ["mount"]
    if fs_type == "btrfs":
        opts += ["-o", "compress=zstd"]
    
    opts += [vdev_path, target]
    shell.run(opts)

    # Fix permissions: 'user:' automatically finds the correct primary group
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        shell.run(["chown", f"{sudo_user}:", target])
        
    return target

def umount_vdev(mount_root, drive_name):
    target = os.path.join(mount_root, drive_name)
    if os.path.ismount(target):
        shell.run(["umount", target])
    if os.path.exists(target) and not os.listdir(target):
        os.rmdir(target)
