"""Launcher functions"""

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
    commands = {
        "bemenu": ["-p", str(prompt), "-l", str(num_lines)],
        "dmenu": ["-p", str(prompt), "-l", str(num_lines)],
        "rofi": ["-dmenu", "-p", str(prompt), "-l", str(num_lines)],
        "wofi": ["--dmenu", "-p", str(prompt), "-L", str(num_lines + 1)],
    }
    command = shlex.split(
        bwm.CONF.get("dmenu", "dmenu_command", fallback="dmenu")
    )
    command.extend(commands.get(command[0], []))
    pwprompts = (
        "Password",
        "password",
        "client_secret",
        "Verify password",
        "Enter Password",
    )
    obscure = bwm.CONF.getboolean("dmenu_passphrase", "obscure", fallback=True)
    if any(i == prompt for i in pwprompts) and obscure is True:
        pass_prompts = {
            "dmenu": dmenu_pass(command[0]),
            "rofi": ["-password"],
            "bemenu": ["-x", "indicator", "*"],
            "wofi": ["-P"],
        }
        command.extend(pass_prompts.get(command[0], []))
    return command


def dmenu_pass(command):
    """Check if dmenu passphrase patch is applied and return the correct command
    line arg list

    Args: command - string
    Returns: list or None

    """
    if command != "dmenu":
        return None
    try:
        # Check for dmenu password patch
        dm_patch = (
            b"P"
            in run(["dmenu", "-h"], capture_output=True, check=False).stderr
        )
    except FileNotFoundError:
        dm_patch = False
    color = bwm.CONF.get(
        "dmenu_passphrase", "obscure_color", fallback="#222222"
    )
    return ["-P"] if dm_patch else ["-nb", color, "-nf", color]


def dmenu_select(num_lines, prompt="Entries", inp=""):
    """Call dmenu and return the selected entry

    Args: num_lines - number of lines to display
          prompt - prompt to show
          inp - string to pass to dmenu via STDIN

    Returns: sel - string

    """
    cmd = dmenu_cmd(num_lines, prompt)
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
    return res.stdout.rstrip("\n") if res.stdout is not None else None


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
