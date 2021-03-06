"""Bitwarden-menu view functions

"""
from os.path import join
import webbrowser

from bwm.menu import dmenu_select
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
    vault_entries_b = str("\n").join(ven).encode(bwm.ENC)
    if options:
        options_b = ("\n".join(options) + "\n").encode(bwm.ENC)
        entries_b = options_b + vault_entries_b
    else:
        entries_b = vault_entries_b
    return dmenu_select(min(bwm.DMENU_LEN, len(options) + len(vault_entries)), inp=entries_b)


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
    elif sel == fields[4]:
        if sel != "URL: None":
            webbrowser.open(sel)
        sel = ""
    return sel


def view_note(entry, folders):
    """Show title and note for a secure note entry.

    Returns: dmenu selection

    """
    fields = [entry['name'] or "Title: None",
              obj_name(folders, entry['folderId']),
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=vault_entries_b)
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
        exp = "{}/{}".format(entry['card']['expMonth'], entry['card']['expYear'])
    fields = [entry['name'] or "Title: None",
              obj_name(folders, entry['folderId']),
              entry['card']['brand'] or "Card Type: None",
              entry['card']['cardholderName'] or "Card Holder Name: None",
              entry['card']['number'] or "Card Number: None",
              exp,
              entry['card']['code'] or "CVV Code: None",
              "Notes: <Enter to view>" if entry['notes'] else "Notes: None"]
    vault_entries_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=vault_entries_b)
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
    vault_entries_b = "\n".join(fields).encode(bwm.ENC)
    sel = dmenu_select(len(fields), inp=vault_entries_b)
    if sel == "Notes: <Enter to view>":
        sel = view_notes(entry['notes'])
    elif sel == "Notes: None":
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
