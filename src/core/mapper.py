from utils import shell
import os
import time
import json

def get_mapping_info_path(drive_name, storage_path):
    return os.path.join(storage_path, f".{drive_name}.mapping.json")

def is_mapped(drive_name, prefix):
    dm_name = f"{prefix}-{drive_name}"
    return os.path.exists(f"/dev/mapper/{dm_name}")

def map_vdev(drive_name, chunks, storage_path, prefix):
    table = []
    current_sector = 0
    dm_name = f"{prefix}-{drive_name}"
    dm_path = f"/dev/mapper/{dm_name}"
    used_loops = []

    try:
        for c in chunks:
            path = os.path.join(storage_path, c['filename'])
            if not os.path.exists(path):
                raise FileNotFoundError(f"Chunk file missing: {path}")
            
            # --direct-io=on speeds up performance by bypassing double-caching
            loop_dev = shell.run(["losetup", "-f", "--show", "--direct-io=on", path])
            used_loops.append(loop_dev)
            
            size = int(shell.run(["blockdev", "--getsz", loop_dev]))
            table.append(f"{current_sector} {size} linear {loop_dev} 0")
            current_sector += size

        # Atomic creation of the virtual block device
        shell.run(["dmsetup", "create", dm_name], input_str="\n".join(table))
        shell.run(["udevadm", "settle"])
        
        # Save state: If the system crashes, we know exactly what to clean up
        with open(get_mapping_info_path(drive_name, storage_path), 'w') as f:
            json.dump(used_loops, f)

        return dm_path
    except Exception as e:
        # Emergency cleanup on partial failure
        for lp in used_loops:
            shell.run(["losetup", "-d", lp], check=False)
        raise e

def unmap_vdev(drive_name, prefix, storage_path):
    dm_name = f"{prefix}-{drive_name}"
    dm_path = f"/dev/mapper/{dm_name}"
    mapping_file = get_mapping_info_path(drive_name, storage_path)
    
    # 1. Remove DM device (with retry loop for kernel "busy" signals)
    if os.path.exists(dm_path):
        shell.run(["udevadm", "settle"])
        for i in range(5):
            try:
                shell.run(["dmsetup", "remove", dm_name])
                break
            except Exception:
                if i == 4: raise
                time.sleep(1)

    # 2. Detach ONLY the loop devices we specifically created for this drive
    if os.path.exists(mapping_file):
        with open(mapping_file, 'r') as f:
            used_loops = json.load(f)
        for lp in used_loops:
            try:
                shell.run(["losetup", "-d", lp])
            except:
                pass # Already detached or gone
        os.remove(mapping_file)
