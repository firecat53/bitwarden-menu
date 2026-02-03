"""Tests for Bitwarden CLI wrapper module."""

import json
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

import pytest

from bwm.bwcli import (
    Item,
    status,
    login,
    unlock,
    lock,
    logout,
    sync,
    get_folders,
    get_collections,
    get_orgs,
)


class TestItem:
    """Tests for the Item class."""

    def test_item_empty(self):
        """Test Item with empty dict adds autotype field."""
        item = Item({})
        assert 'fields' in item
        assert len(item['fields']) == 1
        assert item['fields'][0]['name'] == 'autotype'
        assert item['fields'][0]['value'] == ''
        assert item['fields'][0]['type'] == 0

    def test_item_with_fields(self):
        """Test Item preserves existing fields."""
        data = {
            'name': 'Test',
            'fields': [{'name': 'custom', 'value': 'val', 'type': 0}]
        }
        item = Item(data)
        assert len(item['fields']) == 2
        assert item['fields'][0]['name'] == 'custom'
        assert item['fields'][1]['name'] == 'autotype'

    def test_item_with_existing_autotype(self):
        """Test Item doesn't duplicate autotype field."""
        data = {
            'fields': [{'name': 'autotype', 'value': '{PASSWORD}', 'type': 0}]
        }
        item = Item(data)
        assert len(item['fields']) == 1
        assert item['fields'][0]['value'] == '{PASSWORD}'

    def test_item_preserves_all_data(self):
        """Test Item preserves all entry data."""
        data = {
            'id': 'test-id',
            'name': 'Test Entry',
            'type': 1,
            'login': {'username': 'user', 'password': 'pass'},
            'fields': []
        }
        item = Item(data)
        assert item['id'] == 'test-id'
        assert item['name'] == 'Test Entry'
        assert item['type'] == 1
        assert item['login']['username'] == 'user'

    def test_item_dict_operations(self):
        """Test Item supports standard dict operations."""
        item = Item({'name': 'test'})
        item['custom_key'] = 'custom_value'
        assert item['custom_key'] == 'custom_value'
        assert 'name' in item
        assert item.get('nonexistent', 'default') == 'default'


class TestStatus:
    """Tests for vault status checking."""

    @patch('bwm.bwcli.run')
    def test_status_unlocked(self, mock_run):
        """Test status returns correct data when unlocked."""
        # Note: stdout is split by '\n' and last element is taken, so no trailing newline
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', '', 'status'],
            returncode=0,
            stdout=b'{"status": "unlocked", "userEmail": "test@example.com"}'
        )
        result = status(b'session-key')
        assert result['status'] == 'unlocked'
        assert result['userEmail'] == 'test@example.com'

    @patch('bwm.bwcli.run')
    def test_status_locked(self, mock_run):
        """Test status returns correct data when locked."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', '', 'status'],
            returncode=0,
            stdout=b'{"status": "locked"}'
        )
        result = status()
        assert result['status'] == 'locked'

    @patch('bwm.bwcli.run')
    def test_status_unauthenticated(self, mock_run):
        """Test status returns correct data when unauthenticated."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', '', 'status'],
            returncode=0,
            stdout=b'{"status": "unauthenticated"}'
        )
        result = status()
        assert result['status'] == 'unauthenticated'

    @patch('bwm.bwcli.run')
    def test_status_error(self, mock_run):
        """Test status returns empty dict on error."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', '', 'status'],
            returncode=1,
            stdout=b''
        )
        result = status()
        assert result == {}


class TestLogin:
    """Tests for vault login."""

    @patch('bwm.bwcli.run')
    def test_login_success(self, mock_run):
        """Test successful login returns session."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'login', '--raw', 'email', 'password'],
            returncode=0,
            stdout=b'session-key-12345',
            stderr=b''
        )
        session, error = login('email@example.com', 'password123')
        assert session == b'session-key-12345'
        assert error is None

    @patch('bwm.bwcli.run')
    def test_login_failure(self, mock_run):
        """Test failed login returns False and error."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'login', '--raw', 'email', 'password'],
            returncode=1,
            stdout=b'',
            stderr=b'Invalid password'
        )
        session, error = login('email@example.com', 'wrongpass')
        assert session is False
        assert error == b'Invalid password'

    @patch('bwm.bwcli.run')
    def test_login_with_2fa(self, mock_run):
        """Test login with two-factor authentication."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'login', '--raw', 'email', 'password', '--method', '0', '--code', '123456'],
            returncode=0,
            stdout=b'session-key-2fa',
            stderr=b''
        )
        session, error = login('email@example.com', 'password', method='0', code='123456')
        assert session == b'session-key-2fa'
        assert error is None


class TestUnlock:
    """Tests for vault unlocking."""

    @patch('bwm.bwcli.run')
    def test_unlock_success(self, mock_run):
        """Test successful unlock returns session."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'unlock', '--raw', 'password'],
            returncode=0,
            stdout=b'session-key-unlocked'
        )
        session, error = unlock('correct-password')
        assert session == b'session-key-unlocked'
        assert error is None

    @patch('bwm.bwcli.run')
    def test_unlock_failure(self, mock_run):
        """Test failed unlock returns False."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'unlock', '--raw', 'password'],
            returncode=1,
            stdout=b'',
            stderr=b'Invalid password'
        )
        session, error = unlock('wrong-password')
        assert session is False
        assert error == b'Invalid password'

    def test_unlock_no_password(self):
        """Test unlock with no password returns error."""
        session, error = unlock('')
        assert session is False
        assert error == "No password provided"

    def test_unlock_none_password(self):
        """Test unlock with None password returns error."""
        session, error = unlock(None)
        assert session is False


class TestLock:
    """Tests for vault locking."""

    @patch('bwm.bwcli.run')
    def test_lock_success(self, mock_run):
        """Test successful lock returns True."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'lock'],
            returncode=0,
            stdout=b'Vault locked'
        )
        result = lock()
        assert result is True

    @patch('bwm.bwcli.run')
    def test_lock_failure(self, mock_run):
        """Test failed lock returns False."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'lock'],
            returncode=1,
            stdout=b''
        )
        result = lock()
        assert result is False


class TestLogout:
    """Tests for vault logout."""

    @patch('bwm.bwcli.run')
    def test_logout_success(self, mock_run):
        """Test successful logout returns True."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'logout'],
            returncode=0,
            stdout=b'',
            stderr=b'Logged out'
        )
        result = logout()
        assert result is True

    @patch('bwm.bwcli.run')
    def test_logout_not_logged_in(self, mock_run):
        """Test logout when not logged in returns False."""
        mock_run.return_value = CompletedProcess(
            args=['bw', 'logout'],
            returncode=1,
            stdout=b'',
            stderr=b''
        )
        result = logout()
        assert result is False


class TestSync:
    """Tests for vault sync."""

    @patch('bwm.bwcli.run')
    def test_sync_success(self, mock_run):
        """Test successful sync returns True."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'sync'],
            returncode=0,
            stdout=b'Syncing complete'
        )
        result = sync(b'session-key')
        assert result is True

    @patch('bwm.bwcli.run')
    def test_sync_failure(self, mock_run):
        """Test failed sync returns False."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'sync'],
            returncode=1,
            stdout=b''
        )
        result = sync(b'session-key')
        assert result is False


class TestGetFolders:
    """Tests for folder retrieval."""

    @patch('bwm.bwcli.run')
    def test_get_folders_success(self, mock_run):
        """Test successful folder retrieval."""
        folders = [
            {'id': 'folder-1', 'name': 'Personal'},
            {'id': 'folder-2', 'name': 'Work'}
        ]
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'folders'],
            returncode=0,
            stdout=json.dumps(folders).encode()
        )
        result = get_folders(b'session-key')
        assert 'folder-1' in result
        assert result['folder-1']['name'] == 'Personal'
        assert 'folder-2' in result
        assert result['folder-2']['name'] == 'Work'

    @patch('bwm.bwcli.run')
    def test_get_folders_empty(self, mock_run):
        """Test folder retrieval when no folders exist."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'folders'],
            returncode=0,
            stdout=b'[]'
        )
        result = get_folders(b'session-key')
        assert result == {}

    @patch('bwm.bwcli.run')
    def test_get_folders_failure(self, mock_run):
        """Test failed folder retrieval returns False."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'folders'],
            returncode=1,
            stdout=b''
        )
        result = get_folders(b'session-key')
        assert result is False


class TestGetCollections:
    """Tests for collection retrieval."""

    @patch('bwm.bwcli.run')
    def test_get_collections_success(self, mock_run):
        """Test successful collection retrieval."""
        collections = [
            {'id': 'coll-1', 'name': 'Team', 'organizationId': 'org-1'},
            {'id': 'coll-2', 'name': 'Shared', 'organizationId': 'org-1'}
        ]
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'collections'],
            returncode=0,
            stdout=json.dumps(collections).encode()
        )
        result = get_collections(b'session-key')
        assert 'coll-1' in result
        assert result['coll-1']['name'] == 'Team'

    @patch('bwm.bwcli.run')
    def test_get_collections_by_org(self, mock_run):
        """Test collection retrieval by organization ID."""
        collections = [
            {'id': 'coll-1', 'name': 'Team', 'organizationId': 'org-1'}
        ]
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'collections', '--organizationid', 'org-1'],
            returncode=0,
            stdout=json.dumps(collections).encode()
        )
        result = get_collections(b'session-key', org_id='org-1')
        assert len(result) == 1


class TestGetOrgs:
    """Tests for organization retrieval."""

    @patch('bwm.bwcli.run')
    def test_get_orgs_success(self, mock_run):
        """Test successful organization retrieval."""
        orgs = [
            {'id': 'org-1', 'name': 'My Organization', 'object': 'organization'}
        ]
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'organizations'],
            returncode=0,
            stdout=json.dumps(orgs).encode()
        )
        result = get_orgs(b'session-key')
        assert 'org-1' in result
        assert result['org-1']['name'] == 'My Organization'

    @patch('bwm.bwcli.run')
    def test_get_orgs_empty(self, mock_run):
        """Test organization retrieval when no orgs exist."""
        mock_run.return_value = CompletedProcess(
            args=['bw', '--session', 'key', 'list', 'organizations'],
            returncode=0,
            stdout=b'[]'
        )
        result = get_orgs(b'session-key')
        assert result == {}
