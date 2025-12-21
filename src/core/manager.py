import os
import typer
from config_loader import get_config
from core import database, chunker, mapper, mount, formatter, validator
from utils import shell

conf = get_config()

def create_drive(name: str, size_mb: int, chunk_mb: int, fs: str):
    path = validator.get_drive_path(name)
    prefix = conf['paths']['mapper_prefix']
    storage_root = conf['paths']['storage_root']

    # 1. Ensure Storage Root exists
    if not os.path.exists(storage_root):
        typer.echo(f"[*] Creating storage root: {storage_root}")
        os.makedirs(storage_root, exist_ok=True)

    # 2. Setup Directory & DB
    os.makedirs(path, exist_ok=True)
    db = database.DBManager(path, name)
    total_chunks = size_mb // chunk_mb
    db.initialize({"chunk_size_mb": chunk_mb, "total_chunks": total_chunks, "fs": fs})
    
    # 3. Allocate
    typer.echo("[*] Allocating chunks...")
    chunks = chunker.create_initial_chunks(path, name, total_chunks, chunk_mb)
    for c in chunks:
        db.update_chunk(c['index'], c['hash'], c['filename'])
    
    # 4. Map & Format
    typer.echo("[*] Mapping and Formatting...")
    try:
        vdev = mapper.map_vdev(name, chunks, path, prefix)
        formatter.format_device(vdev, fs)
    finally:
        mapper.unmap_vdev(name, prefix)

    # 5. Fix Ownership (Aggressive)
    # We recursively chown the ENTIRE storage root. This fixes the root folder itself
    # (tgfs-raw) AND the new drive folder inside it.
    fix_permissions(storage_root, recursive=True)
    
    typer.secho(f"[+] Drive '{name}' created successfully.", fg="green")

def mount_drive(name: str):
    validator.require_drive_exists(name)
    path = validator.get_drive_path(name)
    prefix = conf['paths']['mapper_prefix']

    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    fs = db.get_meta("fs")

    if not validator.is_active_in_kernel(name):
        typer.echo(f"[*] Mapping {prefix}-{name}...")
        vdev = mapper.map_vdev(name, chunks, path, prefix)
    else:
        vdev = f"/dev/mapper/{prefix}-{name}"

    typer.echo(f"[*] Mounting to {conf['paths']['mount_root']}/{name}...")
    mnt = mount.mount_vdev(vdev, conf['paths']['mount_root'], name, fs)
    typer.secho(f"[+] Mounted at {mnt}", fg="green")

def umount_drive(name: str):
    prefix = conf['paths']['mapper_prefix']
    
    typer.echo(f"[*] Unmounting {name}...")
    mount.umount_vdev(conf['paths']['mount_root'], name)
    
    typer.echo(f"[*] Removing kernel mapping...")
    mapper.unmap_vdev(name, prefix)
    
    typer.echo("[*] Running integrity check...")
    check_drive(name)
    typer.secho(f"[+] Drive '{name}' safely closed.", fg="green")

def map_drive(name: str):
    validator.require_drive_exists(name)
    path = validator.get_drive_path(name)
    prefix = conf['paths']['mapper_prefix']
    
    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    
    typer.echo(f"[*] Mapping {prefix}-{name}...")
    dev = mapper.map_vdev(name, chunks, path, prefix)
    typer.secho(f"[+] Device available at {dev}", fg="green")

def check_drive(name: str):
    validator.require_drive_exists(name)
    path = validator.get_drive_path(name)
    
    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    total_chunks = int(db.get_meta("total_chunks"))
    padding = chunker.get_padding(total_chunks)
    
    changed_count = 0
    for c in chunks:
        file_path = os.path.join(path, c['filename'])
        if not os.path.exists(file_path):
            typer.secho(f" [!] Missing chunk: {c['filename']}", fg="yellow")
            continue

        new_h = chunker.get_hash(file_path)
        if new_h != c['hash']:
            new_name = chunker.format_name(name, c['chunk_index'], new_h, padding)
            os.rename(file_path, os.path.join(path, new_name))
            db.update_chunk(c['chunk_index'], new_h, new_name)
            typer.echo(f" [!] Updated: Chunk {c['chunk_index']} -> {new_h}")
            changed_count += 1

    if changed_count == 0:
        typer.echo("[-] No changes detected.")
    else:
        typer.echo(f"[*] {changed_count} chunks updated in database.")

def fix_permissions(path, recursive=True):
    """Changes ownership of path to SUDO_USER."""
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        cmd = ["chown"]
        if recursive:
            cmd.append("-R")
        cmd.append(f"{sudo_user}:")
        cmd.append(path)
        shell.run(cmd)
