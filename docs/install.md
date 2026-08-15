# Bitwarden-menu Installation

[Configuration](configure.md) - [Usage](usage.md)

## Requirements

1. Python 3.10+
2. [Bitwarden CLI][1]. Ensure the `bw` command is in `$PATH`
3. [xdg-base-dirs][6]

The rest is only needed for the interactive (launcher) mode:

4. [Pynput][2], for auto-typing as the default `type_library`. Installed by
   `pip install bitwarden-menu[autotype]`, or use one of the alternate type
   libraries in item 7.
5. Dmenu, [Rofi][3], [Wofi][7] or [Bemenu][4]
6. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.
7. (optional) xdotool, ydotool(>= 1.0.0) or wtype (for Wayland). If you have a
   lot of Unicode characters or use a non-U.S. English keyboard layout,
   xdotool/ydotool/wtype are ecessary to handle typing those characters.

#### Archlinux

`$ sudo pacman -S python-pip dmenu`

#### Fedora 34

`$ sudo dnf install python3-devel dmenu`

#### Ubuntu

Ensure Universe repository is enabled.

`$ sudo apt install python3-pip suckless-tools`

## Install (recommended)

`$ pip install --user bitwarden-menu[autotype]`

Add ~/.local/bin to $PATH

Drop the `[autotype]` extra to install without pynput.

**Note:** pynput used to be installed unconditionally. Upgrading an existing
install with a plain `pip install -U bitwarden-menu` leaves it in place, but in
a fresh virtualenv you need the `[autotype]` extra to keep auto-typing working.

### Install (virtualenv)

    $ python -m venv venv
    $ source venv/bin/activate
    $ pip install bitwarden-menu[autotype]

Link to the executable `/path/to/venv/bin/bwm` when assigning a keyboard shortcut.

### Install (virtualenv) from git

    $ git clone https://github.com/firecat53/bitwarden-menu
    $ cd bitwarden-menu
    $ make
    $ make run OR ./venv/bin/bwm
    
### Install (git)
  
    $ git clone https://github.com/firecat53/bitwarden-menu
    $ cd bitwarden-menu
    $ git checkout <branch> (if desired)
    $ pip install --user '.[autotype]' OR
    $ pip install --user -e '.[autotype]' (for editable install)

### Available in [Archlinux AUR][5] and Nix packages


## Wayland (wlroots - Sway)

- Dmenu and Rofi work under XWayland. Bemenu can operate natively in Wayland.
- To enable ydotool to work without sudo
    - Pick a group that one or more users belong to (e.g. `users`) and:

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

[1]: https://github.com/bitwarden/cli "Bitwarden CLI"
[2]: https://github.com/moses-palmer/pynput "pynput"
[3]: https://davedavenport.github.io/rofi/ "Rofi"
[4]: https://github.com/Cloudef/bemenu "Bemenu"
[5]: https://aur.archlinux.org/packages/bitwarden-menu-git "Archlinux AUR"
[6]: https://pypi.org/project/xdg-base-dirs/ "Xdg"
[7]: https://hg.sr.ht/~scoopta/wofi "Wofi"
