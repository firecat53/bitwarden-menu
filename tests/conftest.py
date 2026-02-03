"""Pytest fixtures for bitwarden-menu tests."""

import configparser
import pytest


@pytest.fixture
def sample_login_entry():
    """Sample login entry for testing."""
    return {
        'id': 'test-id-123',
        'organizationId': None,
        'folderId': 'folder-id-1',
        'type': 1,
        'name': 'Test Login',
        'notes': 'Test notes',
        'favorite': False,
        'fields': [{'name': 'autotype', 'value': '{USERNAME}{TAB}{PASSWORD}{ENTER}', 'type': 0}],
        'login': {
            'username': 'testuser',
            'password': 'testpass123',
            'totp': 'otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&period=30&digits=6&issuer=Test',
            'uris': [{'uri': 'https://example.com', 'match': None}]
        },
        'collectionIds': [],
        'card': None,
        'identity': None,
        'secureNote': None,
    }


@pytest.fixture
def sample_card_entry():
    """Sample card entry for testing."""
    return {
        'id': 'card-id-456',
        'organizationId': None,
        'folderId': 'folder-id-1',
        'type': 3,
        'name': 'Test Card',
        'notes': None,
        'favorite': False,
        'fields': [{'name': 'autotype', 'value': '', 'type': 0}],
        'login': None,
        'collectionIds': [],
        'card': {
            'cardholderName': 'John Doe',
            'brand': 'Visa',
            'number': '4111111111111111',
            'expMonth': '12',
            'expYear': '2025',
            'code': '123'
        },
        'identity': None,
        'secureNote': None,
    }


@pytest.fixture
def sample_identity_entry():
    """Sample identity entry for testing."""
    return {
        'id': 'identity-id-789',
        'organizationId': None,
        'folderId': None,
        'type': 4,
        'name': 'Test Identity',
        'notes': 'Identity notes',
        'favorite': False,
        'fields': [{'name': 'autotype', 'value': '', 'type': 0}],
        'login': None,
        'collectionIds': [],
        'card': None,
        'identity': {
            'title': 'Mr',
            'firstName': 'John',
            'middleName': 'Q',
            'lastName': 'Public',
            'address1': '123 Main St',
            'address2': 'Apt 4',
            'address3': '',
            'city': 'Anytown',
            'state': 'CA',
            'postalCode': '12345',
            'country': 'US',
            'company': 'ACME Inc',
            'email': 'john@example.com',
            'phone': '555-1234',
            'ssn': '123-45-6789',
            'username': 'johnpublic',
            'passportNumber': 'AB123456',
            'licenseNumber': 'D1234567'
        },
        'secureNote': None,
    }


@pytest.fixture
def sample_folders():
    """Sample folders dict for testing."""
    return {
        None: {'id': None, 'name': 'No Folder'},
        'folder-id-1': {'id': 'folder-id-1', 'name': 'Personal'},
        'folder-id-2': {'id': 'folder-id-2', 'name': 'Work'},
        'folder-id-3': {'id': 'folder-id-3', 'name': 'Work/Projects'},
    }


@pytest.fixture
def sample_collections():
    """Sample collections dict for testing."""
    return {
        'coll-id-1': {
            'id': 'coll-id-1',
            'name': 'Team Collection',
            'organizationId': 'org-id-1',
            'externalId': None
        },
        'coll-id-2': {
            'id': 'coll-id-2',
            'name': 'Shared',
            'organizationId': 'org-id-1',
            'externalId': None
        },
    }


@pytest.fixture
def sample_orgs():
    """Sample organizations dict for testing."""
    return {
        'org-id-1': {
            'id': 'org-id-1',
            'name': 'My Organization',
            'object': 'organization'
        },
    }


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    conf = configparser.ConfigParser()
    conf.add_section('dmenu')
    conf.set('dmenu', 'dmenu_command', 'dmenu')
    conf.add_section('dmenu_passphrase')
    conf.set('dmenu_passphrase', 'obscure', 'True')
    conf.set('dmenu_passphrase', 'obscure_color', '#222222')
    conf.add_section('vault')
    conf.set('vault', 'session_timeout_min', '360')
    conf.set('vault', 'autotype_default', '{USERNAME}{TAB}{PASSWORD}{ENTER}')
    return conf
