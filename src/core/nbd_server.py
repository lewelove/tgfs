import socket
import struct
import os
import fcntl
import threading
import signal
import sys
import datetime
from core.io import VirtualDisk
from utils import shell

# ... (Keep constants the same) ...
NBD_SET_SOCK = 0xab00
NBD_SET_BLKSIZE = 0xab01
NBD_SET_SIZE = 0xab02
NBD_DO_IT = 0xab03
NBD_CLEAR_SOCK = 0xab04

NBD_CMD_READ = 0
NBD_CMD_WRITE = 1
NBD_CMD_DISC = 2
NBD_CMD_FLUSH = 3
NBD_CMD_TRIM = 4

NBD_REQUEST_MAGIC = 0x25609513
NBD_REPLY_MAGIC = 0x67446698

def log_debug(msg):
    """Simple file logger for debugging background process."""
    with open("/tmp/tgfs_debug.log", "a") as f:
        ts = datetime.datetime.now().isoformat()
        f.write(f"[{ts}] {msg}\n")

class NBDServer:
    def __init__(self, device_path, vdisk: VirtualDisk):
        self.device_path = device_path
        self.vdisk = vdisk
        self.sock_pair = socket.socketpair()
        self.running = False

    def _recv_exact(self, conn, size):
        data = b""
        while len(data) < size:
            chunk = conn.recv(size - len(data))
            if not chunk: 
                raise EOFError("Socket closed prematurely")
            data += chunk
        return data

    def _handle_request(self, conn):
        log_debug("Worker thread started.")
        while self.running:
            try:
                try:
                    header = self._recv_exact(conn, 28)
                except EOFError:
                    log_debug("Kernel closed connection (EOF).")
                    break

                (magic, cmd_type, handle, offset, length) = struct.unpack(">LLQQL", header)

                if magic != NBD_REQUEST_MAGIC:
                    log_debug(f"Invalid magic: {hex(magic)}")
                    break

                error = 0
                response_data = b""

                try:
                    if cmd_type == NBD_CMD_READ:
                        response_data = self.vdisk.read(offset, length)
                    
                    elif cmd_type == NBD_CMD_WRITE:
                        data = self._recv_exact(conn, length)
                        self.vdisk.write(offset, data)
                    
                    elif cmd_type == NBD_CMD_DISC:
                        log_debug("Received DISCONNECT command.")
                        self.running = False
                        return 
                    
                    elif cmd_type == NBD_CMD_FLUSH:
                        self.vdisk.sync()

                    elif cmd_type == NBD_CMD_TRIM:
                        pass 

                    else:
                        log_debug(f"Unknown command type: {cmd_type}")
                        error = 1 
                
                except Exception as e:
                    log_debug(f"CRITICAL IO ERROR processing cmd {cmd_type} at offset {offset}: {e}")
                    import traceback
                    log_debug(traceback.format_exc())
                    error = 5 # EIO

                reply = struct.pack(">LLQ", NBD_REPLY_MAGIC, error, handle)
                conn.sendall(reply)
                
                if cmd_type == NBD_CMD_READ and error == 0:
                    conn.sendall(response_data)

            except Exception as e:
                log_debug(f"Loop crash: {e}")
                break
        log_debug("Worker thread exiting.")

    def start(self):
        log_debug(f"Starting NBD Server on {self.device_path}")
        self.running = True
        
        try:
            nbd_fd = os.open(self.device_path, os.O_RDWR)
        except OSError as e:
            log_debug(f"Failed to open device: {e}")
            return

        try:
            fcntl.ioctl(nbd_fd, NBD_SET_BLKSIZE, 4096) 
            fcntl.ioctl(nbd_fd, NBD_SET_SIZE, self.vdisk.total_size)
            fcntl.ioctl(nbd_fd, NBD_CLEAR_SOCK)

            kernel_sock = self.sock_pair[1]
            my_sock = self.sock_pair[0]
            
            fcntl.ioctl(nbd_fd, NBD_SET_SOCK, kernel_sock.fileno())

            t = threading.Thread(target=self._handle_request, args=(my_sock,))
            t.start()

            log_debug("Calling NBD_DO_IT (Blocking)...")
            fcntl.ioctl(nbd_fd, NBD_DO_IT)
            log_debug("NBD_DO_IT returned.")
            
        except Exception as e:
            log_debug(f"Setup error: {e}")
        finally:
            self.running = False
            self.sock_pair[0].close()
            self.sock_pair[1].close()
            os.close(nbd_fd)
            self.vdisk.close()
            # t.join() # Don't block here in daemon

def run_daemon(drive_path, drive_name, chunk_mb, total_chunks, device="/dev/nbd0"):
    shell.run(["modprobe", "nbd"], check=False)
    vdisk = VirtualDisk(drive_path, drive_name, chunk_mb, total_chunks)
    server = NBDServer(device, vdisk)
    server.start()
