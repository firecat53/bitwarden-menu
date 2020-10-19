"""Provide methods to manipulate Bitwarden vault using the Bitwarden CLI

TODO: capture_output only works in 3.7+. Maybe need to change that?

"""
from copy import deepcopy
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

def get_orgs(session):
    """Return all organizations for the logged in user

        Return: Dict of org dicts {id: dict('object':'organization','id':id,'name':<name>...)}
                False on error

    """
    res = run(["bw", "--session", session, "list", "organizations"],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def get_entries(session=b'', org_name=''):
    """Get all entries, folders, collections and orgs from vault

    Args: session: bytes
          org_name: name of organization. If given, only return items for that org
    1. since the URL is buried in:
        'login'->'uris'->[{match: xxx, uri: http...}, {match2: xxx, uri2: httpxxx}]
        copy the first uri to 'login'->'url' for ease of access later.
    2. Also adjust 'path' to be just the dirname, not including the 'name'
    3. Add the 'autotype' field so it can be edited if necessary

        Return: items (list of dictionaries), folders, collections, orgs
                False on error

    """
    res = run(["bw", "--session", session, "list", "items"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    items = json.loads(res.stdout)
    folders = get_folders(session)
    collections = get_collections(session, org_name)
    orgs = get_orgs(session)
    for item in items:
        path = folders.get(item.get('folderId')).get('name')
        if path == 'No Folder':
            path = '/'
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
    return items, folders, collections, orgs

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

        Return: Dict of folder dicts {id: dict('object':folder,'id':id,'name':<name>)}
                False on error

    """
    res = run(["bw", "--session", session, "list", "folders"], capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def get_collections(session, org_id=''):
    """Return all collection names for user.

        Args: session - session id bytes
              org_id - organization id string.

        Return: Dict of collection dicts {id:
            dict('object':collection,'id':id,'organizationId:<org
                 id>,'externalId':<ext id>,'name':<name>)}

    """
    cmd = ["bw", "--session", session, "list", "collections"]
    if org_id:
        cmd.extend(["--organizationid", org_id])
    res = run(cmd, capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def add_entry(entry, session):
    """Add new entry to vault

    Args: entry - dict with at least these fields
    Returns: new item dict or False on error

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
        Returns: updated entry object (dict) on success, False on failure

    """
    item = deepcopy(entry)
    enc = run(["bw", "encode"], input=json.dumps(item).encode(), capture_output=True, check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session, "edit", "item", item['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)

def delete_entry(entry, session):
    """Delete existing vault entry

        Args: entry - entry dict object
        Returns: entry object (dict) on success, False on failure

    """
    res = run(["bw", "--session", session, "delete", "item", entry['id']],
              capture_output=True, check=False)
    if res.returncode != 0:
        logging.error(res)
        return False
    return entry

def add_folder(folder, session):
    """Add folder

        Args: folder - string (name of folder)
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

def delete_folder(folder, session):
    """Delete folder

        Args: folder - folder object (dict)
              session - bytes
        Returns: folder object (dict) on success, False on failure


    """
    res = run(["bw", "--session", session, "delete", "folder", folder['id']],
              capture_output=True, check=False)
    if res.returncode != 0:
        logging.error(res)
        return False
    return folder

def move_folder(folder, newpath, session):
    """Move or rename folder

        Args: folder - folder dict object
              newpath - string (new name/path)
              session - bytes
        Returns: Folder object on success, False on failure

    """
    fold = deepcopy(folder)
    fold['name'] = newpath
    enc = run(["bw", "encode"],
              input=json.dumps(fold).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session, "edit", "folder", fold['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)

def add_collection(collection, org_id, session):
    """Add collection

        Args: collection - string
              org - organization id string
              session - bytes

        Returns: collection object or False on error

        TODO: remove hack below for bug in bw cli where
        `bw create org-collection` doesn't return the new object id.
        The collection is created, but a sync is needed to obtain the new
        collection id.
        https://github.com/bitwarden/cli/issues/175

    """
    collection = {"name": collection, "organizationId": org_id}
    enc = run(["bw", "encode"],
              input=json.dumps(collection).encode(), capture_output=True, check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "--session", session,
               "--organizationid", org_id.encode(),
               "create", "org-collection".encode(), enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    # Begin hack (see notes above)
    sync(session)
    collections = get_collections(session)
    new = [i for i in collections.values() if i['name'] == collection['name']]
    if len(new) != 1:
        logging.error("Adding collection error: name already exists")
        return False
    res.stdout = json.dumps(new[0])
    # End hack
    return json.loads(res.stdout)

def delete_collection(collection, session):
    """Delete collection

        Args: collection - collection object (dict)
              session - bytes
        Returns: collection object (dict) on success, False on failure

    """
    res = run(["bw", "--session", session,
               "--organizationid", collection['organizationId'].encode(),
               "delete", "org-collection", collection['id']],
              capture_output=True, check=False)
    if res.returncode != 0:
        logging.error(res)
        return False
    return collection

def move_collection(collection, newpath, session):
    """Move or rename collection

        Args: collection - collection object (dict)
              newpath - string (new name/path)
              session - bytes
        Returns: collection object on success, False on failure

        TODO: remove hack below for bug in bw cli where
        `bw edit org-collection` doesn't return the new object id.
        The collection is edited, but a sync is needed to obtain the new
        collection id.
        https://github.com/bitwarden/cli/issues/175

    """
    coll = deepcopy(collection)
    coll['name'] = newpath
    enc = run(["bw", "encode"],
              input=json.dumps(coll).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw",
               "--session", session,
               "--organizationid", coll['organizationId'].encode(),
               "edit", "org-collection", coll['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    # Begin hack (see notes above)
    sync(session)
    collections = get_collections(session)
    new = [i for i in collections.values() if i['name'] == coll['name']]
    if len(new) != 1:
        logging.error("Editing collection error: name already exists")
        return False
    res.stdout = json.dumps(new[0])
    # End hack
    return json.loads(res.stdout)

# vim: set et ts=4 sw=4 :
