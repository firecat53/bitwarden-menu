"""Set global variables. Read the config file. Create default config file if one
doesn't exist.

"""
import configparser
import locale
import logging
import os
import sys
from os.path import exists, expanduser
from subprocess import call

from bwm.bwm import dmenu_err

AUTH_FILE = expanduser("~/.cache/.bwm-auth")
CONF_FILE = expanduser("~/.config/bwm/config.ini")

logging.basicConfig(filename=expanduser("~/.cache/bwm.log"), level=logging.DEBUG)
LOGGER = logging.getLogger("bwm")

ENV = os.environ.copy()
ENV['LC_ALL'] = 'C'
ENC = locale.getpreferredencoding()
SESSION_TIMEOUT_DEFAULT_MIN = 360
SEQUENCE = "{USERNAME}{TAB}{PASSWORD}{ENTER}"
CONF = configparser.ConfigParser()
if not exists(CONF_FILE):
    try:
        os.mkdir(os.path.dirname(CONF_FILE))
    except OSError:
        pass
    with open(CONF_FILE, 'w') as conf_file:
        CONF.add_section('dmenu')
        CONF.set('dmenu', 'dmenu_command', 'dmenu')
        CONF.add_section('dmenu_passphrase')
        CONF.set('dmenu_passphrase', 'nf', '#222222')
        CONF.set('dmenu_passphrase', 'nb', '#222222')
        CONF.set('dmenu_passphrase', 'rofi_obscure', 'True')
        CONF.add_section('vault')
        CONF.set('vault', 'server_1', '')
        CONF.set('vault', 'email_1', '')
        CONF.set('vault', 'session_timeout_min ', str(SESSION_TIMEOUT_DEFAULT_MIN))
        CONF.set('vault', 'autotype_default', SEQUENCE)
        CONF.write(conf_file)
try:
    CONF.read(CONF_FILE)
except configparser.ParsingError as err:
    dmenu_err("Config file error: {}".format(err))
    sys.exit()
if CONF.has_option("vault", "session_timeout_min"):
    SESSION_TIMEOUT_MIN = int(CONF.get("vault", "session_timeout_min"))
else:
    SESSION_TIMEOUT_MIN = SESSION_TIMEOUT_DEFAULT_MIN
if CONF.has_option("dmenu", "l"):
    DMENU_LEN = int(CONF.get("dmenu", "l"))
else:
    DMENU_LEN = 24
if CONF.has_option('vault', 'autotype_default'):
    SEQUENCE = CONF.get("vault", "autotype_default")
if CONF.has_option("vault", "type_library"):
    if CONF.get("vault", "type_library") == "xdotool":
        try:
            call(['xdotool', 'version'])
        except OSError:
            dmenu_err("Xdotool not installed.\n"
                      "Please install or remove that option from config.ini")
            sys.exit()
    elif CONF.get("vault", "type_library") == "ydotool":
        try:
            call(['ydotool'])
        except OSError:
            dmenu_err("Ydotool not installed.\n"
                      "Please install or remove that option from config.ini")
            sys.exit()

# vim: set et ts=4 sw=4 :
