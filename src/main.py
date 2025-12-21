import typer
from core import manager, validator

app = typer.Typer(help="tgfs: Telegram File System CLI", add_completion=False)

@app.command(name="create")
def create(
    name: str = typer.Argument(None, help="The name of the drive"),
    size_mb: int = typer.Option(None, "--size", "-s", help="Total size in MB"),
    chunk_mb: int = typer.Option(None, "--chunk", "-c", help="Chunk size in MB"),
    fs: str = typer.Option(None, "--fs", "-f", help="Filesystem (ext4/btrfs)")
):
    """Initializes, maps, formats, and then unmaps a new virtual drive."""
    # 1. Name Validation Loop
    while True:
        if not name:
            name = typer.prompt("Drive Name")

        if validator.exists_on_disk(name):
            typer.secho(f"Error: Drive folder '{name}' already exists.", fg="red")
            name = None; continue

        if validator.is_active_in_kernel(name):
            typer.secho(f"Error: Drive '{name}' is active in kernel.", fg="red")
            name = None; continue
        
        break

    # 2. Get Remaining Inputs (UPDATED DEFAULTS)
    if not size_mb: size_mb = int(typer.prompt("Total Size (MB)"))
    if not chunk_mb: chunk_mb = int(typer.prompt("Chunk Size (MB)", default=500))
    if not fs: fs = typer.prompt("Filesystem (ext4/btrfs)", default="btrfs")

    # 3. Handover to Manager
    manager.create_drive(name, size_mb, chunk_mb, fs)

@app.command(name="mount")
def mount_cmd(name: str = typer.Argument(None, help="The name of the drive to mount")):
    """Maps and mounts the virtual drive."""
    if not name: name = typer.prompt("Drive Name to mount")
    manager.mount_drive(name)

@app.command(name="umount")
def umount_cmd(name: str = typer.Argument(None, help="The name of the drive to unmount")):
    """Unmounts, unmaps, and runs an integrity check."""
    if not name: name = typer.prompt("Drive Name to unmount")
    manager.umount_drive(name)

@app.command(name="map")
def map_cmd(name: str = typer.Argument(None, help="The name of the drive to map")):
    """Assembles the chunks into a device mapper node without mounting."""
    if not name: name = typer.prompt("Drive Name to map")
    manager.map_drive(name)

@app.command(name="check")
def check_cmd(name: str = typer.Argument(None, help="The name of the drive to check")):
    """Scans chunks for changes and updates the database."""
    if not name: name = typer.prompt("Drive Name to check")
    manager.check_drive(name)

if __name__ == "__main__":
    app()
