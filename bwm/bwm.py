"""Bitwarden-menu main module

"""
from dataclasses import dataclass, field
from enum import Enum, auto
from functools import partial
import multiprocessing
from os import environ, makedirs
from os.path import join
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
import bwm


def get_passphrase(secret="Password"):
    """Get a vault password from dmenu or pinentry

        Args: secret - string ('Password' or '2FA Code' or 'client_secret')
        Returns: string

    """
    pin_prompt = f"SETDESC Enter {secret}\nGETPIN\n"
    pinentry = bwm.CONF.get("dmenu", "pinentry", fallback=None)
    if pinentry:
        password = ""
        out = subprocess.run(pinentry,
                             capture_output=True,
                             check=False,
                             encoding=bwm.ENC,
                             input=pin_prompt).stdout
        if out:
            res = out.split("\n")[2]
            if res.startswith("D "):
                password = res.split("D ")[1]
    else:
        password = dmenu_select(0, f"Enter {secret}")
    return password


@dataclass
class Vault:  # pylint: disable=too-many-instance-attributes
    """Definition for a Vault object

    """
    url: str
    email: str
    passw: str
    twofactor: str
    autotype: str = field(default=None)
    session: bytes = field(default_factory=bytes)
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
    Returns: vaults - list of Vault objects (1st is active) or None on error
                      opening/reading a single vault.

    """
    vaults = [] if vaults is None else vaults
    vault_cli = kwargs.get('vault', "")
    login_cli = kwargs.get('login', "")
    if not vaults:
        args = dict(bwm.CONF.items('vault'))
        servers = [i for i in args if i.startswith('server')]
        for srv in servers:
            idx = srv.rsplit('_', 1)[-1]
            email = args.get(f'email_{idx}', "")
            passw = args.get(f'password_{idx}', "")
            twofactor = args.get(f'twofactor_{idx}', "")
            if not args[srv] or not email:
                continue
            try:
                cmd = args[f'password_cmd_{idx}']
                res = subprocess.run(shlex.split(cmd),
                                     check=False,
                                     capture_output=True,
                                     encoding=bwm.ENC)
                if res.stderr:
                    dmenu_err(f"Password command error: {res.stderr}")
                    sys.exit()
                else:
                    passw = res.stdout.rstrip('\n') if res.stdout else passw
            except KeyError:
                pass
            vaults.append(Vault(args[srv], email, passw, twofactor))
    if vault_cli:
        va_ = [i for i in vaults if i.url == vault_cli
               and (i.email == login_cli or not login_cli)]
        if va_:
            vaults.insert(0, vaults.pop(vaults.index(va_[0])))
        else:
            vaults.insert(0, Vault(vault_cli, login_cli, '', ''))
    if not vaults or (not vaults[0].url or not vaults[0].email):
        sel = get_initial_vault(vault_cli, login_cli)
        if sel:
            vaults.insert(0, sel)
        else:
            return None
    if len(vaults) > 1 and not vault_cli:
        inp = "\n".join(i.url for i in vaults)
        sel = dmenu_select(len(vaults), "Select Vault", inp=inp)
        if not sel or (vaults[0].url == sel and vaults[0].session):
            # No changes if invalid selection or current active vault chosen
            if all(not i.session for i in vaults):
                return None
            return vaults
        # First vault is the active one
        vaults.insert(0, vaults.pop(vaults.index([i for i in vaults if i.url == sel][0])))
    return set_vault(vaults)


def set_vault(vaults):
    """Setup ENV variable and vault info.

    Args: vaults - list of Vault objects (1st one is currently active)
    Returns: vaults - list of Vault objects (with session added for active vault)

    """
    def password():
        passw = get_passphrase()
        return passw or None

    vault = vaults[0]
    vault_dir = join(bwm.DATA_HOME, urlsplit(vault.url).netloc)
    makedirs(vault_dir, exist_ok=True)
    environ["BITWARDENCLI_APPDATA_DIR"] = vault_dir
    status = bwcli.status()
    if status is False:
        vault.session = False
    if status['status'] == 'unauthenticated':
        if status['serverUrl'] is None:
            if bwcli.set_server(vault.url) is False:
                if len(vaults) > 1:
                    vaults.insert(-1, vaults.pop(-1))
                    return vaults
                return None
        vault.passw = vault.passw or password()
        code = get_passphrase("2FA Code") if vault.twofactor else ""
        environ['BW_CLIENTSECRET'] = get_passphrase("client_secret (if required)")
        vault.session, err = bwcli.login(vault.email, vault.passw, vault.twofactor, code)
        del environ['BW_CLIENTSECRET']
    elif status['status'] == 'locked':
        vault.passw = vault.passw or password()
        vault.session, err = bwcli.unlock(vault.passw)
    elif status['status'] == 'unlocked':
        pass
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
        url = dmenu_select(0, "Enter server URL.", "https://vault.bitwarden.com")
        if not url:
            dmenu_err("No URL entered. Try again.")
            return False
    if not email:
        email = dmenu_select(0, "Enter login email address.")
        if not email:
            dmenu_err("No login email address entered. Try again.")
            return False
    twofa = {'None': '', 'TOTP': 0, 'Email': 1, 'Yubikey': 3}
    method = dmenu_select(len(twofa), "Select Two Factor Auth type.", "\n".join(twofa))
    idx = max((i.rsplit('_', 1)[-1] for i in dict(bwm.CONF.items('vault'))
               if i.startswith('server')), default='1')
    # Overwrite blank initial values instead of adding new values (server_2)
    if int(idx) == 1 and not bwm.CONF.get('vault', 'server_1', fallback=''):
        idx = 0
    bwm.CONF.set('vault', f'server_{int(idx) + 1}', url)
    if email:
        bwm.CONF.set('vault', f'email_{int(idx) + 1}', email)
    if method:
        bwm.CONF.set('vault', f'twofactor_{int(idx) + 1}', str(twofa[method]))
    with open(bwm.CONF_FILE, 'w', encoding=bwm.ENC) as conf_file:
        bwm.CONF.write(conf_file)
    return Vault(url, email, '', twofa[method])


def dmenu_view(entries, folders):
    """View/type individual entries (called from dmenu_run)

        Args: entries (list of dicts)
              folders (dict of dicts)

        Returns: None or entry (Item)

    """
    sel = view_all_entries([], entries, folders)
    try:
        entry = entries[int(sel.split('(', 1)[0])]
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


def dmenu_edit(entries, folders, collections, session):
    """Select items to edit (called from dmenu_run)

        Args: entries (list of dicts)
              folders (dict of dict objects)
              collections (dict of dict objects)
              session (bytes)
        Returns: None or entry (Item)

    """
    sel = view_all_entries([], entries, folders)
    try:
        entry = entries[int(sel.split('(', 1)[0])]
    except (ValueError, TypeError):
        return None
    return edit_entry(entry, entries, folders, collections, session)


def dmenu_add(entries, folders, collections, session):
    """Call add item option (called from dmenu_run)

        Args: entries (list of dicts)
              folders (dict of dict objects)
              collections (dict of dict objects)
              session (bytes)
        Returns: None or entry (Item)

    """
    return add_entry(entries, folders, collections, session)


def dmenu_folders(folders, session):
    """Call manage folders option (called from dmenu_run)

        Args: folders (dict of dict objects)
              session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    manage_folders(folders, session)
    return Run.CONTINUE


def dmenu_collections(collections, session):
    """Call manage collections option (called from dmenu_run)

        Args: collections (dict of dict objects)
              session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    manage_collections(collections, session)
    return Run.CONTINUE


def dmenu_sync(session):
    """Call vault sync option (called from dmenu_run)

        Args: session (bytes)

    """
    res = bwcli.sync(session)
    if res is False:
        dmenu_err("Sync error. Check logs.")


def dmenu_clipboard():
    """Process menu entry - Toggle clipboard entry

    """
    bwm.CLIPBOARD = not bwm.CLIPBOARD
    return Run.CONTINUE


class Run(Enum):
    """Enum for dmenu_run return values

    """
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
        hid_fold = [i for i in hid_fold if i in
                    [j['name'] for j in vault.folders.values()]]
        entries_hid = [i for i in vault.entries if i['folder'] not in hid_fold]
    else:
        entries_hid = vault.entries
    options = {'View/Type Individual entries': partial(dmenu_view, entries_hid, vault.folders),
               'View previous entry': partial(dmenu_view_previous_entry,
                                              vault.prev_entry, vault.folders),
               'Edit entries': partial(dmenu_edit, vault.entries, vault.folders,
                                       vault.collections, vault.session),
               'Add entry': partial(dmenu_add, vault.entries, vault.folders,
                                    vault.collections, vault.session),
               'Manage folders': partial(dmenu_folders, vault.folders, vault.session),
               'Manage collections': partial(dmenu_collections, vault.collections, vault.session),
               'Sync vault': partial(dmenu_sync, vault.session),
               'Switch vaults': None,
               "[Clipboard]/Type" if bwm.CLIPBOARD is True else "Clipboard/[Type]": dmenu_clipboard,
               'Lock vault': bwcli.lock}
    sel = view_all_entries(options, entries_hid, vault.folders)
    if not sel:
        return Run.STOP
    if sel == "Lock vault":  # Kill bwm daemon
        options[sel]()
        return Run.LOCK
    if sel == "Sync vault":
        options[sel]()
        return Run.RELOAD
    if sel == "Switch vaults":
        return Run.SWITCH
    if sel not in options:
        # Autotype selected entry
        try:
            entry = vault.entries[int(sel.split('(', 1)[0])]
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
    def __init__(self, server, **kwargs):
        multiprocessing.Process.__init__(self)
        self.server = server
        bwm.CLIPBOARD = kwargs.get('clipboard')
        self.vaults = get_vault(**kwargs)
        if self.vaults is None:
            self.server.kill_flag.set()
            sys.exit()
        self.vault = self.vaults[0]
        self.vault.entries, self.vault.folders, self.vault.collections, self.vault.orgs = \
            bwcli.get_entries(self.vault.session)
        if not all(i for i in (self.vault.entries, self.vault.folders,
                   self.vault.collections, self.vault.orgs) if i is False):
            dmenu_err("Error loading vault entries.")
            self.server.kill_flag.set()
            sys.exit()

    def _set_timer(self):
        """Set inactivity timer

        """
        # pylint: disable=attribute-defined-outside-init
        self.cache_timer = Timer(bwm.SESSION_TIMEOUT_MIN * 60, self.cache_time)
        self.cache_timer.daemon = True
        self.cache_timer.start()

    def run(self):
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
            bwm.CLIPBOARD = dargs.get('clipboard') or bwm.CLIPBOARD
            self.vault.autotype = dargs.get('autotype', "") or bwm.SEQUENCE
            if dargs.get('vault', ""):
                res = Run.SWITCH
                at_saved = self.vault.autotype
            elif dargs.get('lock', False):
                bwcli.lock()
                res = Run.LOCK
            else:
                self.vault.autotype = at_saved if at_saved else self.vault.autotype
                at_saved = ""
                res = dmenu_run(self.vault)
            if res == Run.LOCK:
                try:
                    self.server.kill_flag.set()
                except (EOFError, IOError):
                    return
            if res == Run.RELOAD:
                self.vault.entries, self.vault.folders, self.vault.collections, self.vault.orgs = \
                    bwcli.get_entries(self.vault.session)
                if not all(i for i in (self.vault.entries, self.vault.folders,
                                       self.vault.collections, self.vault.orgs)
                           if i is False):
                    dmenu_err("Error loading entries. See logs.")
                continue
            if res == Run.SWITCH:
                self.vaults = get_vault(self.vaults, **dargs)
                self.vault = self.vaults[0]
                if not self.vault.folders:
                    # Check if folders exist because there will always be the
                    # root folder if entries have been previously retrieved
                    self.vault.entries, self.vault.folders, self.vault.collections, \
                        self.vault.orgs = bwcli.get_entries(self.vault.session)
                if not all(i for i in (self.vault.entries, self.vault.folders,
                           self.vault.collections, self.vault.orgs) if i is False):
                    dmenu_err("Error loading entries. See logs.")
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
        """Kill bwm daemon when cache timer expires

        """
        self.server.cache_time_expired.set()
        if not self.server.start_flag.is_set():
            self.server.kill_flag.set()
            self.server.start_flag.set()

# vim: set et ts=4 sw=4 :
