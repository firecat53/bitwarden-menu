"""Dmenu/Rofi functions

"""
import shlex
import sys
from subprocess import Popen, PIPE

import bwm


def dmenu_cmd(num_lines, prompt):
    """Parse config.ini for dmenu options

    Args: args - num_lines: number of lines to display
                 prompt: prompt to show
    Returns: command invocation (as a list of strings) for
                ["dmenu", "-l", "<num_lines>", "-p", "<prompt>", "-i", ...]

    """
    command = ["dmenu"]
    if bwm.CONF.has_option('dmenu', 'dmenu_command'):
        command = shlex.split(bwm.CONF.get('dmenu', 'dmenu_command'))
    dmenu_command = command[0]
    dmenu_args = command[1:]
    obscure = True
    obscure_color = "#222222"
    if prompt == "Password":
        if bwm.CONF.has_option('dmenu_passphrase', 'obscure'):
            obscure = bwm.CONF.getboolean('dmenu_passphrase', 'obscure')
        if bwm.CONF.has_option('dmenu_passphrase', 'obscure_color'):
            obscure_color = bwm.CONF.get('dmenu_passphrase', 'obscure_color')
    if "rofi" in dmenu_command:
        dmenu = [dmenu_command, "-dmenu", "-p", str(prompt), "-l", str(num_lines)]
        if obscure is True and prompt in ("Password", "Verify password"):
            dmenu.append("-password")
    elif "dmenu" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and prompt in ("Password", "Verify password"):
            dmenu.extend(["-nb", obscure_color, "-nf", obscure_color])
    else:
        # Catchall for some other menu programs. Maybe it'll run and not fail?
        dmenu = [dmenu_command]
    dmenu[1:1] = dmenu_args
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
    if sel is not None:
        sel = sel.decode(bwm.ENC).rstrip('\n')
    return sel


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    """
    return dmenu_select(1, prompt)

# vim: set et ts=4 sw=4 :
