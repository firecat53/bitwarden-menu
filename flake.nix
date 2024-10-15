{
  description = "Dmenu/Rofi/Wofi frontend for managing Bitwarden vaults.";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = ["x86_64-linux" "i686-linux" "aarch64-linux"];
    forAllSystems = f:
      nixpkgs.lib.genAttrs systems (system:
        f {
          pkgs = nixpkgs.legacyPackages.${system};
        });
  in {
    devShells = forAllSystems ({pkgs}: {
      default = pkgs.mkShell {
        buildInputs = with pkgs; [
          pandoc
          python3Packages.venvShellHook
          uv
        ];
        shellHook = ''
          venvShellHook
          alias bwm="python -m bwm"
        '';
        venvDir = "./.venv";
        postVenvCreation = ''
          uv pip install hatch
          uv pip install -e .
          # Prevent venv uv from overriding nixpkgs uv
          [ -f $(pwd)/.venv/bin/uv ] && rm $(pwd)/.venv/bin/uv*
        '';
        C_INCLUDE_PATH = "${pkgs.linuxHeaders}/include";
        HATCH_ENV_TYPE_VIRTUAL_UV_PATH = "${pkgs.uv}/bin/uv"; # use Nix uv instead of hatch downloaded binary
        PYTHONPATH = "$PYTHONPATH:$PWD";
      };
    });
    packages = forAllSystems ({pkgs}: {
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
        propagatedBuildInputs = builtins.attrValues {
          inherit
            (pkgs.python3Packages)
            python
            pynput
            xdg-base-dirs
            ;
        };
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
