"""Editing functions for bitwarden-menu

"""
from copy import deepcopy
import os
from os.path import basename, dirname, join
import random
from secrets import choice
import shlex
import string
from subprocess import call
import tempfile

import bwm.bwcli as bwcli
from bwm.bwtype import autotype_index, autotype_seq, type_text
from bwm.menu import dmenu_select, dmenu_err
import bwm


def obj_name(obj, oid):
    """Return name of folder/collection object based on id

        Args: obj - dict
              oid - string

    """
    return obj[oid]['name']


def edit_entry(entry, entries, folders, collections, session):  # pylint: disable=too-many-branches,too-many-statements
    """Edit title, username, password, url, notes and autotype sequence for an entry.

    Args: entry - selected Entry dict
          entries - list of dicts
          folders - dict of dicts {'id': {xxx,yyy}, ... }
          collections - dict of dicts {'id': {xxx,yyy}, ... }
          session - bytes
    Returns: None or entry (Item)

    """
    item = deepcopy(entry)
    update_colls = "NO"
    while True:
        fields = [str("Name: {}").format(item['name']),
                  str("Folder: {}").format(obj_name(folders, item['folderId'])),
                  str("Collections: {}").format(", ".join(obj_name(collections, i) for i
                                                          in item['collectionIds'])),
                  str("Username: {}").format(item['login']['username']),
                  str("Password: **********") if item['login']['password'] else "Password: None",
                  str("Url: {}").format(item['login']['url']),
                  str("Autotype: {}").format(autotype_seq(item)),
                  "Notes: <Enter to Edit>" if item['notes'] else "Notes: None",
                  "Delete entry",
                  "Save entry"]
        input_b = "\n".join(fields).encode(bwm.ENC)
        sel = dmenu_select(len(fields), inp=input_b)
        if sel == 'Delete entry':
            delete_entry(entry, entries, session)
            return None
        if sel == 'Save entry':
            if not item.get('id'):
                res = bwcli.add_entry(item, session)
                if res is False:
                    dmenu_err("Entry not added. Check logs.")
                    return None
                entries.append(bwcli.Item(res))
            else:
                res = bwcli.edit_entry(item, session, update_colls)
                if res is False:
                    dmenu_err("Error saving entry. Changes not saved.")
                    continue
                entries[entries.index(entry)] = bwcli.Item(res)
            return bwcli.Item(res)
        try:
            field, sel = sel.split(": ", 1)
        except (ValueError, TypeError):
            return entry
        field = field.lower()
        if field == 'password':
            item = edit_password(item) or item
            continue
        if field == 'folder':
            folder = select_folder(folders)
            if folder is not False:
                item['folderId'] = folder['id']
            continue
        if field == 'collections':
            orig = item['collectionIds']
            coll_list = [collections[i] for i in collections if i in item['collectionIds']]
            collection = select_collection(collections, session, coll_list=coll_list)
            item['collectionIds'] = [*collection]
            if collection:
                item['organizationId'] = next(iter(collection.values()))['organizationId']
            if item['collectionIds'] and item['collectionIds'] != orig and orig:
                update_colls = "YES"
            elif item['collectionIds'] != orig and not orig:
                update_colls = "MOVE"
            elif not item['collectionIds'] and orig:
                update_colls = "REMOVE"
            continue
        if field == 'notes':
            item['notes'] = edit_notes(item['notes'])
            continue
        if field in ('username', 'url'):
            edit_b = item['login'][field].encode(bwm.ENC) + \
                    b"\n" if item['login'][field] is not None else b"\n"
        elif field == 'autotype':
            edit_b = item['fields'][autotype_index(item)]['value'].encode(bwm.ENC) + \
                    b"\n" if item['fields'][autotype_index(item)]['value'] is not None else b"\n"
        else:
            edit_b = item[field].encode(bwm.ENC) + b"\n" if item[field] is not None else b"\n"
        sel = dmenu_select(1, "{}".format(field.capitalize()), inp=edit_b)
        if sel:
            if field in ('username', 'url'):
                item['login'][field] = sel
                if field == 'url':
                    item['login']['uris'] = [{'match': None, 'uri': sel}]
            elif field == 'autotype':
                item['fields'][autotype_index(item)]['value'] = sel
            else:
                item[field] = sel


def add_entry(entries, folders, collections, session):
    """Add vault entry

    Args: entries - list of dicts
          folders - dict of folder objects
          collections - dict of collections objects
          session - bytes
    Returns: None or entry (Item)

    """
    folder = select_folder(folders)
    colls = select_collection(collections, session, coll_list=[]) or []
    if folder is False:
        return None
    entry = {"organizationId": next(iter(colls.values()))['organizationId'] if colls else None,
             "folderId": folder['id'],
             "type": 1,
             "name": "",
             "notes": "",
             "favorite": False,
             "fields": [{"name": "autotype", "value": "", "type": 0}],
             "login": {"username": "",
                       "password": "",
                       "url": ""},
             "collectionIds": [*colls],
             "secureNote": "",
             "card": "",
             "identity": ""}
    return edit_entry(entry, entries, folders, collections, session)


def delete_entry(entry, entries, session):
    """Delete an entry

    Args: entry - dict
          entries - list of dicts
          session - bytes

    """
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete of {}".format(entry['name']), inp=input_b)
    if delete != "Yes - confirm delete":
        return
    res = bwcli.delete_entry(entry, session)
    if res is False:
        dmenu_err("Item not deleted. Check logs.")
        return
    del entries[entries.index(res)]


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
        try:
            call(editor)
            fname.seek(0)
            note = fname.read()
        except FileNotFoundError:
            dmenu_err("Terminal not found. Please update config.ini.")
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
        Returns: entry dict

    """
    sel = entry['login']['password']
    pw_orig = sel.encode(bwm.ENC) + b"\n" if sel is not None else b"\n"
    inputs_b = [b"Generate password",
                b"Manually enter password"]
    if entry['login']['password']:
        inputs_b.append(b"Type existing password")
    pw_choice = dmenu_select(len(inputs_b), "Password Options", inp=b"\n".join(inputs_b))
    if pw_choice == "Manually enter password":
        sel = dmenu_select(1, "Password", inp=pw_orig)
        sel_check = dmenu_select(1, "Verify password")
        if not sel_check or sel_check != sel:
            dmenu_err("Passwords do not match. No changes made.")
            return False
    elif pw_choice == "Generate password":
        input_b = b"20\n"
        length = dmenu_select(1, "Password Length?", inp=input_b)
        if not length:
            return False
        try:
            length = int(length)
        except ValueError:
            length = 20
        chars = get_password_chars()
        if chars is False:
            return False
        sel = gen_passwd(chars, length)
        if sel is False:
            dmenu_err("Number of char groups desired is more than requested pw length")
            return False
    elif pw_choice == "Type existing password":
        type_text(entry['login']['password'])
        return False
    else:
        return False
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
    sel = dmenu_select(min(bwm.MAX_LEN, len(folders)), prompt, inp=input_b)
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

    """
    options = ['Create',
               'Move',
               'Rename',
               'Delete']
    while True:
        input_b = b"\n".join(i.encode(bwm.ENC) for i in options) + b"\n\n" + \
            b"\n".join(i['name'].encode(bwm.ENC) for i in folders.values())
        sel = dmenu_select(len(options) + len(folders) + 1, "Manage Folders", inp=input_b)
        if not sel:
            break
        if sel == 'Create':
            create_folder(folders, session)
        elif sel == 'Move':
            move_folder(folders, session)
        elif sel == 'Rename':
            rename_folder(folders, session)
        elif sel == 'Delete':
            delete_folder(folders, session)
        else:
            break


def create_folder(folders, session):
    """Create new folder

    Args: folders - dict of folder objects

    """
    parentfolder = select_folder(folders, prompt="Select parent folder")
    if parentfolder is False:
        return
    pfname = parentfolder['name']
    if pfname == "No Folder":
        pfname = ""
    name = dmenu_select(1, "Folder name")
    if not name:
        return
    name = join(pfname, name)
    folder = bwcli.add_folder(name, session)
    if folder is False:
        dmenu_err("Folder not added. Check logs.")
        return
    folders[folder['id']] = folder


def delete_folder(folders, session):
    """Delete a folder

    Args: folder - folder dict obj
          session - bytes

    """
    folder = select_folder(folders, prompt="Delete Folder:")
    if not folder or folder['name'] == "No Folder":
        return
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=input_b)
    if delete != "Yes - confirm delete":
        return
    res = bwcli.delete_folder(folder, session)
    if res is False:
        dmenu_err("Folder not deleted. Check logs.")
        return
    del folders[folder['id']]


def move_folder(folders, session):
    """Move folder

    Args: folders - dict {'name': folder dict, ...}

    """
    folder = select_folder(folders, prompt="Select folder to move")
    if folder is False or folder['name'] == "No Folder":
        return
    destfolder = select_folder(folders,
            prompt="Select destination folder. 'No Folder' is root.")
    if destfolder is False:
        return
    dname = ""
    if destfolder['name'] != "No Folder":
        dname = destfolder['name']
    folder = bwcli.move_folder(folder, join(dname, basename(folder['name'])), session)
    if folder is False:
        dmenu_err("Folder not added. Check logs.")
        return
    folders[folder['id']] = folder


def rename_folder(folders, session):
    """Rename folder

    Args: folders - dict {'name': folder dict, ...}

    """
    folder = select_folder(folders, prompt="Select folder to rename")
    if folder is False or folder['name'] == "No Folder":
        return
    name = dmenu_select(1, "New folder name", inp=basename(folder['name']).encode(bwm.ENC))
    if not name:
        return
    new = join(dirname(folder['name']), name)
    folder = bwcli.move_folder(folder, new, session)
    if folder is False:
        dmenu_err("Folder not renamed. Check logs.")
        return
    folders[folder['id']] = folder


def select_collection(collections, session,
                      prompt="Collections - Organization (ESC for no selection)",
                      coll_list=False):
    """Select which collection for an entry

    Args: collections - dict of collection dicts {'id': {'id', 'name',...}, ...}
          options - list of menu options for collections
          prompt - displayed prompt
          coll_list - list of collection objects or False if only one collection
                      will be selected

    Returns: collections - dict{id: dict, id1: dict, ...}

    """
    if coll_list is not False:
        # When multiple collections will be selected, they have to come from the
        # same organization.
        org = select_org(session)
        if org is False:
            return False
        orgs = {org['id']: org}
        prompt_name = org['name']
        prompt = "Collections - {} (Enter to select, ESC when done)".format(prompt_name)
        colls = {i: j for i, j in enumerate(collections.values()) if
                 j['organizationId'] == org['id']}
    else:
        orgs = bwcli.get_orgs(session)
        colls = dict(enumerate(collections.values()))
    num_align = len(str(len(colls)))
    pattern = str("{:>{na}} - {} - {}")

    def check_coll(num, coll_list, cur_coll):
        # Check if name and org_id of cur_coll match in coll_list
        # Return num if not in list, otherwise return "*num"
        for i in coll_list:
            if cur_coll['organizationId'] == i['organizationId'] and cur_coll['name'] == i['name']:
                return "*{}".format(num)
        return num

    loop = True
    while loop:
        if coll_list is False:
            coll_list = []
            loop = False
        input_b = str("\n").join(pattern.format(check_coll(j, coll_list, i),
                                                i['name'],
                                                orgs[i['organizationId']]['name'],
                                                na=num_align)
                                 for j, i in colls.items()).encode(bwm.ENC)
        sel = dmenu_select(min(bwm.MAX_LEN, len(colls)), prompt, inp=input_b)
        if not sel:
            return {i['id']: i for i in coll_list}
        if sel.startswith('*'):
            sel = sel.lstrip('*')
            try:
                col = colls[int(sel.split(' - ')[0])]
                coll_list.remove(col)
            except (ValueError, TypeError):
                loop = False
        else:
            try:
                col = colls[int(sel.split(' - ')[0])]
                coll_list.append(col)
            except (ValueError, TypeError):
                loop = False
    return {i['id']: i for i in coll_list}


def manage_collections(collections, session):
    """Rename, create, move or delete collections

    Args: collections - dict of collection objects {'name': dict, ...}
          session - bytes

    """
    options = ['Create',
               'Move',
               'Rename',
               'Delete']
    while True:
        input_b = b"\n".join(i.encode(bwm.ENC) for i in options) + b"\n\n" + \
                b"\n".join(i['name'].encode(bwm.ENC) for i in collections.values())
        sel = dmenu_select(len(options) + len(collections) + 1, "Manage collections", inp=input_b)
        if not sel:
            break
        if sel == 'Create':
            create_collection(collections, session)
        elif sel == 'Move':
            move_collection(collections, session)
        elif sel == 'Rename':
            rename_collection(collections, session)
        elif sel == 'Delete':
            delete_collection(collections, session)
        else:
            break


def create_collection(collections, session):
    """Create new collection

    Args: collections - dict of collection objects

    """
    org_id = select_org(session)
    if org_id is False:
        return
    parentcollection = select_collection(collections, session,
            prompt="Select parent collection (Esc for no parent)")
    pname = ""
    if parentcollection:
        pname = next(iter(parentcollection.values()))['name']
    name = dmenu_select(1, "Collection name")
    if not name:
        return
    name = join(pname, name)
    collection = bwcli.add_collection(name, org_id['id'], session)
    collections[collection['id']] = collection


def delete_collection(collections, session):
    """Delete a collection

    Args: collections- dict of all collection objects
          session - bytes

    """
    collection = select_collection(collections, session, prompt="Delete collection:")
    if not collection:
        return
    collection = next(iter(collection.values()))
    input_b = b"NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete of {}".format(collection['name']), inp=input_b)
    if delete != "Yes - confirm delete":
        return
    res = bwcli.delete_collection(collection, session)
    if res is False:
        dmenu_err("Collection not deleted. Check logs.")
        return
    del collections[collection['id']]


def move_collection(collections, session):
    """Move collection

    Args: collections - dict {'name': collection dict, ...}

    """
    collection = select_collection(collections, session, prompt="Select collection to move")
    if not collection:
        return
    collection = next(iter(collection.values()))
    destcollection = select_collection(collections, session,
            prompt="Select destination collection (Esc to move to root directory)")
    if not destcollection:
        destcollection = {'name': ""}
    else:
        destcollection = next(iter(destcollection.values()))
    res = bwcli.move_collection(collection,
                                join(destcollection['name'], basename(collection['name'])),
                                session)
    if res is False:
        dmenu_err("Collection not moved. Check logs.")
        return
    collections[collection['id']] = res


def rename_collection(collections, session):
    """Rename collection

    Args: collections - dict {'name': collection dict, ...}

    """
    collection = select_collection(collections, session, prompt="Select collection to rename")
    if not collection:
        return
    collection = next(iter(collection.values()))
    name = dmenu_select(1, "New collection name", inp=basename(collection['name']).encode(bwm.ENC))
    if not name:
        return
    new = join(dirname(collection['name']), name)
    res = bwcli.move_collection(collection, new, session)
    if res is False:
        dmenu_err("Collection not deleted. Check logs.")
        return
    collections[collection['id']] = res


def select_org(session):
    """Select organization

    Args: session - bytes

    Returns: False for no entry
             org - dict

    """
    orgs = bwcli.get_orgs(session)
    orgs_ids = dict(enumerate(orgs.values()))
    num_align = len(str(len(orgs)))
    pattern = str("{:>{na}} - {}")
    input_b = str("\n").join(pattern.format(j, i['name'], na=num_align)
                              for j, i in orgs_ids.items()).encode(bwm.ENC)
    sel = dmenu_select(min(bwm.MAX_LEN, len(orgs)), "Select Organization", inp=input_b)
    if not sel:
        return False
    try:
        return orgs_ids[int(sel.split(' - ', 1)[0])]
    except (ValueError, TypeError):
        return False

# vim: set et ts=4 sw=4 :
