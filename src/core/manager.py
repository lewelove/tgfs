import os
import time
import sys
import multiprocessing
import signal
import typer
from config_loader import get_config
from core import database, chunker, formatter, validator, nbd_server
from utils import shell

conf = get_config()

def get_pid_file(name):
    return os.path.join(conf['paths']['storage_root'], f".{name}.pid")

def create_drive(name: str, size_mb: int, chunk_mb: int, fs: str):
    path = validator.get_drive_path(name)
    storage_root = conf['paths']['storage_root']

    if not os.path.exists(storage_root):
        os.makedirs(storage_root, exist_ok=True)

    os.makedirs(path, exist_ok=True)
    
    total_chunks = size_mb // chunk_mb
    if size_mb % chunk_mb != 0: total_chunks += 1
    
    # DB Init
    db = database.DBManager(path, name)
    db.initialize({"chunk_size_mb": chunk_mb, "total_chunks": total_chunks, "fs": fs})
    
    typer.echo("[*] Allocating chunks...")
    chunks = chunker.create_initial_chunks(path, name, total_chunks, chunk_mb)
    for c in chunks:
        st = os.stat(os.path.join(path, c['filename']))
        db.update_chunk(c['index'], c['hash'], c['filename'], st.st_size, st.st_mtime)
    
    typer.echo("[*] Formatting...")
    # To format, we must momentarily mount (attach NBD)
    # We run the daemon in a separate process
    device = "/dev/nbd0"
    p = multiprocessing.Process(
        target=nbd_server.run_daemon,
        args=(path, name, chunk_mb, total_chunks, device)
    )
    p.start()
    
    # Wait for device to appear
    time.sleep(1) 
    
    try:
        formatter.format_device(device, fs)
    except Exception as e:
        typer.secho(f"Formatting failed: {e}", fg="red")
    finally:
        # Kill the temp daemon
        shell.run(["nbd-client", "-d", device], check=False)
        p.terminate()
        p.join()

    fix_permissions(storage_root, recursive=True)
    typer.secho(f"[+] Drive '{name}' created successfully.", fg="green")

def mount_drive(name: str):
    validator.require_drive_exists(name)
    if is_running(name):
        typer.echo(f"Drive {name} is already mounted/running.")
        return

    path = validator.get_drive_path(name)
    db = database.DBManager(path, name)
    chunk_mb = int(db.get_meta("chunk_size_mb"))
    total_chunks = int(db.get_meta("total_chunks"))
    fs = db.get_meta("fs")
    
    device = "/dev/nbd0" # In future, find first free NBD
    
    typer.echo("[*] Starting NBD Daemon...")
    p = multiprocessing.Process(
        target=nbd_server.run_daemon,
        args=(path, name, chunk_mb, total_chunks, device)
    )
    p.daemon = True
    p.start()
    
    # Save PID
    with open(get_pid_file(name), 'w') as f:
        f.write(str(p.pid))
    
    time.sleep(1) # Wait for init
    
    # Mount Filesystem
    mount_point = conf['paths']['mount_root']
    try:
        from core import mount
        mount.mount_vdev(device, mount_point, name, fs)
        typer.secho(f"[+] Mounted {name} at {mount_point}/{name}", fg="green")
    except Exception as e:
        typer.secho(f"[-] Mount failed: {e}", fg="red")
        p.terminate()
        if os.path.exists(get_pid_file(name)): os.remove(get_pid_file(name))

def umount_drive(name: str):
    mount_point = conf['paths']['mount_root']
    
    # 1. System Umount
    from core import mount
    mount.umount_vdev(mount_point, name)
    
    # 2. Stop Daemon
    pid_file = get_pid_file(name)
    if os.path.exists(pid_file):
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        # Disconnect NBD gracefully
        shell.run(["nbd-client", "-d", "/dev/nbd0"], check=False)
        
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
            
        os.remove(pid_file)
    
    # 3. Check integrity
    check_drive(name)
    typer.secho(f"[+] Unmounted {name}", fg="green")

def is_running(name):
    pid_file = get_pid_file(name)
    if not os.path.exists(pid_file): return False
    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read())
        os.kill(pid, 0) # Check if process exists
        return True
    except:
        return False

def check_drive(name: str):
    # Same logic as before, just verifies files on disk
    validator.require_drive_exists(name)
    path = validator.get_drive_path(name)
    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    padding = chunker.get_padding(int(db.get_meta("total_chunks")))
    
    changed = 0
    typer.echo("[*] Scanning chunks for changes...")
    
    for c in chunks:
        # Note: If we wrote data, filenames might still be OLD hash.
        # We need to find the file by index.
        # Current naive impl looks for file in DB. 
        # But IO Engine didn't rename files.
        # So the file on disk is still `drive.001.OLDHASH.img` but content is NEW.
        
        curr_path = os.path.join(path, c['filename'])
        if not os.path.exists(curr_path):
            continue
            
        st = os.stat(curr_path)
        # If mtime changed, rehash
        if abs(st.st_mtime - (c.get('mtime') or 0)) > 0.0001 or st.st_size != c.get('size'):
            new_h = chunker.get_hash(curr_path)
            if new_h != c['hash']:
                # Rename to new hash
                new_name = chunker.format_name(name, c['chunk_index'], new_h, padding)
                new_full = os.path.join(path, new_name)
                os.rename(curr_path, new_full)
                
                db.update_chunk(c['chunk_index'], new_h, new_name, st.st_size, st.st_mtime)
                changed += 1
                typer.echo(f"Updated Chunk {c['chunk_index']}")
    
    typer.echo(f"Check complete. {changed} chunks updated.")

def fix_permissions(path, recursive=True):
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        cmd = ["chown"]
        if recursive: cmd.append("-R")
        cmd.append(f"{sudo_user}:")
        cmd.append(path)
        shell.run(cmd)
