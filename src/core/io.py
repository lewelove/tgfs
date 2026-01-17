import os
import collections
from core import chunker

class VirtualDisk:
    """
    The abstraction layer that treats a folder of chunk files as a single block device.
    Implements an LRU cache for file handles to support unlimited chunks.
    """
    def __init__(self, drive_path, drive_name, chunk_size_mb, total_chunks, read_only=False):
        self.root = drive_path
        self.name = drive_name
        self.chunk_size = chunk_size_mb * 1024 * 1024
        self.total_chunks = total_chunks
        self.total_size = total_chunks * self.chunk_size
        self.read_only = read_only
        
        # Maps chunk_index -> {filename, handle}
        # We assume initial filenames from a scan or DB. 
        # For MVP speed, we just look for files matching the pattern on demand? 
        # No, that's too slow. We need a fast index.
        self.chunk_map = {} 
        self._scan_chunks()

        # LRU Cache for open file descriptors
        self.open_files = collections.OrderedDict() 
        self.max_open_files = 64

    def _scan_chunks(self):
        """Builds an in-memory map of index -> filename."""
        padding = chunker.get_padding(self.total_chunks)
        # Scan dir
        for f in os.listdir(self.root):
            if not f.startswith(f"{self.name}."): continue
            if not f.endswith(".img"): continue
            
            parts = f.split('.')
            if len(parts) < 4: continue
            
            try:
                idx = int(parts[1])
                self.chunk_map[idx] = f
            except ValueError:
                continue

    def _get_file_handle(self, chunk_idx):
        """Returns an open file object for the chunk, managing LRU cache."""
        if chunk_idx not in self.chunk_map:
            # Chunk file missing? Should not happen if initialized correctly.
            # In a real scenario, we might create it if it's sparse?
            # For now, raise error.
            raise IOError(f"Chunk {chunk_idx} missing on disk.")

        filename = self.chunk_map[chunk_idx]
        
        # If already open, move to end (MRU)
        if chunk_idx in self.open_files:
            self.open_files.move_to_end(chunk_idx)
            return self.open_files[chunk_idx]

        # If cache full, pop oldest (LRU)
        if len(self.open_files) >= self.max_open_files:
            old_idx, old_f = self.open_files.popitem(last=False)
            old_f.close()

        # Open new
        path = os.path.join(self.root, filename)
        mode = "rb" if self.read_only else "r+b"
        f = open(path, mode)
        self.open_files[chunk_idx] = f
        return f

    def read(self, offset, length):
        if offset + length > self.total_size:
            length = self.total_size - offset
        
        result = bytearray()
        while length > 0:
            chunk_idx = offset // self.chunk_size
            chunk_offset = offset % self.chunk_size
            to_read = min(length, self.chunk_size - chunk_offset)

            f = self._get_file_handle(chunk_idx)
            f.seek(chunk_offset)
            data = f.read(to_read)
            
            if len(data) < to_read:
                # Pad with zeros if file is shorter than expected (sparse)
                data += b'\x00' * (to_read - len(data))
            
            result.extend(data)
            length -= len(data)
            offset += len(data)
        
        return bytes(result)

    def write(self, offset, data):
        if self.read_only: raise IOError("Read-only mode")
        
        length = len(data)
        data_offset = 0
        
        while length > 0:
            chunk_idx = offset // self.chunk_size
            chunk_offset = offset % self.chunk_size
            to_write = min(length, self.chunk_size - chunk_offset)

            f = self._get_file_handle(chunk_idx)
            f.seek(chunk_offset)
            f.write(data[data_offset : data_offset + to_write])
            
            length -= to_write
            offset += to_write
            data_offset += to_write
    
    def sync(self):
        """Flushes all open handles."""
        for f in self.open_files.values():
            os.fsync(f.fileno())

    def close(self):
        for f in self.open_files.values():
            f.close()
        self.open_files.clear()
