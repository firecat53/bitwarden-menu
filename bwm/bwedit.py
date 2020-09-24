"""Editing functions for bitwarden-menu

"""
import os
from os.path import basename, dirname, join
import random
from secrets import choice
import shlex
import string
from subprocess import call
import tempfile

import bwm.bwcli as bwcli
from bwm.bwtype import autotype_index, autotype_seq
from bwm.menu import dmenu_select, dmenu_err
import bwm


def edit_entry(entry, folders, collections, session):  # pylint: disable=too-many-return-statements, too-many-branches
    """Edit title, username, password, url, notes and autotype sequence for an entry.

    Args: entry - selected Entry dict

    Returns: entry to continue editing when changes are made
             True to continue editing with no changes made
             'deleted' if item is deleted
             False if done

    """
    fields = [str("Name: {}").format(entry['name']),
              str("Folder: {}").format(entry['folder']),
              str("Collections: {}").format(entry['collections']),
              str("Username: {}").format(entry['login']['username']),
              str("Password: **********") if entry['login']['password'] else "Password: None",
              str("Url: {}").format(entry['login']['url']),
              str("Autotype: {}").format(autotype_seq(entry)),
              "Notes: <Enter to Edit>" if entry['notes'] else "Notes: None",
              "Delete entry"]
    input_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=input_b)
    if sel == 'Delete entry':
        res = delete_entry(entry, session)
        if res is False:
            dmenu_err("Item not deleted, see logs")
            return False
        return "deleted"
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
    if field == 'collections':
        collection = select_collection(collections, session)
        if not collection:
            return True
        entry['collectionIds'] = [collections[collection]['id']]
        entry['collections'] = [collection]
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
             Vault object (dict) if added

    """
    folder = select_folder(folders)
    collection = select_collection(collections, session)
    if folder is False:
        return False
    entry = {"organizationId": None,
             "folderId": folder['id'],
             "type": 1,
             "name": "",
             "notes": "",
             "favorite": False,
             "fields": [{"name": "autotype", "value": "", "type": 0}],
             "login": {"username": "",
                       "password": "",
                       "url": ""},
             "folder": folder['name'] if folder != "No Folder" else "/",
             "collections": [collection['name']] if collection is not False else [],
             "secureNote": "",
             "card": "",
             "identity": ""}
    edit = True
    entry_ch = False
    while edit:
        edit = edit_entry(entry, folders, collections, session)
        if not isinstance(edit, bool):
            entry_ch = True
            entry = edit
    if entry_ch is True:
        entry = bwcli.add_entry(entry, session)
        if entry is False:
            return False
    return entry


def delete_entry(entry, session):
    """Delete an entry

    Args: entry - dict
          session - bytes
    Returns: entry (dict) if deleted
             False if not deleted

    """
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete of {}".format(entry['name']), inp=input_b)
    if delete != "Yes - confirm delete":
        return False
    res = bwcli.delete_entry(entry, session)
    if res is False:
        dmenu_err("Item not deleted. Check logs.")
    return res


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

    Args: folders - dict of folder dicts ['id': {'id', 'name',...}, ...]
          options - list of menu options for folders

    Returns: False for no entry
             folder - folder object

    """
    num_align = len(str(len(folders)))
    pattern = str("{:>{na}} - {}")
    folder_names = dict(enumerate(folders.values()))
    input_b = str("\n").join(pattern.format(j, i['name'], na=num_align)
                             for j, i in folder_names.items()).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(folders)), prompt, inp=input_b)
    if not sel:
        return False
    try:
        return folder_names[int(sel.split(' - ')[0])]
    except (ValueError, TypeError):
        return False


def manage_folders(folders, session):
    """Rename, create, move or delete folders

    Args: folders - dict of folder objects {'id': dict, ...}
          session - bytes
    Returns: updated folders (dict) on any changes or False

    """
    edit = True
    options = ['Create',
               'Move',
               'Rename',
               'Delete']
    folder_ch = False
    while edit is True:
        input_b = b"\n".join(i.encode(bwm.ENC) for i in options) + b"\n\n" + \
            b"\n".join(i['name'].encode(bwm.ENC) for i in folders.values())
        sel = dmenu_select(len(options) + len(folders) + 1, "Manage Folders", inp=input_b)
        if not sel:
            edit = False
        elif sel == 'Create':
            folder = create_folder(folders, session)
            if folder:
                folders[folder['id']] = folder
                folder_ch = folders
        elif sel == 'Move':
            folder = move_folder(folders, session)
            if folder:
                folders[folder['id']] = folder
                folder_ch = folders
        elif sel == 'Rename':
            folder = rename_folder(folders, session)
            if folder:
                folders[folder['id']] = folder
                folder_ch = folders
        elif sel == 'Delete':
            folder = delete_folder(folders, session)
            if folder:
                del folders[folder['id']]
                folder_ch = folders
        else:
            edit = False
    return folder_ch


def create_folder(folders, session):
    """Create new folder

    Args: folders - dict of folder objects
    Returns: Folder object or False

    """
    parentfolder = select_folder(folders, prompt="Select parent folder")
    if parentfolder is False:
        return False
    pfname = parentfolder['name']
    if pfname == "No Folder":
        pfname = ""
    name = dmenu_select(1, "Folder name")
    if not name:
        return False
    name = join(pfname, name)
    folder = bwcli.add_folder(name, session)
    if folder is False:
        dmenu_err("Folder not added. Check logs.")
    return folder


def delete_folder(folders, session):
    """Delete a folder

    Args: folder - folder dict obj
          session - bytes
    Returns: Folder object (dict) or False

    """
    folder = select_folder(folders, prompt="Delete Folder:")
    if not folder or folder['name'] == "No Folder":
        return False
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return False
    res = bwcli.delete_folder(folder, session)
    if res is False:
        dmenu_err("Folder not deleted. Check logs.")
    return res


def move_folder(folders, session):
    """Move folder

    Args: folders - dict {'name': folder dict, ...}
    Returns: New folder object or False

    """
    folder = select_folder(folders, prompt="Select folder to move")
    if folder is False or folder['name'] == "No Folder":
        return False
    destfolder = select_folder(folders,
            prompt="Select destination folder. 'No Folder' is root.")
    if destfolder is False:
        return False
    dname = ""
    if destfolder['name'] != "No Folder":
        dname = destfolder['name']
    folder = bwcli.move_folder(folder, join(dname, basename(folder['name'])), session)
    if folder is False:
        dmenu_err("Folder not added. Check logs.")
    return folder


def rename_folder(folders, session):
    """Rename folder

    Args: folders - dict {'name': folder dict, ...}
    Returns: New folder object or False

    """
    folder = select_folder(folders, prompt="Select folder to rename")
    if folder is False or folder['name'] == "No Folder":
        return False
    name = dmenu_select(1, "New folder name", inp=basename(folder['name']).encode(bwm.ENC))
    if not name:
        return False
    new = join(dirname(folder['name']), name)
    folder = bwcli.move_folder(folder, new, session)
    if folder is False:
        dmenu_err("Folder not renamed. Check logs.")
    return folder


def select_collection(collections, session, prompt="Collections - Organization"):
    """Select which collection for an entry

    Args: collections - dict of collection dicts ['id': {'id', 'name',...}, ...]
          options - list of menu options for collections

    Returns: False for no entry
             collection - dict

    """
    orgs = bwcli.get_orgs(session)
    coll_names = dict(enumerate(collections.values()))
    num_align = len(str(len(collections)))
    pattern = str("{:>{na}} - {} - {}")
    input_b = str("\n").join(pattern.format(j,
                                            i['name'],
                                            orgs[i['organizationId']]['name'],
                                            na=num_align)
                             for j, i in coll_names.items()).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(collections)), prompt, inp=input_b)
    if not sel:
        return False
    try:
        return coll_names[int(sel.split(' - ')[0])]
    except (ValueError, TypeError):
        return False


def manage_collections(collections, session):
    """Rename, create, move or delete collections

    Args: collections - dict of collection objects {'name': dict, ...}
          session - bytes
    Returns: updated collections (dict) on any changes or False

    """
    edit = True
    options = ['Create',
               'Move',
               'Rename',
               'Delete']
    collection_ch = False
    while edit is True:
        input_b = b"\n".join(i.encode(bwm.ENC) for i in options) + b"\n\n" + \
                b"\n".join(i['name'].encode(bwm.ENC) for i in collections.values())
        sel = dmenu_select(len(options) + len(collections) + 1, "Manage collections", inp=input_b)
        if not sel:
            edit = False
        elif sel == 'Create':
            collection = create_collection(collections, session)
            if collection:
                collections[collection['id']] = collection
                collection_ch = collections
        elif sel == 'Move':
            collection = move_collection(collections, session)
            if collection:
                collections[collection['id']] = collection
                collection_ch = collections
        elif sel == 'Rename':
            collection = rename_collection(collections, session)
            if collection:
                collections[collection['id']] = collection
                collection_ch = collections
        elif sel == 'Delete':
            collection = delete_collection(collections, session)
            if collection:
                del collections[collection['id']]





                collection_ch = collections
        else:
            edit = False
    return collection_ch


def create_collection(collections, session):
    """Create new collection

    Args: collections - dict of collection objects
    Returns: collection object or False

    """
    parentcollection = select_collection(collections, session,
            prompt="Select parent collection (Esc for no parent)")
    pname = ""
    if parentcollection is not False:
        pname = parentcollection['name']
    name = dmenu_select(1, "Collection name")
    if not name:
        return False
    name = join(pname, name)
    org_id = select_org(session)
    if org_id is False:
        return False
    collection = bwcli.add_collection(name, org_id, session)
    return collection


def delete_collection(collections, session):
    """Delete a collection

    Args: collections- dict of all collection objects
          session - bytes
    Returns: collection obj or False

    """
    collection = select_collection(collections, session, prompt="Delete collection:")
    if not collection:
        return False
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return False
    res = bwcli.delete_collection(collection, session)
    return res if res else False


def move_collection(collections, session):
    """Move collection

    Args: collections - dict {'name': collection dict, ...}
    Returns: New collection object or False

    """
    collection = select_collection(collections, session, prompt="Select collection to move")
    if collection is False:
        return False
    destcollection = select_collection(collections, session,
            prompt="Select destination collection (Esc to move to root directory)")
    if destcollection is False:
        destcollection = {'name': ""}
    return bwcli.move_collection(collection,
                                 join(destcollection['name'], basename(collection['name'])),
                                 session)


def rename_collection(collections, session):
    """Rename collection

    Args: collections - dict {'name': collection dict, ...}
    Returns: New collection object or False

    """
    collection = select_collection(collections, session, prompt="Select collection to rename")
    if not collection:
        return False
    name = dmenu_select(1, "New collection name", inp=basename(collection['name']).encode(bwm.ENC))
    if not name:
        return False
    new = join(dirname(collection['name']), name)
    return bwcli.move_collection(collection, new, session)


def select_org(session):
    """Select organization

    Args: session - bytes

    Returns: False for no entry
             org - string (org id)

    """
    orgs = bwcli.get_orgs(session)
    orgs_ids = dict(enumerate(orgs.values()))
    num_align = len(str(len(orgs)))
    pattern = str("{:>{na}} - {}")
    input_b = str("\n").join(pattern.format(j, i['name'], na=num_align)
                              for j, i in orgs_ids.items()).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.DMENU_LEN, len(orgs)), "Select Organization", inp=input_b)
    if not sel:
        return False
    try:
        return orgs_ids[int(sel.split(' - ', 1)[0])]['id']
    except (ValueError, TypeError):
        return False

# vim: set et ts=4 sw=4 :
