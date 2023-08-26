{
  description = "Dmenu/Rofi/Wofi frontend for managing Bitwarden vaults.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = ["x86_64-linux" "i686-linux" "aarch64-linux"];
    forAllSystems = f:
      nixpkgs.lib.genAttrs systems (system:
        f rec {
          pkgs = nixpkgs.legacyPackages.${system};
          commonPackages = builtins.attrValues {
            inherit
              (pkgs.python3Packages)
              python
              pynput
              xdg
              ;
          };
        });
  in {
    devShells = forAllSystems ({
      pkgs,
      commonPackages,
    }: {
      default = pkgs.mkShell {
        packages = commonPackages ++ [pkgs.pandoc];
        shellHook = ''
          alias bwm="python -m bwm"
          export PYTHONPATH="$PYTHONPATH:$PWD"
        '';
      };
    });
    packages = forAllSystems ({
      pkgs,
      commonPackages,
    }: {
      default = pkgs.python3Packages.buildPythonApplication {
        name = "bitwarden-menu";
        pname = "bitwarden-menu";
        format = "pyproject";
        src = ./.;
        nativeBuildInputs = builtins.attrValues {
          inherit
            (pkgs)
            git
            ;
          inherit
            (pkgs.python3Packages)
            hatchling
            hatch-vcs
            ;
        };
        propagatedBuildInputs = commonPackages;
        meta = {
          description = "Dmenu/Rofi/Wofi frontend for managing Bitwarden vaults.";
          homepage = "https://github.com/firecat53/bitwarden-menu";
          license = pkgs.lib.licenses.mit;
          maintainers = ["firecat53"];
          platforms = systems;
        };
      };
    });
  };
}
