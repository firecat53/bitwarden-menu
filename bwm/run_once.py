"""Entry search and field extraction for --show/--field

Pure helpers over already-loaded vault entries: no unlocking, no `bw` calls.
Used both by the process that starts the daemon (which has the vault in hand)
and by DmenuRunner.show_entry() when a daemon is already running.
"""

import re
import sys
from os.path import join

import bwm
from bwm.bwtype import PLACEHOLDER_AUTOTYPE_TOKENS
from bwm.bwview import obj_name

# Standard autotype token names usable on any entry type. These win over the
# per-type field names below, so a name never changes meaning depending on
# which kind of entry matched.
TOKEN_FIELDS = {
    "title": "{TITLE}",
    "username": "{USERNAME}",
    "url": "{URL}",
    "password": "{PASSWORD}",
    "notes": "{NOTES}",
    "cardnum": "{CARDNUM}",
    "totp": "{TOTP}",
}
FIELD_ALL = "all"
# bwm.IDENTITY's "Title" is the honorific (Mr/Ms/Dr), which would otherwise
# collide with the {TITLE} token. It keeps a distinct name.
IDENTITY_TITLE = "identity title"


def _canon(name):
    """Canonical lookup key: casefolded, no spaces/underscores/hyphens.

    Lets 'Security Code', 'security_code' and 'securitycode' all match.

    Args: name - string
    Returns: string

    """
    return re.sub(r"[\s_-]+", "", name).casefold()


def _type_labels(entry_type):
    """Field labels for a Bitwarden entry type.

    Args: entry_type - int (1 login, 2 note, 3 card, 4 identity)
    Returns: dict {label: bitwarden key}

    """
    dicts = {1: bwm.LOGIN, 3: bwm.CARD, 4: bwm.IDENTITY}
    out = {}
    for label, key in dicts.get(entry_type, {}).items():
        out[IDENTITY_TITLE if label == "Title" else label.lower()] = key
    return out


def _known_fields():
    """Every field name --field accepts, canonical form keyed by lookup key.

    Returns: dict {canonical lookup key: label}

    """
    labels = list(TOKEN_FIELDS)
    for entry_type in (1, 3, 4):
        labels.extend(_type_labels(entry_type))
    return {_canon(i): i for i in labels}


def normalize_field(name):
    """Normalize a field name given on the command line.

    Accepts autotype token names and per-type field names, with or without
    braces and insensitive to case and separators, the special value 'all',
    and 'S:<name>' for a custom field (kept exact and case sensitive).

    Args: name - string
    Returns: normalized field name string
    Raises: ValueError on an unknown field name

    """
    field = name.strip()
    if field.startswith("{") and field.endswith("}"):
        field = field[1:-1].strip()
    if field.casefold() == FIELD_ALL:
        return FIELD_ALL
    if field[:2].casefold() == "s:":
        attr = field[2:]
        if not attr:
            raise ValueError("No field name given for 'S:'")
        return f"S:{attr}"
    known = _known_fields()
    if _canon(field) in known:
        return known[_canon(field)]
    valid = ", ".join(sorted(set(known.values())))
    raise ValueError(
        f"Unknown field '{name}'. Valid fields: {valid}, all, S:<custom field>"
    )


def custom_fields(entry):
    """Custom fields of an entry, excluding the autotype pseudo-field.

    Args: entry - dict
    Returns: dict {name: value}

    """
    return {
        i["name"]: i.get("value") or ""
        for i in entry.get("fields") or []
        if i.get("name") and i["name"] != "autotype"
    }


def entry_fields(entry):
    """Every field this entry can have, in display order.

    Args: entry - dict
    Returns: dict {label: value}

    """
    out = {"title": entry.get("name") or ""}
    typ = entry.get("type")
    if typ == 1:
        out["username"] = get_token(entry, "username")
        out["password"] = get_token(entry, "password")
        out["totp"] = get_token(entry, "totp")
        out["url"] = get_token(entry, "url")
    else:
        source = {3: entry.get("card"), 4: entry.get("identity")}.get(typ) or {}
        for label, key in _type_labels(typ).items():
            out[label] = source.get(key) or ""
    out["notes"] = entry.get("notes") or ""
    for name, value in custom_fields(entry).items():
        out[f"S:{name}"] = value
    return out


def get_token(entry, field):
    """Value of an autotype token field.

    Args: entry - dict
          field - one of TOKEN_FIELDS
    Returns: string, empty if the entry has no such value

    """
    return PLACEHOLDER_AUTOTYPE_TOKENS[TOKEN_FIELDS[field]](entry) or ""


def get_field(entry, field):
    """Value of a normalized field for an entry.

    Args: entry - dict
          field - normalized field name from normalize_field()
    Returns: string, empty if the field has no value

    """
    if field.startswith("S:"):
        return custom_fields(entry).get(field[2:], "")
    if field in TOKEN_FIELDS:
        return get_token(entry, field)
    return entry_fields(entry).get(field, "")


def list_fields(entry):
    """Labels of the fields of an entry that have a value.

    Determines what `-f all` prints.

    Args: entry - dict
    Returns: list of labels

    """
    return [i for i, val in entry_fields(entry).items() if val]


def entry_url(entry):
    """First URL of a login entry.

    Args: entry - dict
    Returns: string

    """
    return get_token(entry, "url") if entry.get("type") == 1 else ""


def search_entries(entries, folders, search_string):
    """Entries matching the search string in folder/name, username or URL.

    Args: entries - list of dicts
          folders - dict of folder objects
          search_string - string to search for

    Returns: list of matching entries

    """
    search_lower = search_string.casefold()
    search_terms = search_lower.split()
    matches = []

    for entry in entries:
        name = entry.get("name") or ""
        folder = obj_name(folders, entry.get("folderId"))
        full_path = join(folder, name)
        username = get_token(entry, "username")
        url = entry_url(entry)

        name, username, url, folder, full_path = [
            i.casefold() for i in (name, username, url, folder, full_path)
        ]

        if search_lower in full_path:
            matches.append(entry)
            continue

        # All search terms must appear somewhere in the entry
        if search_terms and all(
            any(
                term in field
                for field in [name, username, url, folder, full_path]
            )
            for term in search_terms
        ):
            matches.append(entry)

    return matches


def _error(lines, return_errors):
    """Report an error either as a string or on stderr.

    Args: lines - list of strings
          return_errors - if True, return the message instead of printing it

    Returns: error string prefixed with 'ERROR: ' or None

    """
    if return_errors:
        return "ERROR: " + "\n".join(lines)
    for line in lines:
        print(line, file=sys.stderr)
    return None


def show_fields(
    entries,
    folders,
    search_string,
    fields=None,
    return_errors=False,
):
    """Show the requested fields of the entry matching the search string.

    If multiple entries match, return an error.

    Args:
        entries - list of dicts
        folders - dict of folder objects
        search_string - string to search for
        fields - list of field names to output, defaults to ['password']
        return_errors - if True, return error messages instead of printing them

    Returns: the output string, an error string (if return_errors), or None

    The caller decides what to do with the text. Putting it on the clipboard
    happens in the client process: the clipboard belongs to the invoking
    session, and the daemon's environment is whatever it was started with.

    """
    matches = search_entries(entries, folders, search_string)

    if not matches:
        return _error(
            [f"No entries found matching '{search_string}'"], return_errors
        )

    if len(matches) > 1:
        error_lines = [
            f"Multiple entries found matching '{search_string}'. "
            "Please be more specific."
        ]
        for entry in matches:
            folder = obj_name(folders, entry.get("folderId"))
            username = get_token(entry, "username")
            error_lines.append(
                f"  - {join(folder, entry.get('name') or '')} ({username})"
            )
        return _error(error_lines, return_errors)

    entry = matches[0]

    try:
        fields = [normalize_field(i) for i in (fields or ["password"])]
    except ValueError as err:
        return _error([str(err)], return_errors)
    if FIELD_ALL in fields:
        # Labeled, since the caller can't tell which value is which.
        output = "\n".join(
            f"{i}: {get_field(entry, i)}" for i in list_fields(entry)
        )
    else:
        output = "\n".join(get_field(entry, i) for i in fields)

    return output


# vim: set et ts=4 sw=4 :
