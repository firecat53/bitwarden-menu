# Bitwarden-menu Configuration

[Installation](install.md) - [Usage](usage.md)

If you start bitwarden-menu for the first time without a config file, it will
prompt you for vault URL, login and 2FA type and save them in the default config
file `~/.config/bwm/config.ini`. Initial login to some servers, including
vault.bitwarden.com, will require the `client_secret` from your account settings
page. Ensure this is in your clipboard and ready to paste prior to first run.
Once logged in for the first time, you will not need this value again.

OR Copy config.ini.example to `~/.config/bwm/config.ini` and use it as a
reference for additional options.

#### Config.ini values

| Section                   | Key                          | Default                                 | Notes                                                        |
|---------------------------|------------------------------|-----------------------------------------|--------------------------------------------------------------|
| `[dmenu]`                 | `dmenu_command`              | `dmenu`                                 | Command can include arguments                                |
|                           | `pinentry`                   | None                                    |                                                              |
| `[dmenu_passphrase]`      | `obscure`                    | `False`                                 |                                                              |
|                           | `obscure_color`              | `#222222`                               | Only applicable to dmenu                                     |
| `[vault]`                 | `server_n`                   | None                                    | `n` is any integer                                           |
|                           | `login_n`                    | None                                    |                                                              |
|                           | `password_n`                 | None                                    |                                                              |
|                           | `password_cmd_n`             | None                                    |                                                              |
|                           | `twofactor_n`                | None                                    | 0 (TOTP), 1 (email), 3 (yubikey)                             |
|                           | `autotype_default_n`         | None                                    | Overrides global default                                     |
|                           | `session_timeout_min`        | `360`                                   | Value in minutes                                             |
|                           | `editor`                     | `vim`                                   |                                                              |
|                           | `terminal`                   | `xterm`                                 |                                                              |
|                           | `gui_editor`                 | None                                    |                                                              |
|                           | `type_library`               | `pynput`                                | xdotool, ydotool, wtype or pynput                            |
|                           | `hide_folders`               | None                                    | See below for formatting of multiple folders                 |
|                           | `autotype_default`           | `{USERNAME}{TAB}{PASSWORD}{ENTER}`      | [Keepass autotype sequences][1]                              |
| `[password_chars]`        | `lower`                      | `abcdefghijklmnopqrstuvwxyz`            |                                                              |
|                           | `upper`                      | `ABCDEFGHIJKLMNOPQRSTUVWXYZ`            |                                                              |
|                           | `digits`                     | `0123456789`                            |                                                              |
|                           | `punctuation`                | ``!"#$%%&'()*+,-./:;<=>?@[\]^_`{│}~``   |                                                              |
|                           | `Custom Name(s)`             | `Any string`                            |                                                              |
| `[password_char_presets]` | `Letters+Digits+Punctuation` | `upper lower digits punctuation`        | Values from password_chars                                   |
|                           | `Letters+Digits`             | `upper lower digits`                    |                                                              |
|                           | `Letters`                    | `upper lower`                           |                                                              |
|                           | `Digits`                     | `digits`                                |                                                              |
|                           | `Custom Name(s)`             | `Any combo of [password_chars] entries` |                                                              |

#### Config.ini example

    [dmenu]
    # Note that dmenu_command can contain arguments as well
    dmenu_command = rofi -dmenu -theme bwm -i
    # dmenu_command = dmenu -i -l 25 -b -nb #909090 -nf #303030
    pinentry = pinentry-gtk
    title_path = 25

    [dmenu_passphrase]
    ## Obscure password entry.
    obscure = True
    obscure_color = #303030

    [vault]
    server_1 = https://vault.bitwarden.com
    login_1 = joe@joe.com
    server_2 = https://vault.mydomain.net
    login_2 = joe@joe.com
    twofactor_2 = 0
    autotype_default_2 = {TOTP}{ENTER}
    password_cmd_2 = gpg -qd ~/.pass.gpg

    session_timeout_min = 720

    gui_editor = gvim -f
    type_library = xdotool
    hide_folders = Trash
                   Archived
                   Spouse

    ## Set the global default
    autotype_default = {USERNAME}{TAB}{PASSWORD}{ENTER}

    [password_chars]
    # Set custom groups of characters for password generation. Any name is fine and
    # these can be used to create new groups of presets in password_char_presets. If
    # you reuse 'upper', 'lower', 'digits', or 'punctuation', those will
    # replace the default values.
    lower = abcdefghjkmnpqrstuvwxyz
    upper = ABCDEFGHJKMNPQRSTUVWXYZ
    digits = 23456789
    punctuation = !"#$%%&'()*+,-./:;<=>?@[\]^_`{}~
    # NOTE: % needs to be escaped with another % sign
    # Custom EXAMPLES:
    punc min = !?#*@-+$%%
    upper = ABCDEFZ

    [password_char_presets]
    # Set character preset groups for password generation. For multiple sets use a space in between
    # If you set any custom presets here, the default sets will not be displayed unless uncommented below:
    # Valid values are: upper lower digits punctuation
    # Also valid are any custom sets defined in [password_chars]
    # Custom Examples:
    Minimal Punc = upper lower digits "punc min"
    Router Site = upper digits

1. Add your vault URLs, login name and 2FA types (if applicable).
2. Adjust `session_timeout_min` if desired. Default is 6 hours (360 min).
3. Set the dmenu_command to `rofi` if you are using that instead
4. If using Rofi, pass desired theme via `dmenu_command = rofi -theme <theme>.rasi`.
   Dmenu theme options are also passed in `dmenu_command`.
6. Adjust the `autotype_default`, if desired. Allowed codes are the [Keepass 2.x codes][1]
   except for repetitions and most command codes. `{DELAY x}`
   (in milliseconds) is supported. Individual autotype sequences can be edited
   or disabled inside bitwarden-menu.
7. Set `type_library = xdotool` or `type_library = ydotool` (Wayland) if you
   need support for non-U.S. English keyboard layouts and/or characters.

    * When using xdotool, call `setxkbmap` to set your keyboard type somewhere
      in your window manager or desktop environment initialization. For example:
      `exec setxkbmap de` in ~/.config/i3/config.

8. New sets of characters can be set in config.ini in the `[password_chars]`
   section. A new preset for each custom set will be listed in addition to the
   default presets. If you redefine one of the default sets (upper, lower,
   digits, punctuation), it will replace the default values.
9. New preset groups of character sets can be defined in config.ini in the
   `[password_char_presets]` section. You can set any combination of default and
   custom character sets. A minimum of one character from each distinct set will
   be used when generating a new password. If any custom presets are defined,
   the default presets will not be displayed unless they are uncommented.

**Warning** If you choose to store your vault password into config.ini, make
sure to `chmod 600 config.ini`. This is not secure and I only added it as a
convenience for testing.

[1]:  https://keepass.info/help/base/autotype.html#autoseq "Keepass Autotype Sequences"
