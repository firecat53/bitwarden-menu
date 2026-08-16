"""
Provide methods to manipulate Bitwarden vault using the Bitwarden CLI,
primarily via the `serve` command
"""

from http.client import HTTPConnection
import json
import logging
from subprocess import Popen, PIPE
import socket
import time
from urllib.parse import urlencode
from bwm.bwcli import Item, _bw_env

# Default `bw serve` port per their docs
BW_SERVE_PORT = 8087


class BWHTTPConnection(HTTPConnection):
    """
    Open a stub HTTP Connection with our existing socket
    """

    def __init__(self, sock):
        # bw serve >= 2026.6 rejects any request whose Host header isn't
        # localhost/127.0.0.1/[::1] on BW_SERVE_PORT.
        super().__init__("localhost", BW_SERVE_PORT)
        self.sock = sock

    def connect(self):
        pass


class BWCLIServer:
    """Interface to bw serve using Unix socket pair for fast API access"""

    def __init__(self):
        self.client_sock = None
        self.process = None
        self._initialized = False

    def start(self, session=None):
        """Start the bw serve process with socket communication

        Args: session - session token (string or bytes) from CLI login/unlock
                       Required for bw serve to work
        """
        if self._initialized:
            logging.debug("BWCLIServer.start: Already initialized")
            return True

        if not session:
            logging.error(
                "BWCLIServer.start: Session token required to start bw serve"
            )
            return False

        logging.debug(
            "BWCLIServer.start: Starting bw serve process with session"
        )
        try:
            # Create socket pair for communication
            self.client_sock, server_sock = socket.socketpair()
            logging.debug(
                f"BWCLIServer.start: Created socket pair, server_fd={server_sock.fileno()}"
            )

            # Convert session to string if needed
            session_str = (
                session.decode("utf-8")
                if isinstance(session, bytes)
                else session
            )

            # Session via the environment, not --session: this process lives as
            # long as the daemon does, and /proc/<pid>/cmdline is readable by
            # every user on the machine while /proc/<pid>/environ is not. `bw`
            # treats them identically - its --session handler just assigns
            # process.env.BW_SESSION.
            self.process = Popen(
                [
                    "bw",
                    "serve",
                    "--port",
                    str(BW_SERVE_PORT),
                    "--hostname",
                    f"fd+connected://{server_sock.fileno()}",
                ],
                pass_fds=(server_sock.fileno(),),
                stdout=PIPE,
                stderr=PIPE,
                env=_bw_env(session_str),
            )
            logging.debug(
                f"BWCLIServer.start: Started bw serve process, pid={self.process.pid}"
            )

            # Close server socket in parent process
            server_sock.close()

            # Check if process started successfully
            if self.process.poll() is not None:
                logging.error("bw serve process failed to start")
                return False

            # Wait for bw serve to be ready to accept connections
            # Try multiple times with increasing delays
            max_retries = 5
            for attempt in range(max_retries):
                wait_time = 0.2 * (attempt + 1)  # 0.2s, 0.4s, 0.6s, 0.8s, 1.0s
                logging.debug(
                    f"BWCLIServer.start: Waiting {wait_time}s for bw serve to initialize (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)

                # Check if process is still alive
                if self.process.poll() is not None:
                    # Process died - capture stderr for debugging
                    stderr_output = (
                        self.process.stderr.read().decode("utf-8")
                        if self.process.stderr
                        else "No stderr"
                    )
                    stdout_output = (
                        self.process.stdout.read().decode("utf-8")
                        if self.process.stdout
                        else "No stdout"
                    )
                    logging.error("bw serve process died during initialization")
                    logging.error(f"bw serve stderr: {stderr_output}")
                    logging.error(f"bw serve stdout: {stdout_output}")
                    return False

                # Try a simple request to see if it's ready
                try:
                    conn = BWHTTPConnection(self.client_sock)
                    conn.request("GET", "/status")
                    response = conn.getresponse()
                    response.read()  # Consume the response

                    # If we got here without exception, it's ready
                    logging.debug(
                        f"BWCLIServer.start: bw serve ready after {wait_time}s"
                    )
                    self._initialized = True
                    return True
                except (
                    ConnectionResetError,
                    ConnectionRefusedError,
                    BrokenPipeError,
                ) as e:
                    logging.debug(
                        f"BWCLIServer.start: Not ready yet (attempt {attempt + 1}): {e}"
                    )
                    if attempt == max_retries - 1:
                        logging.error(
                            f"BWCLIServer.start: Failed to connect after {max_retries} attempts"
                        )
                        return False
                    continue

            return False

        except FileNotFoundError:
            logging.error("bw command not found. Is Bitwarden CLI installed?")
            return False
        except Exception as e:
            logging.error(f"Failed to start bw serve: {e}")
            return False

    def stop(self):
        """Stop the bw serve process and clean up resources"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                logging.warning(f"Error stopping bw serve process: {e}")
                try:
                    self.process.kill()
                    self.process.wait()
                except Exception:
                    pass

        if self.client_sock:
            try:
                self.client_sock.close()
            except Exception:
                pass

        self._initialized = False

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop()

    def get_status(self):
        """Check status of vault

        Returns: Dict - {serverUrl: <url>, lastSync: date/time, userEmail: <email>,
                        userId: userId, status: <'locked', 'unlocked' or 'unauthenticated'>}
                 or False on error
        """
        if not self._initialized:
            logging.error("BWCLIServer not initialized, call start() first")
            return False

        successful, data = self.request("GET", "/status")
        if not successful:
            return False

        if not data or "template" not in data:
            return {"status": "unauthenticated", "serverUrl": None}

        return data["template"]

    def unlock(self, password: str) -> tuple[str | bool, str]:
        """Unlock vault

        Args: password - string
        Returns: session (string) or False on error, Error message
        """
        logging.debug("BWCLIServer.unlock: Starting unlock")
        logging.debug(
            f"BWCLIServer.unlock: initialized={self._initialized}, process={self.process is not None}"
        )

        if not password:
            logging.error("No password provided")
            return False, "No password provided"

        logging.debug("BWCLIServer.unlock: Sending POST /unlock request")
        successful, data = self.request(
            "POST", "/unlock", {"password": password}
        )
        logging.debug(
            f"BWCLIServer.unlock: Request completed, successful={successful}"
        )

        if not successful:
            # Unlocking is a local operation, so a failure here is a bad master
            # password or a broken vault cache, not a missing network
            error_msg = (
                data
                if isinstance(data, str)
                else "Failed to unlock. Check the master password and "
                "~/.cache/bwm.log."
            )
            logging.error(f"Unlock error: {error_msg}")
            return False, error_msg

        if "raw" in data:
            logging.debug(
                "BWCLIServer.unlock: Unlock successful, session token received"
            )
            return data["raw"], ""

        logging.error("BWCLIServer.unlock: No session token in response")
        return False, "No session token received"

    def lock(self):
        """Lock vault

        Return: True on success, False with any errors
        """
        successful, data = self.request("POST", "/lock")
        if not successful:
            logging.error(f"Lock error: {data}")
            return False
        return True

    def sync(self):
        """Sync web vault changes to local vault

        Return: True on success, False with any errors
        """
        successful, data = self.request("POST", "/sync")
        if not successful:
            error_msg = data if isinstance(data, str) else "Sync failed"
            logging.error(f"Sync error: {error_msg}")
            return False
        return True

    def get_entries(self, org_name=""):
        """Get all entries, folders, collections and orgs from vault

        Args: org_name - name of organization (currently unused)
        Returns: items (list of Items), folders, collections, orgs
                 or (False, False, False, False) on error
        """
        successful, data = self.request("GET", "/list/object/items")
        if not successful:
            error_msg = data if isinstance(data, str) else "Failed to get items"
            logging.error(f"Get entries error: {error_msg}")
            return False, False, False, False

        items = [Item(i) for i in data["data"]] if "data" in data else []
        folders = self.get_folders()
        collections = self.get_collections(org_name)
        orgs = self.get_orgs()

        if folders is False or collections is False or orgs is False:
            return False, False, False, False

        return items, folders, collections, orgs

    def get_folders(self):
        """Return all folder names.

        Return: Dict of folder dicts {id: dict('object':folder,'id':id,'name':<name>)}
                False on error
        """
        successful, data = self.request("GET", "/list/object/folders")
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to get folders"
            )
            logging.error(f"Get folders error: {error_msg}")
            return False

        if "data" not in data:
            return {}

        return {i["id"]: i for i in data["data"]}

    def get_collections(self, org_id=""):
        """Return all collection names for user.

        Args: org_id - organization id string.
        Return: Dict of collection dicts {id: dict('object':collection,'id':id,...)}
                False on error
        """
        if org_id:
            # FIXED: Changed from set to dict
            successful, data = self.request(
                "GET",
                "/list/object/org-collections",
                params={"organizationId": org_id},
            )
        else:
            successful, data = self.request("GET", "/list/object/collections")

        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to get collections"
            )
            logging.error(f"Get collections error: {error_msg}")
            return False

        if "data" not in data:
            return {}

        return {i["id"]: i for i in data["data"]}

    def get_orgs(self):
        """Return all organizations for the logged in user

        Return: Dict of org dicts {id: dict('object':'organization','id':id,'name':<name>...)}
                False on error
        """
        successful, data = self.request("GET", "/list/object/organizations")
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to get organizations"
            )
            logging.error(f"Get organizations error: {error_msg}")
            return False

        if "data" not in data:
            return {}

        return {i["id"]: i for i in data["data"]}

    def add_entry(self, entry):
        """Add new entry to vault

        Args: entry - dict with entry fields
        Returns: new item dict or False on error
        """
        successful, data = self.request("POST", "/object/item", entry)
        if not successful:
            error_msg = data if isinstance(data, str) else "Failed to add entry"
            logging.error(f"Add entry error: {error_msg}")
            return False

        logging.debug(
            f"Add entry successful, item id: {data.get('id', 'unknown')}"
        )
        return data

    def edit_entry(self, entry):
        """Modify existing vault entry

        Args: entry - entry dict object with 'id' field
        Returns: updated entry object (dict) on success, False on failure
        """
        if "id" not in entry:
            logging.error("Entry missing 'id' field")
            return False

        # Check if item belongs to an organization
        params = {}
        if entry.get("organizationId"):
            params["organizationId"] = entry["organizationId"]

        successful, data = self.request(
            "PUT", f"/object/item/{entry['id']}", entry, params=params
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to edit entry"
            )
            logging.error(f"Edit entry error: {error_msg}")
            return False

        # data is already the item object, not wrapped in another 'data' key
        logging.debug(
            f"Edit entry successful, item id: {data.get('id', 'unknown')}"
        )
        return data

    def delete_entry(self, entry):
        """Delete existing vault entry

        Args: entry - entry dict object with 'id' field
        Returns: entry object (dict) on success, False on failure
        """
        if "id" not in entry:
            logging.error("Entry missing 'id' field")
            return False

        successful, data = self.request("DELETE", f"/object/item/{entry['id']}")
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to delete entry"
            )
            logging.error(f"Delete entry error: {error_msg}")
            return False

        logging.debug(f"Delete entry successful for item {entry['id']}")
        return entry

    def move_entry(self, entry):
        """Move entry to an organization collection

        Args: entry - entry dict object with id, organizationId, and collectionIds
        Returns: updated entry object (dict) on success, False on failure
        """
        if "id" not in entry or "organizationId" not in entry:
            logging.error("Entry missing required fields for move")
            return False

        successful, data = self.request(
            "POST",
            f"/move/{entry['id']}/{entry['organizationId']}",
            entry.get("collectionIds", []),
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to move entry"
            )
            logging.error(f"Move entry error: {error_msg}")
            return False

        return data

    def add_folder(self, folder_name):
        """Add folder

        Args: folder_name - string (name of folder)
        Returns: Folder object or False on error
        """
        body = {"name": folder_name}
        successful, data = self.request("POST", "/object/folder", body)
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to add folder"
            )
            logging.error(f"Add folder error: {error_msg}")
            return False

        return data

    def delete_folder(self, folder):
        """Delete folder

        Args: folder - folder object (dict) with 'id' field
        Returns: folder object (dict) on success, False on failure
        """
        if "id" not in folder:
            logging.error("Folder missing 'id' field")
            return False

        successful, data = self.request(
            "DELETE", f"/object/folder/{folder['id']}"
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to delete folder"
            )
            logging.error(f"Delete folder error: {error_msg}")
            return False

        return folder

    def move_folder(self, folder, newpath):
        """Move or rename folder

        Args: folder - folder dict object with 'id' field
              newpath - string (new name/path)
        Returns: Folder object on success, False on failure
        """
        if "id" not in folder:
            logging.error("Folder missing 'id' field")
            return False

        body = dict(folder)
        body["name"] = newpath

        successful, data = self.request(
            "PUT", f"/object/folder/{folder['id']}", body
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to move folder"
            )
            logging.error(f"Move folder error: {error_msg}")
            return False

        return data

    def add_collection(self, collection_name, org_id):
        """Add collection

        Args: collection_name - string
              org_id - organization id string
        Returns: collection object or False on error
        """
        body = {"name": collection_name, "organizationId": org_id}

        successful, data = self.request(
            "POST",
            "/object/org-collection",
            body,
            params={"organizationId": org_id},
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to add collection"
            )
            logging.error(f"Add collection error: {error_msg}")
            return False

        return data

    def delete_collection(self, collection):
        """Delete collection

        Args: collection - collection object (dict) with 'id' and 'organizationId'
        Returns: collection object (dict) on success, False on failure
        """
        if "id" not in collection or "organizationId" not in collection:
            logging.error("Collection missing required fields")
            return False

        successful, data = self.request(
            "DELETE",
            f"/object/org-collection/{collection['id']}",
            params={"organizationId": collection["organizationId"]},
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to delete collection"
            )
            logging.error(f"Delete collection error: {error_msg}")
            return False

        return collection

    def move_collection(self, collection, newpath):
        """Move or rename collection

        Args: collection - collection object (dict) with 'id' and 'organizationId'
              newpath - string (new name/path)
        Returns: collection object on success, False on failure
        """
        if "id" not in collection or "organizationId" not in collection:
            logging.error("Collection missing required fields")
            return False

        body = dict(collection)
        body["name"] = newpath

        successful, data = self.request(
            "PUT",
            f"/object/org-collection/{collection['id']}",
            body,
            params={"organizationId": collection["organizationId"]},
        )
        if not successful:
            error_msg = (
                data if isinstance(data, str) else "Failed to move collection"
            )
            logging.error(f"Move collection error: {error_msg}")
            return False

        return data

    def request(self, method: str, url: str, body=None, params=None):
        """Make HTTP request to bw serve API

        Args: method - HTTP method (GET, POST, PUT, DELETE)
              url - API endpoint URL
              body - Request body (dict)
              params - Query parameters (dict)

        Returns: tuple (success: bool, data: dict or error message)
        """
        if not self._initialized:
            logging.error(
                "BWCLIServer not initialized, call start() with session first"
            )
            return False, "bw serve not initialized"

        try:
            conn = BWHTTPConnection(self.client_sock)
            encoded_body = None
            headers = {}

            if body:
                encoded_body = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json"
                headers["Content-Length"] = str(len(encoded_body))

            # Add any query parameters (session is handled via BW_SESSION env var)
            if params:
                url = f"{url}?{urlencode(params)}"

            # Debug logging
            logging.debug(f"BW Serve Request: {method} {url}")

            conn.request(method, url, encoded_body, headers)

            response = conn.getresponse()
            response_body = response.read().decode("utf-8")

            # Only the status and size are logged. The body of /unlock and
            # /login is the session token, and of /list/object/items the entire
            # decrypted vault - neither belongs in a file on disk.
            logging.debug(
                f"Response status: {response.status}, "
                f"body bytes={len(response_body)}"
            )

            # bw serve returns plain text (not JSON) for some errors, e.g. a
            # bare "Forbidden" from the Host/Origin guards. Check the status
            # first so those surface as-is instead of a JSON decode error.
            if response.status >= 400:
                logging.error(
                    f"HTTP {response.status} from bw serve for {method} {url}: "
                    f"{response_body[:100]}"
                )
                return False, f"HTTP {response.status}: {response_body[:100]}"

            if not response_body:
                return False, "Empty response from server"

            try:
                json_response = json.loads(response_body)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse JSON response: {e}")
                return False, f"Invalid JSON response: {response_body[:100]}"

            success = json_response.get("success", False)

            if success:
                return True, json_response.get("data", {})
            else:
                error_msg = json_response.get("message", "Unknown error")
                return False, error_msg

        except ConnectionResetError as e:
            logging.error(f"Connection reset: {e}")
            return False, f"Connection reset: {e}"
        except Exception as e:
            logging.error(f"Request failed: {e}")
            return False, f"Request failed: {e}"


# vim: set et ts=4 sw=4 :
