{
  description = "Vibori static election-results viewer";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      importer = pkgs.writeShellApplication {
        name = "vibori-import-izbirkom";
        runtimeInputs = [ (pkgs.python3.withPackages (pythonPackages: [ pythonPackages.pysocks ])) ];
        text = ''
          export PYTHONPATH=${./scripts}
          exec python3 ${./scripts/import_izbirkom_api.py} --config ${./config/izbirkom.json} "$@"
        '';
      };
      indexer = pkgs.writeShellApplication {
        name = "vibori-build-index";
        runtimeInputs = [ pkgs.nodejs_22 ];
        text = ''exec node --expose-gc ${./scripts/build-index.mjs} "$@"'';
      };
      generator = pkgs.writeShellApplication {
        name = "vibori-generate";
        runtimeInputs = [ pkgs.nix ];
        text = ''
          nix develop --command npm ci
          VIBORI_STATIC_BUILD=1 nix develop --command npm run generate
          mkdir -p .output/public/data
          cp -a public/data/. .output/public/data/
          if [ -n "''${VIBORI_INDEX_DIR:-}" ]; then
            cp -a "$VIBORI_INDEX_DIR/." .output/public/data/
          fi
          target="''${1:-dist}"
          if [ -e "$target" ] && [ ! -L "$target" ]; then
            echo "Refusing to replace non-symlink target: $target" >&2
            exit 2
          fi
          ln -sfn "$(pwd)/.output/public" "$target"
          echo "Static site: $target"
        '';
      };
      checker = pkgs.writeShellApplication {
        name = "vibori-check";
        runtimeInputs = [ pkgs.mypy pkgs.nodejs_22 pkgs.python3 pkgs.ruff ];
        text = ''
          npm ci
          ruff format --check scripts
          ruff check scripts
          mypy --ignore-missing-imports scripts/import_izbirkom_api.py scripts/izbirkom_api.py
          python3 -m unittest discover -s scripts -p 'test_*.py'
          node --test scripts/*.test.mjs
          npm run typecheck
        '';
      };
    in {
      packages.${system}.default = generator;
      apps.${system} = {
        import-izbirkom = { type = "app"; program = "${importer}/bin/vibori-import-izbirkom"; };
        build-index = { type = "app"; program = "${indexer}/bin/vibori-build-index"; };
        check = { type = "app"; program = "${checker}/bin/vibori-check"; };
        generate = { type = "app"; program = "${generator}/bin/vibori-generate"; };
      };
      devShells.${system}.default = pkgs.mkShell {
        packages = [ pkgs.jq pkgs.mypy pkgs.nodejs_22 pkgs.python3 pkgs.ruff ];
      };
    };
}
