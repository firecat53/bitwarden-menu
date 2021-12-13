# Bitwarden-menu

Dmenu/Rofi frontend for managing Bitwarden vault using the [Bitwarden
CLI](https://bitwarden.com/help/article/cli/) tool.

This project is not associated with the Bitwarden project nor 8bit Solutions
LLC.

## Features

- Auto-type username and/or password on selection. No clipboard copy/paste
  involved.
- Login with 2FA code from Authenticator(TOTP), Email, or Yubikey (only these
  are supported by the Bitwarden CLI).
- Select any single field and have it typed into the active window. Notes fields
  can be viewed line-by-line from within dmenu and the selected line will be
  typed when selected.
- Open the URL in the default web browser from the View/Type menu.
- Alternate keyboard languages and layouts supported via xdotool or ydotool (for
  Wayland)
- Edit entry title, username, URL and password (manually typed or auto-generate)
- Edit notes using terminal or gui editor (set in config.ini, or uses $EDITOR)
- Add and Delete entries
- Rename, move, delete and add folders and collections
- Move any item to or from an organization, including support for multiple collections.
- Prompts for and saves initial server URL and login email
- Define multiple vault URLs in the config file.
- Hide selected folders from the default and 'View/Type Individual entries'
  views.
- Configure session timeout
- Configure the characters and groups of characters used during password
  generation in the config file (see config.ini.example for instructions).
  Multiple character sets can be selected on the fly when using Rofi if the
  `-multi-select` option is passed to Rofi via `dmenu_command`.
- Use a custom Keepass 2.x style [auto-type sequence][autotype] if you have an
  'autotype' field defined in the entry (except for character repetition and the
  'special commands'). Set it per entry and/or set a default in the config file
  for all entries.

## License

- MIT

## Requirements

1. Python 3.7+.
2. [Bitwarden CLI][bwcli]. Ensure the `bw` command is in `$PATH`
3. [Pynput][pynput]
4. Dmenu or [Rofi][rofi]. Rofi configuration/theming should be done via Rofi
   theme files.
5. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.
6. (optional) xdotool or ydotool (for Wayland). If you have a lot of Unicode
   characters or use a non-U.S.  English keyboard layout, xdotool is necessary
   to handle typing those characters.

## Installation

- Installation

  + `pip install --user bitwarden-menu`. Add ~/.local/bin to $PATH
  + In a virtualenv with pip. Link to the executable in
    <path/to/virtualenv/bin/bwm>

        mkvirtualenv bwm
        pip install bitwarden-menu

  + From git. Just clone, install requirements and run
  + Available in the [Archlinux AUR][aur].

- If you start bwm for the first time without a config file, it will prompt
  you for server name, login email, and 2FA type and save them in the config
  file.

- Copy config.ini.example to ~/.config/bwm/config.ini, or use it as a
  reference for additional options.

  + To use a command (e.g. gpg) to lookup db password, set `password_cmd_<n>`
    in config.ini.
  + Adjust `session_timeout_min` if desired. Default is 6 hours (360 min).
  + Set the dmenu_command to `rofi` if you are using that instead
  + Adjust the autotype_default, if desired. Allowed codes are the
    `Keepass 2.x codes`_ except for repetitions and most command codes. `{DELAY
    x}` (in milliseconds) is supported.  Individual autotype sequences can be
    edited or deleted using bwm. To disable autotype for an entry, set it to
    `False`.
  + Set `type_library = xdotool` or `type_library = ydotool` (Wayland) if you
    need support for non-U.S. English keyboard layouts and/or characters.

    * When using xdotool, call `setxkbmap` to set your keyboard type somewhere
      in your window manager or desktop environment initialization. For example:
      `exec setxkbmap de` in ~/.config/i3/config.

- If using Rofi, pass desired theme via `dmenu_command = rofi -theme <theme>.rasi`.
  Dmenu themeing options are also passed via `dmenu_command`
- New sets of characters can be set in config.ini in the `[password_chars]`
  section. A new preset for each custom set will be listed in addition to the
  default presets. If you redefine one of the default sets (upper, lower,
  digits, punctuation), it will replace the default values.
- New preset groups of character sets can be defined in config.ini in the
  `[password_char_presets]` section. You can set any combination of default and
  custom character sets. A minimum of one character from each distinct set will
  be used when generating a new password. If any custom presets are defined, the
  default presets will not be displayed unless they are uncommented.

<b>WARNING:</b> If you choose to store your vault password in config.ini, make
sure to `chmod 600 config.ini`. This is not secure and I only added it as a
convenience for testing.

## Usage

- Run script or bind to keystroke combination
- Enter server URL (default `vault.bitwarden.com`), login email and 2FA type if
  not entered into config.ini already.
- Start typing to match entries.
- Hit Enter immediately after dmenu opens ("`View/Type individual entries`") to
  switch modes to view and/or type the individual fields for the entry. If
  selected, the URL will open in the default browser instead of being typed.
- To view a password without typing it, use the 'Edit Entries' option, then
  select the entry, select 'Password' then select 'Manually enter password'.
  Type 'ESC' to exit without making changes.

### Wayland (wlroots - Sway)

- Dmenu or Rofi work under XWayland.
- To enable ydotool to work without sudo
    - Pick a group that one or more users
      belong to (e.g. `users`) and:

            $ echo "KERNEL==\"uinput\", GROUP=\"users\", MODE=\"0660\", \
            OPTIONS+=\"static_node=uinput\"" | sudo tee \
            /etc/udev/rules.d/80-uinput.rules > /dev/null
            # udevadm control --reload-rules && udevadm trigger

    - Create a systemd user service for ydotoold:

            ~/.config/systemd/user/ydotoold.service
            [Unit]
            Description=ydotoold Service

            [Service]
            ExecStart=/usr/bin/ydotoold

            [Install]
            WantedBy=default.target

    - Enable and start ydotoold.service:

            $ systemctl --user daemon-reload
            $ systemctl --user enable --now ydotoold.service

## Tests

- To run tests: `python tests/tests.py` (not implemented yet)

## Planned features

- Unit tests
- TOTP support
- Notifications for syncing status (e.g. when a sync is complete)

[pynput]: https://github.com/moses-palmer/pynput "Pynput"
[bwcli]: https://github.com/bitwarden/cli "Bitwarden CLI"
[rofi]: https://davedavenport.github.io/rofi/ "Rofi"
[aur]: https://aur.archlinux.org/packages/python-bitwarden-menu-git "Archlinux AUR"
[autotype]: https://keepass.info/help/base/autotype.html#autoseq "Keepass 2.x Autotype codes"
