{
  description = "Vibori static election-results viewer";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      importer = pkgs.writeShellApplication {
        name = "vibori-import-izbirkom";
        runtimeInputs = [ pkgs.python3 pkgs.python3Packages.pysocks ];
        text = ''exec python3 ${./scripts/izbirkom.py} --config ${./config/izbirkom.json} "$@"'';
      };
      indexer = pkgs.writeShellApplication {
        name = "vibori-build-index";
        runtimeInputs = [ pkgs.nodejs_22 ];
        text = ''exec node ${./scripts/build-index.mjs} public/data'';
      };
      generator = pkgs.writeShellApplication {
        name = "vibori-generate";
        runtimeInputs = [ pkgs.nix ];
        text = ''
          nix develop --command npm ci
          nix develop --command npm run generate
          target="''${1:-dist}"
          if [ -e "$target" ] && [ ! -L "$target" ]; then
            echo "Refusing to replace non-symlink target: $target" >&2
            exit 2
          fi
          ln -sfn "$(pwd)/.output/public" "$target"
          echo "Static site: $target"
        '';
      };
    in {
      packages.${system}.default = generator;
      apps.${system} = {
        import-izbirkom = { type = "app"; program = "${importer}/bin/vibori-import-izbirkom"; };
        build-index = { type = "app"; program = "${indexer}/bin/vibori-build-index"; };
        generate = { type = "app"; program = "${generator}/bin/vibori-generate"; };
      };
      devShells.${system}.default = pkgs.mkShell { packages = [ pkgs.nodejs_22 pkgs.python3 pkgs.jq ]; };
    };
}
