"""Dmenu/Rofi functions

"""
import itertools
import shlex
import sys
from subprocess import Popen, PIPE

import bwm

def dmenu_cmd(num_lines, prompt):
    """Parse config.ini for dmenu options

    Args: args - num_lines: number of lines to display
                 prompt: prompt to show
    Returns: command invocation (as a list of strings) for
                dmenu -l <num_lines> -p <prompt> -i ...

    """
    args_dict = {"dmenu_command": "dmenu"}
    if bwm.CONF.has_section('dmenu'):
        args = bwm.CONF.items('dmenu')
        args_dict.update(dict(args))
    command = shlex.split(args_dict["dmenu_command"])
    dmenu_command = command[0]
    dmenu_args = command[1:]
    del args_dict["dmenu_command"]
    lines = "-i -dmenu -multi-select -lines" if "rofi" in dmenu_command else "-i -l"
    if "l" in args_dict:
        lines = "{} {}".format(lines, min(num_lines, int(args_dict['l'])))
        del args_dict['l']
    else:
        lines = "{} {}".format(lines, num_lines)
    if "pinentry" in args_dict:
        del args_dict["pinentry"]
    if prompt == "Passphrase":
        if bwm.CONF.has_section('dmenu_passphrase'):
            args = bwm.CONF.items('dmenu_passphrase')
            args_dict.update(args)
        rofi_obscure = True
        if bwm.CONF.has_option('dmenu_passphrase', 'rofi_obscure'):
            rofi_obscure = bwm.CONF.getboolean('dmenu_passphrase', 'rofi_obscure')
            del args_dict["rofi_obscure"]
        if rofi_obscure is True and "rofi" in dmenu_command:
            dmenu_args.extend(["-password"])
    extras = (["-" + str(k), str(v)] for (k, v) in args_dict.items())
    dmenu = [dmenu_command, "-p", str(prompt)]
    dmenu.extend(dmenu_args)
    dmenu += list(itertools.chain.from_iterable(extras))
    dmenu[1:1] = lines.split()
    dmenu = list(filter(None, dmenu))  # Remove empty list elements
    return dmenu


def dmenu_select(num_lines, prompt="Entries", inp=""):
    """Call dmenu and return the selected entry

    Args: num_lines - number of lines to display
          prompt - prompt to show
          inp - bytes string to pass to dmenu via STDIN

    Returns: sel - string

    """
    cmd = dmenu_cmd(num_lines, prompt)
    sel, err = Popen(cmd,
                     stdin=PIPE,
                     stdout=PIPE,
                     stderr=PIPE,
                     env=bwm.ENV).communicate(input=inp)
    if err:
        cmd = [cmd[0]] + ["-dmenu"] if "rofi" in cmd[0] else [""]
        Popen(cmd[0], stdin=PIPE, stdout=PIPE, env=bwm.ENV).communicate(input=err)
        sys.exit()
    if sel:
        sel = sel.decode(bwm.ENC).rstrip('\n')
    return sel


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    """
    return dmenu_select(1, prompt)
