import os
import xxhash
from utils import shell

def get_hash(path):
    output = shell.run(["xxhsum", "-H64", path]) 
    return output.split()[0]

def get_padding(total_chunks):
    """Calculates padding based on total chunks, minimum 3 digits."""
    return max(3, len(str(int(total_chunks) - 1)))

def format_name(drive_name, index, h, padding):
    """Formats name using decimal index with dynamic padding (e.g., drive.001.hash.img)."""
    idx_str = str(index).zfill(padding)
    return f"{drive_name}.{idx_str}.{h}.img"

def create_initial_chunks(drive_path, drive_name, total_chunks, chunk_size_mb):
    chunks = []
    padding = get_padding(total_chunks)
    
    for i in range(total_chunks):
        # Create temp file
        temp_name = f"{drive_name}.{str(i).zfill(padding)}.tmp"
        path = os.path.join(drive_path, temp_name)
        
        # Allocate space
        shell.run(["fallocate", "-l", f"{chunk_size_mb}M", path])
        
        # Hash and rename
        h = get_hash(path)
        final_name = format_name(drive_name, i, h, padding)
        os.rename(path, os.path.join(drive_path, final_name))
        
        chunks.append({"index": i, "hash": h, "filename": final_name})
    return chunks
