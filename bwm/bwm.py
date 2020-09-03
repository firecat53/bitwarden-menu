"""Bitwarden-menu main module

"""
from contextlib import closing
from multiprocessing import Event, Process
from multiprocessing.managers import BaseManager
import os
from os.path import exists, expanduser
import random
import shlex
import socket
import string
import sys
from subprocess import call, Popen, PIPE
import tempfile
from threading import Timer
import webbrowser

import bwm.bwcli as bwcli
from bwm.bwtype import type_text, type_entry
from bwm.menu import dmenu_select, dmenu_err
import bwm

try:
    # secrets only available python 3.6+
    from secrets import choice
except ImportError:
    def choice(seq):
        """Provide `choice` function call for pw generation

        """
        return random.SystemRandom().choice(seq)


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


def gen_passwd(chars, length=20):
    """Generate password (min = # of distinct character sets picked)

    Args: chars - Dict {preset_name_1: {char_set_1: string, char_set_2: string},
                        preset_name_2: ....}
          length - int (default 20)

    Returns: password - string OR False

    """
    sets = set()
    if chars:
        sets = set(j for i in chars.values() for j in i.values())
    if length < len(sets) or not chars:
        return False
    alphabet = "".join(set("".join(j for j in i.values()) for i in chars.values()))
    # Ensure minimum of one char from each character set
    password = "".join(choice(k) for k in sets)
    password += "".join(choice(alphabet) for i in range(length - len(sets)))
    tpw = list(password)
    random.shuffle(tpw)
    return "".join(tpw)


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
        print("Cache file was corrupted. Stopping all instances. Please try again")
        call(["pkill", "bwm"])  # Kill all prior instances as well
    return int(port), authkey


def get_password_chars():
    """Get characters to use for password generation from defaults, config file
    and user input.

    Returns: Dict {preset_name_1: {char_set_1: string, char_set_2: string},
                   preset_name_2: ....}
    """
    chars = {"upper": string.ascii_uppercase,
             "lower": string.ascii_lowercase,
             "digits": string.digits,
             "punctuation": string.punctuation}
    presets = {}
    presets["Letters+Digits+Punctuation"] = chars
    presets["Letters+Digits"] = {k: chars[k] for k in ("upper", "lower", "digits")}
    presets["Letters"] = {k: chars[k] for k in ("upper", "lower")}
    presets["Digits"] = {k: chars[k] for k in ("digits",)}
    if bwm.CONF.has_section('password_chars'):
        pw_chars = dict(bwm.CONF.items('password_chars'))
        chars.update(pw_chars)
        for key, val in pw_chars.items():
            presets[key.title()] = {k: chars[k] for k in (key,)}
    if bwm.CONF.has_section('password_char_presets'):
        if bwm.CONF.options('password_char_presets'):
            presets = {}
        for name, val in bwm.CONF.items('password_char_presets'):
            try:
                presets[name.title()] = {k: chars[k] for k in shlex.split(val)}
            except KeyError:
                print("Error: Unknown value in preset {}. Ignoring.".format(name))
                continue
    input_b = "\n".join(presets).encode(bwm.ENC)
    char_sel = dmenu_select(len(presets),
                            "Pick character set(s) to use", inp=input_b)
    # This dictionary return also handles Rofi multiple select
    return {k: presets[k] for k in char_sel.split('\n')} if char_sel else False


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
        try:
            email = args_dict['email_{}'.format(idx)]
        except KeyError:
            email = ''
        try:
            passw = args_dict['password_{}'.format(idx)]
        except KeyError:
            passw = ''
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
            vaults.append((srv, email, passw))
    if not vaults:
        res = get_initial_vault()
        if res:
            vaults.append(res)
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
    if status['serverUrl'] != url:
        res = bwcli.set_server(url)
        if res is False:
            return None
    if status['userEmail'] != email or status['status'] == 'unauthenticated':
        session = bwcli.login(email, passw)
    elif status['status'].endswith('locked'):
        session = bwcli.unlock(passw)
    return session if session is not False else None


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


def view_all_entries(options, folders, vault_entries):
    """Generate numbered list of all vault entries and open with dmenu.

    Returns: dmenu selection

    """
    num_align = len(str(len(vault_entries)))
    bw_entry_pattern = str("{:>{na}} - {} - {} - {}")  # Path,username,url
    # Have to number each entry to capture duplicates correctly
    entries = []
    for j, i in enumerate(vault_entries):
        path = folders.get(i.get('folderId')).get('name')
        if path == 'No Folder':
            path = ''
        path = "/".join([path, i.get('name')]).lstrip('/')
        user = i.get('login').get('username') or ""
        try:
            url = i.get('login').get('uris')[0].get('uri')
        except TypeError:
            url = ""
        entries.append([j, path, user, url])
    vault_entries_b = str("\n").join(bw_entry_pattern.format(
        **i, na=num_align) for i in entries).encode(bwm.ENC)
    if options:
        options_b = ("\n".join(options) + "\n").encode(bwm.ENC)
        entries_b = options_b + vault_entries_b
    else:
        entries_b = vault_entries_b
    return dmenu_select(min(bwm.DMENU_LEN, len(options) + len(vault_entries)), inp=entries_b)


def select_folder(bwvo, prompt="Folders"):
    """Select which folder for an entry

    Args: bwvo - vault object
          options - list of menu options for folders

    Returns: False for no entry
             folder - string

    """
    folders = bwvo.folders
    num_align = len(str(len(folders)))
    pattern = str("{:>{na}} - {}")
    input_b = str("\n").join([pattern.format(j, i.path, na=num_align)
                              for j, i in enumerate(folders)]).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(folders)), prompt, inp=input_b)
    if not sel:
        return False
    try:
        return folders[int(sel.split('-', 1)[0])]
    except (ValueError, TypeError):
        return False


def manage_folders(bwvo):
    """Rename, create, move or delete folders

    Args: bwvo - vault object
    Returns: Folder object or False

    """
    edit = True
    options = ['Create',
               'Move',
               'Rename',
               'Delete']
    folder = False
    while edit is True:
        input_b = b"\n".join(i.encode(bwm.ENC) for i in options) + b"\n\n" + \
            b"\n".join(i.path.encode(bwm.ENC) for i in bwvo.folders)
        sel = dmenu_select(len(options) + len(bwvo.folders) + 1, "Folders", inp=input_b)
        if not sel:
            edit = False
        elif sel == 'Create':
            folder = create_folder(bwvo)
        elif sel == 'Move':
            folder = move_folder(bwvo)
        elif sel == 'Rename':
            folder = rename_folder(bwvo)
        elif sel == 'Delete':
            folder = delete_folder(bwvo)
        else:
            edit = False
    return folder


def create_folder(bwvo):
    """Create new folder

    Args: bwvo - vault object
    Returns: Folder object or False

    """
    parentfolder = select_folder(bwvo, prompt="Select parent folder")
    if not parentfolder:
        return False
    name = dmenu_select(1, "Folder name")
    if not name:
        return False
    folder = bwvo.add_folder(parentfolder, name)
    return folder


def delete_folder(bwvo):
    """Delete a folder

    Args: bwvo - vault object
    Returns: Folder object or False

    """
    folder = select_folder(bwvo, prompt="Delete Folder:")
    if not folder:
        return False
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return True
    bwvo.delete_folder(folder)
    return folder


def move_folder(bwvo):
    """Move folder

    Args: bwvo - vault object
    Returns: Folder object or False

    """
    folder = select_folder(bwvo, prompt="Select folder to move")
    if not folder:
        return False
    destfolder = select_folder(bwvo, prompt="Select destination folder")
    if not destfolder:
        return False
    folder = bwvo.folder(folder, destfolder)
    return folder


def rename_folder(bwvo):
    """Rename folder

    Args: bwvo - vault object
    Returns: Folder object or False

    """
    folder = select_folder(bwvo, prompt="Select folder to rename")
    if not folder:
        return False
    name = dmenu_select(1, "New folder name", inp=folder.name.encode(bwm.ENC))
    if not name:
        return False
    folder.name = name
    return folder


def add_entry(bwvo):
    """Add vault entry

    Args: bwvo - vault object
    Returns: False if not added
             vault Entry object on success

    """
    folder = select_folder(bwvo)
    if folder is False:
        return False
    entry = bwvo.add_entry(destination_folder=folder, title="", username="", password="")
    edit = True
    while edit is True:
        edit = edit_entry(bwvo, entry)
    return entry


def delete_entry(bwvo, kp_entry):
    """Delete an entry

    Args: bwvo - vault object
          kp_entry - vault entry
    Returns: True if no delete
             False if delete

    """
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return True
    bwvo.delete_entry(kp_entry)
    return False


def view_entry(kp_entry):
    """Show title, username, password, url and notes for an entry.

    Returns: dmenu selection

    """
    fields = [kp_entry.path or "Title: None",
              kp_entry.username or "Username: None",
              '**********' if kp_entry.password else "Password: None",
              kp_entry.url or "URL: None",
              "Notes: <Enter to view>" if kp_entry.notes else "Notes: None"]
    vault_entries_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=vault_entries_b)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(kp_entry.notes)
    elif sel == "Notes: None":
        sel = ""
    elif sel == '**********':
        sel = kp_entry.password
    elif sel == fields[3]:
        if sel != "URL: None":
            webbrowser.open(sel)
        sel = ""
    return sel


def edit_entry(bwvo, kp_entry):  # pylint: disable=too-many-return-statements, too-many-branches
    """Edit title, username, password, url and autotype sequence for an entry.

    Args: bwvo - vault object
          kp_entry - selected Entry object

    Returns: True to continue editing
             False if done

    """
    fields = [str("Title: {}").format(kp_entry.title),
              str("Path: {}").format(kp_entry.path.rstrip(kp_entry.title)),
              str("Username: {}").format(kp_entry.username),
              str("Password: **********") if kp_entry.password else "Password: None",
              str("Url: {}").format(kp_entry.url),
              "Notes: <Enter to Edit>" if kp_entry.notes else "Notes: None",
              "Delete Entry: "]
    if hasattr(kp_entry, 'autotype_sequence') and hasattr(kp_entry, 'autotype_enabled'):
        fields[5:5] = [str("Autotype Sequence: {}").format(kp_entry.autotype_sequence),
                       str("Autotype Enabled: {}").format(kp_entry.autotype_enabled)]
    input_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=input_b)
    try:
        field, sel = sel.split(": ", 1)
    except (ValueError, TypeError):
        return False
    field = field.lower().replace(" ", "_")
    if field == 'password':
        sel = kp_entry.password
    edit_b = sel.encode(bwm.ENC) + b"\n" if sel is not None else b"\n"
    if field == 'delete_entry':
        return delete_entry(bwvo, kp_entry)
    if field == 'path':
        folder = select_folder(bwvo)
        if not folder:
            return True
        bwvo.move_entry(kp_entry, folder)
        return True
    pw_choice = ""
    if field == 'password':
        input_b = b"Generate password\nManually enter password\n"
        pw_choice = dmenu_select(2, "Password", inp=input_b)
        if pw_choice == "Manually enter password":
            pass
        elif not pw_choice:
            return True
        else:
            pw_choice = ''
            input_b = b"20\n"
            length = dmenu_select(1, "Password Length?", inp=input_b)
            if not length:
                return True
            try:
                length = int(length)
            except ValueError:
                length = 20
            chars = get_password_chars()
            if chars is False:
                return True
            sel = gen_passwd(chars, length)
            if sel is False:
                dmenu_err("Number of char groups desired is more than requested pw length")
                return True

    if field == 'autotype_enabled':
        input_b = b"True\nFalse\n"
        at_enab = dmenu_select(2, "Autotype Enabled? True/False", inp=input_b)
        if not at_enab:
            return True
        sel = not at_enab == 'False'
    if (field not in ('password', 'notes', 'path', 'autotype_enabled')) or pw_choice:
        sel = dmenu_select(1, "{}".format(field.capitalize()), inp=edit_b)
        if not sel:
            return True
        if pw_choice:
            sel_check = dmenu_select(1, "{}".format(field.capitalize()), inp=edit_b)
            if not sel_check or sel_check != sel:
                dmenu_err("Passwords do not match. No changes made.")
                return True
    elif field == 'notes':
        sel = edit_notes(kp_entry.notes)
    setattr(kp_entry, field, sel)
    return True


def edit_notes(note):
    """Use $EDITOR (or 'vim' if not set) to edit the notes entry

    In configuration file:
        Set 'gui_editor' for things like emacs, gvim, leafpad
        Set 'editor' for vim, emacs -nw, nano unless $EDITOR is defined
        Set 'terminal' if using a non-gui editor

    Args: note - string
    Returns: note - string

    """
    if bwm.CONF.has_option("vault", "gui_editor"):
        editor = bwm.CONF.get("vault", "gui_editor")
        editor = shlex.split(editor)
    else:
        if bwm.CONF.has_option("vault", "editor"):
            editor = bwm.CONF.get("vault", "editor")
        else:
            editor = os.environ.get('EDITOR', 'vim')
        if bwm.CONF.has_option("vault", "terminal"):
            terminal = bwm.CONF.get("vault", "terminal")
        else:
            terminal = "xterm"
        terminal = shlex.split(terminal)
        editor = shlex.split(editor)
        editor = terminal + ["-e"] + editor
    note = b'' if note is None else note.encode(bwm.ENC)
    with tempfile.NamedTemporaryFile(suffix=".tmp") as fname:
        fname.write(note)
        fname.flush()
        editor.append(fname.name)
        call(editor)
        fname.seek(0)
        note = fname.read()
    note = '' if not note else note.decode(bwm.ENC)
    return note


def view_notes(notes):
    """View the 'Notes' field line-by-line within dmenu.

    Returns: text of the selected line for typing

    """
    notes_l = notes.split('\n')
    notes_b = "\n".join(notes_l).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(notes_l)), inp=notes_b)
    return sel


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
          bwvo - vault object
    """
    def __init__(self, server):
        Process.__init__(self)
        self.server = server
        self.session = get_vault()
        self.entries = bwcli.get_entries(self.session)
        self.folders = bwcli.get_folders(self.session)
        self.collections = bwcli.get_folders(self.session)
        if self.entries is False:
            self.server.kill_flag.set()
            sys.exit()

    def _set_timer(self):
        """Set inactivity timer

        """
        self.cache_timer = Timer(bwm.SESSION_TIMEOUT_MIN * 60, self.cache_time)
        self.cache_timer.daemon = True
        self.cache_timer.start()

    def run(self):
        while True:
            self.server.start_flag.wait()
            if self.server.kill_flag.is_set():
                break
            if self.entries is False:
                pass
            else:
                self.dmenu_run()
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

    def dmenu_run(self):  # pylint: disable=too-many-branches,too-many-return-statements
        """Run dmenu with the given list of vault Entry objects

        If 'hide_folders' is defined in config.ini, hide those from main and
        view/type all views.

        Args: self.bwvo - vault object

        """
        try:
            self.cache_timer.cancel()
        except AttributeError:
            pass
        self._set_timer()
        options = ['View/Type Individual entries',
                   'Edit entries',
                   'Add entry',
                   'Manage folders',
                   'Manage collections',
                   'Sync vault',
                   'Lock vault']
        if bwm.CONF.has_option("vault", "hide_folders"):
            hid_fold = bwm.CONF.get("vault", "hide_folders").split("\n")
            # Validate ignored folder names in config.ini
            hid_fold = [i for i in hid_fold if i in
                        [j['name'] for j in self.folders.values()]]
        else:
            hid_fold = []
        sel = view_all_entries(options, self.folders,
                               [i for i in self.entries if not
                                any(j in self.folders[i['folderId']]['name'] for
                                    j in hid_fold)])
        if not sel:
            return
        if sel == options[0]:  # ViewType Individual entries
            options = []
            sel = view_all_entries(options, self.folders,
                                   [i for i in self.entries if not
                                    any(j in self.folders[i['folderId']]['name'] for
                                        j in hid_fold)])
            try:
                entry = self.entries.entries[int(sel.split('-', 1)[0])]
            except (ValueError, TypeError):
                return
            text = view_entry(entry)
            type_text(text)
        elif sel == options[1]:  # Edit entries
            options = []
            sel = view_all_entries(options, self.folders, self.entries)
            try:
                entry = self.entries.entries[int(sel.split('-', 1)[0])]
            except (ValueError, TypeError):
                return
            edit = True
            while edit is True:
                edit = edit_entry(self.entries, entry)
            self.entries = bwcli.get_entries(self.session)
        elif sel == options[2]:  # Add entry
            entry = add_entry(self.entries)
            if entry:
                self.entries = bwcli.get_entries(self.session)
        elif sel == options[3]:  # Manage folders
            folder = manage_folders(self.entries)
            if folder:
                self.entries = bwcli.get_entries(self.session)
        elif sel == options[4]:  # Manage collections
            collection = manage_folders(self.entries)
            if collection:
                self.entries = bwcli.get_entries(self.session)
        elif sel == options[5]:  # Sync vault
            self.entries = bwcli.get_entries(self.session)
            if not self.entries:
                return
            self.dmenu_run()
        elif sel == options[6]:  # Kill bwm daemon
            try:
                self.server.kill_flag.set()
            except (EOFError, IOError):
                return
        else:
            try:
                entry = self.entries.entries[int(sel.split('-', 1)[0])]
            except (ValueError, TypeError):
                return
            type_entry(entry)


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
