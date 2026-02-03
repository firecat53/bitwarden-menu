"""Tests for multiprocessing server module."""

import multiprocessing
import socket
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile

import pytest


class TestFindFreePort:
    """Tests for finding free ports."""

    def test_find_free_port_returns_int(self):
        """Test that find_free_port returns an integer."""
        from bwm.__main__ import find_free_port

        port = find_free_port()
        assert isinstance(port, int)

    def test_find_free_port_in_valid_range(self):
        """Test that port is in valid range."""
        from bwm.__main__ import find_free_port

        port = find_free_port()
        assert 1024 <= port <= 65535

    def test_find_free_port_is_available(self):
        """Test that returned port is actually available."""
        from bwm.__main__ import find_free_port, port_in_use

        port = find_free_port()
        assert port_in_use(port) is False


class TestPortInUse:
    """Tests for port availability checking."""

    def test_port_not_in_use(self):
        """Test detection of unused port."""
        from bwm.__main__ import port_in_use, find_free_port

        port = find_free_port()
        assert port_in_use(port) is False

    def test_port_in_use(self):
        """Test detection of used port."""
        from bwm.__main__ import port_in_use

        # Bind to a port temporarily
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.listen(1)
            assert port_in_use(port) is True


class TestRandomStr:
    """Tests for random string generation."""

    def test_random_str_length(self):
        """Test that random string has correct length."""
        from bwm.__main__ import random_str

        result = random_str()
        assert len(result) == 15

    def test_random_str_lowercase_only(self):
        """Test that random string contains only lowercase letters."""
        from bwm.__main__ import random_str

        result = random_str()
        assert result.isalpha()
        assert result.islower()

    def test_random_str_uniqueness(self):
        """Test that multiple calls produce different strings."""
        from bwm.__main__ import random_str

        strings = {random_str() for _ in range(10)}
        # Should have multiple unique strings
        assert len(strings) > 1


class TestGetAuth:
    """Tests for authentication file handling."""

    @patch("bwm.__main__.exists")
    @patch("bwm.__main__.find_free_port")
    @patch("bwm.__main__.random_str")
    @patch("os.open")
    @patch("builtins.open", new_callable=mock_open)
    def test_get_auth_creates_new_file(
        self, mock_file, mock_os_open, mock_rand, mock_port, mock_exists
    ):
        """Test auth file creation when it doesn't exist."""
        import bwm

        mock_exists.return_value = False
        mock_port.return_value = 12345
        mock_rand.return_value = "testauthkey1234"
        mock_os_open.return_value = 3

        # Mock the configparser read to return our values
        with patch.object(bwm.configparser.ConfigParser, "read"):
            with patch.object(bwm.configparser.ConfigParser, "get") as mock_get:
                mock_get.side_effect = lambda section, key: {
                    "port": "12345",
                    "authkey": "testauthkey1234",
                }[key]
                from bwm.__main__ import get_auth

                port, authkey = get_auth()

        assert port == 12345
        assert authkey == b"testauthkey1234"

    @patch("bwm.__main__.exists")
    def test_get_auth_reads_existing_file(self, mock_exists):
        """Test reading existing auth file."""
        import bwm

        mock_exists.return_value = True

        with patch.object(bwm.configparser.ConfigParser, "read"):
            with patch.object(bwm.configparser.ConfigParser, "get") as mock_get:
                mock_get.side_effect = lambda section, key: {
                    "port": "54321",
                    "authkey": "existingkey1234",
                }[key]
                from bwm.__main__ import get_auth

                port, authkey = get_auth()

        assert port == 54321
        assert authkey == b"existingkey1234"


class TestClient:
    """Tests for client connection."""

    @patch("bwm.__main__.BaseManager")
    def test_client_registers_methods(self, mock_manager_class):
        """Test that client registers required methods."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        from bwm.__main__ import client

        client(12345, b"authkey")

        mock_manager.register.assert_any_call("set_event")
        mock_manager.register.assert_any_call("get_pipe")
        mock_manager.register.assert_any_call("read_args_from_pipe")
        mock_manager.connect.assert_called_once()

    @patch("bwm.__main__.BaseManager")
    def test_client_uses_correct_address(self, mock_manager_class):
        """Test that client uses correct port and authkey."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        from bwm.__main__ import client

        client(9999, b"testauth")

        mock_manager_class.assert_called_once_with(
            address=("", 9999), authkey=b"testauth"
        )


class TestServer:
    """Tests for Server class."""

    @patch("bwm.__main__.get_auth")
    def test_server_initialization(self, mock_get_auth):
        """Test Server class initialization."""
        mock_get_auth.return_value = (12345, b"authkey")

        from bwm.__main__ import Server

        server = Server()

        assert server.port == 12345
        assert server.authkey == b"authkey"
        assert server.start_flag.is_set()
        assert not server.kill_flag.is_set()
        assert not server.cache_time_expired.is_set()
        assert not server.args_flag.is_set()

    @patch("bwm.__main__.get_auth")
    def test_server_has_pipe(self, mock_get_auth):
        """Test Server has parent/child pipe connection."""
        mock_get_auth.return_value = (12345, b"authkey")

        from bwm.__main__ import Server

        server = Server()

        # Server should have pipe connections
        assert server._parent_conn is not None
        assert server._child_conn is not None

    @patch("bwm.__main__.get_auth")
    def test_server_get_pipe(self, mock_get_auth):
        """Test _get_pipe returns child connection."""
        mock_get_auth.return_value = (12345, b"authkey")

        from bwm.__main__ import Server

        server = Server()

        assert server._get_pipe() is server._child_conn
