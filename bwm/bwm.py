"""Bitwarden-menu main module

"""
from contextlib import closing
from enum import Enum, auto
from functools import partial
import multiprocessing
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser
import random
import shlex
import socket
import string
import sys
from subprocess import call, Popen, PIPE
from threading import Timer

import bwm.bwcli as bwcli
from bwm.bwedit import add_entry, edit_entry, manage_collections, manage_folders
from bwm.bwtype import type_text, type_entry
from bwm.bwview import view_all_entries, view_entry
from bwm.menu import dmenu_select, dmenu_err
import bwm


def find_free_port():
    """Find random free port to use for BaseManager server

    Returns: int Port

    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(('127.0.0.1', 0))  # pylint:disable=no-member
        return sock.getsockname()[1]  # pylint:disable=no-member


def random_str():
    """Generate random auth string for BaseManager

    Returns: string

    """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(15))


def get_auth():
    """Generate and save port and authkey to ~/.cache/.bwm-auth

    Returns: int port, bytestring authkey

    """
    auth = bwm.configparser.ConfigParser()
    if not exists(bwm.AUTH_FILE):
        fdr = os.open(bwm.AUTH_FILE, os.O_WRONLY | os.O_CREAT, 0o600)
        with open(fdr, 'w') as a_file:
            auth.set('DEFAULT', 'port', str(find_free_port()))
            auth.set('DEFAULT', 'authkey', random_str())
            auth.write(a_file)
    try:
        auth.read(bwm.AUTH_FILE)
        port = auth.get('DEFAULT', 'port')
        authkey = auth.get('DEFAULT', 'authkey').encode()
    except (bwm.configparser.NoOptionError,
            bwm.configparser.MissingSectionHeaderError,
            bwm.configparser.ParsingError,
            multiprocessing.context.AuthenticationError):
        os.remove(bwm.AUTH_FILE)
        dmenu_err("Cache file was corrupted. Stopping all instances. Please try again")
        call(["pkill", "bwm"])  # Kill all prior instances as well
        return None, None
    return int(port), authkey


def get_passphrase():
    """Get a vault password from dmenu or pinentry

    Returns: string

    """
    pinentry = None
    if bwm.CONF.has_option("dmenu", "pinentry"):
        pinentry = bwm.CONF.get("dmenu", "pinentry")
    if pinentry:
        password = ""
        out = Popen(pinentry,
                    stdout=PIPE,
                    stdin=PIPE).communicate(
                        input=b'setdesc Enter vault password\ngetpin\n')[0]
        if out:
            res = out.decode(bwm.ENC).split("\n")[2]
            if res.startswith("D "):
                password = res.split("D ")[1]
    else:
        password = dmenu_select(0, "Passphrase")
    return password


def get_vault():
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
        email = args_dict.get('email_{}'.format(idx), "")
        passw = args_dict.get('password_{}'.format(idx), "")
        try:
            cmd = args_dict['password_cmd_{}'.format(idx)]
            res = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE).communicate()
            if res[1]:
                dmenu_err("Password command error: {}".format(res[1]))
                sys.exit()
            else:
                passw = res[0].decode().rstrip('\n') if res[0] else passw
        except KeyError:
            pass
        if srv:
            vaults.append((args_dict[srv], email, passw))
    if not vaults or (not vaults[0][0] or not vaults[0][1]):
        res = get_initial_vault()
        if res:
            vaults.insert(0, res)
        else:
            return None
    if len(vaults) > 1:
        inp_bytes = "\n".join(i[0] for i in vaults).encode(bwm.ENC)
        sel = dmenu_select(len(vaults), "Select Vault", inp=inp_bytes)
        vaults = [i for i in vaults if i[0] == sel]
        if not sel or not vaults:
            return None
    url, email, passw = vaults[0]
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
        session, err = bwcli.login(email, passw)
    elif status['status'].endswith('locked'):
        session, err = bwcli.unlock(passw)
    if session is False:
        dmenu_err(err)
        return None
    return session


def get_initial_vault():
    """Ask for initial server URL and email if not entered in config file

    """
    url = dmenu_select(0, "Enter server URL.")
    if not url:
        dmenu_err("No URL entered. Try again.")
        return False
    email = dmenu_select(0, "Enter login email address.")
    with open(bwm.CONF_FILE, 'w') as conf_file:
        bwm.CONF.set('vault', 'server_1', url)
        if email:
            bwm.CONF.set('vault', 'email_1', email)
        bwm.CONF.write(conf_file)
    return (url, email, '')


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


def client():
    """Define client connection to server BaseManager

    Returns: BaseManager object
    """
    port, auth = get_auth()
    mgr = BaseManager(address=('', port), authkey=auth)
    mgr.register('set_event')
    mgr.connect()
    return mgr


class DmenuRunner(multiprocessing.Process):
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
        self.cache_timer = Timer(bwm.SESSION_TIMEOUT_MIN * 60, self.cache_time) # pylint: disable=attribute-defined-outside-init
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


class Server(multiprocessing.Process):
    """Run BaseManager server to listen for dmenu calling events

    """
    def __init__(self):
        multiprocessing.Process.__init__(self)
        self.port, self.authkey = get_auth()
        self.start_flag = multiprocessing.Event()
        self.kill_flag = multiprocessing.Event()
        self.cache_time_expired = multiprocessing.Event()
        self.start_flag.set()

    def run(self):
        serv = self.server()  # pylint: disable=unused-variable
        self.kill_flag.wait()

    def server(self):
        """Set up BaseManager server

        """
        mgr = BaseManager(address=('127.0.0.1', self.port),
                          authkey=self.authkey)
        mgr.register('set_event', callable=self.start_flag.set)
        mgr.start()
        return mgr


def run():
    """Main entrypoint. Start the background Manager and Dmenu runner processes.

    """
    server = Server()
    dmenu = DmenuRunner(server)
    dmenu.daemon = True
    server.start()
    dmenu.start()
    server.join()
    if exists(expanduser(bwm.AUTH_FILE)):
        os.remove(expanduser(bwm.AUTH_FILE))

# vim: set et ts=4 sw=4 :
