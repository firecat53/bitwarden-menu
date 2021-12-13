"""Bitwarden-menu main module

"""
from enum import Enum, auto
from functools import partial
import multiprocessing
import shlex
import sys
import subprocess
from threading import Timer

from bwm import bwcli
from bwm.bwedit import add_entry, edit_entry, manage_collections, manage_folders
from bwm.bwtype import type_text, type_entry
from bwm.bwview import view_all_entries, view_entry
from bwm.menu import dmenu_select, dmenu_err
import bwm


def get_passphrase(twofac=False):
    """Get a vault password from dmenu or pinentry

        Args: twofac - bool (default False) prompt for 2FA code
        Returns: string

    """
    pinentry = None
    pin_prompt = 'setdesc Enter vault password\ngetpin\n' if twofac is False \
        else 'setdesc Enter 2FA code\ngetpin\n'
    if bwm.CONF.has_option("dmenu", "pinentry"):
        pinentry = bwm.CONF.get("dmenu", "pinentry")
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
        password = dmenu_select(0, "Password" if twofac is False else "2FA Code")
    return password


def get_vault():
    # pylint: disable=too-many-return-statements,too-many-locals,too-many-branches
    """Read vault login parameters from config or ask for user input.

    Returns: Session - bytes
                       None on error opening/reading vault

    """
    args = bwm.CONF.items('vault')
    args_dict = dict(args)
    servers = [i for i in args_dict if i.startswith('server')]
    vaults = []
    for srv in servers:
        idx = srv.rsplit('_', 1)[-1]
        email = args_dict.get(f'email_{idx}', "")
        passw = args_dict.get(f'password_{idx}', "")
        twofactor = args_dict.get(f'twofactor_{idx}', None)
        if not args_dict[srv] or not email:
            continue
        try:
            cmd = args_dict[f'password_cmd_{idx}']
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
        vaults.append((args_dict[srv], email, passw, twofactor))
    if not vaults or (not vaults[0][0] or not vaults[0][1]):
        res = get_initial_vault()
        if res:
            vaults.insert(0, res)
        else:
            return None
    if len(vaults) > 1:
        inp = "\n".join(i[0] for i in vaults)
        sel = dmenu_select(len(vaults), "Select Vault", inp=inp)
        vaults = [i for i in vaults if i[0] == sel]
        if not sel or not vaults:
            return None
    url, email, passw, twofactor = vaults[0]
    status = bwcli.status()
    if status is False:
        return None
    if not passw:
        passw = get_passphrase()
        if not passw:
            return None
    if status['serverUrl'] != url:
        res = bwcli.set_server(url)
        if res is False:
            return None
    if status['userEmail'] != email or status['status'] == 'unauthenticated':
        code = get_passphrase(True) if twofactor else ""
        session, err = bwcli.login(email, passw, twofactor, code)
    elif status['status'].endswith('locked'):
        session, err = bwcli.unlock(passw)
    if session is False:
        dmenu_err(err)
        return None
    return session


def get_initial_vault():
    """Ask for initial server URL and email if not entered in config file

    """
    url = dmenu_select(0, "Enter server URL.", "https://vault.bitwarden.com")
    if not url:
        dmenu_err("No URL entered. Try again.")
        return False
    email = dmenu_select(0, "Enter login email address.")
    twofa = {'None': '', 'TOTP': 0, 'Email': 1, 'Yubikey': 3}
    method = dmenu_select(len(twofa), "Select Two Factor Auth type.", "\n".join(twofa))
    with open(bwm.CONF_FILE, 'w', encoding=bwm.ENC) as conf_file:
        bwm.CONF.set('vault', 'server_1', url)
        if email:
            bwm.CONF.set('vault', 'email_1', email)
        if method:
            bwm.CONF.set('vault', 'twofactor_1', str(twofa[method]))
        bwm.CONF.write(conf_file)
    return (url, email, '', twofa[method])


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


class Run(Enum):
    """Enum for dmenu_run return values

    """
    LOCK = auto()
    CONTINUE = auto()
    RELOAD = auto()


def dmenu_run(entries, folders, collections, session, prev_entry):
    """Run dmenu with the given list of vault Entry objects

    If 'hide_folders' is defined in config.ini, hide those from main and
    view/type all views.

    Returns: Run Enum (LOCK, CONTINUE or RELOAD)

    """
    if bwm.CONF.has_option("vault", "hide_folders"):
        hid_fold = bwm.CONF.get("vault", "hide_folders").split("\n")
        # Validate ignored folder names in config.ini
        hid_fold = [i for i in hid_fold if i in
                    [j['name'] for j in folders.values()]]
        entries_hid = [i for i in entries if i['folder'] not in hid_fold]
    else:
        entries_hid = entries
    options = {'View/Type Individual entries': partial(dmenu_view, entries_hid, folders),
               'View previous entry': partial(dmenu_view_previous_entry, prev_entry, folders),
               'Edit entries': partial(dmenu_edit, entries, folders, collections, session),
               'Add entry': partial(dmenu_add, entries, folders, collections, session),
               'Manage folders': partial(dmenu_folders, folders, session),
               'Manage collections': partial(dmenu_collections, collections, session),
               'Sync vault': partial(dmenu_sync, session),
               'Lock vault': bwcli.lock}
    sel = view_all_entries(options, entries_hid, folders)
    if not sel:
        return Run.CONTINUE
    if sel == "Lock vault":  # Kill bwm daemon
        options[sel]()
        return Run.LOCK
    if sel == "Sync vault":
        options[sel]()
        return Run.RELOAD
    if sel not in options:
        # Autotype selected entry
        try:
            entry = entries[int(sel.split('(', 1)[0])]
        except (ValueError, TypeError):
            return Run.CONTINUE
        type_entry(entry)
        return Run.CONTINUE
    return options[sel]()


class DmenuRunner(multiprocessing.Process):
    # pylint: disable=too-many-instance-attributes
    """Listen for dmenu calling event and run bwm

    Args: server - Server object

    """
    def __init__(self, server):
        multiprocessing.Process.__init__(self)
        self.server = server
        self.session = get_vault()
        if self.session is None:
            self.server.kill_flag.set()
            sys.exit()
        self.entries, self.folders, self.collections, self.orgs = bwcli.get_entries(self.session)
        self.prev_entry = None
        if not all(i for i in (self.entries, self.folders, self.collections, self.orgs)
                   if i is False):
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
        while True:
            self.server.start_flag.wait()
            if self.server.kill_flag.is_set():
                break
            try:
                self.cache_timer.cancel()
            except AttributeError:
                pass
            self._set_timer()
            res = dmenu_run(self.entries, self.folders, self.collections,
                            self.session, self.prev_entry)
            if res == Run.LOCK:
                try:
                    self.server.kill_flag.set()
                except (EOFError, IOError):
                    return
            if res == Run.RELOAD:
                self.entries, self.folders, self.collections, self.orgs = \
                        bwcli.get_entries(self.session)
                if not all(i for i in (self.entries, self.folders, self.collections, self.orgs)
                           if i is False):
                    dmenu_err("Error loading entries. See logs.")
            if str(res) not in repr(Run.__members__):
                self.prev_entry = res or self.prev_entry
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
