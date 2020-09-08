"""Editing functions for bitwarden-menu

"""
import os
from os.path import basename, dirname, join
import random
import shlex
import string
from subprocess import call
import tempfile

import bwm.bwcli as bwcli
from bwm.bwm import view_all_entries
from bwm.bwtype import autotype_index, autotype_seq
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


def edit_entry(entry, folders, collections):  # pylint: disable=too-many-return-statements, too-many-branches
    """Edit title, username, password, url, notes and autotype sequence for an entry.

    Args: entry - selected Entry dict

    Returns: entry to continue editing when changes are made
             True to continue editing with no changes made
             False if done

    """
    fields = [str("Name: {}").format(entry['name']),
              str("Folder: {}").format(entry['folder']),
              str("Username: {}").format(entry['login']['username']),
              str("Password: **********") if entry['login']['password'] else "Password: None",
              str("Url: {}").format(entry['login']['url']),
              str("Autotype: {}").format(autotype_seq(entry)),
              "Notes: <Enter to Edit>" if entry['notes'] else "Notes: None"]
    input_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=input_b)
    try:
        field, sel = sel.split(": ", 1)
    except (ValueError, TypeError):
        return False
    field = field.lower()
    if field == 'password':
        return edit_password(entry)
    if field == 'folder':
        folder = select_folder(folders)
        if not folder:
            return True
        entry['folderId'] = folders[folder]['id']
        entry['folder'] = folder
        return entry
    if field == 'notes':
        entry['notes'] = edit_notes(entry['notes'])
        return entry
    if field in ('username', 'url'):
        edit_b = entry['login'][field].encode(bwm.ENC) + \
                b"\n" if entry['login'][field] is not None else b"\n"
    elif field == 'autotype':
        edit_b = entry['fields'][autotype_index(entry)]['value'].encode(bwm.ENC) + \
                b"\n" if entry['fields'][autotype_index(entry)]['value'] is not None else b"\n"
    else:
        edit_b = entry[field].encode(bwm.ENC) + b"\n" if entry[field] is not None else b"\n"
    sel = dmenu_select(1, "{}".format(field.capitalize()), inp=edit_b)
    if not sel:
        return True
    if field in ('username', 'url'):
        entry['login'][field] = sel
        if field == 'url':
            entry['login']['uris'] = [{'match': None, 'uri': sel}]
    elif field == 'autotype':
        entry['fields'][autotype_index(entry)]['value'] = sel
    else:
        entry[field] = sel
    return entry


def add_entry(folders, collections, session):
    """Add vault entry

    Args: folders - dict of folder objects
          collections - dict of collections objects
          session - bytes
    Returns: False if not added
             True if added

    """
    folder = select_folder(folders)
    if folder is False:
        return False
    entry = {"organizationId": None,
             "folderId": folders[folder]['id'],
             "type": 1,
             "name": "",
             "notes": "",
             "favorite": False,
             "fields": [{"name": "autotype", "value": "", "type": 0}],
             "login": {"username": "",
                       "password": "",
                       "url": ""},
             "folder": folder if folder != "No Folder" else "/",
             "secureNote": "",
             "card": "",
             "identity": ""}
    edit = True
    entry_ch = False
    while edit:
        edit = edit_entry(entry, folders, collections)
        if not isinstance(edit, bool):
            entry_ch = True
            entry = edit
    if entry_ch is True:
        entry = bwcli.add_entry(entry, session)
        if entry is False:
            return False
    return True


def delete_entry(entries, session):
    """Delete an entry

    Args: entries - list of entry dicts
          session - bytes
    Returns: True if delete
             False if no delete

    """
    sel = view_all_entries([], entries)
    if not sel:
        return False
    try:
        entry = entries[int(sel.split('-', 1)[0])]
    except (ValueError, TypeError):
        return False
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return False
    res = bwcli.delete_entry(entry, session)
    if res is False:
        dmenu_err("Item not deleted. Check logs.")
        return False
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
                dmenu_err("Error: Unknown value in preset {}. Ignoring.".format(name))
                continue
    input_b = "\n".join(presets).encode(bwm.ENC)
    char_sel = dmenu_select(len(presets),
                            "Pick character set(s) to use", inp=input_b)
    # This dictionary return also handles Rofi multiple select
    return {k: presets[k] for k in char_sel.split('\n')} if char_sel else False


def edit_password(entry):
    """Edit password

        Args: entry dict
        Returns: True for no changes, entry for changes

    """
    sel = entry['login']['password']
    pw_orig = sel.encode(bwm.ENC) + b"\n" if sel is not None else b"\n"
    input_b = b"Generate password\nManually enter password\n"
    pw_choice = dmenu_select(2, "Password", inp=input_b)
    if pw_choice == "Manually enter password":
        sel = dmenu_select(1, "Enter password", inp=pw_orig)
        sel_check = dmenu_select(1, "Verify password")
        if not sel_check or sel_check != sel:
            dmenu_err("Passwords do not match. No changes made.")
            return True
    elif pw_choice == "Generate password":
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
    else:
        return True
    entry['login']['password'] = sel
    return entry


def select_folder(folders, prompt="Folders"):
    """Select which folder for an entry

    Args: folders - dict of folder dicts ['name': {'id', 'name',...}, ...]
          options - list of menu options for folders

    Returns: False for no entry
             folder - string

    """
    num_align = len(str(len(folders)))
    pattern = str("{:>{na}} - {}")
    input_b = str("\n").join([pattern.format(j, i, na=num_align)
                              for j, i in enumerate(folders)]).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(folders)), prompt, inp=input_b)
    if not sel:
        return False
    try:
        return sel.split('-', 1)[1].lstrip()
    except (ValueError, TypeError):
        return False


def manage_folders(folders, session):
    """Rename, create, move or delete folders

    Args: folders - dict of folder objects {'name': dict, ...}
          session - bytes
    Returns: True (on any changes) or False

    """
    edit = True
    options = ['Create',
               'Move',
               'Rename',
               'Delete']
    folder_ch = False
    while edit is True:
        input_b = b"\n".join(i.encode(bwm.ENC) for i in options) + b"\n\n" + \
            b"\n".join(i.encode(bwm.ENC) for i in folders)
        sel = dmenu_select(len(options) + len(folders) + 1, "Folders", inp=input_b)
        if not sel:
            edit = False
        elif sel == 'Create':
            folder = create_folder(folders, session)
            if folder:
                folders[folder['name']] = folder
                folder_ch = True
        elif sel == 'Move':
            folder = move_folder(folders, session)
            if folder:
                folders[folder['name']] = folder
                folder_ch = True
        elif sel == 'Rename':
            folder = rename_folder(folders, session)
            if folder:
                folders[folder['name']] = folder
                folder_ch = True
        elif sel == 'Delete':
            folder = delete_folder(folders, session)
            if folder:
                del folders[folder]
                folder_ch = True
        else:
            edit = False
    return folder_ch


def create_folder(folders, session):
    """Create new folder

    Args: folders - dict of folder objects
    Returns: Folder object or False

    """
    parentfolder = select_folder(folders, prompt="Select parent folder")
    if not parentfolder:
        return False
    if parentfolder == "No Folder":
        parentfolder = ""
    name = dmenu_select(1, "Folder name")
    if not name:
        return False
    name = join(parentfolder, name)
    folder = bwcli.add_folder(name, session)
    return folder


def delete_folder(folders, session):
    """Delete a folder

    Args: folder - folder dict obj
          session - bytes
    Returns: Folder name or False

    """
    folder = select_folder(folders, prompt="Delete Folder:")
    if not folder:
        return False
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return False
    res = bwcli.delete_folder(folders, folder, session)
    return folder if res is True else False


def move_folder(folders, session):
    """Move folder

    Args: folders - dict {'name': folder dict, ...}
    Returns: New folder object or False

    """
    folder = select_folder(folders, prompt="Select folder to move")
    if not folder:
        return False
    destfolder = select_folder(folders, prompt="Select destination folder")
    if not destfolder:
        return False
    return bwcli.move_folder(folders, folder, join(destfolder, basename(folder)), session)


def rename_folder(folders, session):
    """Rename folder

    Args: folders - dict {'name': folder dict, ...}
    Returns: New folder object or False

    """
    folder = select_folder(folders, prompt="Select folder to rename")
    if not folder:
        return False
    name = dmenu_select(1, "New folder name", inp=basename(folder).encode(bwm.ENC))
    if not name:
        return False
    new = join(dirname(folder), name)
    return bwcli.move_folder(folders, folder, new, session)


def manage_collections(collections, session):
    """Manage collections

    """
    return False
