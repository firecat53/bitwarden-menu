"""Dmenu/Rofi functions

"""
import shlex
import sys
from subprocess import run

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
    pwprompts = ("Password", "password", "client_secret")
    if any(i in prompt for i in pwprompts):
        if bwm.CONF.has_option('dmenu_passphrase', 'obscure'):
            obscure = bwm.CONF.getboolean('dmenu_passphrase', 'obscure')
        if bwm.CONF.has_option('dmenu_passphrase', 'obscure_color'):
            obscure_color = bwm.CONF.get('dmenu_passphrase', 'obscure_color')
    if "rofi" in dmenu_command:
        dmenu = [dmenu_command, "-dmenu", "-p", str(prompt), "-l", str(num_lines)]
        if obscure is True and any(i in prompt for i in pwprompts):
            dmenu.append("-password")
    elif "dmenu" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and any(i in prompt for i in pwprompts):
            dmenu.extend(["-nb", obscure_color, "-nf", obscure_color])
    elif "bemenu" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and any(i in prompt for i in pwprompts):
            dmenu.append("-x")
    elif "wofi" in dmenu_command:
        dmenu = [dmenu_command, "-p", str(prompt)]
        if obscure is True and any(i in prompt for i in pwprompts):
            dmenu.append("-P")
    else:
        # Catchall for some other menu programs. Maybe it'll run and not fail?
        dmenu = [dmenu_command]
    dmenu[1:1] = dmenu_args
    return dmenu


def dmenu_select(num_lines, prompt="Entries", inp=""):
    """Call dmenu and return the selected entry

    Args: num_lines - number of lines to display
          prompt - prompt to show
          inp - string to pass to dmenu via STDIN

    Returns: sel - string

    """
    cmd = dmenu_cmd(num_lines, prompt)
    res = run(cmd,
              capture_output=True,
              check=False,
              input=inp,
              encoding=bwm.ENC,
              env=bwm.ENV)
    if res.stderr and "rofi " in cmd[0]:
        cmd = [cmd[0]] + ["-dmenu"] if "rofi" in cmd[0] else [""]
        run(cmd[0], check=False, input=res.stderr, env=bwm.ENV)
        sys.exit()
    return res.stdout.rstrip('\n') if res.stdout is not None else None


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    """
    try:
        prompt = prompt.decode(bwm.ENC)
    except AttributeError:
        pass
    return dmenu_select(len(prompt.splitlines()), "Error", inp=prompt)

# vim: set et ts=4 sw=4 :
