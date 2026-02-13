"""Tests for bwm.bwm module - vault selection, data directories, and CLI args."""

import os
from os.path import exists, join
from unittest.mock import patch, MagicMock

import pytest

from bwm.bwm import Vault, get_vault, set_vault


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

    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_vault_dir_uses_email_subdirectory(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, tmp_path, vault_a
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

    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_migration_moves_old_flat_dir(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, tmp_path, vault_a
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

    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_no_migration_when_other_email_dirs_exist(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, tmp_path, vault_a, vault_b
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

    @patch("bwm.bwm.bwcli.status", return_value={"status": "unauthenticated", "serverUrl": None})
    @patch("bwm.bwm.bwcli.set_server", return_value=True)
    @patch("bwm.bwm.get_passphrase", return_value="pw")
    @patch("bwm.bwm.bwcli.login", return_value=(b"session", ""))
    @patch("bwm.bwm.bwcli.sync", return_value=True)
    @patch("bwm.bwm.BWCLIServer")
    def test_no_migration_when_email_dir_already_exists(
        self, mock_server, mock_sync, mock_login, mock_passphrase,
        mock_set_server, mock_status, tmp_path, vault_a
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
