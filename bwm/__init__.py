"""Set global variables. Read the config file. Create default config file if one
doesn't exist.

"""
import configparser
import locale
import logging
import os
import shlex
import sys
from os.path import exists, join
from subprocess import run, DEVNULL

from bwm.menu import dmenu_err
from xdg_base_dirs import xdg_cache_home, xdg_config_home, xdg_data_home

AUTH_FILE = join(xdg_cache_home(), ".bwm-auth")
CONF_FILE = join(xdg_config_home(), "bwm/config.ini")
DATA_HOME = join(xdg_data_home(), "bwm")
SECRET_VALID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
CLIPBOARD = False
CLIPBOARD_CMD = "true"
if os.environ.get('WAYLAND_DISPLAY'):
    clips = ['wl-copy -o']
else:
    clips = ["xsel -b", "xclip -l 1 -selection clip"]
for clip in clips:
    try:
        _ = run(shlex.split(clip), check=False, stdout=DEVNULL, stderr=DEVNULL, input="")
        CLIPBOARD_CMD = clip
        break
    except OSError:
        continue
if CLIPBOARD_CMD == "true":
    dmenu_err(f"{' or '.join([shlex.split(i)[0] for i in clips])} needed for clipboard support")

logging.basicConfig(filename=join(xdg_cache_home(), "bwm.log"), level=logging.ERROR)
LOGGER = logging.getLogger("bwm")

ENV = os.environ.copy()
ENC = locale.getpreferredencoding()
SESSION_TIMEOUT_DEFAULT_MIN = 360
SEQUENCE = "{USERNAME}{TAB}{PASSWORD}{ENTER}"
if not exists(CONF_FILE):
    CONF = configparser.ConfigParser()
    try:
        os.mkdir(os.path.dirname(CONF_FILE))
    except OSError:
        pass
    with open(CONF_FILE, 'w', encoding=ENC) as conf_file:
        CONF.add_section('dmenu')
        CONF.set('dmenu', 'dmenu_command', 'dmenu')
        CONF.add_section('dmenu_passphrase')
        CONF.set('dmenu_passphrase', 'obscure', 'True')
        CONF.set('dmenu_passphrase', 'obscure_color', '#222222')
        CONF.add_section('vault')
        CONF.set('vault', 'server_1', '')
        CONF.set('vault', 'email_1', '')
        CONF.set('vault', 'twofactor_1', '')
        CONF.set('vault', 'session_timeout_min ', str(SESSION_TIMEOUT_DEFAULT_MIN))
        CONF.set('vault', 'autotype_default', SEQUENCE)
        CONF.write(conf_file)
CONF = configparser.ConfigParser()
try:
    CONF.read(CONF_FILE)
except configparser.ParsingError as err:
    dmenu_err(f"Config file error: {err}")
    sys.exit()
if CONF.has_option('dmenu', 'dmenu_command'):
    command = shlex.split(CONF.get('dmenu', 'dmenu_command'))
if "-l" in command:
    MAX_LEN = int(command[command.index("-l") + 1])
elif "-L" in command:
    MAX_LEN = int(command[command.index("-L") + 1])
else:
    MAX_LEN = 24
if CONF.has_option("vault", "session_timeout_min"):
    SESSION_TIMEOUT_MIN = int(CONF.get("vault", "session_timeout_min"))
else:
    SESSION_TIMEOUT_MIN = SESSION_TIMEOUT_DEFAULT_MIN
if CONF.has_option('vault', 'autotype_default'):
    SEQUENCE = CONF.get("vault", "autotype_default")
if CONF.has_option("vault", "type_library"):
    if CONF.get("vault", "type_library") == "xdotool":
        try:
            run(['xdotool', 'version'], check=False, stdout=DEVNULL)
        except OSError:
            dmenu_err("Xdotool not installed.\n"
                      "Please install or remove that option from config.ini")
            sys.exit()
    elif CONF.get("vault", "type_library") == "ydotool":
        try:
            run(['ydotool'], check=False, stdout=DEVNULL)
        except OSError:
            dmenu_err("Ydotool not installed.\n"
                      "Please install or remove that option from config.ini")
            sys.exit()
    elif CONF.get("vault", "type_library") == "wtype":
        try:
            run(['wtype'], check=False, stdout=DEVNULL, stderr=DEVNULL)
        except OSError:
            dmenu_err("Wtype not installed.\n"
                      "Please install or remove that option from config.ini")
            sys.exit()

LOGIN = {"Username": "username",
         "Password": "password",
         "TOTP": "totp"}
CARD = {"Cardholder Name": "cardholderName",
        "Brand": "brand",
        "Number": "number",
        "Expiration Month": "expMonth",
        "Expiration Year": "expYear",
        "Security Code": "code"}
IDENTITY = {"Title": "title",
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
            "License Number": "licenseNumber"}

# vim: set et ts=4 sw=4 :
