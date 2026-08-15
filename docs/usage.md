# Bitwarden-menu Usage

[Installation](install.md) - [Configuration](configure.md)

## Basic

- [Configure](docs/configure.md) config.ini as desired.
- Run `bwm` or bind to keystroke combination.
- Enter vault address, login email and 2FA type on first run if not already configured
  in config.ini.
- Start typing to match entries, `Enter` to type with default autotype sequence
  `{USERNAME}{TAB}{PASSWORD}{ENTER}`.

## CLI Options

`bwm [-h] [-V] [-v VAULT] [-l EMAIL] [-k] [-a AUTOTYPE] [-C] [-c CONFIG] [-s SEARCH] [-f FIELD] [-F]`

-h, --help Print help and exit.

-V, --version Print version and exit.

-v VAULT, --vault URL Vault URL to open, skipping the selection menu. Use with -l
when multiple accounts share the same server.

-l LOGIN, --login LOGIN email for vault. Optional when only one account exists on
the server. Required with -v when multiple accounts share the same server.

-k, --lock Locks vault

-a AUTOTYPE, --autotype AUTOTYPE Override autotype sequence in config.ini

-C, --clipboard Copy values to clipboard instead of typing

-c CONFIG, --config PATH Path to config file. Supports absolute paths, relative
paths, and tilde expansion. Default: ~/.config/bwm/config.ini

-s SEARCH, --show SEARCH Output the password of the matching entry to stdout (or
to the clipboard with -C). See [CLI-only usage](#cli-only-usage)

-f FIELD, --field FIELD Field to output with --show. Repeat for multiple fields,
which are output one per line in the order given. Defaults to the password.
'all' lists values of all fields in the entry.

-F, --foreground Run the daemon in the foreground instead of detaching

## The daemon

`bwm` starts a background daemon on first use and returns immediately. The
daemon holds the unlocked vault. Bitwarden takes 8-12 seconds to unlock even a
small vault. It exits after `session_timeout_min` (default 360) of inactivity,
or immediately on `bwm -k`.

Pass `-F/--foreground` to keep it attached instead. That's useful for
troubleshooting, since a backgrounded daemon sends its output to `/dev/null`.

**Troubleshooting:** a backgrounded daemon sends its output to `/dev/null`, so
run it with `--foreground` to see errors. `BWM_LOG_LEVEL=debug` turns on debug
logging in `~/.cache/bwm.log`, which records each vault's status check, unlock
and entry load.

**Service managers:** a systemd unit with `Type=simple` expects the process to
stay in the foreground. Either add `--foreground` to the `ExecStart` line or use
`Type=forking`.

## CLI-only usage

`--show` prints entry fields to stdout and needs no launcher, no pynput and no
clipboard tool. With `DISPLAY` and `WAYLAND_DISPLAY` unset, bwm prompts for
credentials on the terminal instead of through a launcher, so the whole flow -
initial login, 2FA code, `client_secret`, unlocking - works over ssh or on a
headless machine. Pass `-v` and `-l` (or configure `server_N`/`email_N` in
config.ini) since the interactive first-run wizard needs a launcher.

`--show SEARCH` matches a single entry on its folder path, name, username or
URL. If more than one entry matches, the matching entries are listed on stderr
and bwm exits non-zero, so narrow the search.

    $ bwm -s 'ssh github' -f username -f password
    gituser
    hunter2

Field names are case- and separator-insensitive: `security code`,
`security_code` and `securitycode` are the same field. Valid names are the
autotype placeholders `title`, `username`, `password`, `url`, `notes`, `totp`
and `cardnum`, any field of a card or identity entry (`security code`,
`expiration month`, `ssn`, `first name`, ...), and `S:<name>` for a custom
field. `-f all` outputs every field that has a value, labeled:

    $ bwm -s visa -f all
    title: visa
    cardholder name: J Doe
    brand: Visa
    number: 4111111111111111
    expiration month: 04
    security code: 999

With `-C` the output goes to the clipboard instead of stdout, cleared after 30
seconds.

## Features

- *General features*
    - Compatible with both [Bitwarden.com](https://bitwarden.com) and
      self-hosted [Vaultwarden](https://github.com/dani-garci/vaultwarden)
      accounts. Accounts can be switched on the fly.
    - Alternate keyboard languages and layouts supported via xdotool, ydotool or
      wtype (for Wayland)
    - Add, edit and type TOTP codes. RFC 6238, Steam and custom settings are
      supported.
- *Type entries*
    - Auto-type username and/or password on selection. Use xdotool, ydotool, or
      wtype for non-U.S. English keyboard layout.
    - Select to clipboard if desired (clears clipboard after 30s). If `view/type
      individual entries` isn't selected first, it will copy the password field
      to the clipboard if it exists, otherwise will raise an error.
    - Use a custom [Keepass 2.x style auto-type sequence][1] if you have one
      defined
      (except for character repetition and the 'special commands'). Set it per entry
      or set a global default. Disable autotype for an entry, if desired.
    - Select any single field and have it typed into the active window. Notes fields
      can be viewed line-by-line and the selected line will be typed when
      selected.
    - `Enter` to open the URL in the default web browser from the View/Type menu.
- *Edit*
    - Edit entry title, username, URL and password (manually typed or auto-generate)
    - Edit notes using terminal or gui editor (set in config.ini, or uses $EDITOR)
    - Add and Delete entries
    - Rename, move, delete and add folders
    - Collection management:
        - Add, remove, rename, delete collections
        - Add item to collection(s) (multiple collections supported)
        - Move item from collection back to personal vault
- *Configure* ([docs](configure.md))
    - Prompts for and saves initial vault URL and login if config file isn't
      setup before first run.
    - Set multiple vaults and logins in the config file.
    - Hide selected groups from the default and 'View/Type Individual entries' views.
    - Bitwarden-menu runs in the background after initial startup and will retain the
      entered passphrase for `session_timeout_min` minutes after the last activity.
    - Configure the characters and groups of characters used during password
      generation in the config file (see config.ini.example for instructions).
      Multiple character sets can be selected on the fly when using Rofi if the
      `-multi-select` option is passed via `dmenu_command`.
    - Optional Pinentry support for secure passphrase entry.

## Offline use

Once a vault has been logged into, unlocking it is a purely local operation -
the master password is verified against the encrypted vault cached in
`~/.local/share/bwm/`. Bitwarden-menu can therefore be unlocked and used
without a network connection.

Available offline:

- Unlocking the vault
- View/Type individual entries and the previous entry
- Copy fields to the clipboard, open URLs, generate TOTP codes
- Locking the vault and switching between vaults

Requires a connection to the vault server:

- The *initial* login (and any login after `Lock vault` has been replaced by a
  full logout). Bitwarden's identity server has to issue the tokens, so there is
  no way around this.
- `Sync vault`
- `Edit entries`, `Add entry`, `Manage folders` and `Manage collections`

Selecting one of the server-backed options while offline shows an error instead
of failing partway through. Connectivity is re-tested each time, so those
options start working again as soon as the network returns - there is no need to
restart bitwarden-menu.

Note that the reachability test is a direct TCP connection to the host and port
of the configured vault URL. If your vault is only reachable through an HTTP
proxy, this test will report "offline" even though the Bitwarden CLI can still
reach the server.

[1]: https://keepass.info/help/base/autotype.html#autoseq "Keepass 2.x codes"
