import socket
import struct
import os
import fcntl
import threading
import signal
import sys
from core.io import VirtualDisk
from utils import shell

# NBD Constants
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

class NBDServer:
    def __init__(self, device_path, vdisk: VirtualDisk):
        self.device_path = device_path
        self.vdisk = vdisk
        self.sock_pair = socket.socketpair()
        self.running = False

    def _handle_request(self, conn):
        """
        Reads NBD requests from the kernel and sends replies.
        Protocol:
        Request: [Magic (4)][Type (4)][Handle (8)][From (8)][Len (4)]
        Reply:   [Magic (4)][Error (4)][Handle (8)][Data (if read)]
        """
        while self.running:
            try:
                # Header is 28 bytes
                header = conn.recv(28)
                if not header or len(header) < 28:
                    break

                (magic, cmd_type, handle, offset, length) = struct.unpack(">LLQQL", header)

                if magic != NBD_REQUEST_MAGIC:
                    raise ValueError(f"Invalid magic: {hex(magic)}")

                error = 0
                response_data = b""

                try:
                    if cmd_type == NBD_CMD_READ:
                        response_data = self.vdisk.read(offset, length)
                    
                    elif cmd_type == NBD_CMD_WRITE:
                        # For write, data follows the header immediately
                        data = b""
                        while len(data) < length:
                            chunk = conn.recv(length - len(data))
                            if not chunk: raise IOError("Unexpected EOF in write data")
                            data += chunk
                        self.vdisk.write(offset, data)
                    
                    elif cmd_type == NBD_CMD_DISC:
                        self.running = False
                        # No reply for disconnect
                        return 
                    
                    elif cmd_type == NBD_CMD_FLUSH:
                        self.vdisk.sync()

                    elif cmd_type == NBD_CMD_TRIM:
                        pass # Ignore trim for now

                    else:
                        error = 1 # EPERM/Unknown
                
                except Exception as e:
                    print(f"IO Error: {e}", file=sys.stderr)
                    error = 5 # EIO

                # Send Reply Header
                reply = struct.pack(">LLQ", NBD_REPLY_MAGIC, error, handle)
                conn.sendall(reply)
                
                if cmd_type == NBD_CMD_READ and error == 0:
                    conn.sendall(response_data)

            except Exception as e:
                if self.running:
                    print(f"NBD Loop Error: {e}", file=sys.stderr)
                break

    def start(self):
        """Connects the socket to the kernel driver and starts the loop."""
        self.running = True
        
        # 1. Open the NBD device file
        try:
            nbd_fd = os.open(self.device_path, os.O_RDWR)
        except OSError:
            print(f"Could not open {self.device_path}. Is modprobe nbd loaded?")
            return

        # 2. Handshake: Set block size and total size
        # 4096 is standard block size
        fcntl.ioctl(nbd_fd, NBD_SET_BLKSIZE, 4096) 
        # Total size in bytes
        fcntl.ioctl(nbd_fd, NBD_SET_SIZE, self.vdisk.total_size)
        
        # 3. Clear any old sockets
        fcntl.ioctl(nbd_fd, NBD_CLEAR_SOCK)

        # 4. Attach our socket (the one we read from)
        # socketpair returns (client, server). We give server side to kernel.
        # We read from client side.
        kernel_sock = self.sock_pair[1]
        my_sock = self.sock_pair[0]
        
        fcntl.ioctl(nbd_fd, NBD_SET_SOCK, kernel_sock.fileno())

        # 5. Start the IO loop in a separate thread (or main thread)
        # The ioctl NBD_DO_IT blocks until disconnect.
        # So we need to run our python logic in a thread or process BEFORE calling DO_IT.
        # Or, we call DO_IT in a thread. 
        # Typically: Main thread does IO logic, Worker thread calls DO_IT (which blocks).
        
        t = threading.Thread(target=self._handle_request, args=(my_sock,))
        t.start()

        try:
            # This blocks the process. The Kernel uses this thread to drive the device.
            # When NBD_CMD_DISC is received, this returns.
            fcntl.ioctl(nbd_fd, NBD_DO_IT)
        except OSError:
            pass # Disconnect triggers error sometimes
        finally:
            self.running = False
            my_sock.close()
            kernel_sock.close()
            os.close(nbd_fd)
            self.vdisk.close()
            # Wait for IO thread
            t.join(timeout=1)

def run_daemon(drive_path, drive_name, chunk_mb, total_chunks, device="/dev/nbd0"):
    # Ensure nbd module
    shell.run(["modprobe", "nbd"], check=False)
    
    # Initialize Disk
    vdisk = VirtualDisk(drive_path, drive_name, chunk_mb, total_chunks)
    
    # Start Server
    server = NBDServer(device, vdisk)
    server.start()
