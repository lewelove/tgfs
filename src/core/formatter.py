from utils import shell

def format_device(vdev_path, fs_type):
    if fs_type == "ext4":
        # -F forces it to format even if it's not a block device
        shell.run(["mkfs.ext4", "-F", vdev_path])
    elif fs_type == "btrfs":
        # -f forces overwrite
        # -K skips discard (faster on virtual chunks)
        shell.run(["mkfs.btrfs", "-f", "-K", "-m", "single", "-d", "single", vdev_path])
