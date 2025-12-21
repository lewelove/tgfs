import os
import xxhash
from utils import shell

def get_hash(path):
    h = xxhash.xxh64()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def format_name(drive_name, index, h, padding):
    """Formats name using decimal index with dynamic padding."""
    idx_str = str(index).zfill(padding)
    return f"{drive_name}.{idx_str}.{h}.img"

def create_initial_chunks(drive_path, drive_name, total_chunks, chunk_size_mb):
    chunks = []
    # Calculate padding: max of 3 or the length of the highest index string
    padding = max(3, len(str(total_chunks - 1)))
    
    for i in range(total_chunks):
        temp_name = f"{drive_name}.{str(i).zfill(padding)}.tmp"
        path = os.path.join(drive_path, temp_name)
        shell.run(["fallocate", "-l", f"{chunk_size_mb}M", path])
        
        h = get_hash(path)
        final_name = format_name(drive_name, i, h, padding)
        os.rename(path, os.path.join(drive_path, final_name))
        chunks.append({"index": i, "hash": h, "filename": final_name})
    return chunks
