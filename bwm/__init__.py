"""Set global variables. Read the config file. Create default config file if one
doesn't exist.

"""

import configparser
import locale
import logging
import os
import shlex
import sys
import tempfile
from os.path import exists, join
from subprocess import run, DEVNULL

from xdg_base_dirs import xdg_cache_home, xdg_config_home, xdg_data_home

# Single source of truth for the version. pyproject.toml, flake.nix and the
# man page footer all read this string; bump it with `make release`.
__version__ = "0.5.4"

logger = logging.getLogger("bwm")
logging.basicConfig(
    filename=join(xdg_cache_home(), "bwm.log"), level=logging.WARNING
)


def get_runtime_dir():
    """Get the runtime directory for storing authentication files.

    Uses $XDG_RUNTIME_DIR/bwm/ if available otherwise falls back to $TMPDIR/bwm-<uid>/.

    Returns: Path runtime directory path

    """
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        runtime_dir = join(xdg_runtime, "bwm")
    else:
        runtime_dir = join(tempfile.gettempdir(), f"bwm-{os.getuid()}")
    if not exists(runtime_dir):
        os.makedirs(runtime_dir, mode=0o700)
    return runtime_dir


AUTH_FILE = join(get_runtime_dir(), ".bwm-auth")
CONF_FILE = join(xdg_config_home(), "bwm/config.ini")
DATA_HOME = join(xdg_data_home(), "bwm")
SECRET_VALID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
CLIPBOARD = False
CLIPBOARD_CMD = ""
ENV = os.environ.copy()
ENC = locale.getpreferredencoding()
SESSION_TIMEOUT_DEFAULT_MIN = 360
SESSION_TIMEOUT_MIN = SESSION_TIMEOUT_DEFAULT_MIN
SEQUENCE = "{USERNAME}{TAB}{PASSWORD}{ENTER}"
MAX_LEN = 24
CONF = configparser.ConfigParser()


def reload_config(conf_file=None):
    """Reload config file. Primarily for use with the --config flag.

    Args: conf_file - os.path or None for default

    """
    # pylint: disable=global-statement
    global CONF, MAX_LEN, SESSION_TIMEOUT_MIN, SEQUENCE, CLIPBOARD_CMD
    # pylint: enable=global-statement

    CONF = configparser.ConfigParser()
    conf_file = conf_file if conf_file is not None else CONF_FILE
    if not exists(conf_file):
        conf_dir = os.path.dirname(conf_file)
        try:
            os.makedirs(conf_dir, exist_ok=True)
        except OSError as err:
            logger.error(f"Cannot create config directory {conf_dir}: {err}")
            sys.exit(1)
        with open(conf_file, "w", encoding=ENC) as cfile:
            CONF.add_section("dmenu")
            CONF.set("dmenu", "dmenu_command", "dmenu")
            CONF.add_section("dmenu_passphrase")
            CONF.set("dmenu_passphrase", "obscure", "True")
            CONF.set("dmenu_passphrase", "obscure_color", "#222222")
            CONF.add_section("vault")
            CONF.set("vault", "server_1", "")
            CONF.set("vault", "email_1", "")
            CONF.set("vault", "twofactor_1", "")
            CONF.set(
                "vault", "session_timeout_min ", str(SESSION_TIMEOUT_DEFAULT_MIN)
            )
            CONF.set("vault", "autotype_default", SEQUENCE)
            CONF.write(cfile)
    try:
        CONF.read(conf_file)
    except configparser.ParsingError as err:
        logger.warning(f"Config file error: {err}")
        sys.exit(1)

    MAX_LEN = 24
    if CONF.has_option("dmenu", "dmenu_command"):
        command = shlex.split(CONF.get("dmenu", "dmenu_command"))
        if "-l" in command:
            MAX_LEN = int(command[command.index("-l") + 1])
        elif "-L" in command:
            MAX_LEN = int(command[command.index("-L") + 1])

    if CONF.has_option("vault", "session_timeout_min"):
        SESSION_TIMEOUT_MIN = int(CONF.get("vault", "session_timeout_min"))
    else:
        SESSION_TIMEOUT_MIN = SESSION_TIMEOUT_DEFAULT_MIN
    if CONF.has_option("vault", "autotype_default"):
        SEQUENCE = CONF.get("vault", "autotype_default")
    if CONF.has_option("vault", "type_library"):
        type_library = CONF.get("vault", "type_library")
        for lib in (["xdotool", "version"], ["ydotool"], ["wtype"]):
            if lib[0] != type_library:
                continue
            try:
                run(lib, check=False, stdout=DEVNULL, stderr=DEVNULL)
            except OSError:
                logger.warning(
                    f"{lib[0]} not installed. Please install {lib[0]} or update config.ini"
                )

    # Set up clipboard command
    if os.environ.get("WAYLAND_DISPLAY"):
        clips = ["wl-copy"]
    else:
        clips = ["xsel -b", "xclip -selection clip"]
    for clip in clips:
        try:
            _ = run(
                shlex.split(clip),
                check=False,
                stdout=DEVNULL,
                stderr=DEVNULL,
                input="",
            )
            CLIPBOARD_CMD = clip
            break
        except (OSError, FileNotFoundError):
            CLIPBOARD_CMD = ""
            logger.warning(
                "Clipboard support disabled. Need wl-clipboard, xsel or xclip installed"
            )

LOGIN = {"Username": "username", "Password": "password", "TOTP": "totp"}
CARD = {
    "Cardholder Name": "cardholderName",
    "Brand": "brand",
    "Number": "number",
    "Expiration Month": "expMonth",
    "Expiration Year": "expYear",
    "Security Code": "code",
}
IDENTITY = {
    "Title": "title",
    "First Name": "firstName",
    "Middle Name": "middleName",
    "Last Name": "lastName",
    "Address 1": "address1",
    "Address 2": "address2",
    "Address 3": "address3",
    "City": "city",
    "State": "state",
    "Postal Code": "postalCode",
    "Country": "country",
    "Company": "company",
    "Email": "email",
    "Phone": "phone",
    "SSN": "ssn",
    "Username": "username",
    "Passport Number": "passportNumber",
    "License Number": "licenseNumber",
}

# vim: set et ts=4 sw=4 :
