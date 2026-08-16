"""Bitwarden-menu main module"""

from dataclasses import dataclass, field
from enum import Enum, auto
from functools import partial
from getpass import getpass
import json
import logging
import multiprocessing
from os import environ, makedirs, rename
from os.path import exists, expanduser, join
import shlex
import sys
import subprocess
from threading import Timer
from urllib.parse import urlsplit

from bwm import bwcli
from bwm.bwedit import add_entry, edit_entry, manage_collections, manage_folders
from bwm.bwtype import type_text, type_entry
from bwm.bwview import view_all_entries, view_entry
from bwm.menu import dmenu_select, dmenu_err
from bwm.bwserve import BWCLIServer
import bwm


def _as_bytes(session):
    """Normalize a session token to bytes.

    bwcli returns bytes, the bw serve API returns str.

    Args: session - str or bytes
    Returns: bytes

    """
    return session.encode() if isinstance(session, str) else session


def get_passphrase(secret="Password", obscure=True):
    """Get a vault password from the terminal, dmenu or pinentry

    Every credential prompt in the login/unlock flow goes through here - master
    password, 2FA code and client_secret - so routing this to the terminal is
    what makes the whole flow usable without a launcher.

    Args: secret - string ('Password' or '2FA Code' or 'client_secret')
          obscure - hide what the user types. Told to the launcher explicitly
                    rather than left to dmenu_cmd's prompt matching, which
                    never covered the client_secret prompt.
    Returns: string

    """
    pin_prompt = f"SETDESC Enter {secret}\nGETPIN\n"
    pinentry = bwm.CONF.get("dmenu", "pinentry", fallback=None)
    if bwm.CLI is True:
        try:
            password = getpass(f"Enter {secret}: ")
        except (EOFError, OSError, AttributeError):
            # No terminal to prompt on (e.g. run from a script with stdin
            # closed). Treat it as a cancelled prompt.
            print(
                f"No terminal available to read {secret} from.",
                file=sys.stderr,
            )
            return ""
    elif pinentry:
        password = ""
        out = subprocess.run(
            pinentry,
            capture_output=True,
            check=False,
            encoding=bwm.ENC,
            input=pin_prompt,
        ).stdout
        if out:
            res = out.split("\n")[2]
            if res.startswith("D "):
                password = res.split("D ")[1]
    else:
        password = dmenu_select(0, f"Enter {secret}", obscure=obscure)
    return password


@dataclass
class Vault:  # pylint: disable=too-many-instance-attributes
    """Definition for a Vault object"""

    url: str
    email: str
    passw: str
    twofactor: str
    autotype: str = field(default=None)
    session: bytes = field(default_factory=bytes)
    bwcliserver: BWCLIServer | None = field(default=None)
    use_serve: bool = field(default=True)  # Try to use bw serve by default
    prev_entry: list[bwcli.Item] = field(default=None)
    entries: list[bwcli.Item] = field(default_factory=bwcli.Item)
    folders: dict[dict] = field(default_factory=dict)
    collections: dict[dict] = field(default_factory=dict)
    orgs: dict[dict] = field(default_factory=dict)


def get_vault(vaults=None, **kwargs):
    """Read vault login parameters from config, CLI, or ask for user input.

    Args: vaults - list of Vault objects
          **kwargs - vault (URL string)
                     login (login email address)
                     password (master password, e.g. prompted for by the
                               client on behalf of the daemon)
    Returns: vaults - list of Vault objects (1st is active) or None on error
                      opening/reading a single vault.

    """
    vaults = [] if vaults is None else vaults
    # argparse supplies these keys with a None value when the flag is absent,
    # so `or ""` rather than a dict default
    vault_cli = kwargs.get("vault") or ""
    login_cli = kwargs.get("login") or ""
    passw_cli = kwargs.get("password") or ""
    if not vaults:
        args = dict(bwm.CONF.items("vault"))
        servers = [i for i in args if i.startswith("server")]
        for srv in servers:
            idx = srv.rsplit("_", 1)[-1]
            email = args.get(f"email_{idx}", "")
            passw = args.get(f"password_{idx}", "")
            twofactor = args.get(f"twofactor_{idx}", "")
            if not args[srv] or not email:
                continue
            try:
                cmd = args[f"password_cmd_{idx}"]
                res = subprocess.run(
                    shlex.split(cmd),
                    check=False,
                    capture_output=True,
                    encoding=bwm.ENC,
                )
                if res.stderr:
                    dmenu_err(f"Password command error: {res.stderr}")
                    logging.error(f"Password command error: {res.stderr}")
                    sys.exit(1)
                else:
                    passw = res.stdout.rstrip("\n") if res.stdout else passw
            except KeyError:
                pass
            vaults.append(Vault(args[srv], email, passw, twofactor))
    if vault_cli:
        va_ = [i for i in vaults if i.url == vault_cli]
        if login_cli:
            va_ = [i for i in va_ if i.email == login_cli]
        if len(va_) > 1:
            msg = (
                "Multiple accounts for this vault URL. "
                "Use -l to specify login email."
            )
            dmenu_err(msg)
            return None
        if va_:
            vaults.insert(0, vaults.pop(vaults.index(va_[0])))
            # A password supplied by the caller saves a prompt in set_vault
            vaults[0].passw = vaults[0].passw or passw_cli
        else:
            vaults.insert(0, Vault(vault_cli, login_cli, passw_cli, ""))
    if not vaults or (not vaults[0].url or not vaults[0].email):
        if bwm.CLI is True:
            # get_initial_vault() is an interactive first run wizard that also
            # writes to config.ini. Non-interactive callers pass -v/-l instead.
            # Name the piece that's actually missing: -v alone isn't enough.
            if vault_cli:
                msg = (
                    f"No login email for {vault_cli}. Pass -l, or add "
                    "server_N/email_N to config.ini."
                )
            else:
                msg = (
                    "No vault configured. Add server_N/email_N to config.ini, "
                    "or pass -v and -l."
                )
            dmenu_err(msg)
            return None
        sel = get_initial_vault(vault_cli, login_cli)
        if sel:
            vaults.insert(0, sel)
        else:
            return None
    if len(vaults) > 1 and not vault_cli and bwm.CLI is True:
        dmenu_err("Multiple vaults configured. Specify one with -v.")
        return None
    if len(vaults) > 1 and not vault_cli:
        lines = [
            (f"{'*' if i.session else ' '} {i.url} - {i.email}", i)
            for i in switch_menu_order(vaults)
        ]
        # Keyed on the stripped line - launchers may not return the padding
        by_line = {line.strip(): vault for line, vault in lines}
        inp = "\n".join(line for line, _ in lines)
        sel = dmenu_select(len(vaults), "Select Vault", inp=inp)
        selected = by_line.get(sel.strip()) if sel else None
        if selected is None or (
            selected is vaults[0] and vaults[0].session
        ):
            # No changes if invalid selection or current active vault chosen
            if all(not i.session for i in vaults):
                return None
            return vaults
        # First vault is the active one
        idx = next(n for n, i in enumerate(vaults) if i is selected)
        vaults.insert(0, vaults.pop(idx))
    return set_vault(vaults)


def switch_menu_order(vaults):
    """Order the vaults for display in the switch vault menu.

    Unlocked vaults are the cheap ones to switch to, so they lead the list -
    the topmost is preselected - followed by the currently active vault and
    then the locked ones.

    Args: vaults - list of Vault objects (1st one is currently active)
    Returns: list of Vault objects in display order

    """
    active, rest = vaults[0], vaults[1:]
    return (
        [i for i in rest if i.session]
        + [active]
        + [i for i in rest if not i.session]
    )


def set_vault(vaults):
    """Setup ENV variable and vault info.

    Args: vaults - list of Vault objects (1st one is currently active)
    Returns: vaults - list of Vault objects (with session added for active vault)

    """

    def password():
        passw = get_passphrase()
        return passw or None

    vault = vaults[0]
    netloc_dir = join(bwm.DATA_HOME, urlsplit(vault.url).netloc)
    vault_dir = join(netloc_dir, vault.email)
    # Migrate old flat directory to new netloc/email structure
    if exists(netloc_dir) and not exists(vault_dir):
        # Check that no other vault already has a subdirectory here
        has_other_email_dirs = any(
            exists(join(netloc_dir, v.email))
            for v in vaults
            if v is not vault and v.email
        )
        if not has_other_email_dirs:
            # Old flat dir contains bw CLI data; move into email subdir
            tmp_dir = netloc_dir + ".migrate_tmp"
            try:
                rename(netloc_dir, tmp_dir)
                makedirs(netloc_dir, exist_ok=True)
                rename(tmp_dir, vault_dir)
            except OSError:
                logging.warning("Failed to migrate vault data directory")
                # Fallback: just create the new directory
                makedirs(vault_dir, exist_ok=True)
    makedirs(vault_dir, exist_ok=True)
    environ["BITWARDENCLI_APPDATA_DIR"] = vault_dir

    # Get status first to determine vault state
    # NOTE: Don't start bw serve yet - it requires vault to be authenticated
    status = None
    if vault.bwcliserver is not None:
        # Ask the running server over HTTP. Spawning the CLI costs a Node
        # startup - seconds - which is the bulk of a vault switch.
        status = vault.bwcliserver.get_status() or None
    if status is None:
        # Pass any session we are already holding: `bw status` only reports
        # 'unlocked' when given one, so without this, switching back to a vault
        # that is already unlocked pays for a full unlock again.
        status = bwcli.status(vault.session or b"")
    logging.debug(
        f"set_vault: Initial status check - {status.get('status') if status else 'error'}"
    )

    err = ""
    # Server availability is only ever tested for operations that have already failed or
    # that cannot work offline, so unlocking costs no network round trip
    if not status:
        vault.session = False
        err = (
            "Unable to read the vault status. Is the Bitwarden CLI (bw) "
            "installed and on $PATH? See ~/.cache/bwm.log."
        )
    elif status["status"] == "unauthenticated" and not bwcli.is_online(
        vault.url
    ):
        # The initial login needs the server, unlike unlocking an
        # already authenticated vault, which is entirely local.
        vault.session = False
        err = (
            f"Offline - unable to reach {vault.url}.\n"
            "Initial login requires a network connection. Once logged in, "
            "the vault can be unlocked and read offline."
        )
    elif status["status"] == "unauthenticated":
        if status["serverUrl"] is None:
            # Set server URL using CLI (bw serve not available when unauthenticated)
            success = bwcli.set_server(vault.url)
            if success is False:
                if len(vaults) > 1:
                    vaults.insert(-1, vaults.pop(-1))
                    return vaults
                return None

        vault.passw = vault.passw or password()
        if not vault.passw:
            vault.session = False
            err = b"No password provided"
        else:
            environ["BW_CLIENTSECRET"] = get_passphrase(
                "client_secret (if required)"
            )

            # Step 1: Login via CLI to get session token
            logging.debug("set_vault: Logging in via CLI")
            if vault.twofactor in ("", "1"):
                # Unconfigured or Email OTP: use PTY-based interactive
                # login so the CLI can prompt for 2FA
                result = bwcli.login_pty_start(vault.email, vault.passw)
                if result[0] is False:
                    vault.session, err = result
                else:
                    fd, pid = result
                    code = get_passphrase("2FA Code", obscure=False)
                    vault.session, err = bwcli.login_pty_finish(fd, pid, code)
            else:
                code = (
                    get_passphrase("2FA Code", obscure=False)
                    if vault.twofactor
                    else ""
                )
                vault.session, err = bwcli.login(
                    vault.email, vault.passw, vault.twofactor, code
                )
            logging.debug(
                f"set_vault: CLI login result - session={vault.session is not False}, err={err}"
            )

            del environ["BW_CLIENTSECRET"]

            # Start bw serve, then sync through it
            if vault.session is not False:
                # Serve first, sync second: `bw serve` only requires an
                # authenticated vault, not an unlocked one, so it can come up
                # right after login. Syncing through it then costs an HTTP
                # round trip instead of another ~1.5s of Node startup.
                if vault.use_serve and vault.bwcliserver is None:
                    logging.debug(
                        "set_vault: Starting bw serve with session from login"
                    )
                    vault.bwcliserver = BWCLIServer()
                    if not vault.bwcliserver.start(session=vault.session):
                        logging.info(
                            "bw serve failed to start, falling back to CLI"
                        )
                        vault.bwcliserver.stop()
                        vault.bwcliserver = None
                        vault.use_serve = False
                    else:
                        # Step 3: Call unlock API endpoint on bw serve
                        logging.debug(
                            "set_vault: Calling unlock API on bw serve"
                        )
                        unlock_session, unlock_err = vault.bwcliserver.unlock(
                            vault.passw
                        )
                        if unlock_session is False:
                            logging.warning(
                                f"bw serve unlock API failed: {unlock_err}, but continuing with CLI session"
                            )
                        else:
                            # Unlocking rotates the session, invalidating the
                            # token the CLI unlock returned. Keep the live one
                            # or every later `bw --session` call is rejected.
                            vault.session = _as_bytes(unlock_session)
                            logging.debug(
                                "set_vault: bw serve unlock API successful"
                            )

                logging.debug("set_vault: Syncing vault after login")
                if not sync_vault(vault):
                    logging.warning("set_vault: Vault sync after login failed")

    elif status["status"] == "locked":
        vault.passw = vault.passw or password()

        # Step 1: Unlock via CLI to get session token. This is a local
        # operation and works while offline.
        logging.debug("set_vault: Unlocking via CLI")
        vault.session, err = bwcli.unlock(vault.passw)
        logging.debug(
            f"set_vault: CLI unlock result - session={vault.session is not False}, err={err}"
        )
        if vault.session is False and not bwcli.is_online(vault.url):
            err = (
                f"{err.decode(bwm.ENC) if isinstance(err, bytes) else err}\n\n"
                f"Note: {vault.url} is unreachable, but unlocking does not "
                "need a network connection - check the master password."
            )

        # Step 2: Start bw serve with --session from unlock
        # Step 3: Call /unlock API endpoint to unlock the vault in bw serve
        if (
            vault.session is not False
            and vault.use_serve
            and vault.bwcliserver is None
        ):
            logging.debug(
                "set_vault: Starting bw serve with session from unlock"
            )
            vault.bwcliserver = BWCLIServer()
            if not vault.bwcliserver.start(session=vault.session):
                logging.info("bw serve failed to start, falling back to CLI")
                vault.bwcliserver.stop()
                vault.bwcliserver = None
                vault.use_serve = False
            else:
                # Step 3: Call unlock API endpoint on bw serve
                logging.debug("set_vault: Calling unlock API on bw serve")
                unlock_session, unlock_err = vault.bwcliserver.unlock(
                    vault.passw
                )
                if unlock_session is False:
                    logging.warning(
                        f"bw serve unlock API failed: {unlock_err}, but continuing with CLI session"
                    )
                else:
                    # Unlocking rotates the session, invalidating the token the
                    # CLI unlock returned. Keep the live one or every later
                    # `bw --session` call is rejected.
                    vault.session = _as_bytes(unlock_session)
                    logging.debug("set_vault: bw serve unlock API successful")

    elif status["status"] == "unlocked":
        # Already unlocked, so no need to unlock again. `bw status` doesn't hand
        # the token back in its JSON, so keep the one we passed in, falling back
        # to the environment for a vault unlocked outside bwm.
        vault.session = (
            vault.session
            or status.get("session", b"")
            or environ.get("BW_SESSION", "")
        )
        logging.debug("set_vault: Vault already unlocked via CLI")

        # Start bw serve with the existing session token
        if vault.session and vault.use_serve and vault.bwcliserver is None:
            logging.debug("set_vault: Starting bw serve with existing session")
            vault.bwcliserver = BWCLIServer()
            if not vault.bwcliserver.start(session=vault.session):
                logging.info("bw serve failed to start, falling back to CLI")
                vault.bwcliserver.stop()
                vault.bwcliserver = None
                vault.use_serve = False
            else:
                logging.debug("set_vault: bw serve started successfully")

    if vault.session is False:
        vault.passw = ""
        dmenu_err(err)
        if len(vaults) > 1:
            vaults.insert(-1, vaults.pop(-1))
            vaults = get_vault(vaults)
        else:
            return None
    return vaults


def get_initial_vault(url=None, email=None):
    """Ask for initial server URL and email if not entered in config file or
    passed on the CLI.

     Args: url - string
           login - string

     Returns: Vault object

    """
    if not url:
        url = dmenu_select(
            0, "Enter server URL.", "https://vault.bitwarden.com"
        )
        if not url:
            dmenu_err("No URL entered. Try again.")
            return False
    if not email:
        email = dmenu_select(0, "Enter login email address.")
        if not email:
            dmenu_err("No login email address entered. Try again.")
            return False
    twofa = {"None": "", "TOTP": "0", "Email": "1", "Yubikey": "3"}
    method = dmenu_select(
        len(twofa), "Select Two Factor Auth type.", "\n".join(twofa)
    )
    idx = max(
        (
            i.rsplit("_", 1)[-1]
            for i in dict(bwm.CONF.items("vault"))
            if i.startswith("server")
        ),
        default="1",
    )
    # Overwrite blank initial values instead of adding new values (server_2)
    if int(idx) == 1 and not bwm.CONF.get("vault", "server_1", fallback=""):
        idx = 0
    bwm.CONF.set("vault", f"server_{int(idx) + 1}", url)
    if email:
        bwm.CONF.set("vault", f"email_{int(idx) + 1}", email)
    if method:
        bwm.CONF.set("vault", f"twofactor_{int(idx) + 1}", str(twofa[method]))
    with open(bwm.CONF_FILE, "w", encoding=bwm.ENC) as conf_file:
        bwm.CONF.write(conf_file)
    return Vault(url, email, "", twofa[method])


def dmenu_view(entries, folders):
    """View/type individual entries (called from dmenu_run)

    Args: entries (list of dicts)
          folders (dict of dicts)

    Returns: None or entry (Item)

    """
    sel = view_all_entries([], entries, folders)
    try:
        entry = entries[int(sel.split("(", 1)[0])]
    except (ValueError, TypeError):
        return None
    text = view_entry(entry, folders)
    type_text(text)
    return entry


def dmenu_view_previous_entry(entry, folders):
    """View previous entry

    Args: entry (Item)
    Returns: entry (Item)

    """
    if entry is not None:
        text = view_entry(entry, folders)
        type_text(text)
    return entry


def dmenu_edit(entries, folders, collections, vault):
    """Select items to edit (called from dmenu_run)

    Args: entries (list of dicts)
          folders (dict of dict objects)
          collections (dict of dict objects)
          vault (Vault object)
    Returns: None or entry (Item)

    """
    sel = view_all_entries([], entries, folders)
    try:
        entry = entries[int(sel.split("(", 1)[0])]
    except (ValueError, TypeError):
        return None
    return edit_entry(entry, entries, folders, collections, vault)


def dmenu_add(entries, folders, collections, vault):
    """Call add item option (called from dmenu_run)

    Args: entries (list of dicts)
          folders (dict of dict objects)
          collections (dict of dict objects)
          vault (Vault object)
    Returns: None or entry (Item)

    """
    return add_entry(entries, folders, collections, vault)


def dmenu_folders(folders, vault):
    """Call manage folders option (called from dmenu_run)

    Args: folders (dict of dict objects)
          vault (Vault object)
    Returns: dict {err: <Bool>, reload: <Bool>}

    """
    manage_folders(folders, vault)
    return Run.CONTINUE


def dmenu_collections(collections, vault):
    """Call manage collections option (called from dmenu_run)

    Args: collections (dict of dict objects)
          vault (Vault object)
    Returns: dict {err: <Bool>, reload: <Bool>}

    """
    manage_collections(collections, vault)
    return Run.CONTINUE


def check_online(vault):
    """Verify the vault server is reachable before a network operation.

    Connectivity is re-tested on each call to an operation that needs the
    network. A session started offline starts working again as soon as the
    network comes back.

    Args: vault - Vault object
    Returns: True if online. Shows an error and returns False if not.

    """
    if not bwcli.is_online(vault.url):
        dmenu_err(
            f"Offline - unable to reach {vault.url}.\n"
            "This operation needs a connection to the vault server. "
            "Viewing and typing existing entries works offline."
        )
        return False
    return True


def dmenu_sync(vault):
    """Call vault sync option (called from dmenu_run)

    Args: vault - Vault object
    Returns: True on success, False on error or when offline

    """
    if not check_online(vault):
        return False

    if sync_vault(vault) is False:
        dmenu_err("Sync error. Check logs.")
        return False
    return True


def sync_vault(vault):
    """Sync the vault using the running bw serve, or the CLI

    Going through bw serve when it is up saves spawning a `bw` process, which
    costs ~1.5s of Node startup before it does any work.

    Args: vault - Vault object
    Returns: True on success, False on error

    """
    if vault.bwcliserver:
        return vault.bwcliserver.sync()
    return bwcli.sync(vault.session)


def lock_vault(vault):
    """Lock vault using server or CLI

    Args: vault - Vault object
    Returns: True on success, False on error
    """
    if vault.bwcliserver:
        return vault.bwcliserver.lock()
    else:
        return bwcli.lock()


def dmenu_clipboard():
    """Process menu entry - Toggle clipboard entry"""
    bwm.CLIPBOARD = not bwm.CLIPBOARD
    return Run.CONTINUE


class Run(Enum):
    """Enum for dmenu_run return values"""

    LOCK = auto()
    CONTINUE = auto()
    RELOAD = auto()
    STOP = auto()
    SWITCH = auto()


def dmenu_run(vault):
    """Run dmenu with the given vault object

    If 'hide_folders' is defined in config.ini, hide those from main and
    view/type all views.

    Returns: Run Enum (LOCK, CONTINUE, RELOAD, STOP or SWITCH)

    """
    if bwm.CONF.has_option("vault", "hide_folders"):
        hid_fold = bwm.CONF.get("vault", "hide_folders").split("\n")
        # Validate ignored folder names in config.ini
        hid_fold = [
            i
            for i in hid_fold
            if i in [j["name"] for j in vault.folders.values()]
        ]
        entries_hid = [i for i in vault.entries if i["folder"] not in hid_fold]
    else:
        entries_hid = vault.entries

    def needs_server(func):
        """Block an option that writes to the vault while offline"""

        def wrapper():
            if not check_online(vault):
                return Run.CONTINUE
            return func()

        return wrapper

    options = {
        "View/Type Individual entries": partial(
            dmenu_view, entries_hid, vault.folders
        ),
        "View previous entry": partial(
            dmenu_view_previous_entry, vault.prev_entry, vault.folders
        ),
        "Edit entries": needs_server(
            partial(
                dmenu_edit,
                vault.entries,
                vault.folders,
                vault.collections,
                vault,
            )
        ),
        "Add entry": needs_server(
            partial(
                dmenu_add,
                vault.entries,
                vault.folders,
                vault.collections,
                vault,
            )
        ),
        "Manage folders": needs_server(
            partial(dmenu_folders, vault.folders, vault)
        ),
        "Manage collections": needs_server(
            partial(dmenu_collections, vault.collections, vault)
        ),
        "Sync vault": partial(dmenu_sync, vault),
        "Switch vaults": None,
        "[Clipboard]/Type"
        if bwm.CLIPBOARD is True
        else "Clipboard/[Type]": dmenu_clipboard,
        "Lock vault": partial(lock_vault, vault),
    }
    sel = view_all_entries(options, entries_hid, vault.folders)
    if not sel:
        return Run.STOP
    if sel == "Lock vault":  # Kill bwm daemon
        options[sel]()
        return Run.LOCK
    if sel == "Sync vault":
        # Nothing to reload if the sync was skipped or failed
        return Run.RELOAD if options[sel]() else Run.CONTINUE
    if sel == "Switch vaults":
        return Run.SWITCH
    if sel not in options:
        # Autotype selected entry
        try:
            entry = vault.entries[int(sel.split("(", 1)[0])]
        except (ValueError, TypeError):
            return Run.STOP
        type_entry(entry, vault.autotype)
        return Run.STOP
    return options[sel]()


class DmenuRunner(multiprocessing.Process):
    # pylint: disable=too-many-instance-attributes
    """Listen for dmenu calling event and run bwm

    Args: server - Server object

    """

    def __init__(self, server, unlocked=None, background=True, **kwargs):
        multiprocessing.Process.__init__(self)
        self.server = server
        self.unlocked = unlocked
        self.background = background
        cfile = kwargs.get("config")
        bwm.reload_config(None if cfile is None else expanduser(cfile))
        bwm.CLIPBOARD = kwargs.get("clipboard")
        self.vaults = get_vault(**kwargs)
        if self.vaults is None:
            self.server.kill_flag.set()
            # __init__ runs in the parent process, so this is the exit code the
            # user sees. Failing to open a vault is not success.
            sys.exit(1)
        self.vault = self.vaults[0]

        # Get entries using server or CLI
        if self.vault.bwcliserver:
            (
                self.vault.entries,
                self.vault.folders,
                self.vault.collections,
                self.vault.orgs,
            ) = self.vault.bwcliserver.get_entries()
        else:
            (
                self.vault.entries,
                self.vault.folders,
                self.vault.collections,
                self.vault.orgs,
            ) = bwcli.get_entries(self.vault.session)

        if not all(
            i
            for i in (
                self.vault.entries,
                self.vault.folders,
                self.vault.collections,
                self.vault.orgs,
            )
            if i is False
        ):
            dmenu_err("Error loading vault entries.")
            self.server.kill_flag.set()
            sys.exit(1)
        self._publish_unlocked()

    def _publish_unlocked(self):
        """Publish which vaults hold a session, for the client to query.

        The client uses this to decide whether a --show request needs a master
        password prompt, which has to happen in the client's terminal.

        """
        if self.unlocked is None:
            return
        data = json.dumps(
            [[i.url, i.email] for i in self.vaults if i.session]
        ).encode(bwm.ENC)
        if len(data) >= len(self.unlocked):
            logging.warning("Too many unlocked vaults to publish")
            return
        with self.unlocked.get_lock():
            self.unlocked.value = data

    def unlock_for_show(self, **kwargs):
        """Unlock a vault the daemon isn't holding yet, for a --show request.

        The client already prompted for the master password and sent it along,
        so get_vault() can unlock without any interaction. CLI mode is forced on
        for the attempt so a failure reports to stderr instead of popping a
        launcher dialog at a user who is sitting at a terminal.

        The GUI's active vault is restored afterwards: running a CLI query
        shouldn't move the menu out from under someone.

        Args: kwargs - the client's parsed args, including 'password'
        Returns: the unlocked Vault, or None

        """
        prev_active = self.vault
        prev_appdata = environ.get("BITWARDENCLI_APPDATA_DIR")
        prev_cli = bwm.CLI
        bwm.CLI = True
        try:
            vaults = get_vault(self.vaults, **kwargs)
        finally:
            bwm.CLI = prev_cli
        if not vaults:
            return None
        self.vaults = vaults
        vault = self.vaults[0]
        if vault.session is False or not vault.session:
            return None
        # Test folders, not entries: Vault.entries defaults to bwcli.Item(),
        # which seeds itself with a 'fields' key and is therefore truthy even
        # when nothing has been loaded. The Run.SWITCH branch does the same.
        if not vault.folders:
            if vault.bwcliserver:
                res = vault.bwcliserver.get_entries()
            else:
                res = bwcli.get_entries(vault.session)
            if not res or res[0] is False:
                return None
            vault.entries, vault.folders, vault.collections, vault.orgs = res
        self._publish_unlocked()
        # Put the GUI back where it was
        if prev_active in self.vaults:
            self.vaults.insert(
                0, self.vaults.pop(self.vaults.index(prev_active))
            )
        self.vault = prev_active
        if prev_appdata is not None:
            environ["BITWARDENCLI_APPDATA_DIR"] = prev_appdata
        return vault

    def show_entry(self, **kwargs):
        """Handle a --show request and send the result back to the client.

        Runs in the daemon, which has no terminal, so this must never call a
        launcher or prompt. Results travel back as an (ok, text) tuple.

        Args: kwargs - the client's parsed args

        """
        # pylint: disable=import-outside-toplevel
        from bwm.run_once import show_fields

        vault = self.vault
        url = kwargs.get("vault", "")
        if url:
            login = kwargs.get("login", "")
            matched = [
                i
                for i in self.vaults
                if i.url == url and (not login or i.email == login) and i.session
            ]
            if not matched:
                vault = self.unlock_for_show(**kwargs)
                if vault is None:
                    self.server.send_result(
                        kwargs.get("show_id"),
                        (False, f"Could not unlock vault {url}."),
                    )
                    return
            else:
                vault = matched[0]
        self.server.send_result(
            kwargs.get("show_id"),
            show_fields(
                vault.entries,
                vault.folders,
                kwargs.get("show", ""),
                fields=kwargs.get("field"),
            ),
        )

    def _set_timer(self):
        """Set inactivity timer"""
        # pylint: disable=attribute-defined-outside-init
        self.cache_timer = Timer(bwm.SESSION_TIMEOUT_MIN * 60, self.cache_time)
        self.cache_timer.daemon = True
        self.cache_timer.start()

    def run(self):
        bwm.detach_from_terminal(self.background)
        if self.background:
            # Started from a --show invocation, this process inherited
            # bwm.CLI=True. It is now detached with no terminal to prompt on,
            # and everything it does from here is GUI work, so CLI mode would
            # only suppress menus - notably the vault selection menu.
            bwm.CLI = False
        at_saved = ""
        while True:
            self.server.start_flag.wait()
            if self.server.kill_flag.is_set():
                break
            try:
                self.cache_timer.cancel()
            except AttributeError:
                pass
            self._set_timer()
            dargs = {}
            if self.server.args_flag.is_set():
                dargs = self.server.get_args()
                self.server.args_flag.clear()
            if dargs.get("show"):
                # --show handles the clipboard itself and must not leave the
                # GUI's clipboard mode toggled
                prev_clipboard = bwm.CLIPBOARD
                try:
                    bwm.CLIPBOARD = bool(dargs.get("clipboard"))
                    self.show_entry(**dargs)
                finally:
                    bwm.CLIPBOARD = prev_clipboard
                self.server.start_flag.clear()
                continue
            bwm.CLIPBOARD = dargs.get("clipboard") or bwm.CLIPBOARD
            self.vault.autotype = dargs.get("autotype", "") or bwm.SEQUENCE
            if dargs.get("vault", ""):
                res = Run.SWITCH
                at_saved = self.vault.autotype
            elif dargs.get("lock", False):
                # lock_vault, not bwcli.lock: the daemon usually has a bw serve
                # running, and the menu's "Lock vault" option already goes
                # through it.
                lock_vault(self.vault)
                res = Run.LOCK
            else:
                self.vault.autotype = (
                    at_saved if at_saved else self.vault.autotype
                )
                at_saved = ""
                res = dmenu_run(self.vault)
            if res == Run.LOCK:
                try:
                    self.server.kill_flag.set()
                except (EOFError, IOError):
                    return
            if res == Run.RELOAD:
                # Reload entries using server or CLI
                if self.vault.bwcliserver:
                    (
                        self.vault.entries,
                        self.vault.folders,
                        self.vault.collections,
                        self.vault.orgs,
                    ) = self.vault.bwcliserver.get_entries()
                else:
                    (
                        self.vault.entries,
                        self.vault.folders,
                        self.vault.collections,
                        self.vault.orgs,
                    ) = bwcli.get_entries(self.vault.session)

                if not all(
                    i
                    for i in (
                        self.vault.entries,
                        self.vault.folders,
                        self.vault.collections,
                        self.vault.orgs,
                    )
                    if i is False
                ):
                    dmenu_err("Error loading entries. See logs.")
                continue
            if res == Run.SWITCH:
                self.vaults = get_vault(self.vaults, **dargs)
                if self.vaults is None:
                    continue
                self.vault = self.vaults[0]
                if not self.vault.folders:
                    # Check if folders exist because there will always be the
                    # root folder if entries have been previously retrieved
                    if self.vault.bwcliserver:
                        (
                            self.vault.entries,
                            self.vault.folders,
                            self.vault.collections,
                            self.vault.orgs,
                        ) = self.vault.bwcliserver.get_entries()
                    else:
                        (
                            self.vault.entries,
                            self.vault.folders,
                            self.vault.collections,
                            self.vault.orgs,
                        ) = bwcli.get_entries(self.vault.session)

                if not all(
                    i
                    for i in (
                        self.vault.entries,
                        self.vault.folders,
                        self.vault.collections,
                        self.vault.orgs,
                    )
                    if i is False
                ):
                    dmenu_err("Error loading entries. See logs.")
                self._publish_unlocked()
                continue
            if res == Run.CONTINUE:
                continue
            if str(res) not in repr(Run.__members__):
                self.vault.prev_entry = res or self.vault.prev_entry
            if self.server.cache_time_expired.is_set():
                self.server.kill_flag.set()
            if self.server.kill_flag.is_set():
                break
            self.server.start_flag.clear()

    def cache_time(self):
        """Kill bwm daemon when cache timer expires"""
        self.server.cache_time_expired.set()
        if not self.server.start_flag.is_set():
            self.server.kill_flag.set()
            self.server.start_flag.set()


# vim: set et ts=4 sw=4 :
