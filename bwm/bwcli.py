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
    return dict(json.loads(res.stdout))

def set_server(url="https://vault.bitwarden.com"):
    """Set vault URL

        Returns: True if successful or False on error

    """
    res = run(["bw", "config", "server", url], capture=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return True

def login(email, password):
    """Initial login to Bitwarden Vault.

        Returns: session (bytes) or False on error

    """
    res = run(["bw", "login", "--raw", email, password], capture=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return res.stdout

def unlock(password):
    """Unlock vault

        Returns: session (bytes) or False on error

    """
    res = run(["bw", "unlock", "--raw", password], capture=True, check=False)
    if not res.stdout:
        logging.debug(res)
        return False
    return res.stdout

def lock():
    """Lock vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "lock"], capture=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return True

def logout():
    """Logout of vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "logout"], capture=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return True

def get_entries(session=b''):
    """Get all entries from vault

        Return: List of objects

    """
    res = run(["bw", "--session", session, "list", "items"], capture=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return json.loads(res.stdout)

def sync(session=b''):
    """Sync web vault changes to local vault

        Return: True on success, False with any errors

    """
    res = run(["bw", "--session", session, "lock"], capture=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return True

def get_folders(session):
    """Return all folder names.

        Return: List of folder dicts {id: dict('object':folder,'id':id,'name':<name>)}

    """
    res = run(["bw", "--session", session, "list", "folders"], capture=True, check=False)
    if not res.stderr:
        logging.debug(res)
        return False
    return {i['id']:i for i in json.loads(res.stdout)}

def get_collections(session):
    """Return all collection names.

        Return: List of collection dicts {id:
            dict('object':collection,'id':id,'organizationId:<org
                 id>,'externalId':<ext id>,'name':<name>)}

    """
    res = run(["bw", "--session", session, "list", "collections"], capture=True, check=False)
    if not res.stderr:
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
