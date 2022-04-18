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
from urllib import parse

from bwm import bwcli
from bwm.bwtype import autotype_index, autotype_seq, type_text
from bwm.menu import dmenu_select, dmenu_err
from bwm.totp import gen_otp
import bwm


def obj_name(obj, oid):
    """Return name of folder/collection object based on id

        Args: obj - dict
              oid - string

    """
    return obj[oid]['name']


def edit_entry(entry, entries, folders, collections, session):
    # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    """Edit an entry.

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
        colls = ", ".join(obj_name(collections, i) for i in item['collectionIds'])
        fields = [f"Name: {item['name']}",
                  f"Folder: {obj_name(folders, item['folderId'])}",
                  f"Collections: {colls}",
                  f"Autotype: {autotype_seq(item)}",
                  "Notes: <Enter to Edit>" if item['notes'] else "Notes: None",
                  "Delete entry",
                  "Save entry"]
        add_f = []
        if int(item['type']) == 1:
            add_f = [f"Username: {item['login']['username']}",
                     "Password: **********" if item['login']['password'] else "Password: None",
                     "TOTP: ******" if item['login']['totp'] else "TOTP: None",
                     "URLs: <Enter to Edit>" if item.get('login', {}).get('uris', [])
                     else "URLs: None"]
        elif int(item['type']) == 3:
            add_f = [f"{i}: {item['card'][j]}" for i, j in bwm.CARD.items()]
        elif int(item['type']) == 4:
            add_f = [f"{i}: {item['identity'][j]}" for i, j in bwm.IDENTITY.items()]
        fields[-4:-4] = add_f
        inp = "\n".join(fields)
        sel = dmenu_select(len(fields), inp=inp)
        if not [i for i in fields if sel and sel in i]:
            return entry
        field = sel.split(": ", 1)[0]
        if field == 'Delete entry':
            delete_entry(entry, entries, session)
            return None
        if field == 'Save entry':
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
        if field == 'Folder':
            folder = select_folder(folders)
            if folder is not False:
                item['folderId'] = folder['id']
            continue
        if field == 'Collections':
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
        if field == 'Notes':
            item['notes'] = edit_notes(item['notes'])
            continue
        if field == 'Autotype':
            edit = f"{item['fields'][autotype_index(item)]['value']}\n" \
                    if item['fields'][autotype_index(item)]['value'] is not None else "\n"
            sel = dmenu_select(1, field, inp=edit)
            if sel:
                item['fields'][autotype_index(item)]['value'] = sel
            continue
        if field == 'Name':
            edit = f"{item['name']}\n" if item['name'] is not None else "\n"
            sel = dmenu_select(1, field, inp=edit)
            if sel:
                item['name'] = sel
            continue
        if item['type'] == 1:
            item = _handle_login(item, field)
            continue
        if item['type'] == 3:
            edit = f"{item['card'][bwm.CARD[field]]}\n" if \
                item['card'][bwm.CARD[field]] is not None else "\n"
        if item['type'] == 4:
            edit = f"{item['identity'][bwm.IDENTITY[field]]}\n" if \
                item['identity'][bwm.IDENTITY[field]] is not None else "\n"
        sel = dmenu_select(1, field, inp=edit)
        if sel is not None:
            if item['type'] == 3:
                item['card'][bwm.CARD[field]] = sel
            if item['type'] == 4:
                item['identity'][bwm.IDENTITY[field]] = sel


def _handle_login(item, field):
    """Handle editing for login type entries

    """
    if field == 'Password':
        item = edit_password(item) or item
        return item
    if field == 'TOTP':
        item = edit_totp(item) or item
        return item
    if field.startswith('URLs'):
        item = edit_urls(item)
        return item
    edit = f"{item['login'][bwm.LOGIN[field]]}\n" if \
        item['login'][bwm.LOGIN[field]] is not None else "\n"
    sel = dmenu_select(1, field, inp=edit)
    if sel:
        item['login'][bwm.LOGIN[field]] = sel
    return item


def add_entry(entries, folders, collections, session):
    """Add vault entry

    Args: entries - list of dicts
          folders - dict of folder objects
          collections - dict of collections objects
          session - bytes
    Returns: None or entry (Item)

    """
    itypes = {"Login": 1, "Secure Note": 2, "Card": 3, "Identity": 4}
    itype = dmenu_select(len(itypes), "Item Type", inp="\n".join(itypes))
    if itype not in itypes:
        return None
    folder = select_folder(folders)
    colls = select_collection(collections, session, coll_list=[]) or []
    if folder is False:
        return None
    entry = {"organizationId": next(iter(colls.values()))['organizationId'] if colls else None,
             "folderId": folder['id'],
             "type": itypes[itype],
             "name": "",
             "notes": "",
             "favorite": False,
             "fields": [{"name": "autotype", "value": "", "type": 0}],
             "login": "",
             "collectionIds": [*colls],
             "secureNote": "",
             "card": "",
             "identity": ""}
    if itype == "Login":
        entry["login"] = {"username": "",
                          "password": "",
                          "totp": "",
                          "uris": []}
    elif itype == "Secure Note":
        entry["secureNote"] = {"type": 0}
    elif itype == "Card":
        entry["card"] = {"cardholderName": "",
                         "brand": "",
                         "number": "",
                         "expMonth": "",
                         "expYear": "",
                         "code": ""}
    elif itype == "Identity":
        entry["identity"] = {"title": "",
                             "firstName": "",
                             "middleName": "",
                             "lastName": "",
                             "address1": "",
                             "address2": "",
                             "address3": "",
                             "city": "",
                             "state": "",
                             "postalCode": "",
                             "country": "",
                             "company": "",
                             "email": "",
                             "phone": "",
                             "ssn": "",
                             "username": "",
                             "passportNumber": "",
                             "licenseNumber": ""}
    return edit_entry(entry, entries, folders, collections, session)


def delete_entry(entry, entries, session):
    """Delete an entry

    Args: entry - dict
          entries - list of dicts
          session - bytes

    """
    inp = "NO\nYes - confirm delete\n"
    delete = dmenu_select(2, f"Confirm delete of {entry['name']}", inp=inp)
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


def edit_urls(entry):
    """Edit multiple URLs

    Args: entry
    Returns: entry object with updated URLs

    """
    uris = entry.get('login', {}).get('uris')
    urls = [i['uri'] for i in uris] if uris else []
    sel = dmenu_select(len(urls) or 1, "URL (Type to add new)", inp="\n".join(urls))
    if not sel:
        return entry
    if sel not in urls:
        entry.setdefault('login', {})
        entry['login'].setdefault('uris', [])
        entry['login']['uris'].append({'uri': sel, 'match': None})
    else:
        idx = urls.index(sel)
        sel = dmenu_select(1, "URL", inp=f"{sel}\nDelete URL")
        if not sel:
            return entry
        if sel == "Delete URL":
            del entry['login']['uris'][idx]
        else:
            entry['login']['uris'][idx]['uri'] = sel
    return entry


def edit_totp(entry):  # pylint: disable=too-many-statements,too-many-branches
    """Edit TOTP generation information

    Args: entry - Entry object

    Returns: entry - Entry object or False

    """
    otp_url = entry['login']['totp']

    if otp_url is not None:
        inputs = [
            "Enter secret key",
            "Type TOTP",
        ]
        otp_choice = dmenu_select(len(inputs), "TOTP", inp="\n".join(inputs))
    else:
        otp_choice = "Enter secret key"

    if otp_choice == "Type TOTP":
        type_text(gen_otp(otp_url))
    elif otp_choice == "Enter secret key":
        inputs = []
        if otp_url:
            parsed_otp_url = parse.urlparse(otp_url)
            query_string = parse.parse_qs(parsed_otp_url.query)
            inputs = [query_string["secret"][0]]
        secret_key = dmenu_select(1, "Secret Key?", inp="\n".join(inputs))

        if secret_key is None:
            return False
        if not secret_key:
            entry['login']['totp'] = ""
            return entry

        for char in secret_key:
            if char.upper() not in bwm.SERCRET_VALID_CHARS:
                dmenu_err("Invaild character in secret key, "
                          f"valid characters are {bwm.SERCRET_VALID_CHARS}")
                return False

        inputs = [
            "Defaut RFC 6238 token settings",
            "Steam token settings",
            "Use cusom settings"
        ]

        otp_settings_choice = dmenu_select(len(inputs), "Settings", inp="\n".join(inputs))

        if otp_settings_choice == "Defaut RFC 6238 token settings":
            algorithm_choice = "sha1"
            time_step_choice = 30
            code_size_choice = 6
        elif otp_settings_choice == "Steam token settings":
            algorithm_choice = "sha1"
            time_step_choice = 30
            code_size_choice = 5
        elif otp_settings_choice == "Use custom settings":
            inputs = ["SHA-1", "SHA-256", "SHA-512"]
            algorithm_choice = dmenu_select(len(inputs), "Algorithm", inp="\n".join(inputs))
            if not algorithm_choice:
                return False
            algorithm_choice = algorithm_choice.replace("-", "").lower()

            time_step_choice = dmenu_select(1, "Time Step (sec)", inp="30\n")
            if not time_step_choice:
                return False
            try:
                time_step_choice = int(time_step_choice)
            except ValueError:
                time_step_choice = 30

            code_size_choice = dmenu_select(1, "Code Size", inp="6\n")
            if not code_size_choice:
                return False
            try:
                code_size_choice = int(time_step_choice)
            except ValueError:
                code_size_choice = 6

        otp_url = (f"otpauth://totp/Main:none?secret={secret_key}&period={time_step_choice}"
                   f"&digits={code_size_choice}&issuer=Main")
        if algorithm_choice != "sha1":
            otp_url += "&algorithm=" + algorithm_choice
        if otp_settings_choice == "Steam token settings":
            otp_url += "&encoder=steam"
        entry['login']['totp'] = otp_url
        return entry


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
                dmenu_err(f"Error: Unknown value in preset {name}. Ignoring.")
                continue
    inp = "\n".join(presets)
    char_sel = dmenu_select(len(presets),
                            "Pick character set(s) to use", inp=inp)
    # This dictionary return also handles Rofi multiple select
    return {k: presets[k] for k in char_sel.split('\n')} if char_sel else False


def edit_password(entry):  # pylint: disable=too-many-return-statements
    """Edit password

        Args: entry dict
        Returns: entry dict

    """
    sel = entry['login']['password']
    pw_orig = sel + "\n" if sel is not None else "\n"
    inputs = ["Generate password",
              "Manually enter password"]
    if entry['login']['password']:
        inputs.append("Type existing password")
    pw_choice = dmenu_select(len(inputs), "Password Options", inp="\n".join(inputs))
    if pw_choice == "Manually enter password":
        sel = dmenu_select(1, "Password", inp=pw_orig)
        sel_check = dmenu_select(1, "Verify password")
        if sel_check is None or sel_check != sel:
            dmenu_err("Passwords do not match. No changes made.")
            return False
    elif pw_choice == "Generate password":
        inp = "20\n"
        length = dmenu_select(1, "Password Length?", inp=inp)
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
    inp = str("\n").join(pattern.format(j, i['name'], na=num_align)
                         for j, i in folder_names.items())
    sel = dmenu_select(min(bwm.MAX_LEN, len(folders)), prompt, inp=inp)
    if not sel:
        return False
    try:
        return folder_names[int(sel.split(' - ', maxsplit=1)[0])]
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
        inp = "\n".join(i for i in options) + "\n\n" + \
            "\n".join(i['name'] for i in folders.values())
        sel = dmenu_select(len(options) + len(folders) + 1, "Manage Folders", inp=inp)
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
    inp = "NO\nYes - confirm delete\n"
    delete = dmenu_select(2, "Confirm delete", inp=inp)
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
    name = dmenu_select(1, "New folder name", inp=basename(folder['name']))
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
        prompt = f"Collections - {prompt_name} (Enter to select, ESC when done)"
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
                return f"*{num}"
        return num

    loop = True
    while loop:
        if coll_list is False:
            coll_list = []
            loop = False
        inp = str("\n").join(pattern.format(check_coll(j, coll_list, i),
                                            i['name'],
                                            orgs[i['organizationId']]['name'],
                                            na=num_align)
                             for j, i in colls.items())
        sel = dmenu_select(min(bwm.MAX_LEN, len(colls)), prompt, inp=inp)
        if not sel:
            return {i['id']: i for i in coll_list}
        if sel.startswith('*'):
            sel = sel.lstrip('*')
            try:
                col = colls[int(sel.split(' - ', maxsplit=1)[0])]
                coll_list.remove(col)
            except (ValueError, TypeError):
                loop = False
        else:
            try:
                col = colls[int(sel.split(' - ', maxsplit=1)[0])]
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
        inp = "\n".join(i for i in options) + "\n\n" + \
                "\n".join(i['name'] for i in collections.values())
        sel = dmenu_select(len(options) + len(collections) + 1, "Manage collections", inp=inp)
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
    inp = "NO\nYes - confirm delete\n"
    delete = dmenu_select(2, f"Confirm delete of {collection['name']}", inp=inp)
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
                                       prompt="Select destination collection "
                                              "(Esc to move to root directory)")
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
    name = dmenu_select(1, "New collection name", inp=basename(collection['name']))
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
    inp = str("\n").join(pattern.format(j, i['name'], na=num_align)
                         for j, i in orgs_ids.items())
    sel = dmenu_select(min(bwm.MAX_LEN, len(orgs)), "Select Organization", inp=inp)
    if not sel:
        return False
    try:
        return orgs_ids[int(sel.split(' - ', 1)[0])]
    except (ValueError, TypeError):
        return False

# vim: set et ts=4 sw=4 :
