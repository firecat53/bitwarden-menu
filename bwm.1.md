---
title: Bitwarden-menu
section: 1
header: User Manual
footer: Bitwarden-menu v0.5.4
date: 2026-08-15
---

# NAME

bitwarden-menu - Fully featured Dmenu/Rofi/Bemenu frontend for autotype and
managing of Bitwarden/Vaultwarden vaults.

# SYNOPSIS

**bitwarden-menu** [**--help**] [**--version**] [**--vault** URL] [**--login** email] [**--lock**] [**--autotype** pattern] [**--clipboard**] [**--config** PATH] [**--show** term] [**--field** name] [**--foreground**]

# DESCRIPTION

**Bitwarden-menu** is a fast and minimal application to facilitate password entry and
manage most aspects of Bitwarden/Vaultwarden vaults.

# OPTIONS

**-v**, **--vault** Vault URL. Use with **-l** when multiple accounts share the same server.

**-l**, **--login**  Login email address. Optional when only one account exists on
the server. Required with **-v** when multiple accounts share the same server.

**-k**, **--lock**  Lock vault

**-a**, **--autotype**  Autotype sequence from
https://keepass.info/help/base/autotype.html#autoseq . Overrides global default
from config.ini for current vault.

**-C**, **--clipboard** Select to clipboard

**-s**, **--show** Search term. Outputs the matched entry's password (default)
or the fields selected by **--field** to stdout, or to the clipboard with
**--clipboard**. Requires a single matching entry

**-f**, **--field** Field to output with **--show**. Repeat for multiple fields,
which are output one per line in the order given. Case and separator
insensitive. One of the autotype placeholders *title*, *username*, *password*,
*url*, *notes*, *totp*, *cardnum*; any card or identity field name such as
*security code*, *expiration month* or *ssn*; `S:<name>` for a custom field; or
*all* for every field that has a value, labeled. Defaults to *password*

**-F**, **--foreground** Run the daemon in the foreground instead of detaching.
For troubleshooting, and for service managers expecting Type=simple

**-c**, **--config** _PATH_
Path to config file. Supports absolute paths, relative paths, and tilde expansion.
Default: ~/.config/bwm/config.ini

**-V**, **--version**  Print version and exit

**-h**, **--help**  Print help and exit

# DAEMON

**bwm** starts a background daemon on first use and returns immediately. The
daemon holds the unlocked vault so later invocations do not pay the unlock cost
again, and exits after *session_timeout_min* of inactivity or on **--lock**.

With **DISPLAY** and **WAYLAND_DISPLAY** unset, credentials are prompted for on
the terminal rather than through a launcher, so the full login - including 2FA
and *client_secret* - works on a headless machine.

# EXAMPLES

    bwm
    bwm -v https://vault.mydomain.net -l user@domain.com -a '{TOTP}{ENTER}'
    bwm -s 'ssh github'
    bwm -s 'ssh github' -f username -f password
    bwm -s visa -f 'security code'
    bwm -s 'ssh github' -f all
    bwm --foreground

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
|                           | `email_n`                    | None                                    |
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

# ENVIRONMENT

**BWM_LOG_LEVEL**
Log level for _~/.cache/bwm.log_. One of *critical*, *error*, *warning*, *info*
or *debug*; an unrecognized value falls back to the default and says so in the
log. Default *warning*; set to *debug* to record each vault's status check,
unlock and entry load. A backgrounded daemon sends its output to /dev/null, so
this and **--foreground** are how to see what it is doing.

The log records vault entry names, item ids and server URLs, but never
passwords, TOTP seeds, session tokens or vault contents. It is created mode
0600.

**DISPLAY**, **WAYLAND_DISPLAY**
When neither is set, bwm prompts on the terminal instead of through a launcher,
which is what makes the initial login, 2FA included, work on a headless machine.

# FILES

~/.config/bwm/config.ini

~/.cache/bwm.log

# AUTHOR

Scott Hansen - <tech@firecat53.net>

# COPYRIGHT  

MIT

# SEE ALSO

More information available at https://github.com/firecat53/bitwarden-menu
