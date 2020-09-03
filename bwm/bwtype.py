"""Module to handling typing using pynput or xdotool

"""
import re
import time
from subprocess import call

from pykeyboard import PyKeyboard
from pymouse.x11 import X11Error

from bwm import CONF, SEQUENCE
from bwm.bwm import dmenu_err

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
                      "tokenizing auto-type string: %s\n" % (autotype))
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
    "{TITLE}"   : lambda e: e.title,
    "{USERNAME}": lambda e: e.username,
    "{URL}"     : lambda e: e.url,
    "{PASSWORD}": lambda e: e.password,
    "{NOTES}"   : lambda e: e.notes,
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

PYUSERINPUT_AUTOTYPE_TOKENS = {
    "{TAB}"       : lambda kbd: kbd.tab_key,
    "{ENTER}"     : lambda kbd: kbd.return_key,
    "~"           : lambda kbd: kbd.return_key,
    "{UP}"        : lambda kbd: kbd.up_key,
    "{DOWN}"      : lambda kbd: kbd.down_key,
    "{LEFT}"      : lambda kbd: kbd.left_key,
    "{RIGHT}"     : lambda kbd: kbd.right_key,
    "{INSERT}"    : lambda kbd: kbd.insert_key,
    "{INS}"       : lambda kbd: kbd.insert_key,
    "{DELETE}"    : lambda kbd: kbd.delete_key,
    "{DEL}"       : lambda kbd: kbd.delete_key,
    "{HOME}"      : lambda kbd: kbd.home_key,
    "{END}"       : lambda kbd: kbd.end_key,
    "{PGUP}"      : lambda kbd: kbd.page_up_key,
    "{PGDN}"      : lambda kbd: kbd.page_down_key,
    "{SPACE}"     : lambda kbd: kbd.space_key,
    "{BACKSPACE}" : lambda kbd: kbd.backspace_key,
    "{BS}"        : lambda kbd: kbd.backspace_key,
    "{BKSP}"      : lambda kbd: kbd.backspace_key,
    "{BREAK}"     : lambda kbd: kbd.break_key,
    "{CAPSLOCK}"  : lambda kbd: kbd.caps_lock_key,
    "{ESC}"       : lambda kbd: kbd.escape_key,
    "{WIN}"       : lambda kbd: kbd.windows_l_key,
    "{LWIN}"      : lambda kbd: kbd.windows_l_key,
    "{RWIN}"      : lambda kbd: kbd.windows_r_key,
    "{APPS}"      : lambda kbd: kbd.apps_key,
    "{HELP}"      : lambda kbd: kbd.help_key,
    "{NUMLOCK}"   : lambda kbd: kbd.num_lock_key,
    "{PRTSC}"     : lambda kbd: kbd.print_screen_key,
    "{SCROLLLOCK}": lambda kbd: kbd.scroll_lock_key,
    "{F1}"        : lambda kbd: kbd.function_keys[1],
    "{F2}"        : lambda kbd: kbd.function_keys[2],
    "{F3}"        : lambda kbd: kbd.function_keys[3],
    "{F4}"        : lambda kbd: kbd.function_keys[4],
    "{F5}"        : lambda kbd: kbd.function_keys[5],
    "{F6}"        : lambda kbd: kbd.function_keys[6],
    "{F7}"        : lambda kbd: kbd.function_keys[7],
    "{F8}"        : lambda kbd: kbd.function_keys[8],
    "{F9}"        : lambda kbd: kbd.function_keys[9],
    "{F10}"       : lambda kbd: kbd.function_keys[10],
    "{F11}"       : lambda kbd: kbd.function_keys[11],
    "{F12}"       : lambda kbd: kbd.function_keys[12],
    "{F13}"       : lambda kbd: kbd.function_keys[13],
    "{F14}"       : lambda kbd: kbd.function_keys[14],
    "{F15}"       : lambda kbd: kbd.function_keys[15],
    "{F16}"       : lambda kbd: kbd.function_keys[16],
    "{ADD}"       : lambda kbd: kbd.numpad_keys['Add'],
    "{SUBTRACT}"  : lambda kbd: kbd.numpad_keys['Subtract'],
    "{MULTIPLY}"  : lambda kbd: kbd.numpad_keys['Multiply'],
    "{DIVIDE}"    : lambda kbd: kbd.numpad_keys['Divide'],
    "{NUMPAD0}"   : lambda kbd: kbd.numpad_keys['0'],
    "{NUMPAD1}"   : lambda kbd: kbd.numpad_keys['1'],
    "{NUMPAD2}"   : lambda kbd: kbd.numpad_keys['2'],
    "{NUMPAD3}"   : lambda kbd: kbd.numpad_keys['3'],
    "{NUMPAD4}"   : lambda kbd: kbd.numpad_keys['4'],
    "{NUMPAD5}"   : lambda kbd: kbd.numpad_keys['5'],
    "{NUMPAD6}"   : lambda kbd: kbd.numpad_keys['6'],
    "{NUMPAD7}"   : lambda kbd: kbd.numpad_keys['7'],
    "{NUMPAD8}"   : lambda kbd: kbd.numpad_keys['8'],
    "{NUMPAD9}"   : lambda kbd: kbd.numpad_keys['9'],
    "+"           : lambda kbd: kbd.shift_key,
    "^"           : lambda kbd: kbd.control_key,
    "%"           : lambda kbd: kbd.alt_key,
    "@"           : lambda kbd: kbd.windows_l_key,
}


def type_entry_pyuserinput(entry, tokens):
    """Use PyUserInput to auto-type the selected entry

    """
    kbd = PyKeyboard()
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    try:
                        kbd.type_string(to_type)
                    except (X11Error, KeyError):
                        dmenu_err("Unable to type string...bad character.\n"
                                  "Try setting `type_library = xdotool` in config.ini")
                        return
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                try:
                    kbd.type_string(to_type)
                except (X11Error, KeyError):
                    dmenu_err("Unable to type string...bad character.\n"
                              "Try setting `type_library = xdotool` in config.ini")
                    return
            elif token in PYUSERINPUT_AUTOTYPE_TOKENS:
                to_tap = PYUSERINPUT_AUTOTYPE_TOKENS[token](kbd)
                kbd.tap_key(to_tap)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    kbd.tap_key(to_tap)
                    enter_idx = False
            else:
                dmenu_err("Unsupported auto-type token (pyuserinput): \"%s\"" % (token))
                return
        else:
            try:
                kbd.type_string(token)
            except (X11Error, KeyError):
                dmenu_err("Unable to type string...bad character.\n"
                          "Try setting `type_library = xdotool` in config.ini")
                return


XDOTOOL_AUTOTYPE_TOKENS = {
    "{TAB}"       : ['key', 'Tab'],
    "{ENTER}"     : ['key', 'Return'],
    "~"           : ['key', 'Return'],
    "{UP}"        : ['key', 'Up'],
    "{DOWN}"      : ['key', 'Down'],
    "{LEFT}"      : ['key', 'Left'],
    "{RIGHT}"     : ['key', 'Right'],
    "{INSERT}"    : ['key', 'Insert'],
    "{INS}"       : ['key', 'Insert'],
    "{DELETE}"    : ['key', 'Delete'],
    "{DEL}"       : ['key', 'Delete'],
    "{HOME}"      : ['key', 'Home'],
    "{END}"       : ['key', 'End'],
    "{PGUP}"      : ['key', 'Page_Up'],
    "{PGDN}"      : ['key', 'Page_Down'],
    "{SPACE}"     : ['type', ' '],
    "{BACKSPACE}" : ['key', 'BackSpace'],
    "{BS}"        : ['key', 'BackSpace'],
    "{BKSP}"      : ['key', 'BackSpace'],
    "{BREAK}"     : ['key', 'Break'],
    "{CAPSLOCK}"  : ['key', 'Caps_Lock'],
    "{ESC}"       : ['key', 'Escape'],
    "{WIN}"       : ['key', 'Super'],
    "{LWIN}"      : ['key', 'Super_L'],
    "{RWIN}"      : ['key', 'Super_R'],
    # "{APPS}"      : ['key', ''],
    # "{HELP}"      : ['key', ''],
    "{NUMLOCK}"   : ['key', 'Num_Lock'],
    # "{PRTSC}"     : ['key', ''],
    "{SCROLLLOCK}": ['key', 'Scroll_Lock'],
    "{F1}"        : ['key', 'F1'],
    "{F2}"        : ['key', 'F2'],
    "{F3}"        : ['key', 'F3'],
    "{F4}"        : ['key', 'F4'],
    "{F5}"        : ['key', 'F5'],
    "{F6}"        : ['key', 'F6'],
    "{F7}"        : ['key', 'F7'],
    "{F8}"        : ['key', 'F8'],
    "{F9}"        : ['key', 'F9'],
    "{F10}"       : ['key', 'F10'],
    "{F11}"       : ['key', 'F11'],
    "{F12}"       : ['key', 'F12'],
    "{F13}"       : ['key', 'F13'],
    "{F14}"       : ['key', 'F14'],
    "{F15}"       : ['key', 'F15'],
    "{F16}"       : ['key', 'F16'],
    "{ADD}"       : ['key', 'KP_Add'],
    "{SUBTRACT}"  : ['key', 'KP_Subtract'],
    "{MULTIPLY}"  : ['key', 'KP_Multiply'],
    "{DIVIDE}"    : ['key', 'KP_Divide'],
    "{NUMPAD0}"   : ['key', 'KP_0'],
    "{NUMPAD1}"   : ['key', 'KP_1'],
    "{NUMPAD2}"   : ['key', 'KP_2'],
    "{NUMPAD3}"   : ['key', 'KP_3'],
    "{NUMPAD4}"   : ['key', 'KP_4'],
    "{NUMPAD5}"   : ['key', 'KP_5'],
    "{NUMPAD6}"   : ['key', 'KP_6'],
    "{NUMPAD7}"   : ['key', 'KP_7'],
    "{NUMPAD8}"   : ['key', 'KP_8'],
    "{NUMPAD9}"   : ['key', 'KP_9'],
    "+"           : ['key', 'Shift'],
    "^"           : ['Key', 'Ctrl'],
    "%"           : ['key', 'Alt'],
    "@"           : ['key', 'Super'],
}


def type_entry_xdotool(entry, tokens):
    """Auto-type entry entry using xdotool

    """
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['xdotool', 'type', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['xdotool', 'type', to_type])
            elif token in XDOTOOL_AUTOTYPE_TOKENS:
                cmd = ['xdotool'] + XDOTOOL_AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['xdotool'] + XDOTOOL_AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err("Unsupported auto-type token (xdotool): \"%s\"" % (token))
                return
        else:
            call(['xdotool', 'type', token])


YDOTOOL_AUTOTYPE_TOKENS = {
    "{TAB}"       : ['key', 'TAB'],
    "{ENTER}"     : ['key', 'ENTER'],
    "~"           : ['key', 'Return'],
    "{UP}"        : ['key', 'UP'],
    "{DOWN}"      : ['key', 'DOWN'],
    "{LEFT}"      : ['key', 'LEFT'],
    "{RIGHT}"     : ['key', 'RIGHT'],
    "{INSERT}"    : ['key', 'INSERT'],
    "{INS}"       : ['key', 'INSERT'],
    "{DELETE}"    : ['key', 'DELETE'],
    "{DEL}"       : ['key', 'DELETE'],
    "{HOME}"      : ['key', 'HOME'],
    "{END}"       : ['key', 'END'],
    "{PGUP}"      : ['key', 'PAGEUP'],
    "{PGDN}"      : ['key', 'PAGEDOWN'],
    "{SPACE}"     : ['type', ' '],
    "{BACKSPACE}" : ['key', 'BACKSPACE'],
    "{BS}"        : ['key', 'BACKSPACE'],
    "{BKSP}"      : ['key', 'BACKSPACE'],
    "{BREAK}"     : ['key', 'BREAK'],
    "{CAPSLOCK}"  : ['key', 'CAPSLOCK'],
    "{ESC}"       : ['key', 'ESC'],
    # "{WIN}"       : ['key', 'Super'],
    # "{LWIN}"      : ['key', 'Super_L'],
    # "{RWIN}"      : ['key', 'Super_R'],
    # "{APPS}"      : ['key', ''],
    # "{HELP}"      : ['key', ''],
    "{NUMLOCK}"   : ['key', 'NUMLOCK'],
    # "{PRTSC}"     : ['key', ''],
    "{SCROLLLOCK}": ['key', 'SCROLLLOCK'],
    "{F1}"        : ['key', 'F1'],
    "{F2}"        : ['key', 'F2'],
    "{F3}"        : ['key', 'F3'],
    "{F4}"        : ['key', 'F4'],
    "{F5}"        : ['key', 'F5'],
    "{F6}"        : ['key', 'F6'],
    "{F7}"        : ['key', 'F7'],
    "{F8}"        : ['key', 'F8'],
    "{F9}"        : ['key', 'F9'],
    "{F10}"       : ['key', 'F10'],
    "{F11}"       : ['key', 'F11'],
    "{F12}"       : ['key', 'F12'],
    "{F13}"       : ['key', 'F13'],
    "{F14}"       : ['key', 'F14'],
    "{F15}"       : ['key', 'F15'],
    "{F16}"       : ['key', 'F16'],
    "{ADD}"       : ['key', 'KPPLUS'],
    "{SUBTRACT}"  : ['key', 'KPMINUS'],
    "{MULTIPLY}"  : ['key', 'KPASTERISK'],
    "{DIVIDE}"    : ['key', 'KPSLASH'],
    "{NUMPAD0}"   : ['key', 'KP0'],
    "{NUMPAD1}"   : ['key', 'KP1'],
    "{NUMPAD2}"   : ['key', 'KP2'],
    "{NUMPAD3}"   : ['key', 'KP3'],
    "{NUMPAD4}"   : ['key', 'KP4'],
    "{NUMPAD5}"   : ['key', 'KP5'],
    "{NUMPAD6}"   : ['key', 'KP6'],
    "{NUMPAD7}"   : ['key', 'KP7'],
    "{NUMPAD8}"   : ['key', 'KP8'],
    "{NUMPAD9}"   : ['key', 'KP9'],
    "+"           : ['key', 'LEFTSHIFT'],
    "^"           : ['Key', 'LEFTCTRL'],
    "%"           : ['key', 'LEFTALT'],
    # "@"           : ['key', 'Super']
}


def type_entry_ydotool(entry, tokens):
    """Auto-type entry entry using ydotool

    """
    enter_idx = True
    for token, special in tokens:
        if special:
            cmd = token_command(token)
            if callable(cmd):
                cmd()
            elif token in PLACEHOLDER_AUTOTYPE_TOKENS:
                to_type = PLACEHOLDER_AUTOTYPE_TOKENS[token](entry)
                if to_type:
                    call(['ydotool', 'type', to_type])
            elif token in STRING_AUTOTYPE_TOKENS:
                to_type = STRING_AUTOTYPE_TOKENS[token]
                call(['ydotool', 'type', to_type])
            elif token in YDOTOOL_AUTOTYPE_TOKENS:
                cmd = ['ydotool'] + YDOTOOL_AUTOTYPE_TOKENS[token]
                call(cmd)
                # Add extra {ENTER} key tap for first instance of {ENTER}. It
                # doesn't get recognized for some reason.
                if enter_idx is True and token in ("{ENTER}", "~"):
                    cmd = ['ydotool'] + YDOTOOL_AUTOTYPE_TOKENS[token]
                    call(cmd)
                    enter_idx = False
            else:
                dmenu_err("Unsupported auto-type token (ydotool): \"%s\"" % (token))
                return
        else:
            call(['ydotool', 'type', token])


def type_entry(entry):
    """Pick which library to use to type strings

    Defaults to pyuserinput

    """
    sequence = SEQUENCE
    if hasattr(entry, 'autotype_enabled') and entry.autotype_enabled is False:
        dmenu_err("Autotype disabled for this entry")
        return
    if hasattr(entry, 'autotype_sequence') and \
            entry.autotype_sequence is not None and \
            entry.autotype_sequence != 'None':
        sequence = entry.autotype_sequence
    tokens = tokenize_autotype(sequence)

    library = 'pyuserinput'
    if CONF.has_option('vault', 'type_library'):
        library = CONF.get('vault', 'type_library')
    if library == 'xdotool':
        type_entry_xdotool(entry, tokens)
    elif library == 'ydotool':
        type_entry_ydotool(entry, tokens)
    else:
        type_entry_pyuserinput(entry, tokens)


def type_text(data):
    """Type the given text data

    """
    library = 'pyuserinput'
    if CONF.has_option('vault', 'type_library'):
        library = CONF.get('vault', 'type_library')
    if library == 'xdotool':
        call(['xdotool', 'type', data])
    elif library == 'ydotool':
        call(['ydotool', 'type', data])
    else:
        kbd = PyKeyboard()
        try:
            kbd.type_string(data)
        except (X11Error, KeyError):
            dmenu_err("Unable to type string...bad character.\n"
                      "Try setting `type_library = xdotool` in config.ini")

# vim: set et ts=4 sw=4 :
