"""Launcher functions"""

from os.path import basename
import shlex
import sys
from subprocess import run

import bwm


def dmenu_cmd(num_lines, prompt, obscure=None):
    """Parse config.ini for dmenu options

    Args: args - num_lines: number of lines to display
                 prompt: prompt to show
                 obscure: True/False to force hiding typed input, or None to
                          guess from the prompt text
    Returns: command invocation (as a list of strings) for
                ["dmenu", "-l", "<num_lines>", "-p", "<prompt>", "-i", ...]

    """
    commands = {
        "bemenu": ["-p", str(prompt), "-l", str(num_lines)],
        "dmenu": ["-p", str(prompt), "-l", str(num_lines)],
        "wmenu": ["-p", str(prompt), "-l", str(num_lines)],
        "rofi": ["-dmenu", "-p", str(prompt), "-l", str(num_lines)],
        "tofi": ["--require-match=false",
                 f"--prompt-text={str(prompt)}: ",
                 f"--num-results={str(num_lines)}"],
        "wofi": ["--dmenu", "-p", str(prompt), "-L", str(num_lines + 1)],
        "yofi": ["-p", str(prompt)],
        "fuzzel": ["--dmenu", "-p", str(prompt) + " ", "-l", str(num_lines)],
    }
    command = shlex.split(
        bwm.CONF.get("dmenu", "dmenu_command", fallback="dmenu")
    )
    # basename so that an absolute dmenu_command (/usr/bin/rofi) still matches
    launcher = basename(command[0])
    command.extend(commands.get(launcher, []))
    # Matching on the prompt text is a fallback for callers that don't say.
    # It has to stay an exact match: "Password Options" and "Password Length?"
    # are menus that would become unreadable if they were hidden. Callers that
    # know they're reading a secret pass obscure=True and skip the guessing.
    pwprompts = (
        "Password",
        "password",
        "client_secret",
        "Verify password",
        "Enter Password",
    )
    if obscure is None:
        obscure = any(i == prompt for i in pwprompts)
    conf_obscure = bwm.CONF.getboolean(
        "dmenu_passphrase", "obscure", fallback=True
    )
    if obscure and conf_obscure is True:
        pass_prompts = {
            "rofi": ["-password"],
            "bemenu": ["-x", "indicator", "*"],
            "tofi": ["--hide-input=true", "--hidden-character=*"],
            "wofi": ["-P"],
            "yofi": ["--password"],
            "fuzzel": ["--password"],
        }
        # dmenu_pass runs the launcher to look for the password patch, so only
        # call it for the launcher actually in use.
        if launcher in ("dmenu", "wmenu"):
            command.extend(dmenu_pass(launcher))
        else:
            command.extend(pass_prompts.get(launcher, []))
    if launcher == "yofi":
        # A subcommand, so it goes after every option, --password included
        command.append("dialog")
    return command


def dmenu_pass(command):
    """Check if the dmenu passphrase patch is applied and return the correct
    command line arg list for dmenu or wmenu

    Args: command - string
    Returns: list or None

    """
    if command not in ("dmenu", "wmenu"):
        return None
    try:
        # Check for dmenu password patch
        dm_patch = (
            b"P"
            in run([command, "-h"], capture_output=True, check=False).stderr
        )
    except FileNotFoundError:
        dm_patch = False
    color = bwm.CONF.get(
        "dmenu_passphrase", "obscure_color", fallback="#222222"
    )
    dargs = {"dmenu": ["-nb", color, "-nf", color],
             "wmenu": ["-n", color, "-N", color]}
    return ["-P"] if dm_patch else dargs[command]


def dmenu_select(num_lines, prompt="Entries", inp="", obscure=None):
    """Call dmenu and return the selected entry

    Args: num_lines - number of lines to display
          prompt - prompt to show
          inp - string to pass to dmenu via STDIN
          obscure - True to hide what the user types, None to guess from the
                    prompt text

    Returns: sel - string

    """
    # With no lines, rofi and fuzzel show only the input box, hiding a
    # suggested value like the default server URL.
    if inp and num_lines < 1:
        num_lines = 1
    cmd = dmenu_cmd(num_lines, prompt, obscure=obscure)
    # wofi shows the prompt as GTK placeholder text, which disappears whenever
    # the input box has focus - and it always does when there's no list. A
    # blank row keeps focus on the list, and --exec-search makes enter return
    # what was typed even when it matches that row.
    wofi_filler = basename(cmd[0]) == "wofi" and not inp
    if wofi_filler:
        cmd.append("--exec-search")
        inp = " \n"
    try:
        res = run(
            cmd,
            capture_output=True,
            check=False,
            input=inp,
            encoding=bwm.ENC,
            env=bwm.ENV,
        )
    except FileNotFoundError:
        print(f"dmenu command not found: {cmd[0]}", file=sys.stderr)
        sys.exit(1)
    if res.returncode != 0 and res.stderr:
        # Without this the launcher failing (no display, bad config) is
        # indistinguishable from the user cancelling, and bwm exits silently.
        print(f"dmenu command error: {res.stderr.strip()}", file=sys.stderr)
    if res.stdout is None:
        return None
    sel = res.stdout.rstrip("\n")
    # Enter on an empty wofi input box selects the blank row
    return "" if wofi_filler and sel == " " else sel


def dmenu_err(prompt):
    """Pops up a dmenu prompt with an error message

    In CLI mode, print to stderr instead. A launcher isn't necessarily
    installed and there's a terminal to print to.

    """
    try:
        prompt = prompt.decode(bwm.ENC)
    except AttributeError:
        pass
    if bwm.CLI is True:
        print(prompt, file=sys.stderr)
        return None
    return dmenu_select(len(prompt.splitlines()), "Error", inp=prompt)


# vim: set et ts=4 sw=4 :
