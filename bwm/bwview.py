"""Bitwarden-menu view functions

"""
from os.path import join
import webbrowser

from bwm.menu import dmenu_select
from bwm.totp import gen_otp
import bwm


def obj_name(obj, oid):
    """Return name of folder/collection object based on id

        Args: obj - dict
              oid - string

    """
    path = obj[oid]['name']
    if path == 'No Folder':
        path = '/'
    return path


def view_all_entries(options, vault_entries, folders):
    """Generate numbered list of all vault entries and open with dmenu.

    Returns: dmenu selection

    """
    num_align = len(str(len(vault_entries)))
    # Login: Num(l) - Folder/name - username - url
    bw_login_pattern = str("{:>{na}}(l) - {} - {} - {}")
    # Secure Note: Num(n) - Folder/name
    bw_note_pattern = str("{:>{na}}(n) - {}")
    # Card: Num(c) - Folder/name - card type - card owner - card #
    bw_card_pattern = str("{:>{na}}(c) - {} - {} - {} - {}")
    # Identity: Num(i) - Folder/name - lastName, firstName - email - phone
    bw_ident_pattern = str("{:>{na}}(i) - {} - {}, {} - {} - {}")
    # Have to number each entry to capture duplicates correctly
    ven = []
    for j, i in enumerate(vault_entries):
        if i['type'] == 1:
            ven.append(bw_login_pattern.format(
                j,
                join(obj_name(folders, i['folderId']), i['name']),
                i['login']['username'],
                make_url_entries(i)[0].split(": ", 1)[1],
                na=num_align))
        elif i['type'] == 2:
            ven.append(bw_note_pattern.format(
                j,
                join(obj_name(folders, i['folderId']), i['name']),
                na=num_align))
        elif i['type'] == 3:
            ven.append(bw_card_pattern.format(
                j,
                join(obj_name(folders, i['folderId']), i['name']),
                i['card']['brand'],
                i['card']['cardholderName'],
                i['card']['number'],
                na=num_align))
        elif i['type'] == 4:
            ven.append(bw_ident_pattern.format(
                j,
                join(obj_name(folders, i['folderId']), i['name']),
                i['identity']['lastName'],
                i['identity']['firstName'],
                i['identity']['email'],
                i['identity']['phone'],
                na=num_align))
    vault_entries_s = str("\n").join(ven)
    if options:
        options_s = ("\n".join(options) + "\n")
        entries_s = options_s + vault_entries_s
    else:
        entries_s = vault_entries_s
    return dmenu_select(min(bwm.MAX_LEN, len(options) + len(vault_entries)), inp=entries_s)


def view_entry(entry, folders):
    """Show an entry (login, card, identity or secure note)

    """
    entry_types = {1: view_login, 2: view_note, 3: view_card, 4: view_ident}
    return entry_types[entry['type']](entry, folders)


def make_url_entries(entry):
    """Parse multiple URL's for viewing

    Args: entry
    Returns: list of strings ["URL: xxxxx", "URL1: xxxx", "URL2: xxxx"]

    """
    urls = entry.get('login').get('uris') if entry.get('login') else None
    return [f"URL{j}: {i['uri']}" for j, i in enumerate(urls, 1)] if urls else ["URL: None"]


def view_login(entry, folders):
    """Show title, username, password, url and notes for a login entry.

    Returns: dmenu selection to type

    """
    fields = [f"Title: {entry['name'] or 'None'}",
              f"Folder: {obj_name(folders, entry['folderId'])}",
              f"Username: {entry['login']['username'] or 'None'}",
              f"Password: {'**********' if entry['login']['password'] else 'None'}",
              f"TOTP: {'******' if entry['login']['totp'] else 'None'}",
              f"Notes: {'<Enter to view>' if entry['notes'] else 'None'}"]
    fields[-1:-1] = make_url_entries(entry)
    sel = dmenu_select(len(fields), inp="\n".join(fields))
    if sel.endswith(": None") or sel not in fields:
        return ""
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == 'Password: **********':
        sel = entry['login']['password']
    elif sel == "TOTP: ******":
        sel = gen_otp(entry['login']['totp'])
    elif sel.startswith("URL"):
        if sel != "URL: None":
            webbrowser.open(sel.split(": ", 1)[-1])
        sel = ""
    else:
        sel = sel.split(": ", 1)[1]
    return sel


def view_note(entry, folders):
    """Show title and note for a secure note entry.

    Returns: dmenu selection

    """
    fields = [f"Title: {entry['name'] or 'None'}",
              f"Folder: {obj_name(folders, entry['folderId'])}",
              f"Notes: {'<Enter to view>' if entry['notes'] else 'None'}"]
    sel = dmenu_select(len(fields), inp="\n".join(fields))
    if sel.endswith(": None") or sel not in fields:
        return ""
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    else:
        sel = sel.split(": ", 1)[1]
    return sel


def view_card(entry, folders):
    """Show title, card info and notes for a card entry.

    Returns: dmenu selection

    """
    fields = [f"Title: {entry['name'] or 'None'}",
              f"Folder: {obj_name(folders, entry['folderId'])}",
              f"Notes: {'<Enter to view>' if entry['notes'] else 'None'}"]
    fields[-1:-1] = [f"{i}: {entry['card'][j] or 'None'}" for i, j in bwm.CARD.items()]
    sel = dmenu_select(len(fields), inp="\n".join(fields))
    if sel.endswith(": None") or sel not in fields:
        return ""
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    else:
        sel = sel.split(": ", 1)[1]
    return sel


def view_ident(entry, folders):
    """Show title, identify information and notes for an identity entry.

    Returns: dmenu selection

    """
    fields = [f"Title: {entry['name'] or 'None'}",
              f"Folder: {obj_name(folders, entry['folderId'])}",
              f"Notes: {'<Enter to view>' if entry['notes'] else 'None'}"]
    fields[-1:-1] = [f"{i}: {entry['identity'][j] or 'None'}" for i, j in bwm.IDENTITY.items()]
    sel = dmenu_select(len(fields), inp="\n".join(fields))
    if sel.endswith(": None") or sel not in fields:
        return ""
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    else:
        sel = sel.split(": ", 1)[1]
    return sel


def view_notes(notes):
    """View the 'Notes' field line-by-line within dmenu.

    Returns: text of the selected line for typing

    """
    sel = dmenu_select(min(bwm.MAX_LEN, len(notes.split('\n'))), inp=notes)
    return sel
