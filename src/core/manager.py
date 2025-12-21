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

    if not os.path.exists(storage_root):
        os.makedirs(storage_root, exist_ok=True)

    os.makedirs(path, exist_ok=True)
    db = database.DBManager(path, name)
    total_chunks = size_mb // chunk_mb
    db.initialize({"chunk_size_mb": chunk_mb, "total_chunks": total_chunks, "fs": fs})
    
    typer.echo("[*] Allocating chunks...")
    chunks = chunker.create_initial_chunks(path, name, total_chunks, chunk_mb)
    for c in chunks:
        # Store initial stats to enable fast 'check' later
        st = os.stat(os.path.join(path, c['filename']))
        db.update_chunk(c['index'], c['hash'], c['filename'], st.st_size, st.st_mtime)
    
    typer.echo("[*] Mapping and Formatting...")
    try:
        vdev = mapper.map_vdev(name, chunks, path, prefix)
        formatter.format_device(vdev, fs)
    finally:
        mapper.unmap_vdev(name, prefix, path)

    fix_permissions(storage_root, recursive=True)
    typer.secho(f"[+] Drive '{name}' created successfully.", fg="green")

def check_drive(name: str):
    validator.require_drive_exists(name)
    path = validator.get_drive_path(name)
    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    padding = chunker.get_padding(int(db.get_meta("total_chunks")))
    
    changed_count = 0
    skipped_count = 0

    for c in chunks:
        file_path = os.path.join(path, c['filename'])
        if not os.path.exists(file_path):
            continue

        st = os.stat(file_path)
        # SKIP LOGIC: If size and mtime are identical to DB, the chunk is unchanged
        if abs(st.st_mtime - (c.get('mtime') or 0)) < 0.0001 and st.st_size == c.get('size'):
            skipped_count += 1
            continue

        # Only hash if mtime changed
        new_h = chunker.get_hash(file_path)
        if new_h != c['hash']:
            new_name = chunker.format_name(name, c['chunk_index'], new_h, padding)
            new_path = os.path.join(path, new_name)
            os.rename(file_path, new_path)
            
            # Update DB with new stats
            new_st = os.stat(new_path)
            db.update_chunk(c['chunk_index'], new_h, new_name, new_st.st_size, new_st.st_mtime)
            typer.echo(f" [!] Updated: Chunk {c['chunk_index']} -> {new_h}")
            changed_count += 1
        else:
            # Hash matches but mtime was different? Update DB mtime to match disk
            db.update_chunk(c['chunk_index'], c['hash'], c['filename'], st.st_size, st.st_mtime)

    typer.echo(f"[-] Check complete: {skipped_count} skipped, {changed_count} updated.")

def mount_drive(name: str):
    validator.require_drive_exists(name)
    path = validator.get_drive_path(name)
    prefix = conf['paths']['mapper_prefix']
    db = database.DBManager(path, name)
    
    vdev = mapper.map_vdev(name, db.get_chunks(), path, prefix)
    mount.mount_vdev(vdev, conf['paths']['mount_root'], name, db.get_meta("fs"))
    typer.secho(f"[+] Mounted {name}", fg="green")

def umount_drive(name: str):
    path = validator.get_drive_path(name)
    mount.umount_vdev(conf['paths']['mount_root'], name)
    mapper.unmap_vdev(name, conf['paths']['mapper_prefix'], path)
    check_drive(name)
    typer.secho(f"[+] Closed {name}", fg="green")

def fix_permissions(path, recursive=True):
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        cmd = ["chown"]
        if recursive: cmd.append("-R")
        cmd.append(f"{sudo_user}:")
        cmd.append(path)
        shell.run(cmd)
