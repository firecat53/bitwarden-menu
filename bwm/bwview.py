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
                i['login']['url'],
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


def view_login(entry, folders):
    """Show title, username, password, url and notes for a login entry.

    Returns: dmenu selection

    """
    fields = [entry['name'] or "Title: None",
              obj_name(folders, entry['folderId']),
              entry['login']['username'] or "Username: None",
              '**********' if entry['login']['password'] else "Password: None",
              "TOTP: ******" if entry['login']['totp'] else "TOTP: None",
              entry['login']['url'] or "URL: None",
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries = "\n".join(fields)
    sel = dmenu_select(len(fields), inp=vault_entries)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == "Notes: None":
        sel = ""
    elif sel == '**********':
        sel = entry['login']['password']
    elif sel == "TOTP: ******":
        sel = gen_otp(entry['login']['totp'])
    elif sel == fields[5]:
        if sel != "URL: None":
            webbrowser.open(sel)
        sel = ""
    return sel if not sel.endswith(": None") else ""


def view_note(entry, folders):
    """Show title and note for a secure note entry.

    Returns: dmenu selection

    """
    fields = [entry['name'] or "Title: None",
              obj_name(folders, entry['folderId']),
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries = "\n".join(fields)
    sel = dmenu_select(len(fields), inp=vault_entries)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == "Notes: None":
        sel = ""
    return sel


def view_card(entry, folders):
    """Show title, card info and notes for a card entry.

    Returns: dmenu selection

    """
    exp = "Expiration Date: None"
    if entry['card']['expMonth'] or entry['card']['expYear']:
        exp = f"{entry['card']['expMonth']}/{entry['card']['expYear']}"
    fields = [entry['name'] or "Title: None",
              obj_name(folders, entry['folderId']),
              entry['card']['brand'] or "Card Type: None",
              entry['card']['cardholderName'] or "Card Holder Name: None",
              entry['card']['number'] or "Card Number: None",
              exp,
              entry['card']['code'] or "CVV Code: None",
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries = "\n".join(fields)
    sel = dmenu_select(len(fields), inp=vault_entries)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == "Notes: None":
        sel = ""
    return sel


def view_ident(entry, folders):
    """Show title, identify information and notes for an identity entry.

    Returns: dmenu selection

    """
    fields = [entry['name'] or "Title: None",
              obj_name(folders, entry['folderId']),
              entry['identity']['title'] or "Title: None",
              entry['identity']['firstName'] or "First name: None",
              entry['identity']['middleName'] or "Middle name: None",
              entry['identity']['lastName'] or "Last name: None",
              entry['identity']['address1'] or "Address1: None",
              entry['identity']['address2'] or "Address2: None",
              entry['identity']['address3'] or "Address3: None",
              entry['identity']['city'] or "City: None",
              entry['identity']['state'] or "State: None",
              entry['identity']['postalCode'] or "Postal Code: None",
              entry['identity']['country'] or "Country: None",
              entry['identity']['email'] or "Email: None",
              entry['identity']['phone'] or "Phone: None",
              entry['identity']['ssn'] or "SSN: None",
              entry['identity']['username'] or "Username: None",
              entry['identity']['passportNumber'] or "Passport #: None",
              entry['identity']['licenseNumber'] or "License #: None",
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries = "\n".join(fields)
    sel = dmenu_select(len(fields), inp=vault_entries)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == "Notes: None":
        sel = ""
    return sel


def view_notes(notes):
    """View the 'Notes' field line-by-line within dmenu.

    Returns: text of the selected line for typing

    """
    sel = dmenu_select(min(bwm.MAX_LEN, len(notes.split('\n'))), inp=notes)
    return sel
