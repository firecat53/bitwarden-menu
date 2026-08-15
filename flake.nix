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
          uv pip install -e '.[autotype]' --quiet
          alias bwm="python -m bwm"
        '';
        venvDir = "./.venv";
        postVenvCreation = ''
          uv pip install hatch pytest pytest-cov
          uv pip install -e '.[autotype]'
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
        pname = "bitwarden-menu";
        version = builtins.head (builtins.match
          ".*\n__version__ = \"([^\"]+)\".*"
          (builtins.readFile ./bwm/__init__.py));
        format = "pyproject";
        src = ./.;
        nativeBuildInputs = builtins.attrValues {
          inherit
            (pkgs.python3Packages)
            hatchling
            ;
        };
        # pynput is the `autotype` extra in pyproject.toml, not a hard
        # dependency. Kept here so the packaged app is fully featured.
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
