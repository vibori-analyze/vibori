{
  description = "Vibori — статический обозреватель результатов выборов";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let pkgs = nixpkgs.legacyPackages.x86_64-linux; in {
      devShells.x86_64-linux.default = pkgs.mkShell {
        packages = [ pkgs.nodejs_22 pkgs.python3 pkgs.jq ];
        shellHook = ''echo "Vibori: npm install && npm run dev"'';
      };
    };
}
