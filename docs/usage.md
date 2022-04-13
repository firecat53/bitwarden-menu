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

`bwm [-h] [-v VAULT] [-l LOGIN] [-a AUTOTYPE] `

--help, -h Output a usage message and exit.

-v VAULT, --vault URL Vault URL to open, skipping the selection menu

-l LOGIN, --login LOGIN email for vault

-a AUTOTYPE, --autotype AUTOTYPE Override autotype sequence in config.ini

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
    - Auto-type username and/or password on selection. No clipboard copy/paste
      involved. Use xdotool, ydotool, or wtype for non-U.S. English keyboard layout.
    - Use a custom [Keepass 2.x style auto-type sequence][1] if you have one defined
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

[1]: https://keepass.info/help/base/autotype.html#autoseq "Keepass 2.x codes"
