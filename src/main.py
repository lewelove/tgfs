import typer
import sys
from core import manager, validator, nbd_server

app = typer.Typer(help="tgfs: Telegram File System CLI (NBD Architecture)", add_completion=False)

@app.command(name="create")
def create(
    name: str = typer.Argument(None, help="The name of the drive"),
    size_mb: int = typer.Option(None, "--size", "-s", help="Total size in MB"),
    chunk_mb: int = typer.Option(None, "--chunk", "-c", help="Chunk size in MB"),
    fs: str = typer.Option(None, "--fs", "-f", help="Filesystem (ext4/btrfs)")
):
    """Initializes and formats a new drive using NBD."""
    while True:
        if not name: name = typer.prompt("Drive Name")
        if validator.exists_on_disk(name):
            typer.secho(f"Error: Drive '{name}' already exists.", fg="red")
            name = None; continue
        break

    if not size_mb: size_mb = int(typer.prompt("Total Size (MB)"))
    if not chunk_mb: chunk_mb = int(typer.prompt("Chunk Size (MB)", default=500))
    if not fs: fs = typer.prompt("Filesystem (ext4/btrfs)", default="btrfs")

    manager.create_drive(name, size_mb, chunk_mb, fs)

@app.command(name="mount")
def mount_cmd(name: str = typer.Argument(None)):
    """Starts the NBD daemon and mounts the filesystem."""
    if not name: name = typer.prompt("Drive Name")
    manager.mount_drive(name)

@app.command(name="umount")
def umount_cmd(name: str = typer.Argument(None)):
    """Unmounts filesystem and stops the NBD daemon."""
    if not name: name = typer.prompt("Drive Name")
    manager.umount_drive(name)

@app.command(name="check")
def check_cmd(name: str = typer.Argument(None)):
    """Scans chunks, updates hashes in DB."""
    if not name: name = typer.prompt("Drive Name")
    manager.check_drive(name)

@app.command(name="internal-serve", hidden=True)
def internal_serve(
    path: str, 
    name: str, 
    chunk_mb: int, 
    total_chunks: int, 
    device: str
):
    """
    Internal Entrypoint: Runs the NBD server. 
    Called via subprocess to detach from terminal.
    """
    nbd_server.run_daemon(path, name, chunk_mb, total_chunks, device)

if __name__ == "__main__":
    app()
