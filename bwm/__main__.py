"""Read, type and edit Bitwarden vault entries using dmenu style launchers"""

import argparse
from contextlib import closing
from getpass import getpass
import json
import multiprocessing
from multiprocessing.managers import BaseManager, RemoteError
import os
from os.path import exists, expanduser
import random
import socket
import string
from subprocess import call
import sys

import bwm
from bwm import bwcli
from bwm.bwm import DmenuRunner
from bwm.menu import dmenu_err
from bwm.bwtype import type_clipboard
from bwm.run_once import show_fields

# Python 3.14 default is 'forkserver'. Set to 'fork' for backwards compatibility.
# Tolerate the context already being set: this module gets imported a second
# time as `bwm.__main__` from the daemon children, and anything that touches
# multiprocessing before importing it fixes the context too.
try:
    multiprocessing.set_start_method("fork")
except RuntimeError:
    pass

# Shared buffer holding the JSON list of unlocked [url, email] pairs
UNLOCKED_BUF_SIZE = 8192


def find_free_port():
    """Find random free port to use for BaseManager server

    Returns: int Port

    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))  # pylint:disable=no-member
        return sock.getsockname()[1]  # pylint:disable=no-member


def port_in_use(port):
    """Return Boolean"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def random_str():
    """Generate random auth string for BaseManager

    Returns: string

    """
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(15))


def get_auth():
    """Generate and save port and authkey to auth file.

    Uses $XDG_RUNTIME_DIR/bwm/ if available otherwise falls back to $TMPDIR/bwm-<uid>/.

    Returns: int port, bytestring authkey

    """
    auth = bwm.configparser.ConfigParser()
    if not exists(bwm.AUTH_FILE):
        fdr = os.open(bwm.AUTH_FILE, os.O_WRONLY | os.O_CREAT, 0o600)
        with open(fdr, "w", encoding=bwm.ENC) as a_file:
            auth.set("DEFAULT", "port", str(find_free_port()))
            auth.set("DEFAULT", "authkey", random_str())
            auth.write(a_file)
    try:
        auth.read(bwm.AUTH_FILE)
        port = auth.get("DEFAULT", "port")
        authkey = auth.get("DEFAULT", "authkey").encode()
    except (
        bwm.configparser.NoOptionError,
        bwm.configparser.MissingSectionHeaderError,
        bwm.configparser.ParsingError,
        multiprocessing.context.AuthenticationError,
    ):
        os.remove(bwm.AUTH_FILE)
        dmenu_err(
            "Cache file was corrupted. Stopping all instances. Please try again"
        )
        call(["pkill", "bwm"])  # Kill all prior instances as well
        return None, None
    return int(port), authkey


def client(port, auth):
    """Define client connection to server BaseManager

    Returns: BaseManager object
    """
    mgr = BaseManager(address=("", port), authkey=auth)
    mgr.register("set_event")
    mgr.register("get_pipe")
    mgr.register("read_args_from_pipe")
    mgr.register("receive_show_result")
    mgr.register("get_unlocked_vaults")
    mgr.connect()
    return mgr


class Server(multiprocessing.Process):  # pylint: disable=too-many-instance-attributes
    """Run BaseManager server to listen for dmenu calling events"""

    def __init__(self, unlocked=None, background=True):
        multiprocessing.Process.__init__(self)
        self.background = background
        self.unlocked = unlocked
        self.port, self.authkey = get_auth()
        self.start_flag = multiprocessing.Event()
        self.kill_flag = multiprocessing.Event()
        self.cache_time_expired = multiprocessing.Event()
        self.args_flag = multiprocessing.Event()
        self.start_flag.set()
        self.args = None
        # Duplex so --show results can travel back to the client, which is the
        # process with the user's stdout attached.
        self._parent_conn, self._child_conn = multiprocessing.Pipe(duplex=True)

    def run(self):
        bwm.detach_from_terminal(self.background)
        try:
            _ = self.server()
            try:
                self.kill_flag.wait()
            except KeyboardInterrupt:
                self.kill_flag.set()
        finally:
            if exists(expanduser(bwm.AUTH_FILE)):
                os.remove(expanduser(bwm.AUTH_FILE))

    def _get_pipe(self):
        return self._child_conn

    def get_args(self):
        """Reads arguments sent by the client to the server"""
        return self._parent_conn.recv()

    def send_result(self, result):
        """Send a --show result from the daemon back to the client

        Args: result - string

        """
        self._parent_conn.send(result)

    def receive_show_result(self, timeout=30):
        """Read the --show result the daemon sent back.

        Args: timeout - maximum seconds to wait
        Returns: the result string, or None on timeout

        """
        if self._child_conn.poll(timeout):
            return self._child_conn.recv()
        return None

    def unlocked_vaults(self):
        """Vaults the daemon currently holds a session for

        Read from shared memory rather than a multiprocessing.Manager: the
        manager would be an extra process, orphaned when the invocation that
        created it exits, with nothing left to shut it down.

        Returns: list of [url, email] pairs

        """
        if self.unlocked is None:
            return []
        raw = self.unlocked.value
        return json.loads(raw) if raw else []

    def server(self):
        """Set up BaseManager server"""
        mgr = BaseManager(
            address=("127.0.0.1", self.port), authkey=self.authkey
        )
        mgr.register("set_event", callable=self.start_flag.set)
        mgr.register("get_pipe", callable=self._get_pipe)
        mgr.register("read_args_from_pipe", callable=self.args_flag.set)
        mgr.register("receive_show_result", callable=self.receive_show_result)
        mgr.register("get_unlocked_vaults", callable=self.unlocked_vaults)
        mgr.start()  # pylint: disable=consider-using-with
        return mgr


def run(foreground=False, **kwargs):
    """Start the Manager and Dmenu runner processes.

    Everything that prompts - get_vault()/set_vault() inside
    DmenuRunner.__init__ - runs here in the parent, while the terminal is still
    attached. Only after that do the children fork and the parent let go.

    Args: foreground - bool, block until the daemon exits instead of detaching
          kwargs - parsed CLI args

    Returns: the --show output when this invocation started the daemon to serve
             one, otherwise None. The parent has the unlocked vault in hand, so
             answering here avoids a round trip through the daemon.

    """
    # The BaseManager callables run in the manager's own process, so state the
    # DmenuRunner publishes has to live in memory both can see. Shared memory
    # rather than a Manager: no extra process to leak when this one exits.
    unlocked = multiprocessing.Array("c", UNLOCKED_BUF_SIZE)

    server = Server(unlocked=unlocked, background=not foreground)
    if kwargs.get("show"):
        # Otherwise DmenuRunner.run() would immediately pop the entry menu
        server.start_flag.clear()
    result = None
    started = False
    try:
        # DmenuRunner.__init__ exits on a failure to open the vault, so it has
        # to be inside the try to get the auth file cleaned up.
        dmenu = DmenuRunner(
            server,
            unlocked=unlocked,
            background=not foreground,
            **kwargs,
        )
        if kwargs.get("show"):
            result = show_fields(
                dmenu.vault.entries,
                dmenu.vault.folders,
                kwargs.get("show", ""),
                fields=kwargs.get("field"),
                return_errors=True,
            )
        dmenu.daemon = foreground
        server.start()
        started = True
        dmenu.start()
        if foreground:
            server.join()
    except KeyboardInterrupt:
        sys.exit()
    finally:
        # Once the server is running it removes the auth file itself when it
        # exits. Only clean up here if it never started, or if we waited for it.
        if (not started or foreground) and exists(expanduser(bwm.AUTH_FILE)):
            os.remove(expanduser(bwm.AUTH_FILE))
    return result


def leave(code=0, detached=False):
    """Exit, without waiting on a daemon we deliberately left running.

    multiprocessing's atexit handler joins non-daemonic children, so a plain
    sys.exit() here would block until the daemon's session timeout expires.
    os._exit() skips that, which is exactly what backgrounding needs.

    Args: code - exit status
          detached - True once the daemon children are running

    """
    if not detached:
        sys.exit(code)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # pylint: disable=protected-access


def deliver_show_result(result, clipboard=False, detached=False):
    """Print a --show result, or put it on the clipboard, and exit.

    The copy happens here in the client, not in the daemon: the clipboard
    belongs to the invoking session, while the daemon's environment is whatever
    it was started with. A daemon started from a tty has no DISPLAY or
    WAYLAND_DISPLAY, so it would hunt for the wrong clipboard tool forever.

    Args: result - string from the daemon or from run(). None on failure, an
                   'ERROR: ' prefixed message on a reported error.
          clipboard - copy instead of printing
          detached - True once the daemon children are running

    """
    if result is None:
        leave(1, detached)
    if result.startswith("ERROR:"):
        print(result[7:], file=sys.stderr)  # Strip "ERROR: " prefix
        leave(1, detached)
    if clipboard:
        if not type_clipboard(result):
            print(bwm.clipboard_missing_msg(), file=sys.stderr)
            leave(1, detached)
        leave(0, detached)
    if result:
        print(result)
    leave(0, detached)


def config_has_password(url, login):
    """Whether config.ini can supply a password for this vault.

    Args: url - vault URL or None
          login - login email or None
    Returns: bool

    """
    if not bwm.CONF.has_section("vault"):
        return False
    vault_args = dict(bwm.CONF.items("vault"))
    for key in [i for i in vault_args if i.startswith("server")]:
        idx = key.rsplit("_", 1)[-1]
        if url and vault_args[key] != url:
            continue
        if login and vault_args.get(f"email_{idx}", "") != login:
            continue
        if f"password_{idx}" in vault_args or f"password_cmd_{idx}" in vault_args:
            return True
    return False


def daemon_unlocked_vaults(manager):
    """Vaults the running daemon holds a session for.

    Returns: list of [url, email] pairs, or None if the daemon predates
             --show support and has no such callable registered.

    """
    try:
        unlocked = manager.get_unlocked_vaults()  # pylint: disable=no-member
    except RemoteError:
        # Daemon started from an older version: the callable isn't registered
        return None
    if hasattr(unlocked, "_getvalue"):
        unlocked = unlocked._getvalue()
    return list(unlocked)


def show_password_prompt(unlocked, args):
    """Ask for the master password in the client process, if it's needed.

    The daemon has no terminal, so prompting there would pop up a launcher.
    Only ask when the requested vault isn't already unlocked and the config
    can't supply the password.

    Args: unlocked - list of [url, email] pairs the daemon has unlocked
          args - parsed CLI args
    Returns: password string, or None if no prompt is needed

    """
    url, login = args.get("vault"), args.get("login")
    if not url:
        # No vault given: the daemon uses its active vault, already unlocked
        return None
    for vault_url, vault_email in unlocked:
        if vault_url == url and (not login or vault_email == login):
            return None
    if config_has_password(url, login):
        return None
    try:
        return getpass("Enter Password: ")
    except (EOFError, OSError, AttributeError):
        return None


def main():
    """Main script entrypoint"""
    parser = argparse.ArgumentParser(
        description="Dmenu-compatible launcher frontend for Bitwarden/Vaultwarden"
    )

    parser.add_argument(
        "-a",
        "--autotype",
        type=str,
        required=False,
        help="Override autotype sequence in config.ini",
    )

    parser.add_argument(
        "-C",
        "--clipboard",
        action="store_true",
        default=False,
        required=False,
        help="Copy values to clipboard instead of typing.",
    )

    parser.add_argument(
        "-f",
        "--field",
        type=str,
        action="append",
        required=False,
        metavar="FIELD",
        help="Field to output with --show. Repeat for multiple fields, in "
        "order. One of: title, username, password, url, notes, totp, "
        "cardnum, any card/identity field name, S:<custom field>, or 'all' "
        "for every field with a value. Defaults to password",
    )

    parser.add_argument(
        "-F",
        "--foreground",
        action="store_true",
        default=False,
        required=False,
        help="Run the daemon in the foreground instead of detaching. For "
        "troubleshooting, and for service managers expecting Type=simple",
    )

    parser.add_argument(
        "-k",
        "--lock",
        required=False,
        action="store_true",
        help="Lock vault",
    )

    parser.add_argument(
        "-s",
        "--show",
        type=str,
        required=False,
        help="Output the password of the matched entry, or the fields given "
        "by --field, to stdout",
    )

    parser.add_argument(
        "-l",
        "--login",
        type=str,
        required=False,
        help="Login email address. Optional when only one account exists on the "
        "server. Required with -v when multiple accounts share the same server.",
    )

    parser.add_argument(
        "-v",
        "--vault",
        type=str,
        required=False,
        help="Vault URL to open, skipping the database selection menu. "
        "Use -l to specify login email when multiple accounts share the same server.",
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"bwm {bwm.__version__}",
        help="Show version and exit",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=str,
        required=False,
        help="Path to config file (default: ~/.config/bwm/config.ini)",
    )

    args = vars(parser.parse_args())

    if args["field"] and not args["show"]:
        parser.error("--field requires --show")

    args = args if any(args.values()) else {}

    # Prompts have to reach the user before anything forks. With no display
    # there is no launcher to prompt with, so use the terminal.
    bwm.CLI = bool(args.get("show")) or not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    )

    # DmenuRunner loads the config too, but that runs in the daemon process.
    # Anything main() reads out of CONF has to be loaded here first.
    cfile = args.get("config")
    bwm.reload_config(None if cfile is None else expanduser(cfile))

    if args.get("vault") and not args.get("login"):
        vault_args = dict(bwm.CONF.items("vault"))
        servers = [i for i in vault_args if i.startswith("server")]
        matches = [s for s in servers if vault_args[s] == args["vault"]]
        if len(matches) > 1:
            msg = ("Multiple accounts for this vault URL. "
                   "Use -l to specify login email.")
            print(msg, file=sys.stderr)
            sys.exit(1)

    foreground = bool(args.get("foreground"))
    port, auth = get_auth()
    if port_in_use(port) is False and args.get("lock"):
        # No daemon to tell, so just lock the vault. Falling through to run()
        # would start one and unlock it - the exact opposite of what was asked.
        if not bwcli.lock():
            print("Could not lock the vault.", file=sys.stderr)
            leave(1)
        leave(0)
    if port_in_use(port) is False:
        # No daemon yet. Unlocking a vault takes 8-12 seconds, so start one and
        # leave it warm rather than paying that on every --show. Credentials are
        # prompted for here, before run() detaches.
        result = run(**args)
        if args.get("show"):
            deliver_show_result(
                result,
                clipboard=bool(args.get("clipboard")),
                detached=not foreground,
            )
        leave(0, detached=not foreground)
    try:
        manager = client(port, auth)
        conn = manager.get_pipe()  # pylint: disable=no-member
        if args.get("show"):
            unlocked = daemon_unlocked_vaults(manager)
            if unlocked is None:
                # Probe before sending: a daemon that doesn't understand these
                # args would fall through and pop up its entry menu.
                print(
                    "The running bwm daemon is from a version without --show "
                    "support. Kill it (bwm -k) and try again.",
                    file=sys.stderr,
                )
                sys.exit(1)
            args["password"] = show_password_prompt(unlocked, args)
        if args:
            conn.send(args)
            manager.read_args_from_pipe()  # pylint: disable=no-member
        manager.set_event()  # pylint: disable=no-member
        if args.get("show"):
            # The daemon has no terminal, so it sends the result back here
            result = manager.receive_show_result()  # pylint: disable=no-member
            # AutoProxy objects need _getvalue() for the actual string
            if hasattr(result, "_getvalue"):
                result = result._getvalue()
            deliver_show_result(
                result, clipboard=bool(args.get("clipboard"))
            )
    except ConnectionRefusedError:
        # Don't print the ConnectionRefusedError if any other exceptions are raised.
        pass


if __name__ == "__main__":
    main()

# vim: set et ts=4 sw=4 :
