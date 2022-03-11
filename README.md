# Bitwarden-menu

![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bitwarden-menu)
![PyPI](https://img.shields.io/pypi/v/bitwarden-menu)
![GitHub contributors](https://img.shields.io/github/contributors/firecat53/bitwarden-menu)

Dmenu/Rofi frontend for managing Bitwarden vaults. Uses the [Bitwarden
CLI](https://bitwarden.com/help/article/cli/) tool to interact with the
Bitwarden database.

This project is not associated with the Bitwarden project nor 8bit Solutions
LLC.

## Installation

`pip install --user bitwarden-menu`

Ensure `~/.local/bin` is in your `$PATH`. Run `bwm` and enter your database
path, keyfile path, and password.

For full installation documention see the [installation docs][docs/install.md].

## Full Documentation

[Installation](docs/install.md) - [Configuration](docs/configure.md) - [Usage](docs/usage.md)

## Requirements

1. Python 3.7+
2. [Bitwarden CLI][bwcli]. Ensure the `bw` command is in `$PATH`
3. [Pynput][pynput]
4. Dmenu, [Rofi][rofi] or [Bemenu][bemenu]
5. (optional) Pinentry.
6. (optional) xdotool or ydotool (for Wayland).

## Features

- Supports [bitwarden.com](https://bitwarden.com) and self-hosted
  [Vaultwarden](https://github.com/dani-garcia/vaultwarden) accounts.
- Auto-type username and/or password on selection. No clipboard copy/paste
  involved.
- Supports login with 2FA code from Authenticator(TOTP), Email, or Yubikey.
- Background process allows selectable time-out for locking the database.
- Use a custom [Keepass 2.x style auto-type sequence][6].
- Type, view or edit any field.
- Open the URL in the default web browser.
- Non U.S. English keyboard languages and layouts supported via xdotool or
  ydotool (for Wayland).
- Edit notes using terminal or gui editor.
- Add and Delete entries
- Rename, move, delete and add folders and collections
- Move any item to or from an organization, including support for multiple
  collections.
- Hide selected folders from the default and 'View/Type Individual entries'
  views.
- Define multiple vault URLs in the config file.
- Configure the characters and groups of characters used during password
  generation.
- Optional Pinentry support for secure passphrase entry.

## License

- MIT

## Usage

`bwm [-h] [-v VAULT] [-l LOGIN] [-a AUTOTYPE]`

- Run `bwm` or bind to keystroke combination.
- Enter account URL on first run.
- Start typing to match entries.
- [Configure](docs/configure.md) ~/.config/bwm/config.ini as desired.
- More detailed [usage information](docs/usage.md).

## Tests

To run tests in a venv: `make test` (not implemented yet)

## Development

- To install bitwarden-menu in a venv: `make`
- Build man page from Markdown source: `make man`

## Planned features

- Unit tests
- TOTP support
- Notifications for syncing status (e.g. when a sync is complete)
- Clipboard support

[pynput]: https://github.com/moses-palmer/pynput "Pynput"
[bwcli]: https://github.com/bitwarden/cli "Bitwarden CLI"
[rofi]: https://davedavenport.github.io/rofi/ "Rofi"
[aur]: https://aur.archlinux.org/packages/bitwarden-menu-git "Archlinux AUR"
[autotype]: https://keepass.info/help/base/autotype.html#autoseq "Keepass 2.x Autotype codes"
[bemenu]: https://github.com/Cloudef/bemenu "Bemenu"
