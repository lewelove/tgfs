{
  description = "tgfs: Telegram File System CLI (MVP1)";

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
        lvm2
        util-linux
        e2fsprogs
        btrfs-progs
        sqlite
      ];
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [ (pkgs.python3.withPackages pythonDeps) ] ++ systemDeps;

        shellHook = ''
          export PYTHONPATH="$PYTHONPATH:$(pwd)/src"
          clear
        '';
      };
    };
}
