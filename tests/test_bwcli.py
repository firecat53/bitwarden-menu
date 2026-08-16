"""Tests for Bitwarden CLI wrapper module."""

import json
import os
import socket
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

import pytest

from bwm.bwcli import (
    Item,
    _log_err,
    is_online,
    status,
    login,
    unlock,
    lock,
    logout,
    sync,
    get_entries,
    get_folders,
    get_collections,
    get_orgs,
)


class TestItem:
    """Tests for the Item class."""

    def test_item_empty(self):
        """Test Item with empty dict adds autotype field."""
        item = Item({})
        assert "fields" in item
        assert len(item["fields"]) == 1
        assert item["fields"][0]["name"] == "autotype"
        assert item["fields"][0]["value"] == ""
        assert item["fields"][0]["type"] == 0

    def test_item_with_fields(self):
        """Test Item preserves existing fields."""
        data = {
            "name": "Test",
            "fields": [{"name": "custom", "value": "val", "type": 0}],
        }
        item = Item(data)
        assert len(item["fields"]) == 2
        assert item["fields"][0]["name"] == "custom"
        assert item["fields"][1]["name"] == "autotype"

    def test_item_with_existing_autotype(self):
        """Test Item doesn't duplicate autotype field."""
        data = {
            "fields": [{"name": "autotype", "value": "{PASSWORD}", "type": 0}]
        }
        item = Item(data)
        assert len(item["fields"]) == 1
        assert item["fields"][0]["value"] == "{PASSWORD}"

    def test_item_preserves_all_data(self):
        """Test Item preserves all entry data."""
        data = {
            "id": "test-id",
            "name": "Test Entry",
            "type": 1,
            "login": {"username": "user", "password": "pass"},
            "fields": [],
        }
        item = Item(data)
        assert item["id"] == "test-id"
        assert item["name"] == "Test Entry"
        assert item["type"] == 1
        assert item["login"]["username"] == "user"

    def test_item_dict_operations(self):
        """Test Item supports standard dict operations."""
        item = Item({"name": "test"})
        item["custom_key"] = "custom_value"
        assert item["custom_key"] == "custom_value"
        assert "name" in item
        assert item.get("nonexistent", "default") == "default"


class TestStatus:
    """Tests for vault status checking."""

    @patch("bwm.bwcli.run")
    def test_status_unlocked(self, mock_run):
        """Test status returns correct data when unlocked."""
        # Note: stdout is split by '\n' and last element is taken, so no trailing newline
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"],
            returncode=0,
            stdout=b'{"status": "unlocked", "userEmail": "test@example.com"}',
        )
        result = status(b"session-key")
        assert result["status"] == "unlocked"
        assert result["userEmail"] == "test@example.com"

    @patch("bwm.bwcli.run")
    def test_status_locked(self, mock_run):
        """Test status returns correct data when locked."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"],
            returncode=0,
            stdout=b'{"status": "locked"}',
        )
        result = status()
        assert result["status"] == "locked"

    @patch("bwm.bwcli.run")
    def test_status_unauthenticated(self, mock_run):
        """Test status returns correct data when unauthenticated."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"],
            returncode=0,
            stdout=b'{"status": "unauthenticated"}',
        )
        result = status()
        assert result["status"] == "unauthenticated"

    @patch("bwm.bwcli.run")
    def test_status_error(self, mock_run):
        """Test status returns empty dict on error."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"], returncode=1, stdout=b""
        )
        result = status()
        assert result == {}

    @patch("bwm.bwcli.run")
    def test_status_trailing_newline(self, mock_run):
        """Test status parses output with a trailing newline."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"],
            returncode=0,
            stdout=b'{"status": "locked"}\n\n',
        )
        assert status()["status"] == "locked"

    @patch("bwm.bwcli.run")
    def test_status_offline_nonzero_exit(self, mock_run):
        """Test status parses valid output when the CLI exits non-zero.

        Offline, the CLI can fail to fetch the server config and exit 1 while
        still printing the status JSON (bitwarden/clients#18373).
        """
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"],
            returncode=1,
            stdout=b'{"status": "locked"}\n',
            stderr=b"FetchError: getaddrinfo ENOTFOUND vault.example.com",
        )
        assert status()["status"] == "locked"

    @patch("bwm.bwcli.run")
    def test_status_unparseable(self, mock_run):
        """Test status returns empty dict when stdout is not JSON."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "", "status"],
            returncode=1,
            stdout=b"FetchError: getaddrinfo ENOTFOUND vault.example.com",
        )
        assert status() == {}


class TestIsOnline:
    """Tests for the vault server reachability check."""

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_reachable(self, mock_conn):
        """Test a reachable server returns True."""
        assert is_online("https://vault.bitwarden.com") is True
        assert mock_conn.call_args[0][0] == ("vault.bitwarden.com", 443)

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_default_http_port(self, mock_conn):
        """Test http URLs default to port 80."""
        assert is_online("http://vault.example.com") is True
        assert mock_conn.call_args[0][0] == ("vault.example.com", 80)

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_explicit_port(self, mock_conn):
        """Test an explicit port in the URL is used."""
        assert is_online("https://vault.example.com:8443") is True
        assert mock_conn.call_args[0][0] == ("vault.example.com", 8443)

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_bare_hostname(self, mock_conn):
        """Test a URL with no scheme is still parsed."""
        assert is_online("vault.example.com") is True
        assert mock_conn.call_args[0][0] == ("vault.example.com", 443)

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_unreachable(self, mock_conn):
        """Test an unreachable server returns False."""
        mock_conn.side_effect = OSError("Network is unreachable")
        assert is_online("https://vault.bitwarden.com") is False

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_timeout(self, mock_conn):
        """Test a connection timeout returns False."""
        mock_conn.side_effect = TimeoutError("timed out")
        assert is_online("https://vault.bitwarden.com") is False

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_no_hostname(self, mock_conn):
        """Test a URL with no hostname returns False without connecting."""
        for url in ("", "///", "https://"):
            assert is_online(url) is False
        mock_conn.assert_not_called()

    @patch("bwm.bwcli.socket.create_connection")
    def test_is_online_unresolvable_host(self, mock_conn):
        """Test a hostname that will not resolve returns False.

        urlsplit will happily treat junk as a hostname, so the DNS failure has
        to be handled rather than avoided.
        """
        mock_conn.side_effect = socket.gaierror("Name or service not known")
        assert is_online("not a url") is False
        assert mock_conn.call_args[0][0] == ("not a url", 443)


class TestLogin:
    """Tests for vault login."""

    @patch("bwm.bwcli.run")
    def test_login_success(self, mock_run):
        """Test successful login returns session."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "login", "--raw", "email", "password"],
            returncode=0,
            stdout=b"session-key-12345",
            stderr=b"",
        )
        session, error = login("email@example.com", "password123")
        assert session == b"session-key-12345"
        assert error is None

    @patch("bwm.bwcli.run")
    def test_login_failure(self, mock_run):
        """Test failed login returns False and error."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "login", "--raw", "email", "password"],
            returncode=1,
            stdout=b"",
            stderr=b"Invalid password",
        )
        session, error = login("email@example.com", "wrongpass")
        assert session is False
        assert error == b"Invalid password"

    @patch("bwm.bwcli.run")
    def test_login_succeeds_with_stderr_warnings(self, mock_run):
        """Test login succeeds when the CLI writes warnings to stderr.

        The CLI logs to stderr and can exit non-zero on an otherwise successful
        command when it cannot reach the server (bitwarden/clients#18373), so
        only an empty stdout counts as a failure.
        """
        mock_run.return_value = CompletedProcess(
            args=["bw", "login", "--raw", "email", "password"],
            returncode=1,
            stdout=b"session-key-12345",
            stderr=b"warning: unable to fetch server config",
        )
        session, error = login("email@example.com", "password123")
        assert session == b"session-key-12345"
        assert error is None

    @patch("bwm.bwcli.run")
    def test_login_with_2fa(self, mock_run):
        """Test login with two-factor authentication."""
        mock_run.return_value = CompletedProcess(
            args=[
                "bw",
                "login",
                "--raw",
                "email",
                "password",
                "--method",
                "0",
                "--code",
                "123456",
            ],
            returncode=0,
            stdout=b"session-key-2fa",
            stderr=b"",
        )
        session, error = login(
            "email@example.com", "password", method="0", code="123456"
        )
        assert session == b"session-key-2fa"
        assert error is None


class TestUnlock:
    """Tests for vault unlocking."""

    @patch("bwm.bwcli.run")
    def test_unlock_success(self, mock_run):
        """Test successful unlock returns session."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "unlock", "--raw", "password"],
            returncode=0,
            stdout=b"session-key-unlocked",
        )
        session, error = unlock("correct-password")
        assert session == b"session-key-unlocked"
        assert error is None

    @patch("bwm.bwcli.run")
    def test_unlock_failure(self, mock_run):
        """Test failed unlock returns False."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "unlock", "--raw", "password"],
            returncode=1,
            stdout=b"",
            stderr=b"Invalid password",
        )
        session, error = unlock("wrong-password")
        assert session is False
        assert error == b"Invalid password"

    @patch("bwm.bwcli.run")
    def test_unlock_succeeds_offline(self, mock_run):
        """Test unlock succeeds when the CLI exits non-zero while offline.

        Unlocking verifies the master password against the local vault cache,
        so it works without a network connection even though the CLI may fail
        to fetch the server config.
        """
        mock_run.return_value = CompletedProcess(
            args=["bw", "unlock", "--raw", "password"],
            returncode=1,
            stdout=b"session-key-12345",
            stderr=b"FetchError: getaddrinfo ENOTFOUND vault.example.com",
        )
        session, error = unlock("password123")
        assert session == b"session-key-12345"
        assert error is None

    def test_unlock_no_password(self):
        """Test unlock with no password returns error."""
        session, error = unlock("")
        assert session is False
        assert error == "No password provided"

    def test_unlock_none_password(self):
        """Test unlock with None password returns error."""
        session, error = unlock(None)
        assert session is False


class TestLock:
    """Tests for vault locking."""

    @patch("bwm.bwcli.run")
    def test_lock_success(self, mock_run):
        """Test successful lock returns True."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "lock"], returncode=0, stdout=b"Vault locked"
        )
        result = lock()
        assert result is True

    @patch("bwm.bwcli.run")
    def test_lock_failure(self, mock_run):
        """Test failed lock returns False."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "lock"], returncode=1, stdout=b""
        )
        result = lock()
        assert result is False


class TestLogout:
    """Tests for vault logout."""

    @patch("bwm.bwcli.run")
    def test_logout_success(self, mock_run):
        """Test successful logout returns True."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "logout"],
            returncode=0,
            stdout=b"",
            stderr=b"Logged out",
        )
        result = logout()
        assert result is True

    @patch("bwm.bwcli.run")
    def test_logout_not_logged_in(self, mock_run):
        """Test logout when not logged in returns False."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "logout"], returncode=1, stdout=b"", stderr=b""
        )
        result = logout()
        assert result is False


class TestSync:
    """Tests for vault sync."""

    @patch("bwm.bwcli.run")
    def test_sync_success(self, mock_run):
        """Test successful sync returns True."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "sync"],
            returncode=0,
            stdout=b"Syncing complete",
        )
        result = sync(b"session-key")
        assert result is True

    @patch("bwm.bwcli.run")
    def test_sync_failure(self, mock_run):
        """Test failed sync returns False."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "sync"], returncode=1, stdout=b""
        )
        result = sync(b"session-key")
        assert result is False


class TestGetFolders:
    """Tests for folder retrieval."""

    @patch("bwm.bwcli.run")
    def test_get_folders_success(self, mock_run):
        """Test successful folder retrieval."""
        folders = [
            {"id": "folder-1", "name": "Personal"},
            {"id": "folder-2", "name": "Work"},
        ]
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "list", "folders"],
            returncode=0,
            stdout=json.dumps(folders).encode(),
        )
        result = get_folders(b"session-key")
        assert "folder-1" in result
        assert result["folder-1"]["name"] == "Personal"
        assert "folder-2" in result
        assert result["folder-2"]["name"] == "Work"

    @patch("bwm.bwcli.run")
    def test_get_folders_empty(self, mock_run):
        """Test folder retrieval when no folders exist."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "list", "folders"],
            returncode=0,
            stdout=b"[]",
        )
        result = get_folders(b"session-key")
        assert result == {}

    @patch("bwm.bwcli.run")
    def test_get_folders_failure(self, mock_run):
        """Test failed folder retrieval returns False."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "list", "folders"],
            returncode=1,
            stdout=b"",
        )
        result = get_folders(b"session-key")
        assert result is False


class TestGetCollections:
    """Tests for collection retrieval."""

    @patch("bwm.bwcli.run")
    def test_get_collections_success(self, mock_run):
        """Test successful collection retrieval."""
        collections = [
            {"id": "coll-1", "name": "Team", "organizationId": "org-1"},
            {"id": "coll-2", "name": "Shared", "organizationId": "org-1"},
        ]
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "list", "collections"],
            returncode=0,
            stdout=json.dumps(collections).encode(),
        )
        result = get_collections(b"session-key")
        assert "coll-1" in result
        assert result["coll-1"]["name"] == "Team"

    @patch("bwm.bwcli.run")
    def test_get_collections_by_org(self, mock_run):
        """Test collection retrieval by organization ID."""
        collections = [
            {"id": "coll-1", "name": "Team", "organizationId": "org-1"}
        ]
        mock_run.return_value = CompletedProcess(
            args=[
                "bw",
                "--session",
                "key",
                "list",
                "collections",
                "--organizationid",
                "org-1",
            ],
            returncode=0,
            stdout=json.dumps(collections).encode(),
        )
        result = get_collections(b"session-key", org_id="org-1")
        assert len(result) == 1


class TestGetOrgs:
    """Tests for organization retrieval."""

    @patch("bwm.bwcli.run")
    def test_get_orgs_success(self, mock_run):
        """Test successful organization retrieval."""
        orgs = [
            {"id": "org-1", "name": "My Organization", "object": "organization"}
        ]
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "list", "organizations"],
            returncode=0,
            stdout=json.dumps(orgs).encode(),
        )
        result = get_orgs(b"session-key")
        assert "org-1" in result
        assert result["org-1"]["name"] == "My Organization"

    @patch("bwm.bwcli.run")
    def test_get_orgs_empty(self, mock_run):
        """Test organization retrieval when no orgs exist."""
        mock_run.return_value = CompletedProcess(
            args=["bw", "--session", "key", "list", "organizations"],
            returncode=0,
            stdout=b"[]",
        )
        result = get_orgs(b"session-key")
        assert result == {}


class TestSessionTokenIsClean:
    """`bw <cmd> --raw` ends its output with a newline.

    Keeping it makes every later `bw --session <token>` reject the session as
    invalid, so `bw status` reports 'locked' and bwm unlocks all over again -
    8-10 seconds each time a vault is switched to.

    """

    def test_unlock_strips_the_newline(self):
        from bwm.bwcli import unlock

        with patch(
            "bwm.bwcli.run",
            return_value=CompletedProcess([], 0, stdout=b"tok123==\n", stderr=b""),
        ):
            session, err = unlock("pw")
        assert session == b"tok123=="
        assert err is None

    def test_login_strips_the_newline(self):
        from bwm.bwcli import login

        with patch(
            "bwm.bwcli.run",
            return_value=CompletedProcess([], 0, stdout=b"tok456==\n", stderr=b""),
        ):
            session, err = login("me@x.com", "pw")
        assert session == b"tok456=="
        assert err is None

    def test_token_round_trips_into_status(self):
        """The token unlock returns must be usable as-is by status()."""
        from bwm.bwcli import status, unlock

        with patch(
            "bwm.bwcli.run",
            return_value=CompletedProcess([], 0, stdout=b"tok789==\n", stderr=b""),
        ):
            session, _ = unlock("pw")
        with patch("bwm.bwcli.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                [], 0, stdout=b'{"status": "unlocked"}', stderr=b""
            )
            status(session)
        # The token travels in the environment, not on the command line
        assert mock_run.call_args[0][0] == ["bw", "status"]
        assert mock_run.call_args[1]["env"]["BW_SESSION"] == "tok789=="

    def test_empty_stdout_is_still_a_failure(self):
        """Stripping must not turn a failure into a success."""
        from bwm.bwcli import unlock

        with patch(
            "bwm.bwcli.run",
            return_value=CompletedProcess([], 1, stdout=b"", stderr=b"bad password"),
        ):
            session, err = unlock("pw")
        assert session is False
        assert err == b"bad password"


class TestLogErr:
    """Tests that failed `bw` calls never write secrets to the log file.

    The log lives on disk, so argv (which holds the master password for
    `bw login`/`bw unlock` and the session token everywhere else) and stdout
    (the decrypted vault for `bw list items`) must never reach it.

    """

    @pytest.mark.parametrize(
        "args,secrets",
        [
            (["bw", "unlock", "--raw", "MasterPw123"], ["MasterPw123"]),
            (
                [
                    "bw", "login", "--raw", "me@example.com", "MasterPw123",
                    "--method", "1", "--code", "987654",
                ],
                ["me@example.com", "MasterPw123", "987654"],
            ),
            (
                ["bw", "--session", b"SessionToken1234", "list", "items"],
                ["SessionToken1234"],
            ),
            (
                [
                    "bw", "create", "--session", b"SessionToken1234", "item",
                    b"eyJwYXNzd29yZCI6ICJzM2NyZXQifQ==",
                ],
                ["SessionToken1234", "eyJwYXNzd29yZCI"],
            ),
            (
                [
                    "bw", "delete", "--session", b"SessionToken1234",
                    "--organizationid", b"org-id-1", "org-collection",
                    "coll-id-1",
                ],
                ["SessionToken1234", "org-id-1", "coll-id-1"],
            ),
        ],
    )
    def test_log_err_redacts_secrets(self, args, secrets, caplog):
        """Test that no secret-bearing argv element is logged."""
        res = CompletedProcess(
            args=args, returncode=1, stdout=b"", stderr=b"boom"
        )
        _log_err(res)
        assert all(secret not in caplog.text for secret in secrets)
        assert "<redacted>" in caplog.text
        assert "boom" in caplog.text

    def test_log_err_keeps_subcommand(self, caplog):
        """Test that the safe part of the command survives redaction."""
        res = CompletedProcess(
            args=["bw", "--session", b"tok", "list", "items"],
            returncode=1,
            stdout=b"",
            stderr=b"",
        )
        _log_err(res)
        assert "bw --session <redacted> list items" in caplog.text

    def test_get_entries_does_not_log_vault(self, caplog):
        """Test that a failed `bw list items` never logs the vault contents."""
        import logging

        caplog.set_level(logging.DEBUG)
        vault = json.dumps([{"login": {"password": "PlaintextPw"}}]).encode()
        with patch("bwm.bwcli.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                args=["bw", "--session", b"tok", "list", "items"],
                returncode=1,
                stdout=vault,
                stderr=b"error",
            )
            result = get_entries(b"tok")
        assert result is False
        assert "PlaintextPw" not in caplog.text
        assert "tok" not in caplog.text


class TestSecretsStayOutOfArgv:
    """Session tokens and the master password must never reach the argv.

    /proc/<pid>/cmdline is world readable; /proc/<pid>/environ is not. `bw`
    treats the two as equivalent - its --session handler assigns
    process.env.BW_SESSION, and --passwordenv reads process.env[name] - so
    moving them costs nothing.

    """

    SESSION = b"S3ss10nT0ken=="
    PASSWORD = "MasterPw123"

    def _calls(self, fn, *args, stdout=b"[]", **kwargs):
        """Run fn with bwcli.run patched, returning the (argv, kwargs) used."""
        with patch("bwm.bwcli.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                [], 0, stdout=stdout, stderr=b""
            )
            fn(*args, **kwargs)
        return [(c[0][0], c[1]) for c in mock_run.call_args_list]

    @pytest.mark.parametrize(
        "name",
        [
            "status",
            "get_orgs",
            "get_entries",
            "sync",
            "get_folders",
            "get_collections",
        ],
    )
    def test_session_commands_use_the_environment(self, name):
        """Test that read commands pass the token via BW_SESSION."""
        import bwm.bwcli as bwcli_mod

        fn = getattr(bwcli_mod, name)
        stdout = b'{"status": "locked"}' if name == "status" else b"[]"
        for argv, kwargs in self._calls(fn, self.SESSION, stdout=stdout):
            assert self.SESSION.decode() not in " ".join(str(i) for i in argv)
            assert "--session" not in argv
            assert kwargs["env"]["BW_SESSION"] == self.SESSION.decode()

    @pytest.mark.parametrize(
        "fn_name,args",
        [
            ("add_entry", ({"name": "x"},)),
            ("delete_entry", ({"id": "abc"},)),
            ("add_folder", ("f",)),
            ("delete_folder", ({"id": "abc"},)),
            ("move_folder", ({"id": "abc"}, "new")),
            ("add_collection", ("c", "org1")),
            ("delete_collection", ({"id": "a", "organizationId": "o"},)),
            ("move_collection", ({"id": "a", "organizationId": "o"}, "new")),
        ],
    )
    def test_write_commands_use_the_environment(self, fn_name, args):
        """Test that write commands pass the token via BW_SESSION."""
        import bwm.bwcli as bwcli_mod

        fn = getattr(bwcli_mod, fn_name)
        with patch("bwm.bwcli.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                [], 0, stdout=b"{}", stderr=b""
            )
            fn(*args, self.SESSION)
        for call in mock_run.call_args_list:
            argv = call[0][0]
            assert "--session" not in argv
            assert self.SESSION.decode() not in " ".join(str(i) for i in argv)

    def test_unlock_password_is_not_in_argv(self):
        """Test that unlock points bw at an env var instead of the password."""
        from bwm.bwcli import unlock, BW_PASSWORD_ENV

        with patch("bwm.bwcli.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                [], 0, stdout=b"tok\n", stderr=b""
            )
            unlock(self.PASSWORD)
        argv, kwargs = mock_run.call_args[0][0], mock_run.call_args[1]
        assert self.PASSWORD not in argv
        assert "--passwordenv" in argv
        assert kwargs["env"][BW_PASSWORD_ENV] == self.PASSWORD

    def test_login_password_is_not_in_argv(self):
        """Test the same for login, including the 2FA variant."""
        from bwm.bwcli import login, BW_PASSWORD_ENV

        for extra in ({}, {"method": "1", "code": "123456"}):
            with patch("bwm.bwcli.run") as mock_run:
                mock_run.return_value = CompletedProcess(
                    [], 0, stdout=b"tok\n", stderr=b""
                )
                login("me@example.com", self.PASSWORD, **extra)
            argv = mock_run.call_args[0][0]
            kwargs = mock_run.call_args[1]
            assert self.PASSWORD not in argv
            assert "--passwordenv" in argv
            assert kwargs["env"][BW_PASSWORD_ENV] == self.PASSWORD
            if extra:
                assert "--code" in argv and "123456" in argv

    def test_pty_login_password_is_not_in_argv(self):
        """Test that the interactive 2FA login also uses execvpe."""
        from bwm.bwcli import login_pty_start, BW_PASSWORD_ENV

        with patch("bwm.bwcli.pty.fork", return_value=(0, 5)):
            with patch("bwm.bwcli.os.execvpe") as execvpe:
                with patch("bwm.bwcli.os._exit", side_effect=RuntimeError):
                    with pytest.raises(RuntimeError):
                        login_pty_start("me@example.com", self.PASSWORD)
        argv, env = execvpe.call_args[0][1], execvpe.call_args[0][2]
        assert self.PASSWORD not in argv
        assert "--passwordenv" in argv
        assert env[BW_PASSWORD_ENV] == self.PASSWORD

    def test_env_does_not_leak_into_the_parent(self):
        """Test that the secrets go to the child only, never os.environ.

        bwm spawns dmenu, $EDITOR, the clipboard tool and password_cmd; none of
        them should inherit the master password.

        """
        from bwm.bwcli import unlock, BW_PASSWORD_ENV

        with patch("bwm.bwcli.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                [], 0, stdout=b"tok\n", stderr=b""
            )
            unlock(self.PASSWORD)
        assert BW_PASSWORD_ENV not in os.environ

    def test_falsy_session_leaves_inherited_one_alone(self):
        """Test that no session means bw falls back to an inherited BW_SESSION."""
        from bwm.bwcli import _bw_env

        with patch.dict(os.environ, {"BW_SESSION": "inherited"}):
            assert _bw_env(b"")["BW_SESSION"] == "inherited"
            assert _bw_env(b"mine")["BW_SESSION"] == "mine"
