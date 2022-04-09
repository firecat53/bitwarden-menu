"""Module to handling typing using pynput, xdotool, ydotool or wtype

"""
# flake8: noqa
import re
import time
from subprocess import call

from bwm import CONF, SEQUENCE
from bwm.menu import dmenu_err
from bwm.totp import gen_otp


def autotype_seq(entry):
    """Return value for autotype sequence

        Args: entry - dict
        Return: string

    """
    return next((i.get('value') for i in entry['fields'] if i.get('name') == 'autotype'), "")


def autotype_index(entry):
    """Returns index of the autotype field list in entry['fields']

        Args: entry - dict
        Returns: int  entry['fields'][autotype_index(entry] = \
                {"name": "autotype", "value": "{USERNAME}{TAB}{PASSWORD}{ENTER}"}

    """
    return next((entry['fields'].index(i) for i in entry['fields'] if
                 i.get('name') == 'autotype'))


def tokenize_autotype(autotype):
    """Process the autotype sequence

    Args: autotype - string
    Returns: tokens - generator ((token, if_special_char T/F), ...)

    """
    while autotype:
        opening_idx = -1
        for char in "{+^%~@":
            idx = autotype.find(char)
            if idx != -1 and (opening_idx == -1 or idx < opening_idx):
                opening_idx = idx

        if opening_idx == -1:
            # found the end of the string without further opening braces or
            # other characters
            yield autotype, False
            return

        if opening_idx > 0:
            yield autotype[:opening_idx], False

        if autotype[opening_idx] in "+^%~@":
            yield autotype[opening_idx], True
            autotype = autotype[opening_idx + 1:]
            continue

        closing_idx = autotype.find('}')
        if closing_idx == -1:
            dmenu_err("Unable to find matching right brace (}) while" +
                      f"tokenizing auto-type string: {autotype}\n")
            return
        if closing_idx == opening_idx + 1 and closing_idx + 1 < len(autotype) \
                and autotype[closing_idx + 1] == '}':
            yield "{}}", True
            autotype = autotype[closing_idx + 2:]
            continue
        yield autotype[opening_idx:closing_idx + 1], True
        autotype = autotype[closing_idx + 1:]


def token_command(token):
    """When token denotes a special command, this function provides a callable
    implementing its behaviour.

    """
    cmd = None

    def _check_delay():
        match = re.match(r'{DELAY (\d+)}', token)
        if match:
            delay = match.group(1)
            nonlocal cmd
            cmd = lambda t=delay: time.sleep(int(t) / 1000)
            return True
        return False

    if _check_delay():  # {DELAY x}
        return cmd
    return None


PLACEHOLDER_AUTOTYPE_TOKENS = {
    "{TITLE}"   : lambda e: e['name'],
    "{USERNAME}": lambda e: e['login']['username'],
    "{URL}"     : lambda e: e['login']['url'],
    "{PASSWORD}": lambda e: e['login']['password'],
    "{NOTES}"   : lambda e: e['notes'],
    "{CARDNUM}" : lambda e: e['card']['number'],
    "{TOTP}"    : lambda e: gen_otp(e['login']['totp']),
}

STRING_AUTOTYPE_TOKENS = {
    "{PLUS}"      : '+',
    "{PERCENT}"   : '%',
    "{CARET}"     : '^',
    "{TILDE}"     : '~',
    "{LEFTPAREN}" : '(',
    "{RIGHTPAREN}": ')',
    "{LEFTBRACE}" : '{',
    "{RIGHTBRACE}": '}',
    "{AT}"        : '@',
    "{+}"         : '+',
    "{%}"         : '%',
    "{^}"         : '^',
    "{~}"         : '~',
    "{(}"         : '(',
    "{)}"         : ')',
    "{[}"         : '[',
    "{]}"         : ']',
    "{{}"         : '{',
    "{}}"         : '}',
}


def type_entry_pynput(entry, tokens):  # pylint: disable=too-many-branches
    """Use pynput to auto-type the selected entry

    """
    try:
        from pynput import keyboard
        from .tokens_pynput import AUTOTYPE_TOKENS
    except ModuleNotFoundError:
        return
    kbd = keyboard.Controller()
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    try:
                        kbd.type(to_type)
                    except kbd.InvalidCharacterException:
                        dmenu_err("Unable to type string...bad character.\n"
                                  "Try setting `type_library = xdotool` in config.ini")
                        return
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                try:
                    kbd.type(to_type)
                except kbd.InvalidCharacterException:
                    dmenu_err("Unable to type string...bad character.\n"
                              "Try setting `type_library = xdotool` in config.ini")
                    return
            elif token in AUTOTYPE_TOKENS:
                to_tap = AUTOTYPE_TOKENS[token]
                kbd.tap(to_tap)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    kbd.tap(to_tap)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (pynput): {token}")
                return
        else:
            try:
                kbd.type(token)
            except kbd.InvalidCharacterException:
                dmenu_err("Unable to type string...bad character.\n"
                          "Try setting `type_library = xdotool` in config.ini")
                return


def type_entry_xdotool(entry, tokens):
    """Auto-type entry entry using xdotool

    """
    enter_idx = True
    from .tokens_xdotool import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['xdotool', 'type', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['xdotool', 'type', to_type])
            elif token in AUTOTYPE_TOKENS:
                cmd = ['xdotool'] + AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['xdotool'] + AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (xdotool): {token}")
                return
        else:
            call(['xdotool', 'type', token])


def type_entry_ydotool(entry, tokens):
    """Auto-type entry entry using ydotool

    """
    enter_idx = True
    from .tokens_ydotool import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['ydotool', 'type', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['ydotool', 'type', to_type])
            elif token in AUTOTYPE_TOKENS:
                cmd = ['ydotool'] + AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['ydotool'] + AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err(f"Unsupported auto-type token (ydotool): {token}")
                return
        else:
            call(['ydotool', 'type', token])


def type_entry_wtype(entry, tokens):
    """Auto-type entry entry using wtype

    """
    from .tokens_wtype import AUTOTYPE_TOKENS
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()  # pylint: disable=not-callable
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['wtype', '--', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['wtype', '--', to_type])
            elif token in AUTOTYPE_TOKENS:
                cmd = ['wtype', '-k', AUTOTYPE_TOKENS[token]]
                call(cmd)
            else:
                dmenu_err(f"Unsupported auto-type token (wtype): {token}")
                return
        else:
            call(['wtype', '--', token])


def type_entry(entry):
    """Pick which library to use to type strings

    Defaults to pynput

    Args: entry - dict

    """
    # Don't autotype anything except for login and cards - for now TODO
    if entry['type'] not in (1, 3):
        dmenu_err("Autotype currently disabled for this type of entry")
        return
    sequence = autotype_seq(entry)
    if sequence == 'False':
        dmenu_err("Autotype disabled for this entry")
        return
    if not sequence or sequence == 'None':
        sequence = SEQUENCE
        if entry['type'] == 3:
            sequence = "{CARDNUM}"
    tokens = tokenize_autotype(sequence)

    library = 'pynput'
    if CONF.has_option('vault', 'type_library'):
        library = CONF.get('vault', 'type_library')
    if library == 'xdotool':
        type_entry_xdotool(entry, tokens)
    elif library == 'ydotool':
        type_entry_ydotool(entry, tokens)
    elif library == 'wtype':
        type_entry_wtype(entry, tokens)
    else:
        type_entry_pynput(entry, tokens)


def type_text(data):
    """Type the given text data

    """
    library = 'pynput'
    if CONF.has_option('vault', 'type_library'):
        library = CONF.get('vault', 'type_library')
    if library == 'xdotool':
        call(['xdotool', 'type', data])
    elif library == 'ydotool':
        call(['ydotool', 'type', data])
    elif library == 'wtype':
        call(['wtype', '--', data])
    else:
        try:
            from pynput import keyboard
        except ModuleNotFoundError:
            return
        kbd = keyboard.Controller()
        try:
            kbd.type(data)
        except kbd.InvalidCharacterException:
            dmenu_err("Unable to type string...bad character.\n"
                      "Try setting `type_library = xdotool` in config.ini")

# vim: set et ts=4 sw=4 :
