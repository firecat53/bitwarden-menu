# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bitwarden-menu (`bwm`) is a dmenu/rofi/bemenu/tofi/wmenu/wofi frontend for Bitwarden and
Vaultwarden vaults, driving the Bitwarden CLI (`bw`) underneath. It also works
headless as a CLI-only password lookup via `--show`.

## Development Commands

```bash
make                 # Create .venv and install '.[autotype,test]'
make run             # Run bwm from the venv
make test            # pytest
make test-cov        # pytest with HTML + term-missing coverage
make man             # Regenerate bwm.1 from bwm.1.md (needs pandoc)
make version         # Print __version__ from bwm/__init__.py
make clean

nix develop          # Dev shell (uv-managed .venv, pandoc, hatch, pytest)
hatch shell          # Alternative editable venv
```

Run a single test: `.venv/bin/pytest tests/test_bwm.py::test_name` (or
`-k pattern`). `addopts = "-v --tb=short"` is already set in `pyproject.toml`.

Debug logging: `BWM_LOG_LEVEL=debug bwm ...` writes to `$XDG_CACHE_HOME/bwm.log`
(mode 0600, since debug records entry names and URLs). The env var is read at
import time, before config loading, so config.ini cannot set it.

`bwm -F/--foreground` keeps the daemon attached to the terminal — use it when
debugging anything in the daemon processes.

### Releases

`make release VERSION=x.y.z` (no leading `v`) bumps `__version__` in
`bwm/__init__.py`, updates the man page footer/date, rebuilds `bwm.1`, commits,
and opens `$EDITOR` for the annotated tag prefilled with commits since the last
tag. Push with `git push origin <branch> --follow-tags`. The version lives only
in `bwm/__init__.py`; CI fails the build if a pushed tag disagrees with it.
Pushes to `main` publish a `.devN` build to TestPyPI; tags publish to PyPI.

## Architecture

### Process model — this is the part that surprises people

A `bwm` invocation is a *client*. The vault lives in a detached *daemon*, so
unlocking (8-12 seconds) happens once instead of on every lookup.

- `__main__.py` writes a port + authkey into `$XDG_RUNTIME_DIR/bwm/` (the
  `AUTH_FILE`) and checks whether that port is live.
  - Port dead → `run()` builds `DmenuRunner` **in the client, while the terminal
    is still attached**, so every credential prompt happens before forking, then
    starts the `Server` and `DmenuRunner` processes and detaches.
  - Port live → connect as a client over `multiprocessing.BaseManager`, push the
    parsed args through a duplex `Pipe`, and set the daemon's start event.
- `Server` (in `__main__.py`) is a third process hosting the BaseManager. Its
  registered callables run *in that process*, so anything the daemon publishes
  to clients (the unlocked-vault list) goes through a `multiprocessing.Array` of
  JSON, not a Manager — a Manager would be yet another orphanable process.
- Anything with a user-facing prompt must happen client-side: the daemon has no
  terminal and no `DISPLAY`. This is why `show_password_prompt()` and the
  clipboard copy (`deliver_show_result()`) live in `__main__.py`.
- Exiting the client uses `leave(code, detached=True)` → `os._exit()`, because
  multiprocessing's atexit handler would otherwise join the daemon and block
  until the session timeout.
- `bwm.CLI` is a global mode flag: True for `--show` or when there is no
  `DISPLAY`/`WAYLAND_DISPLAY`, which routes prompts to the terminal instead of a
  launcher. `DmenuRunner.run()` resets it to False once detached.

### Vault access: two layers

`bwm/bwcli.py` shells out to `bw` per command. `bwm/bwserve.py` (`BWCLIServer`)
starts a single long-lived `bw serve` and talks HTTP to it over a
`socket.socketpair()` — much faster, and the session token is passed via the
environment (not `--session`, which would expose it in `/proc/<pid>/cmdline`).

`Vault.bwcliserver` is set when `bw serve` came up; callers in `bwm.py` and
`bwedit.py` branch on `if vault.bwcliserver:` and fall back to the `bwcli`
function otherwise. **Any new vault operation needs both paths.**

### Menu loop

`DmenuRunner.run()` blocks on the server's start event, then loops
`dmenu_run(vault)`, which returns a `Run` enum (`LOCK`, `CONTINUE`, `RELOAD`,
`STOP`, `SWITCH`) that the loop acts on. Vault-writing menu options are wrapped
in `needs_server()` so they're blocked while offline; read/type paths keep
working offline.

### `--show` / `--field`

`bwm/run_once.py` holds pure helpers over already-loaded entries (no unlocking,
no `bw` calls), used both by the client that starts the daemon (it has the vault
in hand — no round trip) and by `DmenuRunner.show_entry()` when a daemon already
runs. Results travel back over the duplex pipe tagged with a random
`show_id`, demultiplexed in `Server.receive_show_result()` so two concurrent
`--show` calls can't take each other's secret.

Field names in `run_once.py`: standard autotype tokens (`title`, `username`,
`password`, …) win over per-entry-type field names, so a name never changes
meaning based on which entry matched.

### Typing backends

`bwm/bwtype.py` tokenizes Keepass-style autotype sequences and dispatches to one
of `tokens_pynput.py` (default), `tokens_xdotool.py` (X11, non-US layouts),
`tokens_wtype.py` / `tokens_ydotool.py` (Wayland), selected by the `type_library`
config option.

## Configuration

- Loaded by `bwm.reload_config(conf_file=None)` in `bwm/__init__.py`, **not** at
  import time. It is called twice: once in `main()` (the client reads `[vault]`
  before forking) and once in `DmenuRunner.__init__()` (the daemon process).
  Anything `main()` needs from `CONF` must be available after that first call.
- Custom path flows from `-c/--config` through argparse into `DmenuRunner`
  kwargs.
- Sections: `[dmenu]`, `[dmenu_passphrase]`, `[vault]` (multi-account via
  `server_N` / `email_N` / `password_N` / `password_cmd_N`), `[password_chars]`,
  `[password_char_presets]`.
- Vault data always lives in `~/.local/share/bwm/` regardless of config path.

## Tests

`tests/conftest.py` installs an autouse `no_network` fixture that fails any test
resolving a non-local hostname. If a new test touches vault code, patch
`bwm.bwcli.is_online` (or `bwm.bwcli.socket.create_connection`) rather than
loosening the guard. `tests/test_server.py` binds real local sockets, which the
guard permits.
