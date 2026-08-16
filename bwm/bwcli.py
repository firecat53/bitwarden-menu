"""Provide methods to manipulate Bitwarden vault using the Bitwarden CLI"""

from copy import deepcopy
import json
import logging
import os
import pty
import re
import select
import socket
import time
from subprocess import DEVNULL, run
from urllib.parse import urlsplit


# Name of the variable `bw --passwordenv` is pointed at. Only the name ever
# reaches argv; the password itself stays in the child's environment.
BW_PASSWORD_ENV = "BW_PASSWORD"


# Every argv token `bw` is invoked with in this module that is safe to log.
# The sanitizer below is deliberately fail-closed: anything not listed here -
# session tokens, passwords, item ids, base64 item payloads - is redacted.
_LOGGABLE_ARGS = frozenset(
    (
        "bw",
        "config",
        "create",
        "delete",
        "edit",
        "encode",
        "folder",
        "folders",
        "item",
        "items",
        "list",
        "lock",
        "login",
        "org-collection",
        "organizations",
        "server",
        "status",
        "sync",
        "unlock",
        "--code",
        "--method",
        "--organizationid",
        "--raw",
        "--session",
        "--passwordenv",
        BW_PASSWORD_ENV,
    )
)


def _decode(val):
    """Decode bytes to str, leaving anything else alone"""
    return val.decode("utf-8", "replace") if isinstance(val, bytes) else val


def _bw_env(session=None, password=None):
    """Environment for a `bw` child process, carrying secrets out of argv.

    /proc/<pid>/cmdline is world readable, so a session token or master
    password passed as an argument is visible to every other user on the
    machine for as long as the process lives - and `bw serve` lives as long as
    the daemon does. /proc/<pid>/environ is readable only by its owner.

    `bw` treats the two as equivalent: its --session handler is literally
    `process.env.BW_SESSION = key`, and --passwordenv reads process.env[name].

    Args: session - session token, str or bytes. Falsy leaves any inherited
                    BW_SESSION alone, which is how a vault unlocked outside
                    bwm keeps working.
          password - master password, or None

    Returns: dict suitable for the env= argument of run()/Popen()

    """
    env = dict(os.environ)
    if session:
        env["BW_SESSION"] = _decode(session)
    if password is not None:
        env[BW_PASSWORD_ENV] = password
    return env


def _log_err(res, note=""):
    """Log a failed `bw` invocation without leaking secrets into the log file.

    Never log a CompletedProcess directly. Its repr includes argv - which holds
    the master password for `bw login`/`bw unlock` and the session token for
    every other command - as well as stdout, which for `bw list items` is the
    entire decrypted vault. Only the redacted command, exit status and stderr
    are recorded here. The log is a plain file on disk, so it must never hold
    vault contents or credentials.

    Args: res - CompletedProcess
          note - optional extra context string

    """
    cmd = " ".join(
        str(_decode(i)) if _decode(i) in _LOGGABLE_ARGS else "<redacted>"
        for i in res.args
    )
    stderr = _decode(res.stderr) or ""
    logging.error(
        f"`{cmd}` failed (exit {res.returncode}): {stderr.strip()}"
        f"{f' [{note}]' if note else ''}"
    )


def is_online(url, timeout=2):
    """Check whether the vault server is reachable.

    Used to tell an offline session apart from a genuine error. Unlocking an
    already authenticated vault and reading entries are local operations, but
    logging in, syncing and any edit require the server.

    Args: url - vault server URL string
          timeout - seconds to wait for the TCP connection

    Returns: True if a TCP connection to the server succeeds, else False

    """
    parts = urlsplit(url if "//" in url else f"//{url}")
    if not parts.hostname:
        logging.debug(f"is_online: could not parse a hostname from {url}")
        return False
    port = parts.port or (80 if parts.scheme == "http" else 443)
    try:
        with socket.create_connection((parts.hostname, port), timeout):
            return True
    except OSError as exc:
        logging.debug(f"is_online: {url} unreachable - {exc}")
        return False


def status(session=b""):
    """Check status of vault

    Returns: Dict -
             {serverUrl: <url>,
             lastSync: date/time,
             userEmail: <email>,
             userId: userId,
             status: <'locked', 'unlocked' or 'unauthenticated'>}
        Empty dict {} on error

    """
    res = run(
        ["bw", "status"],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return {}
    # The CLI can print warnings before the returned JSON (e.g. when it fails
    # to fetch the server config while offline), so only parse the last line.
    try:
        return dict(json.loads(res.stdout.strip().split(b"\n")[-1]))
    except (ValueError, TypeError):
        _log_err(res)
        return {}


def set_server(url="https://vault.bitwarden.com"):
    """Set vault URL

    Returns: True if successful or False on error

    """
    res = run(["bw", "config", "server", url], capture_output=True, check=False)
    if not res.stdout:
        _log_err(res)
        return False
    return True


def login(email, password, method=None, code=""):
    """Initial login to Bitwarden Vault. May require BW_CLIENTSECRET to be set.

    Args: email - string
          password - string
          method - int (0: Authenticator, 1: Email, 3: Yubikey)
          code - OTP code

    Returns: session (bytes) or False on error, Error message

    """
    if not email or not password:
        logging.error("No email or password provided")
        return (False, b"No email or password provided")
    cmd = ["bw", "login", "--raw", email, "--passwordenv", BW_PASSWORD_ENV]
    if method and code:
        cmd.extend(["--method", method, "--code", code])
    res = run(
        cmd,
        capture_output=True,
        stdin=DEVNULL,
        check=False,
        env=_bw_env(password=password),
    )
    # Only an empty stdout means failure. The CLI writes warnings to stderr and
    # can exit non-zero on a successful command when it cannot reach the server
    # (bitwarden/clients#18373), so neither is treated as an error here.
    if not res.stdout:
        _log_err(res)
        return (False, res.stderr)
    # `--raw` still ends with a newline. Keeping it makes every later
    # `bw --session <token>` reject the session as invalid.
    return res.stdout.strip(), None


def _pty_read(fd, timeout=10):
    """Read from a PTY file descriptor until idle or timeout.

    Returns: bytes read

    """
    output = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        remaining = max(0.1, min(deadline - time.time(), 2))
        try:
            ready, _, _ = select.select([fd], [], [], remaining)
        except (ValueError, OSError):
            break
        if ready:
            try:
                data = os.read(fd, 4096)
                if not data:
                    break
                output += data
            except OSError:
                break
        else:
            # No data for 2 seconds - process is likely waiting for input
            break
    return output


def login_pty_start(email, password):
    """Start login with a PTY so the CLI can prompt for 2FA interactively.

    The bw CLI opens /dev/tty directly for interactive prompts, bypassing
    stdin/stdout redirection. A PTY gives the child process its own
    controlling terminal that we can read/write via the master fd.

    Args: email - string
          password - string

    Returns: (master_fd, pid) or (False, error message bytes)

    """
    if not email or not password:
        logging.error("No email or password provided")
        return (False, b"No email or password provided")
    cmd = ["bw", "login", "--raw", email, "--passwordenv", BW_PASSWORD_ENV]
    env = _bw_env(password=password)
    pid, fd = pty.fork()
    if pid == 0:
        # Child process. execvpe, not execvp: the password rides in the
        # environment rather than on the command line.
        os.execvpe(cmd[0], cmd, env)
        os._exit(1)
    # Parent: read initial output (prompts) until CLI is waiting for input
    _pty_read(fd, timeout=15)
    return (fd, pid)


def login_pty_finish(fd, pid, code, timeout=60):
    """Send the 2FA code to the bw login process and get the session token.

    Args: fd - PTY master file descriptor from login_pty_start
          pid - child process ID from login_pty_start
          code - OTP code string
          timeout - seconds to wait for completion

    Returns: session (bytes) or False on error, Error message

    """
    try:
        os.write(fd, (code + "\n").encode())
    except OSError as exc:
        logging.error(f"Failed to send OTP code: {exc}")
        return (False, str(exc).encode())

    # Read output until the process exits (not idle timeout),
    # since the CLI makes an API call that can take several seconds
    result = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        exited = False
        try:
            wpid, status = os.waitpid(pid, os.WNOHANG)
            if wpid != 0:
                exited = True
        except ChildProcessError:
            exited = True
            status = 0
        try:
            remaining = max(0.1, deadline - time.time())
            ready, _, _ = select.select([fd], [], [], min(remaining, 1))
            if ready:
                data = os.read(fd, 4096)
                if data:
                    result += data
                elif exited:
                    break
            elif exited:
                break
        except (OSError, ValueError):
            break

    if not exited:
        import signal

        os.kill(pid, signal.SIGTERM)
        try:
            _, status = os.waitpid(pid, 0)
        except ChildProcessError:
            status = 1
    try:
        os.close(fd)
    except OSError:
        pass

    exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 1
    if exit_code != 0:
        # The PTY output is returned to the caller for the error dialog but is
        # not logged - on a partial success it can contain the session token.
        logging.error(f"Email OTP login failed (exit {exit_code})")
        return (False, result or b"Email OTP login failed")

    # Extract session token: strip ANSI escapes and find the raw token
    cleaned = re.sub(rb"\x1b\[[0-9;]*[a-zA-Z]", b"", result)
    for line in reversed(cleaned.strip().split(b"\n")):
        line = line.strip()
        # Session token is a long string with no spaces
        if len(line) > 20 and b" " not in line:
            return (line, None)

    logging.error(
        f"Could not extract session token from {len(result)} bytes of output"
    )
    return (False, result or b"Could not extract session token")


def unlock(password):
    """Unlock vault

    The master password is verified locally against the cached vault, so this
    also works without a network connection.

    Returns: session (bytes) or False on error, Error message

    """
    if not password:
        logging.error("No password provided")
        return (False, "No password provided")
    res = run(
        ["bw", "unlock", "--raw", "--passwordenv", BW_PASSWORD_ENV],
        capture_output=True,
        check=False,
        env=_bw_env(password=password),
    )
    # Deliberately not checking returncode - see the note in login()
    if not res.stdout:
        _log_err(res)
        return (False, res.stderr)
    # `--raw` still ends with a newline. Keeping it makes every later
    # `bw --session <token>` reject the session as invalid.
    return res.stdout.strip(), None


def lock():
    """Lock vault

    Return: True on success, False with any errors

    """
    res = run(["bw", "lock"], capture_output=True, check=False)
    if not res.stdout:
        _log_err(res)
        return False
    return True


def get_orgs(session):
    """Return all organizations for the logged in user

    Return: Dict of org dicts {id: dict('object':'organization','id':id,'name':<name>...)}
            False on error

    """
    res = run(
        ["bw", "list", "organizations"],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return {i["id"]: i for i in json.loads(res.stdout)}


class Item(dict):
    """Set some default attributes to all items"""

    def __init__(self, /, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault("fields", [])
        if not any(i.get("name") == "autotype" for i in self.get("fields")):
            self["fields"].append({"name": "autotype", "value": "", "type": 0})


def get_entries(session, org_name=""):
    """Get all entries, folders, collections and orgs from vault

    Args: session: bytes
          org_name: name of organization. If given, only return items for that org
    1. the URL is buried in:
        'login'->'uris'->[{match: xxx, uri: http...}, {match2: xxx, uri2: httpxxx}]
    2. Also adjust 'path' to be just the dirname, not including the 'name'
    3. Add the 'autotype' field so it can be edited if necessary

        Return: items (list of Items), folders, collections, orgs
                False on error

    """
    # Never log the session token or stdout here - stdout is the entire
    # decrypted vault and the log is a plain file on disk.
    logging.debug(f"get_entries: session present={bool(session)}")

    res = run(
        ["bw", "list", "items"],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )

    logging.debug(
        f"get_entries: returncode={res.returncode}, "
        f"stdout bytes={len(res.stdout or b'')}"
    )

    if not res.stdout:
        _log_err(res)
        return False

    if res.returncode != 0:
        _log_err(res)
        return False

    items = [Item(i) for i in json.loads(res.stdout)]
    folders = get_folders(session)
    collections = get_collections(session, org_name)
    orgs = get_orgs(session)
    return items, folders, collections, orgs


def sync(session):
    """Sync web vault changes to local vault

    Return: True on success, False with any errors

    """
    res = run(
        ["bw", "sync"],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return True


def get_folders(session):
    """Return all folder names.

    Return: Dict of folder dicts {id: dict('object':folder,'id':id,'name':<name>)}
            False on error

    """
    res = run(
        ["bw", "list", "folders"],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return {i["id"]: i for i in json.loads(res.stdout)}


def get_collections(session, org_id=""):
    """Return all collection names for user.

    Args: session - session id bytes
          org_id - organization id string.

    Return: Dict of collection dicts {id:
        dict('object':collection,'id':id,'organizationId:<org
             id>,'externalId':<ext id>,'name':<name>)}

    """
    cmd = ["bw", "list", "collections"]
    if org_id:
        cmd.extend(["--organizationid", org_id])
    res = run(cmd, capture_output=True, check=False, env=_bw_env(session))
    if not res.stdout:
        _log_err(res)
        return False
    return {i["id"]: i for i in json.loads(res.stdout)}


def add_entry(entry, session):
    """Add new entry to vault

    Args: entry - dict with at least these fields
    Returns: new item dict or False on error

    New item template:
    {
        "organizationId":null,
        "folderId":null,
        "type":1,
        "name":"Item name",
        "notes":null,
        "favorite":false,
        "fields":[],
        "login":null,
        "secureNote":null,
        "card":null,
        "identity":null}'

    """
    enc = run(
        ["bw", "encode"],
        input=json.dumps(entry).encode(),
        capture_output=True,
        check=False,
    )
    if not enc.stdout:
        _log_err(enc)
        return False
    res = run(
        ["bw", "create", "item", enc.stdout],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return json.loads(res.stdout)


def edit_entry(entry, session, update_coll="NO"):
    # pylint: disable=too-many-return-statements
    """Modify existing vault entry

    Args: entry - entry dict object
          session - session id
          update_coll - 'YES' if item collections have been modified.
                        'MOVE' if collections are added so item needs to be
                            move to an org.  Returns: updated entry object
                            (dict) on success, False on failure
                        'REMOVE' if collections are removed so item needs to
                            be moved from the org to personal vault.

    """
    item = deepcopy(entry)
    if update_coll == "YES":
        # bw edit item-collections is unreliable, use delete+add instead
        res = delete_entry(entry, session)
        if res is False:
            return False
        item["id"] = None
        # organizationId and collectionIds are already set on item
        res = add_entry(item, session)
        if res is False:
            return False
        return res
    elif update_coll == "MOVE":
        # bw move command is unreliable, use delete+add instead
        res = delete_entry(entry, session)
        if res is False:
            return False
        item["id"] = None
        # organizationId and collectionIds are already set on item
        res = add_entry(item, session)
        if res is False:
            return False
        return res
    elif update_coll == "REMOVE":
        res = delete_entry(entry, session)
        if res is False:
            return False
        item["id"] = None
        item["collectionIds"] = []
        item["organizationId"] = None
        res = add_entry(item, session)
        if res is False:
            return False
        return res
    enc = run(
        ["bw", "encode"],
        input=json.dumps(item).encode(),
        capture_output=True,
        check=False,
    )
    if not enc.stdout:
        _log_err(enc)
        return False
    res = run(
        ["bw", "edit", "item", item["id"], enc.stdout],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return json.loads(res.stdout)


def delete_entry(entry, session):
    """Delete existing vault entry

    Args: entry - entry dict object
    Returns: entry object (dict) on success, False on failure

    """
    res = run(
        ["bw", "delete", "item", entry["id"]],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if res.returncode != 0:
        _log_err(res)
        return False
    return entry


def add_folder(folder, session):
    """Add folder

    Args: folder - string (name of folder)
          session - bytes

    Returns: Folder object or False on error

    """
    folder = {"name": folder}
    enc = run(
        ["bw", "encode"],
        input=json.dumps(folder).encode(),
        capture_output=True,
        check=False,
    )
    if not enc.stdout:
        _log_err(enc)
        return False
    res = run(
        ["bw", "create", "folder", enc.stdout],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return json.loads(res.stdout)


def delete_folder(folder, session):
    """Delete folder

    Args: folder - folder object (dict)
          session - bytes
    Returns: folder object (dict) on success, False on failure


    """
    res = run(
        ["bw", "delete", "folder", folder["id"]],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if res.returncode != 0:
        _log_err(res)
        return False
    return folder


def move_folder(folder, newpath, session):
    """Move or rename folder

    Args: folder - folder dict object
          newpath - string (new name/path)
          session - bytes
    Returns: Folder object on success, False on failure

    """
    fold = deepcopy(folder)
    fold["name"] = newpath
    enc = run(
        ["bw", "encode"],
        input=json.dumps(fold).encode(),
        capture_output=True,
        check=False,
    )
    if not enc.stdout:
        _log_err(enc)
        return False
    res = run(
        ["bw", "edit", "folder", fold["id"], enc.stdout],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return json.loads(res.stdout)


def add_collection(collection, org_id, session):
    """Add collection

    Args: collection - string
          org - organization id string
          session - bytes

    Returns: collection object or False on error

    """
    collection = {"name": collection, "organizationId": org_id}
    enc = run(
        ["bw", "encode"],
        input=json.dumps(collection).encode(),
        capture_output=True,
        check=False,
    )
    if not enc.stdout:
        _log_err(enc)
        return False
    res = run(
        [
            "bw",
            "create",
            "--organizationid",
            org_id.encode(),
            "org-collection".encode(),
            enc.stdout,
        ],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return json.loads(res.stdout)


def delete_collection(collection, session):
    """Delete collection

    Args: collection - collection object (dict)
          session - bytes
    Returns: collection object (dict) on success, False on failure

    """
    res = run(
        [
            "bw",
            "delete",
            "--organizationid",
            collection["organizationId"].encode(),
            "org-collection",
            collection["id"],
        ],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if res.returncode != 0:
        _log_err(res)
        return False
    return collection


def move_collection(collection, newpath, session):
    """Move or rename collection

    Args: collection - collection object (dict)
          newpath - string (new name/path)
          session - bytes
    Returns: collection object on success, False on failure

    """
    coll = deepcopy(collection)
    coll["name"] = newpath
    enc = run(
        ["bw", "encode"],
        input=json.dumps(coll).encode(),
        capture_output=True,
        check=False,
    )
    if not enc.stdout:
        _log_err(enc)
        return False
    res = run(
        [
            "bw",
            "edit",
            "--organizationid",
            coll["organizationId"].encode(),
            "org-collection",
            coll["id"],
            enc.stdout,
        ],
        capture_output=True,
        check=False,
        env=_bw_env(session),
    )
    if not res.stdout:
        _log_err(res)
        return False
    return json.loads(res.stdout)


# vim: set et ts=4 sw=4 :
