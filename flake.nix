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
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [ (pkgs.python3.withPackages pythonDeps) ] ++ systemDeps;

        shellHook = ''
          export PYTHONPATH="$PYTHONPATH:$(pwd)/src"
          # Try to load module if possible (might fail in containers)
          sudo modprobe nbd 2>/dev/null || true
          clear
          echo "TGFS Dev Shell (NBD Architecture)"
        '';
      };
    };
}
