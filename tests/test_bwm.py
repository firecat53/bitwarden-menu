"""Tests for bwm.bwm module - vault selection, data directories, and CLI args."""

import configparser
import json
import multiprocessing
import os
from os.path import exists, join
from unittest.mock import patch, MagicMock

import pytest

from bwm.bwm import Vault, check_online, dmenu_sync, get_vault, set_vault


@pytest.fixture
def vault_a():
    return Vault("https://vault.bitwarden.com", "alice@example.com", "pw1", "0")


@pytest.fixture
def vault_b():
    return Vault("https://vault.bitwarden.com", "bob@example.com", "pw2", "0")


@pytest.fixture
def vault_c():
    return Vault("https://vault.mydomain.net", "carol@example.com", "pw3", "0")


@pytest.fixture
def mock_config_vaults():
    """Config with two accounts on the same server."""
    import configparser
    conf = configparser.ConfigParser()
    conf.add_section("dmenu")
    conf.set("dmenu", "dmenu_command", "dmenu")
    conf.add_section("dmenu_passphrase")
    conf.add_section("vault")
    conf.set("vault", "server_1", "https://vault.bitwarden.com")
    conf.set("vault", "email_1", "alice@example.com")
    conf.set("vault", "server_2", "https://vault.bitwarden.com")
    conf.set("vault", "email_2", "bob@example.com")
    conf.set("vault", "session_timeout_min", "360")
    conf.set("vault", "autotype_default", "{USERNAME}{TAB}{PASSWORD}{ENTER}")
    return conf


class TestVaultMenuDisplay:
    """Tests for vault selection menu format."""

    @patch("bwm.bwm.set_vault")
    @patch("bwm.bwm.dmenu_select")
    def test_menu_shows_url_and_email(self, mock_select, mock_set, vault_a, vault_b):
        """Menu input should contain 'url - email' for each vault."""
        mock_select.return_value = f"{vault_b.url} - {vault_b.email}"
        mock_set.side_effect = lambda v: v
        vaults = [vault_a, vault_b]

        get_vault(vaults)

        mock_select.assert_called_once()
        inp = mock_select.call_args[1]["inp"]
        assert f"{vault_a.url} - {vault_a.email}" in inp
        assert f"{vault_b.url} - {vault_b.email}" in inp

    @patch("bwm.bwm.set_vault")
    @patch("bwm.bwm.dmenu_select")
    def test_menu_differentiates_same_server_accounts(
        self, mock_select, mock_set, vault_a, vault_b
    ):
        """Same-server vaults should show as separate lines."""
        mock_select.return_value = f"{vault_b.url} - {vault_b.email}"
        mock_set.side_effect = lambda v: v
        vaults = [vault_a, vault_b]

        get_vault(vaults)

        inp = mock_select.call_args[1]["inp"]
        lines = inp.split("\n")
        assert len(lines) == 2
        assert lines[0] != lines[1]


class TestVaultMenuSelection:
    """Tests for vault selection matching logic."""

    @patch("bwm.bwm.set_vault")
    @patch("bwm.bwm.dmenu_select")
    def test_selecting_second_vault_reorders(
        self, mock_select, mock_set, vault_a, vault_b
    ):
        """Selecting the second vault should move it to position 0."""
        mock_select.return_value = f"{vault_b.url} - {vault_b.email}"
        mock_set.side_effect = lambda v: v
        vaults = [vault_a, vault_b]

        result = get_vault(vaults)

        assert result[0] is vault_b

    @patch("bwm.bwm.set_vault")
    @patch("bwm.bwm.dmenu_select")
    def test_selecting_first_vault_with_session_returns_unchanged(
        self, mock_select, mock_set, vault_a, vault_b
    ):
        """Selecting the current active vault (with session) returns vaults as-is."""
        vault_a.session = b"active-session"
        mock_select.return_value = f"{vault_a.url} - {vault_a.email}"
        vaults = [vault_a, vault_b]

        result = get_vault(vaults)

        assert result[0] is vault_a
        mock_set.assert_not_called()

    @patch("bwm.bwm.dmenu_select")
    def test_no_selection_returns_none_without_sessions(
        self, mock_select, vault_a, vault_b
    ):
        """Empty selection with no active sessions returns None."""
        mock_select.return_value = ""
        vaults = [vault_a, vault_b]

        result = get_vault(vaults)

        assert result is None

    @patch("bwm.bwm.set_vault")
    @patch("bwm.bwm.dmenu_select")
    def test_selection_matches_on_both_url_and_email(
        self, mock_select, mock_set, vault_a, vault_b
    ):
        """Selection matching uses both URL and email, not just URL."""
        mock_select.return_value = f"{vault_a.url} - {vault_a.email}"
        mock_set.side_effect = lambda v: v
        vaults = [vault_b, vault_a]  # vault_b is first

        result = get_vault(vaults)

        # vault_a should be moved to front
        assert result[0] is vault_a


class TestVaultCliArgs:
    """Tests for -v and -l CLI argument handling."""

    @patch("bwm.bwm.set_vault")
    def test_vault_cli_selects_matching_vault(self, mock_set, vault_a, vault_c):
        """Using -v with a unique URL selects that vault."""
        mock_set.side_effect = lambda v: v
        vaults = [vault_a, vault_c]

        result = get_vault(vaults, vault="https://vault.mydomain.net")

        assert result[0] is vault_c

    @patch("bwm.bwm.set_vault")
    def test_vault_cli_with_login_selects_correct_account(
        self, mock_set, vault_a, vault_b
    ):
        """-v URL -l email selects the correct same-server account."""
        mock_set.side_effect = lambda v: v
        vaults = [vault_a, vault_b]

        result = get_vault(
            vaults,
            vault="https://vault.bitwarden.com",
            login="bob@example.com",
        )

        assert result[0] is vault_b

    @patch("bwm.bwm.dmenu_err")
    def test_vault_cli_ambiguous_returns_none(
        self, mock_err, vault_a, vault_b
    ):
        """-v URL without -l when multiple accounts match returns None with error."""
        vaults = [vault_a, vault_b]

        result = get_vault(
            vaults, vault="https://vault.bitwarden.com"
        )

        assert result is None
        mock_err.assert_called_once()
        assert "Multiple accounts" in mock_err.call_args[0][0]

    @patch("bwm.bwm.set_vault")
    def test_vault_cli_no_match_creates_new(self, mock_set, vault_a):
        """-v URL with unknown URL creates a new vault entry."""
        mock_set.side_effect = lambda v: v
        vaults = [vault_a]

        result = get_vault(
            vaults,
            vault="https://new.vault.com",
            login="new@example.com",
        )

        assert result[0].url == "https://new.vault.com"
        assert result[0].email == "new@example.com"

    @patch("bwm.bwm.set_vault")
    def test_single_vault_cli_match_no_ambiguity_error(
        self, mock_set, vault_a, vault_c
    ):
        """-v URL with only one match should not error."""
        mock_set.side_effect = lambda v: v
        vaults = [vault_a, vault_c]

        result = get_vault(
            vaults, vault="https://vault.bitwarden.com"
        )

        assert result is not None
        assert result[0] is vault_a


class TestVaultDataDirectory:
    """Tests for data directory path using netloc/email structure."""

    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_vault_dir_uses_email_subdirectory(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, mock_online, tmp_path, vault_a
    ):
        """Data directory should be DATA_HOME/netloc/email."""
        mock_bwserver = MagicMock()
        mock_bwserver.start.return_value = True
        mock_bwserver.unlock.return_value = (b"session", "")
        mock_server.return_value = mock_bwserver

        with patch("bwm.DATA_HOME", str(tmp_path)):
            set_vault([vault_a])

        expected = join(str(tmp_path), "vault.bitwarden.com", "alice@example.com")
        assert os.environ["BITWARDENCLI_APPDATA_DIR"] == expected
        assert exists(expected)


class TestVaultDataMigration:
    """Tests for migrating old flat directory to netloc/email structure."""

    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_migration_moves_old_flat_dir(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, mock_online, tmp_path, vault_a
    ):
        """Old flat netloc directory should be migrated into netloc/email."""
        mock_bwserver = MagicMock()
        mock_bwserver.start.return_value = True
        mock_bwserver.unlock.return_value = (b"session", "")
        mock_server.return_value = mock_bwserver

        # Create old flat directory with a data file
        old_dir = join(str(tmp_path), "vault.bitwarden.com")
        os.makedirs(old_dir)
        with open(join(old_dir, "data.json"), "w") as f:
            f.write('{"test": true}')

        with patch("bwm.DATA_HOME", str(tmp_path)):
            set_vault([vault_a])

        new_dir = join(str(tmp_path), "vault.bitwarden.com", "alice@example.com")
        assert exists(new_dir)
        assert exists(join(new_dir, "data.json"))

    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_no_migration_when_other_email_dirs_exist(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, mock_online, tmp_path, vault_a, vault_b
    ):
        """Should not migrate if another vault already has a subdirectory."""
        mock_bwserver = MagicMock()
        mock_bwserver.start.return_value = True
        mock_bwserver.unlock.return_value = (b"session", "")
        mock_server.return_value = mock_bwserver

        # Create netloc dir with an existing email subdir for vault_b
        netloc_dir = join(str(tmp_path), "vault.bitwarden.com")
        os.makedirs(join(netloc_dir, "bob@example.com"))
        # Also create a file in the netloc dir (shouldn't be migrated)
        with open(join(netloc_dir, "stale.json"), "w") as f:
            f.write('{"old": true}')

        with patch("bwm.DATA_HOME", str(tmp_path)):
            set_vault([vault_a, vault_b])

        alice_dir = join(netloc_dir, "alice@example.com")
        assert exists(alice_dir)
        # The stale file should still be in the netloc dir (no migration happened)
        assert exists(join(netloc_dir, "stale.json"))

    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_no_migration_when_email_dir_already_exists(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, mock_online, tmp_path, vault_a
    ):
        """Should not migrate if the email subdirectory already exists."""
        mock_bwserver = MagicMock()
        mock_bwserver.start.return_value = True
        mock_bwserver.unlock.return_value = (b"session", "")
        mock_server.return_value = mock_bwserver

        # Create the new-style directory structure already in place
        email_dir = join(str(tmp_path), "vault.bitwarden.com", "alice@example.com")
        os.makedirs(email_dir)
        with open(join(email_dir, "data.json"), "w") as f:
            f.write('{"existing": true}')

        with patch("bwm.DATA_HOME", str(tmp_path)):
            set_vault([vault_a])

        # Existing data should be untouched
        assert exists(join(email_dir, "data.json"))
        with open(join(email_dir, "data.json")) as f:
            assert "existing" in f.read()


class TestOffline:
    """Tests for offline operation."""

    @patch("bwm.bwm.dmenu_err")
    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    def test_check_online_when_reachable(
        self, mock_online, mock_err, vault_a
    ):
        """check_online passes silently when the server is reachable."""
        assert check_online(vault_a) is True
        mock_online.assert_called_once_with(vault_a.url)
        mock_err.assert_not_called()

    @patch("bwm.bwm.dmenu_err")
    @patch("bwm.bwm.bwcli.is_online", return_value=False)
    def test_check_online_when_unreachable(
        self, mock_online, mock_err, vault_a
    ):
        """check_online reports an error when the server is unreachable."""
        assert check_online(vault_a) is False
        assert "Offline" in mock_err.call_args[0][0]

    @patch("bwm.bwm.dmenu_err")
    @patch("bwm.bwm.bwcli.sync")
    @patch("bwm.bwm.bwcli.is_online", return_value=False)
    def test_sync_skipped_when_offline(
        self, mock_online, mock_sync, mock_err, vault_a
    ):
        """Sync should not be attempted while offline."""
        assert dmenu_sync(vault_a) is False
        mock_sync.assert_not_called()

    @patch("bwm.bwm.dmenu_err")
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    def test_sync_runs_when_online(
        self, mock_online, mock_sync, mock_err, vault_a
    ):
        """Sync should run and report success while online."""
        assert dmenu_sync(vault_a) is True
        mock_sync.assert_called_once()
        mock_err.assert_not_called()

    @patch("bwm.bwm.dmenu_err")
    @patch("bwm.bwm.get_passphrase")
    @patch("bwm.bwm.bwcli.login")
    @patch("bwm.bwm.bwcli.is_online", return_value=False)
    @patch(
        "bwm.bwm.bwcli.status",
        return_value={"status": "unauthenticated", "serverUrl": None},
    )
    def test_login_refused_when_offline(
        self, mock_status, mock_online, mock_login, mock_passphrase, mock_err,
        tmp_path, vault_a
    ):
        """An unauthenticated vault should fail fast offline, without prompting."""
        with patch("bwm.DATA_HOME", str(tmp_path)):
            result = set_vault([vault_a])

        assert result is None
        assert vault_a.session is False
        # No password/2FA prompt and no doomed login attempt
        mock_passphrase.assert_not_called()
        mock_login.assert_not_called()
        assert "Offline" in mock_err.call_args[0][0]

    @patch("bwm.bwm.BWCLIServer")
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.unlock", return_value=(b"session", None))
    @patch("bwm.bwm.bwcli.is_online", return_value=False)
    @patch("bwm.bwm.bwcli.status", return_value={"status": "locked"})
    def test_unlock_allowed_when_offline(
        self, mock_status, mock_online, mock_unlock, mock_passphrase,
        mock_server, tmp_path, vault_a
    ):
        """A locked vault should still unlock offline - it is a local operation."""
        mock_bwserver = MagicMock()
        mock_bwserver.start.return_value = True
        mock_bwserver.unlock.return_value = (b"session", "")
        mock_server.return_value = mock_bwserver

        with patch("bwm.DATA_HOME", str(tmp_path)):
            result = set_vault([vault_a])

        assert result == [vault_a]
        assert vault_a.session == b"session"
        mock_unlock.assert_called_once()
        # Unlocking is local, so it must not cost a reachability check
        mock_online.assert_not_called()


class TestVaultFromConfig:
    """Tests for loading vaults from config."""

    @patch("bwm.bwm.set_vault")
    @patch("bwm.bwm.dmenu_select")
    def test_loads_same_server_vaults_from_config(
        self, mock_select, mock_set, mock_config_vaults
    ):
        """Config with two same-server accounts should create two Vault objects."""
        mock_select.return_value = ""
        import bwm
        with patch.object(bwm, "CONF", mock_config_vaults):
            result = get_vault()

        # Returns None because no selection was made
        assert result is None
        # But dmenu_select was called with both vaults
        mock_select.assert_called_once()
        inp = mock_select.call_args[1]["inp"]
        assert "alice@example.com" in inp
        assert "bob@example.com" in inp


class TestCliMode:
    """Non-interactive mode: prompts and errors use the terminal."""

    def test_get_passphrase_uses_getpass(self, monkeypatch):
        """The master password is read from the terminal, not a launcher."""
        import bwm
        from bwm.bwm import get_passphrase

        monkeypatch.setattr(bwm, "CLI", True)
        with patch("bwm.bwm.getpass", return_value="hunter2") as gp, \
                patch("bwm.bwm.dmenu_select") as sel:
            assert get_passphrase() == "hunter2"
        sel.assert_not_called()
        assert "Password" in gp.call_args[0][0]

    def test_get_passphrase_prompts_name_the_secret(self, monkeypatch):
        """2FA and client_secret prompts go to the terminal too.

        These are the prompts the login flow needs, so routing this one
        function is what makes a CLI login possible.

        """
        import bwm
        from bwm.bwm import get_passphrase

        monkeypatch.setattr(bwm, "CLI", True)
        for secret in ("2FA Code", "client_secret"):
            with patch("bwm.bwm.getpass", return_value="x") as gp:
                assert get_passphrase(secret) == "x"
            assert secret in gp.call_args[0][0]

    def test_get_passphrase_no_tty(self, monkeypatch, capsys):
        """No terminal to prompt on is a message, not a traceback."""
        import bwm
        from bwm.bwm import get_passphrase

        monkeypatch.setattr(bwm, "CLI", True)
        with patch("bwm.bwm.getpass", side_effect=EOFError):
            assert get_passphrase() == ""
        assert "No terminal available" in capsys.readouterr().err

    def test_get_passphrase_gui_unaffected(self, monkeypatch):
        """With CLI off, the launcher is still used."""
        import bwm
        from bwm.bwm import get_passphrase

        monkeypatch.setattr(bwm, "CLI", False)
        with patch.object(bwm, "CONF", configparser.ConfigParser()), \
                patch("bwm.bwm.dmenu_select", return_value="from-dmenu") as sel:
            assert get_passphrase() == "from-dmenu"
        sel.assert_called_once()

    def test_get_vault_multiple_needs_v(self, monkeypatch, mock_config_vaults):
        """Vault selection can't be shown, so -v is required."""
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch.object(bwm, "CONF", mock_config_vaults), \
                patch("bwm.bwm.dmenu_select") as sel, \
                patch("bwm.bwm.dmenu_err") as err:
            assert get_vault() is None
        sel.assert_not_called()
        assert "-v" in err.call_args[0][0]

    def test_get_vault_no_config_no_wizard(self, monkeypatch):
        """The interactive first run wizard is never launched in CLI mode."""
        import bwm

        empty = configparser.ConfigParser()
        empty.add_section("vault")
        monkeypatch.setattr(bwm, "CLI", True)
        with patch.object(bwm, "CONF", empty), \
                patch("bwm.bwm.get_initial_vault") as wizard, \
                patch("bwm.bwm.dmenu_err") as err:
            assert get_vault() is None
        wizard.assert_not_called()
        assert "No vault configured" in err.call_args[0][0]


class TestDmenuRunnerShow:
    """The daemon answers --show without ever touching a launcher."""

    def _runner(self, vaults):
        """A DmenuRunner with __init__ bypassed (it opens a real vault)."""
        from bwm.bwm import DmenuRunner

        runner = DmenuRunner.__new__(DmenuRunner)
        runner.server = MagicMock()
        runner.unlocked = multiprocessing.Array("c", 8192)
        runner.vaults = vaults
        runner.vault = vaults[0]
        return runner

    def _vault(self, entries, folders, url="https://v.example.com",
               email="a@example.com", session=b"sess"):
        from bwm.bwm import Vault

        vault = Vault(url, email, "", "", session=session)
        vault.entries = entries
        vault.folders = folders
        return vault

    def test_sends_result_for_active_vault(self, entries, sample_folders):
        runner = self._runner([self._vault(entries, sample_folders)])
        with patch("bwm.bwm.dmenu_select") as sel, patch("bwm.bwm.dmenu_err") as err:
            runner.show_entry(show="Test Login", field=["username"])
        runner.server.send_result.assert_called_once_with(None, (True, "testuser"))
        sel.assert_not_called()
        err.assert_not_called()

    def test_locked_vault_is_unlocked_with_the_sent_password(
        self, entries, sample_folders
    ):
        """The client already prompted for it, so use it rather than refusing.

        Matches what the GUI's 'Switch vaults' does with the same password.

        """
        runner = self._runner([self._vault(entries, sample_folders)])
        target = self._vault(
            entries, sample_folders, url="https://other.example.com"
        )
        with patch("bwm.bwm.get_vault", return_value=[target]) as gv:
            runner.show_entry(
                show="Test Login",
                vault="https://other.example.com",
                password="master",
                field=["password"],
            )
        assert gv.call_args.kwargs["password"] == "master"
        runner.server.send_result.assert_called_once_with(None, (True, "testpass123"))

    def test_failed_unlock_reports_without_a_gui_prompt(
        self, entries, sample_folders
    ):
        """A wrong password must not pop a dialog at a terminal user."""
        runner = self._runner([self._vault(entries, sample_folders)])
        with patch("bwm.bwm.get_vault", return_value=None), \
                patch("bwm.bwm.dmenu_select") as sel:
            runner.show_entry(show="x", vault="https://other.example.com")
        sel.assert_not_called()
        ok, sent = runner.server.send_result.call_args[0][1]
        assert ok is False and "Could not unlock" in sent

    def test_gui_focus_is_restored_after_unlock(
        self, entries, sample_folders
    ):
        """A CLI query shouldn't move the GUI's menu to another vault."""
        active = self._vault(entries, sample_folders)
        runner = self._runner([active])
        target = self._vault(
            entries, sample_folders, url="https://other.example.com"
        )
        with patch("bwm.bwm.get_vault", return_value=[target, active]):
            runner.show_entry(
                show="Test Login",
                vault="https://other.example.com",
                password="master",
            )
        assert runner.vault is active
        assert runner.vaults[0] is active

    def test_cli_mode_restored_after_unlock(self, entries, sample_folders):
        """CLI mode is forced on only for the unlock attempt."""
        import bwm

        runner = self._runner([self._vault(entries, sample_folders)])
        seen = {}
        def record(*_a, **_k):
            seen["cli"] = bwm.CLI
            return None
        with patch.object(bwm, "CLI", False), \
                patch("bwm.bwm.get_vault", side_effect=record):
            runner.show_entry(show="x", vault="https://other.example.com")
            assert seen["cli"] is True
            assert bwm.CLI is False

    def test_selects_the_named_vault(self, entries, sample_folders):
        other = self._vault(
            entries, sample_folders, url="https://other.example.com"
        )
        runner = self._runner([self._vault([], {}), other])
        runner.show_entry(
            show="Test Login",
            vault="https://other.example.com",
            field=["password"],
        )
        runner.server.send_result.assert_called_once_with(None, (True, "testpass123"))

    def test_publish_unlocked_only_lists_sessions(self, sample_folders):
        runner = self._runner(
            [
                self._vault([], sample_folders),
                self._vault(
                    [], sample_folders, url="https://locked.example.com",
                    session=b"",
                ),
            ]
        )
        runner._publish_unlocked()
        assert json.loads(runner.unlocked.value) == [
            ["https://v.example.com", "a@example.com"]
        ]


class TestCliVaultMessages:
    """CLI errors have to name the piece that's actually missing."""

    def _empty_conf(self):
        conf = configparser.ConfigParser()
        conf.add_section("vault")
        return conf

    def test_vault_given_without_login(self, monkeypatch):
        """`-v <url>` alone still needs an email; don't claim -v is missing."""
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch.object(bwm, "CONF", self._empty_conf()), \
                patch("bwm.bwm.get_initial_vault") as wizard, \
                patch("bwm.bwm.dmenu_err") as err:
            # argparse supplies login=None when -l is absent
            assert get_vault(vault="https://v.example.com", login=None) is None
        wizard.assert_not_called()
        msg = err.call_args[0][0]
        assert "No login email" in msg and "https://v.example.com" in msg

    def test_nothing_given(self, monkeypatch):
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch.object(bwm, "CONF", self._empty_conf()), \
                patch("bwm.bwm.dmenu_err") as err:
            assert get_vault(vault=None, login=None) is None
        assert "No vault configured" in err.call_args[0][0]

    def test_vault_and_login_proceed_to_set_vault(self, monkeypatch):
        """With both, an unconfigured vault is built and unlocked normally."""
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch.object(bwm, "CONF", self._empty_conf()), \
                patch("bwm.bwm.set_vault", side_effect=lambda v: v) as sv:
            vaults = get_vault(
                vault="https://v.example.com", login="me@example.com"
            )
        sv.assert_called_once()
        assert vaults[0].url == "https://v.example.com"
        assert vaults[0].email == "me@example.com"

    def test_password_kwarg_prefills_vault(self, monkeypatch):
        """The client's prompt result reaches set_vault without a GUI prompt."""
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch.object(bwm, "CONF", self._empty_conf()), \
                patch("bwm.bwm.set_vault", side_effect=lambda v: v):
            vaults = get_vault(
                vault="https://v.example.com",
                login="me@example.com",
                password="from-client",
            )
        assert vaults[0].passw == "from-client"


class TestDaemonLeavesCliMode:
    """A daemon started by --show must not stay in CLI mode.

    bwm.CLI is a global set per invocation. The DmenuRunner child inherits it
    across the fork, but once detached it has no terminal to prompt on and
    serves GUI requests - where CLI mode suppresses menus instead.

    """

    def _runner(self, background):
        from bwm.bwm import DmenuRunner

        runner = DmenuRunner.__new__(DmenuRunner)
        runner.server = MagicMock()
        runner.server.kill_flag.is_set.return_value = True  # exit the loop
        runner.background = background
        runner.unlocked = None
        runner.vaults = []
        runner.vault = MagicMock()
        return runner

    def test_backgrounded_daemon_clears_cli(self, monkeypatch):
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch("bwm.detach_from_terminal"):
            self._runner(background=True).run()
        assert bwm.CLI is False

    def test_foreground_daemon_keeps_terminal_prompts(self, monkeypatch):
        """--foreground still has the terminal attached."""
        import bwm

        monkeypatch.setattr(bwm, "CLI", True)
        with patch("bwm.detach_from_terminal"):
            self._runner(background=False).run()
        assert bwm.CLI is True

    def test_switch_vaults_shows_the_menu_in_gui_mode(self, mock_config_vaults):
        """The symptom: CLI mode skipped vault selection entirely."""
        import bwm
        from bwm.bwm import get_vault

        vaults = [
            Vault("https://vault.bitwarden.com", "alice@example.com", "", "",
                  session=b"tok"),
            Vault("https://vault.bitwarden.com", "bob@example.com", "", ""),
        ]
        with patch.object(bwm, "CLI", False), \
                patch.object(bwm, "CONF", mock_config_vaults), \
                patch("bwm.bwm.set_vault", side_effect=lambda v: v), \
                patch("bwm.bwm.dmenu_select",
                      return_value="https://vault.bitwarden.com - bob@example.com") as sel:
            result = get_vault(list(vaults))
        sel.assert_called_once()
        assert result[0].email == "bob@example.com"


class TestSwitchVaultMenu:
    """The menu has to say which vaults are already unlocked.

    Switching to an unlocked vault is instant, switching to a locked one costs
    a master password prompt and an unlock, so the menu marks the unlocked ones
    with a '*' and puts them on top where the launcher preselects them.

    """

    def _vaults(self, *specs):
        return [
            Vault("https://v.example.com", email, "", "",
                  session=b"tok" if unlocked else b"")
            for email, unlocked in specs
        ]

    def _menu(self, vaults, mock_config_vaults, sel_return=""):
        import bwm
        from bwm.bwm import get_vault

        with patch.object(bwm, "CLI", False), \
                patch.object(bwm, "CONF", mock_config_vaults), \
                patch("bwm.bwm.set_vault", side_effect=lambda v: v), \
                patch("bwm.bwm.dmenu_select", return_value=sel_return) as sel:
            result = get_vault(vaults)
        return result, sel.call_args[1]["inp"].split("\n")

    def test_unlocked_vaults_are_starred(self, mock_config_vaults):
        vaults = self._vaults(("a@x.com", True), ("b@x.com", False))
        _, lines = self._menu(vaults, mock_config_vaults)
        assert [i[0] for i in lines] == ["*", " "]

    def test_other_unlocked_vaults_come_first(self, mock_config_vaults):
        """Active is 'a', so 'c' - the other unlocked one - leads."""
        vaults = self._vaults(
            ("a@x.com", True), ("b@x.com", False), ("c@x.com", True)
        )
        _, lines = self._menu(vaults, mock_config_vaults)
        assert [i.rsplit(" - ", 1)[1] for i in lines] == [
            "c@x.com", "a@x.com", "b@x.com"
        ]

    def test_active_drops_below_every_other_unlocked_vault(
        self, mock_config_vaults
    ):
        vaults = self._vaults(
            ("a@x.com", True), ("b@x.com", True),
            ("c@x.com", True), ("d@x.com", True),
        )
        _, lines = self._menu(vaults, mock_config_vaults)
        assert lines[-1].rsplit(" - ", 1)[1] == "a@x.com"

    def test_a_starred_selection_still_switches(self, mock_config_vaults):
        """The marker is display only - it must not break the match."""
        vaults = self._vaults(("a@x.com", True), ("b@x.com", True))
        result, _ = self._menu(
            vaults, mock_config_vaults,
            sel_return="* https://v.example.com - b@x.com",
        )
        assert result[0].email == "b@x.com"

    def test_a_launcher_that_eats_the_padding_still_matches(
        self, mock_config_vaults
    ):
        vaults = self._vaults(("a@x.com", True), ("b@x.com", False))
        result, _ = self._menu(
            vaults, mock_config_vaults,
            sel_return="https://v.example.com - b@x.com",
        )
        assert result[0].email == "b@x.com"

    def test_reselecting_the_active_vault_changes_nothing(
        self, mock_config_vaults
    ):
        vaults = self._vaults(("a@x.com", True), ("b@x.com", False))
        result, _ = self._menu(
            vaults, mock_config_vaults,
            sel_return="* https://v.example.com - a@x.com",
        )
        assert result[0].email == "a@x.com"


class TestSwitchToUnlockedVault:
    """Switching to an already unlocked vault must not unlock it again.

    `bw status` only reports 'unlocked' when it is given a session, so calling
    it bare made every switch look locked and pay for a full unlock - 8-10
    seconds against a real server.

    """

    def _vault(self):
        return Vault(
            "https://v.example.com", "me@x.com", "pw", "", session=b"tok"
        )

    def test_status_is_asked_about_the_session_we_hold(self, tmp_path):
        import bwm

        vault = self._vault()
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "unlocked", "serverUrl": "x"}) as st, \
                patch("bwm.bwm.bwcli.unlock") as unlock, \
                patch("bwm.bwm.BWCLIServer"):
            set_vault([vault])
        st.assert_called_once_with(b"tok")
        unlock.assert_not_called()

    def test_existing_session_is_kept(self, tmp_path):
        """`bw status` doesn't echo the token back, so don't clobber it."""
        import bwm

        vault = self._vault()
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "unlocked", "serverUrl": "x"}), \
                patch("bwm.bwm.bwcli.unlock"), \
                patch("bwm.bwm.BWCLIServer"):
            set_vault([vault])
        assert vault.session == b"tok"

    def test_locked_vault_still_unlocks(self, tmp_path):
        """A vault with no session, or a stale one, unlocks as before."""
        import bwm

        vault = Vault("https://v.example.com", "me@x.com", "pw", "")
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "locked", "serverUrl": "x"}), \
                patch("bwm.bwm.bwcli.unlock",
                      return_value=(b"fresh", None)) as unlock, \
                patch("bwm.bwm.BWCLIServer") as srv:
            srv.return_value.start.return_value = False  # fall back to the CLI
            set_vault([vault])
        unlock.assert_called_once_with("pw")
        assert vault.session == b"fresh"


class TestSessionRotation:
    """Unlocking again through `bw serve` invalidates the CLI's token.

    set_vault() unlocks twice - once via the CLI for a token, then again
    through the serve API - and Bitwarden rotates the session on each unlock.
    Keeping the first token means every later `bw --session <token>` is
    rejected, `bw status` reports 'locked', and switching to an already
    unlocked vault pays for a whole new unlock.

    """

    def _serve(self, rotated="rotated-token"):
        srv = MagicMock()
        srv.start.return_value = True
        srv.unlock.return_value = (rotated, None)
        return srv

    def test_rotated_token_replaces_the_cli_one(self, tmp_path):
        import bwm

        vault = Vault("https://v.example.com", "me@x.com", "pw", "")
        srv = self._serve()
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "locked", "serverUrl": "x"}), \
                patch("bwm.bwm.bwcli.unlock", return_value=(b"cli-token", None)), \
                patch("bwm.bwm.BWCLIServer", return_value=srv):
            set_vault([vault])
        assert vault.session == b"rotated-token"

    def test_failed_serve_unlock_keeps_the_cli_token(self, tmp_path):
        """Falling back to the CLI means the CLI token is still the live one."""
        import bwm

        vault = Vault("https://v.example.com", "me@x.com", "pw", "")
        srv = self._serve()
        srv.unlock.return_value = (False, "nope")
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "locked", "serverUrl": "x"}), \
                patch("bwm.bwm.bwcli.unlock", return_value=(b"cli-token", None)), \
                patch("bwm.bwm.BWCLIServer", return_value=srv):
            set_vault([vault])
        assert vault.session == b"cli-token"

    def test_switching_back_reuses_the_live_token(self, tmp_path):
        """The whole point: no second unlock when switching to it again."""
        import bwm

        vault = Vault("https://v.example.com", "me@x.com", "pw", "")
        srv = self._serve()
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "locked", "serverUrl": "x"}), \
                patch("bwm.bwm.bwcli.unlock", return_value=(b"cli-token", None)), \
                patch("bwm.bwm.BWCLIServer", return_value=srv):
            set_vault([vault])
        assert vault.session == b"rotated-token"
        # Now switch away and back. The running server answers the status
        # check, so no `bw` process is spawned and nothing is unlocked again.
        srv.get_status.return_value = {"status": "unlocked", "serverUrl": "x"}
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status") as st, \
                patch("bwm.bwm.bwcli.unlock") as unlock:
            set_vault([vault])
        srv.get_status.assert_called_once()
        st.assert_not_called()
        unlock.assert_not_called()


class TestStatusViaServer:
    """Spawning `bw` costs a Node startup - seconds. Use the running server.

    Measured on a dev machine: `bw --version` 1.8s, `bw status` 3.5s. A vault
    switch made exactly one such call, which was most of its cost.

    """

    def _vault(self, srv=None):
        return Vault(
            "https://v.example.com", "me@x.com", "pw", "",
            session=b"tok", bwcliserver=srv,
        )

    def test_running_server_answers_instead_of_the_cli(self, tmp_path):
        import bwm

        srv = MagicMock()
        srv.get_status.return_value = {"status": "unlocked", "serverUrl": "x"}
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status") as cli_status, \
                patch("bwm.bwm.bwcli.unlock") as unlock:
            set_vault([self._vault(srv)])
        srv.get_status.assert_called_once()
        cli_status.assert_not_called()   # no Node process spawned
        unlock.assert_not_called()

    def test_falls_back_to_the_cli_without_a_server(self, tmp_path):
        import bwm

        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "unlocked", "serverUrl": "x"}) as cli_status, \
                patch("bwm.bwm.bwcli.unlock"), \
                patch("bwm.bwm.BWCLIServer"):
            set_vault([self._vault()])
        cli_status.assert_called_once_with(b"tok")

    def test_falls_back_when_the_server_errors(self, tmp_path):
        """get_status() returns False if the server is wedged."""
        import bwm

        srv = MagicMock()
        srv.get_status.return_value = False
        with patch.object(bwm, "DATA_HOME", str(tmp_path)), \
                patch("bwm.bwm.bwcli.status",
                      return_value={"status": "unlocked", "serverUrl": "x"}) as cli_status, \
                patch("bwm.bwm.bwcli.unlock"):
            set_vault([self._vault(srv)])
        cli_status.assert_called_once_with(b"tok")


class TestSyncAndLockPreferTheRunningServer:
    """Every `bw` invocation costs ~1.5s of Node startup before it does work.

    When a bw serve is already up, syncing and locking through it is an HTTP
    round trip instead.

    """

    def _vault(self, server=None):
        v = Vault("https://vault.example.com", "a@example.com", "pw", "")
        v.session = b"session"
        v.bwcliserver = server
        return v

    def test_sync_vault_uses_the_server_when_up(self):
        from bwm.bwm import sync_vault

        srv = MagicMock()
        srv.sync.return_value = True
        with patch("bwm.bwm.bwcli.sync") as cli_sync:
            assert sync_vault(self._vault(srv)) is True
        srv.sync.assert_called_once()
        cli_sync.assert_not_called()

    def test_sync_vault_falls_back_to_the_cli(self):
        from bwm.bwm import sync_vault

        with patch("bwm.bwm.bwcli.sync", return_value=True) as cli_sync:
            assert sync_vault(self._vault(None)) is True
        cli_sync.assert_called_once_with(b"session")

    def test_dmenu_sync_goes_through_the_server(self):
        srv = MagicMock()
        srv.sync.return_value = True
        with patch("bwm.bwm.check_online", return_value=True), \
                patch("bwm.bwm.bwcli.sync") as cli_sync:
            assert dmenu_sync(self._vault(srv)) is True
        srv.sync.assert_called_once()
        cli_sync.assert_not_called()

    def test_lock_flag_uses_the_server(self):
        """`bwm -k` sent to a running daemon must not spawn a `bw` process.

        The menu's "Lock vault" option already went through lock_vault(); the
        --lock flag called bwcli.lock() directly.

        """
        from bwm.bwm import lock_vault

        srv = MagicMock()
        srv.lock.return_value = True
        with patch("bwm.bwm.bwcli.lock") as cli_lock:
            assert lock_vault(self._vault(srv)) is True
        srv.lock.assert_called_once()
        cli_lock.assert_not_called()

    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    @patch(
        "bwm.bwm.bwcli.status",
        return_value={"status": "unauthenticated", "serverUrl": None},
    )
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_post_login_sync_goes_through_the_server(
        self, mock_server, mock_cli_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, mock_online, tmp_path, vault_a
    ):
        """After login, serve comes up first and the sync goes through it.

        `bw serve` only needs an authenticated vault, not an unlocked one, so
        it can start straight after login - which means the post-login sync
        need not pay for another `bw` process.

        """
        srv = MagicMock()
        srv.start.return_value = True
        srv.unlock.return_value = (b"session2", "")
        srv.sync.return_value = True
        mock_server.return_value = srv

        with patch("bwm.DATA_HOME", str(tmp_path)):
            set_vault([vault_a])

        srv.start.assert_called_once()
        srv.sync.assert_called_once()
        mock_cli_sync.assert_not_called()

    @patch("bwm.bwm.bwcli.is_online", return_value=True)
    @patch(
        "bwm.bwm.bwcli.status",
        return_value={"status": "unauthenticated", "serverUrl": None},
    )
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_post_login_sync_falls_back_when_serve_fails(
        self, mock_server, mock_cli_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, mock_online, tmp_path, vault_a
    ):
        """If bw serve won't start, the sync still happens via the CLI."""
        srv = MagicMock()
        srv.start.return_value = False
        mock_server.return_value = srv

        with patch("bwm.DATA_HOME", str(tmp_path)):
            set_vault([vault_a])

        srv.sync.assert_not_called()
        mock_cli_sync.assert_called_once()

    def test_lock_flag_dispatches_through_lock_vault(self):
        """Drive DmenuRunner.run() one iteration with --lock.

        Asserting on lock_vault() alone would not have caught this: the bug
        was that the --lock branch never called it.

        """
        from bwm.bwm import DmenuRunner

        runner = DmenuRunner.__new__(DmenuRunner)
        runner.background = False
        runner.vaults = [self._vault(MagicMock())]
        runner.vault = runner.vaults[0]
        runner.server = MagicMock()
        # top of loop False, end of loop True, so exactly one pass runs
        runner.server.kill_flag.is_set.side_effect = [False, True]
        runner.server.cache_time_expired.is_set.return_value = False
        runner.server.args_flag.is_set.return_value = True
        runner.server.get_args.return_value = {"lock": True}

        with patch.object(DmenuRunner, "_set_timer"), \
                patch("bwm.bwm.lock_vault") as lock_vault, \
                patch("bwm.bwm.bwcli.lock") as cli_lock:
            runner.run()

        lock_vault.assert_called_once_with(runner.vault)
        cli_lock.assert_not_called()
