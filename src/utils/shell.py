import subprocess
import typer

def run(cmd, input_str=None, check=True):
    try:
        res = subprocess.run(
            cmd,
            input=input_str.encode() if input_str else None,
            capture_output=True,
            check=check
        )
        return res.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        typer.secho(f"Error executing: {' '.join(cmd)}", fg=typer.colors.RED)
        typer.secho(f"Stderr: {e.stderr.decode()}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
