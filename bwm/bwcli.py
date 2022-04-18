"""Provide methods to manipulate Bitwarden vault using the Bitwarden CLI

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


def login(email, password, method=None, code=""):
    """Initial login to Bitwarden Vault. May require BW_CLIENTSECRET to be set.

        Args: email - string
              password - string
              method - int (0: Authenticator, 1: Email, 3: Yubikey)
              code - OTP code

        Returns: session (bytes) or False on error, Error message

    """
    cmd = ["bw", "login", "--raw", email, password]
    if method and code:
        cmd = ["bw", "login", "--raw", email, password, "--method", method, "--code", code]
    res = run(cmd, capture_output=True, check=False)
    if not res.stdout or res.stderr:
        logging.error(res)
        return (False, res.stderr)
    return res.stdout, None


def unlock(password):
    """Unlock vault

        Returns: session (bytes) or False on error, Error message

    """
    if not password:
        logging.error("No password provided")
        return (False, "No password provided")
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
    return {i['id']: i for i in json.loads(res.stdout)}


class Item(dict):
    """Set some default attributes to all items

    """
    def __init__(self, /, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setdefault('fields', [])
        if not any(i['name'] == 'autotype' for i in self.get('fields')):
            self['fields'].append({'name': 'autotype', 'value': "", 'type': 0})


def get_entries(session, org_name=''):
    """Get all entries, folders, collections and orgs from vault

    Args: session: bytes
          org_name: name of organization. If given, only return items for that org
    1. since the URL is buried in:
        'login'->'uris'->[{match: xxx, uri: http...}, {match2: xxx, uri2: httpxxx}]
        copy the first uri to 'login'->'url' for ease of access later.
    2. Also adjust 'path' to be just the dirname, not including the 'name'
    3. Add the 'autotype' field so it can be edited if necessary

        Return: items (list of Items), folders, collections, orgs
                False on error

    """
    res = run(["bw", "--session", session, "list", "items"],
              capture_output=True,
              check=False)
    if not res.stdout:
        logging.error(res)
        return False
    items = [Item(i) for i in json.loads(res.stdout)]
    folders = get_folders(session)
    collections = get_collections(session, org_name)
    orgs = get_orgs(session)
    return items, folders, collections, orgs


def sync(session):
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
    res = run(["bw", "--session", session, "list", "folders"],
              capture_output=True,
              check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return {i['id']: i for i in json.loads(res.stdout)}


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
    return {i['id']: i for i in json.loads(res.stdout)}


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
        "notes":null,
        "favorite":false,
        "fields":[],
        "login":null,
        "secureNote":null,
        "card":null,
        "identity":null}'

    """
    enc = run(["bw", "encode"],
              input=json.dumps(entry).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "create",
               "--session", session,
               "item", enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)


def edit_entry(entry, session, update_coll='NO'):
    # pylint: disable=too-many-return-statements
    """Modify existing vault entry

        Args: entry - entry dict object
              session - session id
              update_coll - 'YES' if item collections have been modified.
                            'MOVE' if collections are added so item needs to be
                                move to an org.  Returns: updated entry object
                                (dict) on success, False on failure
                            'REMOVE' if collections are removed so item needs to
                                be moved from the org to personal vault.

    """
    item = deepcopy(entry)
    if update_coll == 'YES':
        enc = run(["bw", "encode"],
                  input=json.dumps(item['collectionIds']).encode(),
                  capture_output=True,
                  check=False)
        if not enc.stdout:
            logging.error(enc)
            return False
        res = run(["bw", "edit",
                   "--session", session,
                   "item-collections", item['id'], enc.stdout],
                  capture_output=True, check=False)
        if not res.stdout:
            logging.error(res)
            return False
    elif update_coll == 'MOVE':
        res = move_entry(entry, session)
        if res is False:
            return False
    elif update_coll == 'REMOVE':
        res = delete_entry(entry, session)
        if res is False:
            return False
        item['id'] = None
        item['collectionIds'] = []
        item['organizationId'] = None
        res = add_entry(item, session)
        if res is False:
            return False
        return res
    enc = run(["bw", "encode"],
              input=json.dumps(item).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "edit",
               "--session", session,
               "item", item['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)


def move_entry(entry, session):
    """Move entry to an organization (if it currently belongs to personal vault)

        Assumes entry already has the organizationId and collectionIds updated.

        Args: entry - entry dict object
              session - session id
        Returns: updated entry object (dict) on success, False on failure

    """
    item = deepcopy(entry)
    enc = run(["bw", "encode"],
              input=json.dumps(item['collectionIds']).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "move",
               "--session", session,
               item['id'],
               item['organizationId'].encode(),
               enc.stdout],
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
    res = run(["bw", "delete",
               "--session", session,
               "item", entry['id']],
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
    enc = run(["bw", "encode"],
              input=json.dumps(folder).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "create",
               "--session", session,
               "folder", enc.stdout],
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
    res = run(["bw", "delete",
               "--session", session,
               "folder", folder['id']],
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
    res = run(["bw", "edit",
               "--session", session,
               "folder", fold['id'], enc.stdout],
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

    """
    collection = {"name": collection, "organizationId": org_id}
    enc = run(["bw", "encode"],
              input=json.dumps(collection).encode(),
              capture_output=True,
              check=False)
    if not enc.stdout:
        logging.error(enc)
        return False
    res = run(["bw", "create",
               "--session", session,
               "--organizationid", org_id.encode(),
               "org-collection".encode(), enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)


def delete_collection(collection, session):
    """Delete collection

        Args: collection - collection object (dict)
              session - bytes
        Returns: collection object (dict) on success, False on failure

    """
    res = run(["bw", "delete",
               "--session", session,
               "--organizationid", collection['organizationId'].encode(),
               "org-collection", collection['id']],
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
    res = run(["bw", "edit",
               "--session", session,
               "--organizationid", coll['organizationId'].encode(),
               "org-collection", coll['id'], enc.stdout],
              capture_output=True, check=False)
    if not res.stdout:
        logging.error(res)
        return False
    return json.loads(res.stdout)

# vim: set et ts=4 sw=4 :
