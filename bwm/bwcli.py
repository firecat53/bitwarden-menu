"""Provide methods to manipulate Bitwarden vault using the Bitwarden CLI

TODO: capture_output only works in 3.7+. Maybe need to change that?

"""
import json
import logging
from subprocess import run

def status(session=b''):
    """Check status of vault

        Returns: Dict -
                 {serverUrl: <url>,
                 lastSync: date/time,
                 userEmail: <email>,
                 userId: userId,
                 status: <'locked', 'unlocked' or 'unauthenticated'>}
            False on error

    """
    res = run(["bw", "--session", session, "status"], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return dict(json.loads(res.stdout.split(b'\n')[-1]))

def set_server(url="https://vault.bitwarden.com"):
    """Set vault URL

        Returns: True if successful or False on error

    """
    res = run(["bw", "config", "server", url], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return True

def login(email, password):
    """Initial login to Bitwarden Vault.

        Returns: session (bytes) or False on error, Error message

    """
    res = run(["bw", "login", "--raw", email, password], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return (False, res.stderr)
    return res.stdout, None

def unlock(password):
    """Unlock vault

        Returns: session (bytes) or False on error, Error message

    """
    res = run(["bw", "unlock", "--raw", password], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return (False, res.stderr)
    return res.stdout, None

def lock():
    """Lock vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "lock"], capture_output=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return True

def logout():
    """Logout of vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "logout"], capture_output=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return True

def get_entries(session=b''):
    """Get all entries, folders and collections from vault

    For now: since the URL is buried in:
        'login'->'uris'->[{match: xxx, uri: http...}, {match2: xxx, uri2: httpxxx}]
    copy the first uri to 'login'->'uri' for ease of access later.

        Return: items (list of dictionaries), folders, collections
                False on error

    """
    res = run(["bw", "--session", session, "list", "items"], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    items = json.loads(res.stdout)
    folders = get_folders(session)
    collections = get_collections(session)
    for item in items:
        path = folders.get(item.get('folderId')).get('name')
        if path == 'No Folder':
            path = ''
        path = "/".join([path, item.get('name')]).lstrip('/')
        item['path'] = path
        try:
            for uri in item['login']['uris']:
                item['login']['uri'] = uri['uri']
                break
        except KeyError:
            item['login']['uri'] = ""
        item['collections'] = [collections[i]['name'] for i in item['collectionIds']]
    return items, folders, collections

def sync(session=b''):
    """Sync web vault changes to local vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "--session", session, "lock"], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return True

def get_folders(session):
    """Return all folder names.

        Return: List of folder dicts {id: dict('object':folder,'id':id,'name':<name>)}

    """
    res = run(["bw", "--session", session, "list", "folders"], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def get_collections(session):
    """Return all collection names.

        Return: List of collection dicts {id:
            dict('object':collection,'id':id,'organizationId:<org
                 id>,'externalId':<ext id>,'name':<name>)}

    """
    res = run(["bw", "--session", session, "list", "collections"], capture_output=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def add_entry():
    """Add new entry to vault

    """

def edit_entry():
    """Modify existing vault entry

    """

def delete_entry():
    """Delete existing vault entry

    """

def add_folder():
    """Add folder

    """

def delete_folder():
    """Delete folder

    """

def move_folder():
    """Move or rename folder

    """

def add_collection():
    """Add collection

    """

def delete_collection():
    """Delete collection

    """

def move_collection():
    """Move or rename collection

    """

# vim: set et ts=4 sw=4 :
