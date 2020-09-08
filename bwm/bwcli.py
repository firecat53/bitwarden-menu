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
        logging.error(res)
        return False
    return dict(json.loads(res.stdout.split(b'\n')[-1]))

def set_server(url="https://vault.bitwarden.com"):
    """Set vault URL

        Returns: True if successful or False on error

    """
    res = run(["bw", "config", "server", url], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return True

def login(email, password):
    """Initial login to Bitwarden Vault.

        Returns: session (bytes) or False on error, Error message

    """
    res = run(["bw", "login", "--raw", email, password], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return (False, res.stderr)
    return res.stdout, None

def unlock(password):
    """Unlock vault

        Returns: session (bytes) or False on error, Error message

    """
    res = run(["bw", "unlock", "--raw", password], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return (False, res.stderr)
    return res.stdout, None

def lock():
    """Lock vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "lock"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return True

def logout():
    """Logout of vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "logout"], capture_output=True, check=False)
    if not res.stderr:
        logging.error(res)
        return False
    return True

def get_entries(session=b''):
    """Get all entries, folders and collections from vault

    1. since the URL is buried in:
        'login'->'uris'->[{match: xxx, uri: http...}, {match2: xxx, uri2: httpxxx}]
        copy the first uri to 'login'->'url' for ease of access later.
    2. Also adjust 'path' to be just the dirname, not including the 'name'
    3. Add the 'autotype' field so it can be edited if necessary

        Return: items (list of dictionaries), folders, collections
                False on error

    """
    res = run(["bw", "--session", session, "list", "items"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    items = json.loads(res.stdout)
    folders = get_folders(session)
    folder_ids = {i['id']: i for i in folders.values()}
    collections = get_collections(session)
    for item in items:
        path = folder_ids.get(item.get('folderId')).get('name')
        if path == 'No Folder':
            path = '/'
        item['folder'] = path
        try:
            for uri in item['login']['uris']:
                item['login']['url'] = uri['uri']
                break
            else:
                item['login']['url'] = ""
        except KeyError:
            item['login']['url'] = ""
        item.setdefault('fields', [])
        if not any([i['name'] == 'autotype' for i in item.get('fields')]):
            item['fields'].append({'name': 'autotype', 'value':"", 'type':0})
        item['collections'] = [collections[i]['name'] for i in item['collectionIds']]
    return items, folders, collections

def sync(session=b''):
    """Sync web vault changes to local vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "--session", session, "sync"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return True

def get_folders(session):
    """Return all folder names.

        Return: Dict of folder dicts {name: dict('object':folder,'id':id,'name':<name>)}
                False on error

    """
    res = run(["bw", "--session", session, "list", "folders"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return {i['name']:i for i in json.loads(res.stdout)}

def get_collections(session):
    """Return all collection names.

        Return: Dict of collection dicts {id:
            dict('object':collection,'id':id,'organizationId:<org
                 id>,'externalId':<ext id>,'name':<name>)}

    """
    res = run(["bw", "--session", session, "list", "collections"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def add_entry(entry, session):
    """Add new entry to vault

    Args: entry - dict with at least these fields
    Returns: new item dict

    New item template:
    {
        "organizationId":null,
        "folderId":null,
        "type":1,
        "name":"Item name",
        "notes":"Some notes about this item.",
        "favorite":false,
        "fields":[],
        "login":null,
        "secureNote":null,
        "card":null,
        "identity":null}'

    """
    enc = run(["bw", "encode"], input=json.dumps(entry).encode(), capture_output=True, check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session, "create", "item", enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)

def edit_entry(entry, session):
    """Modify existing vault entry

        Args: entry - entry dict object
        Returns: True on success, False on failure

    """
    enc = run(["bw", "encode"], input=json.dumps(entry).encode(), capture_output=True, check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session, "edit", "item", entry['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return True

def delete_entry(entry, session):
    """Delete existing vault entry

        Args: entry - entry dict object
        Returns: True on success, False on failure

    """
    res = run(["bw", "--session", session, "delete", "item", entry['id']],
              capture_output=True, check=False)
    if res.returncode != 0:
        logging.error(res)
        return False
    return True

def add_folder(folder, session):
    """Add folder

        Args: folder - string
              session - bytes

        Returns: Folder object or False on error

    """
    folder = {"name": folder}
    enc = run(["bw", "encode"], input=json.dumps(folder).encode(), capture_output=True, check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session, "create", "folder", enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)

def delete_folder(folders, folder, session):
    """Delete folder

        Args: folders - dict of folder dicts {'name': {'id': <id>, 'name': <name>, ...}
              folder - name of folder to delete (string)
              session - bytes
        Returns: True on success, False on failure


    """
    fid = folders[folder]['id']
    res = run(["bw", "--session", session, "delete", "folder", fid],
              capture_output=True, check=False)
    if res.returncode != 0:
        logging.error(res)
        return False
    return True

def move_folder(folders, oldpath, newpath, session):
    """Move folder

        Args: folders - dict of all folder dicts {'name': {'id':<id>, 'name':<name>, ...}
              oldpath - string (old name/path)
              newpath - string (new name/path)
              session - bytes
        Returns: Folder object on success, False on failure

    """
    folders[newpath] = folders.pop(oldpath)
    folders[newpath]['name'] = newpath
    enc = run(["bw", "encode"],
              input=json.dumps(folders[newpath]).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session, "edit", "folder", folders[newpath]['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)

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
