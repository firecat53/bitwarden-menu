---
title: Bitwarden-menu
section: 1
header: User Manual
footer: Bitwarden-menu v0.4.0
date: 2022-04-18
---

# NAME

bitwarden-menu - Fully featured Dmenu/Rofi/Bemenu frontend for autotype and
managing of Bitwarden/Vaultwarden vaults.

# SYNOPSIS

**bitwarden-menu** [**--vault** URL] [**--login** email] [**--autotype** pattern]

# DESCRIPTION

**Bitwarden-menu** is a fast and minimal application to facilitate password entry and
manage most aspects of Bitwarden/Vaultwarden vaults.

# OPTIONS

**-v**, **--vault** Vault URL

**-l**, **--login**  Login email address

**-a**, **--autotype**  Autotype sequence from
https://keepass.info/help/base/autotype.html#autoseq . Overrides global default
from config.ini for current vault.

# EXAMPLES

	bwm
    bwm -v https://vault.mydomain.net -l user@domain.com -a '{TOTP}{ENTER}'

# CONFIGURATION  

If you start bitwarden-menu for the first time without a config file, it will prompt
you for vault, login and 2FA type (if applicable) and save them in a default
config file.

OR Copy config.ini.example to ~/.config/bwm/config.ini and use it as a reference
for additional options.

## config.ini options and defaults

| Section                   | Key                          | Default                                 |
|---------------------------|------------------------------|-----------------------------------------|
| `[dmenu]`                 | `dmenu_command`              | `dmenu`                                 |
|                           | `pinentry`                   | None                                    |
| `[dmenu_passphrase]`      | `obscure`                    | `False`                                 |
|                           | `obscure_color`              | `#222222`                               |
| `[vault]`                 | `server_n`                   | None                                    |
|                           | `login_n`                    | None                                    |
|                           | `twofactor_n`                | None                                    |
|                           | `password_n`                 | None                                    |
|                           | `password_cmd_n`             | None                                    |
|                           | `autotype_default_n`         | None                                    |
|                           | `session_timeout_min`        | `360`                                   |
|                           | `editor`                     | `vim`                                   |
|                           | `terminal`                   | `xterm`                                 |
|                           | `gui_editor`                 | None                                    |
|                           | `type_library`               | `pynput`                                |
|                           | `hide_folders`               | None                                    |
|                           | `autotype_default`           | `{USERNAME}{TAB}{PASSWORD}{ENTER}`      |
| `[password_chars]`        | `lower`                      | `abcdefghijklmnopqrstuvwxyz`            |
|                           | `upper`                      | `ABCDEFGHIJKLMNOPQRSTUVWXYZ`            |
|                           | `digits`                     | `0123456789`                            |
|                           | `punctuation`                | ``!"#$%%&'()*+,-./:;<=>?@[\]^_`{│}~``   |
|                           | `Custom Name(s)`             | `Any string`                            |
| `[password_char_presets]` | `Letters+Digits+Punctuation` | `upper lower digits punctuation`        |
|                           | `Letters+Digits`             | `upper lower digits`                    |
|                           | `Letters`                    | `upper lower`                           |
|                           | `Digits`                     | `digits`                                |
|                           | `Custom Name(s)`             | `Any combo of [password_chars] entries` |

# FILES

~/.config/bwm/config.ini

# AUTHOR

Scott Hansen - <firecat4153@gmail.com>

# COPYRIGHT  

MIT

# SEE ALSO

More information available at https://github.com/firecat53/bitwarden-menu
