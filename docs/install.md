# Bitwarden-menu Installation

[Configuration](configure.md) - [Usage](usage.md)

## Requirements

1. Python 3.7+
2. [Bitwarden CLI][1]. Ensure the `bw` command is in `$PATH`
3. [Pynput][2] and [Xdg][6]
4. Dmenu, [Rofi][3], [Wofi][7] or [Bemenu][4]
5. (optional) Pinentry. Make sure to set which flavor of pinentry command to use
   in the config file.
6. (optional) xdotool, ydotool(>= 1.0.0) or wtype (for Wayland). If you have a
   lot of Unicode characters or use a non-U.S. English keyboard layout,
   xdotool/ydotool/wtype are ecessary to handle typing those characters.

#### Archlinux

`$ sudo pacman -S python-pip dmenu`

#### Fedora 34

`$ sudo dnf install python3-devel dmenu`

#### Ubuntu 21.10

Ensure Universe repository is enabled.

`$ sudo apt install python3-pip suckless-tools`

## Install (recommended)

`$ pip install --user bitwarden-menu`

Add ~/.local/bin to $PATH

### Install (virtualenv)

    $ python -m venv venv
    $ source venv/bin/activate
    $ pip install bitwarden-menu

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
    $ pip install --user . OR
    $ pip install --user -e . (for editable install)

### Available in [Archlinux AUR][5]


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
[6]: https://pypi.org/project/xdg/ "Xdg"
[7]: https://hg.sr.ht/~scoopta/wofi "Wofi"
