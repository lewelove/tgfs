{
  description = "tgfs: Telegram File System CLI (NBD MVP)";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      
      pythonDeps = ps: with ps; [ 
        typer
        xxhash
        toml
      ];

      systemDeps = with pkgs; [
        util-linux
        e2fsprogs
        btrfs-progs
        sqlite
        nbd # For nbd-client utility
        kmod # For modprobe
      ];

      # Define the 'tgfs' executable wrapper
      tgfsScript = pkgs.writeShellScriptBin "tgfs" ''
        # 1. Validation
        if [ -z "$TGFS_ROOT" ]; then
           echo "Error: TGFS_ROOT is not set. Ensure you are inside the 'nix develop' shell."
           exit 1
        fi

        # 2. Auto-escalate to sudo if not root
        # We use -E to preserve PYTHONPATH and TGFS_ROOT so python knows where files are
        if [ "$EUID" -ne 0 ]; then
           exec sudo -E "$0" "$@"
        fi

        # 3. Execute
        python3 "$TGFS_ROOT/src/main.py" "$@"
      '';

    in
    {
      devShells.${system}.default = pkgs.mkShell {
        # Add the script to the inputs
        buildInputs = [ (pkgs.python3.withPackages pythonDeps) tgfsScript ] ++ systemDeps;

        shellHook = ''
          # Capture the absolute path of the project root when shell starts
          export TGFS_ROOT="$(pwd)"
          export PYTHONPATH="$PYTHONPATH:$TGFS_ROOT/src"
          
          # Try to load module if possible (might fail in containers)
          sudo modprobe nbd 2>/dev/null || true
          
          clear
          echo "TGFS Dev Shell (NBD Architecture)"
          echo "Command 'tgfs' is now available."
        '';
      };
    };
}
