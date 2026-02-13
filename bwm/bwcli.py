"""Provide methods to manipulate Bitwarden vault using the Bitwarden CLI"""

from copy import deepcopy
import json
import logging
import os
import pty
import re
import select
import time
from subprocess import DEVNULL, run


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
        ["bw", "--session", session, "status"], capture_output=True, check=False
    )
    if not res.stdout:
        logging.error(res)
        return {}
    return dict(json.loads(res.stdout.split(b"\n")[-1]))


def set_server(url="https://vault.bitwarden.com"):
    """Set vault URL

    Returns: True if successful or False on error

    """
    res = run(["bw", "config", "server", url], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
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
    cmd = ["bw", "login", "--raw", email, password]
    if method and code:
        cmd = [
            "bw",
            "login",
            "--raw",
            email,
            password,
            "--method",
            method,
            "--code",
            code,
        ]
    res = run(cmd, capture_output=True, stdin=DEVNULL, check=False)
    if not res.stdout or res.stderr:
        logging.error(res)
        return (False, res.stderr)
    return res.stdout, None


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
    cmd = ["bw", "login", "--raw", email, password]
    pid, fd = pty.fork()
    if pid == 0:
        # Child process
        os.execvp(cmd[0], cmd)
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
        logging.error(f"Email OTP login failed (exit {exit_code}): {result}")
        return (False, result or b"Email OTP login failed")

    # Extract session token: strip ANSI escapes and find the raw token
    cleaned = re.sub(rb"\x1b\[[0-9;]*[a-zA-Z]", b"", result)
    for line in reversed(cleaned.strip().split(b"\n")):
        line = line.strip()
        # Session token is a long string with no spaces
        if len(line) > 20 and b" " not in line:
            return (line, None)

    logging.error(f"Could not extract session token from: {result}")
    return (False, result or b"Could not extract session token")


def unlock(password):
    """Unlock vault

    Returns: session (bytes) or False on error, Error message

    """
    if not password:
        logging.error("No password provided")
        return (False, "No password provided")
    res = run(
        ["bw", "unlock", "--raw", password], capture_output=True, check=False
    )
    if not res.stdout:
        logging.error(res)
        return (False, res.stderr)
    return res.stdout, None


def lock():
    """Lock vault

    Return: True on success, False with any errors

    """
    res = run(["bw", "lock"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return True


def logout():
    """Logout of vault

    Return: True on success, False with any errors

    """
    res = run(["bw", "logout"], capture_output=True, check=False)
    if not res.stderr:
        logging.error(res)
        return False
    return True


def get_orgs(session):
    """Return all organizations for the logged in user

    Return: Dict of org dicts {id: dict('object':'organization','id':id,'name':<name>...)}
            False on error

    """
    res = run(
        ["bw", "--session", session, "list", "organizations"],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
        return False
    return {i["id"]: i for i in json.loads(res.stdout)}


class Item(dict):
    """Set some default attributes to all items"""

    def __init__(self, /, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault("fields", [])
        if not any(i["name"] == "autotype" for i in self.get("fields")):
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
    logging.debug(
        f"get_entries: session type={type(session)}, value (first 20 chars)={str(session)[:20]}"
    )

    res = run(
        ["bw", "--session", session, "list", "items"],
        capture_output=True,
        check=False,
    )

    logging.debug(f"get_entries: returncode={res.returncode}")
    logging.debug(f"get_entries: stdout (first 200 chars)={res.stdout[:200]}")
    logging.debug(
        f"get_entries: stderr={res.stderr.decode('utf-8') if res.stderr else 'None'}"
    )

    if not res.stdout:
        logging.error(res)
        return False

    if res.returncode != 0:
        logging.error(f"get_entries failed with return code {res.returncode}")
        logging.error(f"stdout: {res.stdout.decode('utf-8')}")
        logging.error(
            f"stderr: {res.stderr.decode('utf-8') if res.stderr else 'None'}"
        )
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
        ["bw", "--session", session, "sync"], capture_output=True, check=False
    )
    if not res.stdout:
        logging.error(res)
        return False
    return True


def get_folders(session):
    """Return all folder names.

    Return: Dict of folder dicts {id: dict('object':folder,'id':id,'name':<name>)}
            False on error

    """
    res = run(
        ["bw", "--session", session, "list", "folders"],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
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
    cmd = ["bw", "--session", session, "list", "collections"]
    if org_id:
        cmd.extend(["--organizationid", org_id])
    res = run(cmd, capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
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
        logging.error(enc)
        return False
    res = run(
        ["bw", "create", "--session", session, "item", enc.stdout],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
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
        logging.error(enc)
        return False
    res = run(
        ["bw", "edit", "--session", session, "item", item["id"], enc.stdout],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)


def delete_entry(entry, session):
    """Delete existing vault entry

    Args: entry - entry dict object
    Returns: entry object (dict) on success, False on failure

    """
    res = run(
        ["bw", "delete", "--session", session, "item", entry["id"]],
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        logging.error(res)
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
        logging.error(enc)
        return False
    res = run(
        ["bw", "create", "--session", session, "folder", enc.stdout],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)


def delete_folder(folder, session):
    """Delete folder

    Args: folder - folder object (dict)
          session - bytes
    Returns: folder object (dict) on success, False on failure


    """
    res = run(
        ["bw", "delete", "--session", session, "folder", folder["id"]],
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        logging.error(res)
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
        logging.error(enc)
        return False
    res = run(
        ["bw", "edit", "--session", session, "folder", fold["id"], enc.stdout],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
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
        logging.error(enc)
        return False
    res = run(
        [
            "bw",
            "create",
            "--session",
            session,
            "--organizationid",
            org_id.encode(),
            "org-collection".encode(),
            enc.stdout,
        ],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
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
            "--session",
            session,
            "--organizationid",
            collection["organizationId"].encode(),
            "org-collection",
            collection["id"],
        ],
        capture_output=True,
        check=False,
    )
    if res.returncode != 0:
        logging.error(res)
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
        logging.error(enc)
        return False
    res = run(
        [
            "bw",
            "edit",
            "--session",
            session,
            "--organizationid",
            coll["organizationId"].encode(),
            "org-collection",
            coll["id"],
            enc.stdout,
        ],
        capture_output=True,
        check=False,
    )
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)


# vim: set et ts=4 sw=4 :
