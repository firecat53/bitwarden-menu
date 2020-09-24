"""Bitwarden-menu main module

"""
from contextlib import closing
from enum import Enum, auto
from functools import partial
from multiprocessing import Event, Process
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser, join
import random
import shlex
import socket
import string
import sys
from subprocess import call, Popen, PIPE
from threading import Timer
import webbrowser

import bwm.bwcli as bwcli
from bwm.bwedit import add_entry, edit_entry, manage_collections, manage_folders
from bwm.bwtype import type_text, type_entry
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
        with open(bwm.AUTH_FILE, 'w') as a_file:
            auth.set('DEFAULT', 'port', str(find_free_port()))
            auth.set('DEFAULT', 'authkey', random_str())
            auth.write(a_file)
    try:
        auth.read(bwm.AUTH_FILE)
        port = auth.get('DEFAULT', 'port')
        authkey = auth.get('DEFAULT', 'authkey').encode()
    except (bwm.configparser.NoOptionError, bwm.configparser.MissingSectionHeaderError):
        os.remove(bwm.AUTH_FILE)
        dmenu_err("Cache file was corrupted. Stopping all instances. Please try again")
        call(["pkill", "bwm"])  # Kill all prior instances as well
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


def view_all_entries(options, vault_entries):
    """Generate numbered list of all vault entries and open with dmenu.

    Returns: dmenu selection

    """
    num_align = len(str(len(vault_entries)))
    bw_entry_pattern = str("{:>{na}} - {} - {} - {}")  # Folder/name,username,url
    # Have to number each entry to capture duplicates correctly
    vault_entries_b = str("\n").join(bw_entry_pattern.format(
        j,
        join(i['folder'], i['name']),
        i['login']['username'],
        i['login']['url'],
        na=num_align) for j, i in enumerate(vault_entries)).encode(bwm.ENC)
    if options:
        options_b = ("\n".join(options) + "\n").encode(bwm.ENC)
        entries_b = options_b + vault_entries_b
    else:
        entries_b = vault_entries_b
    return dmenu_select(min(bwm.DMENU_LEN, len(options) + len(vault_entries)), inp=entries_b)


def view_entry(entry):
    """Show title, username, password, url and notes for an entry.

    Returns: dmenu selection

    """
    fields = [entry['name'] or "Title: None",
              entry['folder'],
              entry['login']['username'] or "Username: None",
              '**********' if entry['login']['password'] else "Password: None",
              entry['login']['url'] or "URL: None",
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=vault_entries_b)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == "Notes: None":
        sel = ""
    elif sel == '**********':
        sel = entry['login']['password']
    elif sel == fields[3]:
        if sel != "URL: None":
            webbrowser.open(sel)
        sel = ""
    return sel


def view_notes(notes):
    """View the 'Notes' field line-by-line within dmenu.

    Returns: text of the selected line for typing

    """
    notes_l = notes.split('\n')
    notes_b = "\n".join(notes_l).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(notes_l)), inp=notes_b)
    return sel


def dmenu_view(entries):
    """View/type individual entries (called from dmenu_run)

        Args: entries (list of dicts)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    sel = view_all_entries([], entries)
    try:
        entry = entries[int(sel.split('-', 1)[0])]
    except (ValueError, TypeError):
        return {'err': False, 'reload': False}
    text = view_entry(entry)
    type_text(text)
    return {'err': False, 'reload': False}


def dmenu_edit(entries, folders, collections, session):
    """Select items to edit (called from dmenu_run)

        Args: entries (list of dicts)
              folders (dict of dict objects)
              collections (dict of dict objects)
              session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    sel = view_all_entries([], entries)
    try:
        entry = entries[int(sel.split('-', 1)[0])]
    except (ValueError, TypeError):
        return {'err': False, 'reload': False}
    edit = True
    entry_ch = False
    while edit != "deleted" and edit:
        edit = edit_entry(entry, folders, collections, session)
        if not isinstance(edit, bool):
            entry_ch = True
            entry = edit
    if entry_ch is True:
        if entry != "deleted":
            res = bwcli.edit_entry(entry, session)
            if res is False:
                dmenu_err("Error editing entry")
                return {'err': True, 'reload': False}
        return {'err': False, 'reload': True}
    return {'err': False, 'reload': False}


def dmenu_add(folders, collections, session):
    """Call add item option (called from dmenu_run)

        Args: folders (dict of dict objects)
              collections (dict of dict objects)
              session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}
    """
    entry = add_entry(folders, collections, session)
    if entry:
        return {'err': False, 'reload': True}
    dmenu_err("No entry added")
    return {'err': True, 'reload': False}


def dmenu_folders(folders, session):
    """Call manage folders option (called from dmenu_run)

        Args: folders (dict of dict objects)
              session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    folder_ch = manage_folders(folders, session)
    if folder_ch is True:
        return {'err': False, 'reload': True}
    return {'err': False, 'reload': False}


def dmenu_collections(collections, session):
    """Call manage collections option (called from dmenu_run)

        Args: collections (dict of dict objects)
              session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    collection_ch = manage_collections(collections, session)
    if collection_ch is True:
        return {'err': False, 'reload': True}
    return {'err': False, 'reload': False}


def dmenu_sync(session):
    """Call vault sync option (called from dmenu_run)

        Args: session (bytes)
        Returns: dict {err: <Bool>, reload: <Bool>}

    """
    res = bwcli.sync(session)
    if res is False:
        dmenu_err("Sync error. Check logs.")
        return {'err': True, 'reload': False}
    return {'err': False, 'reload': True}


class Run(Enum):
    """Enum for dmenu_run return values

    """
    LOCK = auto()
    CONTINUE = auto()
    RELOAD = auto()


def dmenu_run(entries, folders, collections, session):
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
    options = {'View/Type Individual entries': partial(dmenu_view, entries_hid),
               'Edit entries': partial(dmenu_edit, entries, folders, collections, session),
               'Add entry': partial(dmenu_add, folders, collections, session),
               'Manage folders': partial(dmenu_folders, folders, session),
               'Manage collections': partial(dmenu_collections, collections, session),
               'Sync vault': partial(dmenu_sync, session),
               'Lock vault': bwcli.lock}
    sel = view_all_entries(options, entries_hid)
    if not sel:
        return Run.CONTINUE
    if sel == "Lock vault":  # Kill bwm daemon
        return Run.LOCK
    if sel not in options:
        # Autotype selected entry
        try:
            entry = entries[int(sel.split('-', 1)[0])]
        except (ValueError, TypeError):
            return Run.CONTINUE
        type_entry(entry)
        return Run.CONTINUE
    res = options[sel]()
    if res['err'] is True:
        return Run.CONTINUE
    if res['reload'] is True:
        return Run.RELOAD
    return Run.CONTINUE


def client():
    """Define client connection to server BaseManager

    Returns: BaseManager object
    """
    port, auth = get_auth()
    mgr = BaseManager(address=('', port), authkey=auth)
    mgr.register('set_event')
    mgr.connect()
    return mgr


class DmenuRunner(Process):
    """Listen for dmenu calling event and run bwm

    Args: server - Server object

    """
    def __init__(self, server):
        Process.__init__(self)
        self.server = server
        self.session = get_vault()
        if self.session is None:
            self.server.kill_flag.set()
            sys.exit()
        self.entries, self.folders, self.collections, self.orgs = bwcli.get_entries(self.session)
        if not all((self.entries, self.folders, self.collections, self.orgs)):
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
            res = dmenu_run(self.entries, self.folders, self.collections, self.session)
            if res == Run.LOCK:
                try:
                    self.server.kill_flag.set()
                except (EOFError, IOError):
                    return
            if res == Run.RELOAD:
                self.entries, self.folders, self.collections, self.orgs = \
                        bwcli.get_entries(self.session)
                if not all((self.entries, self.folders, self.collections, self.orgs)):
                    dmenu_err("Error loading entries. See logs.")
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


class Server(Process):
    """Run BaseManager server to listen for dmenu calling events

    """
    def __init__(self):
        Process.__init__(self)
        self.port, self.authkey = get_auth()
        self.start_flag = Event()
        self.kill_flag = Event()
        self.cache_time_expired = Event()
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
