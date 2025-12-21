import typer
import os
from config_loader import get_config
from core import database, chunker, mapper, mount, formatter
from utils import shell

app = typer.Typer(help="tgfs: Telegram File System CLI", add_completion=False)
conf = get_config()

def get_drive_path(name: str):
    return os.path.join(conf['paths']['storage_root'], name)

def check_logic(name: str):
    path = get_drive_path(name)
    if not os.path.exists(path):
        typer.secho(f"Error: Drive folder for '{name}' not found.", fg="red")
        return

    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    
    changed_count = 0
    for c in chunks:
        file_path = os.path.join(path, c['filename'])
        if not os.path.exists(file_path):
            continue

        new_h = chunker.get_hash(file_path)
        if new_h != c['hash']:
            new_name = chunker.format_name(name, c['chunk_index'], new_h)
            os.rename(file_path, os.path.join(path, new_name))
            db.update_chunk(c['chunk_index'], new_h, new_name)
            typer.echo(f" [!] Updated: Chunk {c['chunk_index']} -> {new_h}")
            changed_count += 1

    if changed_count == 0:
        typer.echo("[-] No changes detected.")
    else:
        typer.echo(f"[*] {changed_count} chunks updated in database.")

@app.command(name="create")
def create(
    name: str = typer.Argument(None, help="The name of the drive"),
    size_mb: int = typer.Option(None, "--size", "-s", help="Total size in MB"),
    chunk_mb: int = typer.Option(None, "--chunk", "-c", help="Chunk size in MB"),
    fs: str = typer.Option(None, "--fs", "-f", help="Filesystem (ext4/btrfs)")
):
    """Initializes, maps, formats, and then unmaps a new virtual drive."""
    prefix = conf['paths']['mapper_prefix']

    # 1. Validate Name (Loop until unique and available)
    while True:
        if not name:
            name = typer.prompt("Drive Name")

        path = get_drive_path(name)

        # Check Disk
        if os.path.exists(path):
            typer.secho(f"Error: Drive folder '{name}' already exists at {path}.", fg="red")
            name = None # Reset to force re-prompt
            continue

        # Check Kernel
        if mapper.is_mapped(name, prefix):
            typer.secho(f"Error: Device '{prefix}-{name}' is already active in kernel.", fg="red")
            name = None # Reset to force re-prompt
            continue
        
        break # Name is valid and available

    # 2. Get remaining parameters only after name is confirmed
    if not size_mb: size_mb = int(typer.prompt("Total Size (MB)"))
    if not chunk_mb: chunk_mb = int(typer.prompt("Chunk Size (MB)", default=10))
    if not fs: fs = typer.prompt("Filesystem (ext4/btrfs)", default="ext4")

    # 3. Proceed with creation
    os.makedirs(path, exist_ok=True)
    db = database.DBManager(path, name)
    total_chunks = size_mb // chunk_mb
    db.initialize({"chunk_size_mb": chunk_mb, "total_chunks": total_chunks, "fs": fs})
    
    typer.echo("[*] Allocating chunks...")
    chunks = chunker.create_initial_chunks(path, name, total_chunks, chunk_mb)
    for c in chunks:
        db.update_chunk(c['index'], c['hash'], c['filename'])
    
    typer.echo("[*] Mapping and Formatting...")
    try:
        vdev = mapper.map_vdev(name, chunks, path, prefix)
        formatter.format_device(vdev, fs)
    finally:
        mapper.unmap_vdev(name, prefix)

    # Fix ownership
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        shell.run(["chown", "-R", f"{sudo_user}:", path])
        
    typer.secho(f"[+] Drive '{name}' created successfully.", fg="green")

@app.command(name="mount")
def mount_cmd(name: str = typer.Argument(None)):
    if not name: name = typer.prompt("Drive Name to mount")
    path = get_drive_path(name)
    prefix = conf['paths']['mapper_prefix']
    
    if not os.path.exists(path):
        typer.secho(f"Error: Drive '{name}' not found.", fg="red")
        raise typer.Exit(1)

    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    fs = db.get_meta("fs")
    
    if not mapper.is_mapped(name, prefix):
        typer.echo(f"[*] Mapping {prefix}-{name}...")
        vdev = mapper.map_vdev(name, chunks, path, prefix)
    else:
        vdev = f"/dev/mapper/{prefix}-{name}"
    
    typer.echo(f"[*] Mounting to {conf['paths']['mount_root']}/{name}...")
    mnt = mount.mount_vdev(vdev, conf['paths']['mount_root'], name, fs)
    typer.secho(f"[+] Mounted at {mnt}", fg="green")

@app.command(name="umount")
def umount_cmd(name: str = typer.Argument(None)):
    if not name: name = typer.prompt("Drive Name to unmount")
    prefix = conf['paths']['mapper_prefix']
    mount.umount_vdev(conf['paths']['mount_root'], name)
    mapper.unmap_vdev(name, prefix)
    typer.echo("[*] Running integrity check...")
    check_logic(name)
    typer.secho(f"[+] Drive '{name}' safely closed.", fg="green")

@app.command(name="map")
def map_cmd(name: str = typer.Argument(None)):
    if not name: name = typer.prompt("Drive Name to map")
    path = get_drive_path(name)
    prefix = conf['paths']['mapper_prefix']
    db = database.DBManager(path, name)
    chunks = db.get_chunks()
    dev = mapper.map_vdev(name, chunks, path, prefix)
    typer.secho(f"[+] Device available at {dev}", fg="green")

@app.command(name="check")
def check_cmd(name: str = typer.Argument(None)):
    if not name: name = typer.prompt("Drive Name to check")
    check_logic(name)

if __name__ == "__main__":
    app()
