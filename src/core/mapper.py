from utils import shell
import os
import time

def is_mapped(drive_name, prefix):
    """Checks if the device mapper node already exists."""
    dm_name = f"{prefix}-{drive_name}"
    return os.path.exists(f"/dev/mapper/{dm_name}")

def map_vdev(drive_name, chunks, storage_path, prefix):
    table = []
    current_sector = 0
    dm_name = f"{prefix}-{drive_name}"
    dm_path = f"/dev/mapper/{dm_name}"

    # We no longer auto-remove here. We assume the caller checked is_mapped().
    for c in chunks:
        path = os.path.join(storage_path, c['filename'])
        if not os.path.exists(path):
            raise FileNotFoundError(f"Chunk file missing: {path}")
            
        loop_dev = shell.run(["losetup", "-f", "--show", path])
        size = int(shell.run(["blockdev", "--getsz", loop_dev]))
        table.append(f"{current_sector} {size} linear {loop_dev} 0")
        current_sector += size

    shell.run(["dmsetup", "create", dm_name], input_str="\n".join(table))
    shell.run(["udevadm", "settle"])
    
    return dm_path

def unmap_vdev(drive_name, prefix):
    dm_name = f"{prefix}-{drive_name}"
    dm_path = f"/dev/mapper/{dm_name}"
    
    if os.path.exists(dm_path):
        shell.run(["udevadm", "settle"])
        for i in range(5):
            try:
                shell.run(["dmsetup", "remove", dm_name])
                break
            except Exception:
                if i == 4: raise
                time.sleep(1)

    shell.run(["losetup", "-D"])
