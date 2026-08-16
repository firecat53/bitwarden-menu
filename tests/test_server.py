"""Tests for multiprocessing server module."""

import configparser
import json
import multiprocessing
import socket
import sys
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


class TestMainConfigLoading:
    """main() reads CONF, so it has to load the config itself.

    reload_config() otherwise only runs inside DmenuRunner, which lives in the
    daemon process - so anything main() reads was hitting an empty CONF.

    """

    def test_vault_arg_without_config_file(self, tmp_path, monkeypatch):
        """`bwm -v <url>` with no config file must not raise NoSectionError."""
        import bwm
        from bwm.__main__ import main

        monkeypatch.setattr(
            sys, "argv", ["bwm", "-v", "https://vault.example.com"]
        )
        monkeypatch.setattr(bwm, "CONF_FILE", str(tmp_path / "config.ini"))
        monkeypatch.setattr(bwm, "CONF", configparser.ConfigParser())
        # Stop before anything starts a daemon or talks to the network
        with patch("bwm.__main__.get_auth", return_value=(None, None)), \
                patch("bwm.__main__.port_in_use", return_value=True), \
                patch("bwm.__main__.client", side_effect=ConnectionRefusedError):
            main()
        assert bwm.CONF.has_section("vault")

    def test_config_without_vault_section(self, tmp_path):
        """A hand written config missing [vault] gets an empty one added."""
        import bwm

        conf = tmp_path / "config.ini"
        conf.write_text("[dmenu]\ndmenu_command = dmenu\n")
        bwm.reload_config(str(conf))
        # get_vault() and main() both do dict(CONF.items("vault"))
        assert dict(bwm.CONF.items("vault")) == {}
        assert bwm.CONF.has_section("dmenu_passphrase")


class TestRunFailureCleanup:
    """DmenuRunner.__init__ runs in the parent, so its exit is the user's.

    Failing to open a vault used to exit 0 with no output, and left the auth
    file behind because the construction sat outside run()'s try/finally.

    """

    def test_failed_startup_exits_nonzero_and_cleans_up(self, tmp_path):
        """A vault that can't be opened is a failure, not a silent success."""
        import bwm
        from bwm.__main__ import run

        auth = tmp_path / ".bwm-auth"
        auth.write_text("[DEFAULT]\nport = 1\nauthkey = abc\n")
        with patch.object(bwm, "AUTH_FILE", str(auth)), \
                patch("bwm.__main__.Server"), \
                patch(
                    "bwm.__main__.DmenuRunner", side_effect=SystemExit(1)
                ):
            with pytest.raises(SystemExit) as exc:
                run()
        assert exc.value.code == 1
        assert not auth.exists()


class TestShowResultChannel:
    """The daemon has no terminal, so --show results travel back to the client."""

    @patch("bwm.__main__.get_auth")
    def test_pipe_is_duplex(self, mock_get_auth):
        """A one-way pipe can't carry results back to the client."""
        mock_get_auth.return_value = (12345, b"authkey")
        from bwm.__main__ import Server

        server = Server()
        server._parent_conn.send("daemon -> client")
        assert server._child_conn.recv() == "daemon -> client"
        server._child_conn.send("client -> daemon")
        assert server._parent_conn.recv() == "client -> daemon"

    @patch("bwm.__main__.get_auth")
    def test_send_and_receive_result(self, mock_get_auth):
        """send_result in the daemon, receive_show_result in the client."""
        mock_get_auth.return_value = (12345, b"authkey")
        from bwm.__main__ import Server

        server = Server()
        server.send_result("hunter2")
        assert server.receive_show_result(timeout=1) == "hunter2"

    @patch("bwm.__main__.get_auth")
    def test_receive_times_out(self, mock_get_auth):
        """Nothing sent means None, not a hang."""
        mock_get_auth.return_value = (12345, b"authkey")
        from bwm.__main__ import Server

        server = Server()
        assert server.receive_show_result(timeout=0.01) is None

    @patch("bwm.__main__.get_auth")
    def test_unlocked_vaults_published(self, mock_get_auth):
        """The client reads this to decide whether to prompt."""
        mock_get_auth.return_value = (12345, b"authkey")
        from bwm.__main__ import Server

        assert Server().unlocked_vaults() == []
        buf = multiprocessing.Array("c", 8192)
        buf.value = json.dumps(
            [["https://v.example.com", "a@example.com"]]
        ).encode()
        server = Server(unlocked=buf)
        assert server.unlocked_vaults() == [
            ["https://v.example.com", "a@example.com"]
        ]


class TestDeliverShowResult:
    """Exit codes and streams for --show output."""

    def test_prints_value(self, capsys):
        from bwm.__main__ import deliver_show_result

        with pytest.raises(SystemExit) as exc:
            deliver_show_result("hunter2")
        assert exc.value.code == 0
        assert capsys.readouterr().out == "hunter2\n"

    def test_error_to_stderr_exits_1(self, capsys):
        from bwm.__main__ import deliver_show_result

        with pytest.raises(SystemExit) as exc:
            deliver_show_result("ERROR: nope")
        assert exc.value.code == 1
        assert capsys.readouterr().err.strip() == "nope"

    def test_none_exits_1(self):
        from bwm.__main__ import deliver_show_result

        with pytest.raises(SystemExit) as exc:
            deliver_show_result(None)
        assert exc.value.code == 1

    def test_empty_is_silent_success(self, capsys):
        """Clipboard mode: nothing to print, but not a failure."""
        from bwm.__main__ import deliver_show_result

        with pytest.raises(SystemExit) as exc:
            deliver_show_result("")
        assert exc.value.code == 0
        assert capsys.readouterr().out == ""


class TestShowPasswordPrompt:
    """Prompting happens in the client, never in the daemon."""

    def test_no_vault_arg_never_prompts(self):
        """Without -v the daemon uses its active vault, already unlocked."""
        from bwm.__main__ import show_password_prompt

        with patch("bwm.__main__.getpass") as gp:
            assert show_password_prompt([], {}) is None
        gp.assert_not_called()

    def test_unlocked_vault_never_prompts(self):
        from bwm.__main__ import show_password_prompt

        with patch("bwm.__main__.getpass") as gp:
            res = show_password_prompt(
                [["https://v.example.com", "a@example.com"]],
                {"vault": "https://v.example.com"},
            )
        assert res is None
        gp.assert_not_called()

    def test_locked_vault_prompts(self):
        from bwm.__main__ import show_password_prompt

        with patch("bwm.__main__.getpass", return_value="master") as gp:
            res = show_password_prompt(
                [["https://other.example.com", "a@example.com"]],
                {"vault": "https://v.example.com"},
            )
        assert res == "master"
        gp.assert_called_once()

    def test_config_password_skips_prompt(self, tmp_path):
        """password_cmd_n in config means the daemon can unlock unaided."""
        import bwm
        from bwm.__main__ import show_password_prompt

        conf = tmp_path / "config.ini"
        conf.write_text(
            "[vault]\nserver_1 = https://v.example.com\n"
            "email_1 = a@example.com\npassword_cmd_1 = pass show vault\n"
        )
        bwm.reload_config(str(conf))
        with patch("bwm.__main__.getpass") as gp:
            res = show_password_prompt([], {"vault": "https://v.example.com"})
        assert res is None
        gp.assert_not_called()

    def test_no_terminal_returns_none(self):
        from bwm.__main__ import show_password_prompt

        with patch("bwm.__main__.getpass", side_effect=EOFError):
            assert show_password_prompt(
                [], {"vault": "https://v.example.com"}
            ) is None


class TestOldDaemonDetection:
    """An upgraded client talking to a daemon started before --show existed.

    The old daemon has neither callable registered, so calls raise RemoteError.
    Detecting that *before* sending args matters: a daemon handed arguments it
    doesn't understand falls through and pops up its GUI entry menu.

    """

    def test_missing_callable_reports_none(self):
        from multiprocessing.managers import RemoteError
        from bwm.__main__ import daemon_unlocked_vaults

        mgr = MagicMock()
        mgr.get_unlocked_vaults.side_effect = RemoteError("KeyError")
        assert daemon_unlocked_vaults(mgr) is None

    def test_current_daemon_returns_the_list(self):
        from bwm.__main__ import daemon_unlocked_vaults

        mgr = MagicMock()
        mgr.get_unlocked_vaults.return_value = [["https://v", "a@b.c"]]
        assert daemon_unlocked_vaults(mgr) == [["https://v", "a@b.c"]]

    def test_autoproxy_value_is_unwrapped(self):
        from bwm.__main__ import daemon_unlocked_vaults

        proxy = MagicMock()
        proxy._getvalue.return_value = [["https://v", "a@b.c"]]
        mgr = MagicMock()
        mgr.get_unlocked_vaults.return_value = proxy
        assert daemon_unlocked_vaults(mgr) == [["https://v", "a@b.c"]]

    def test_main_exits_without_sending_args(self, monkeypatch, capsys):
        """No args are sent, so the old daemon never shows its menu."""
        from multiprocessing.managers import RemoteError
        import bwm
        from bwm.__main__ import main

        monkeypatch.setattr(sys, "argv", ["bwm", "-s", "accredo"])
        monkeypatch.setattr(bwm, "CONF", configparser.ConfigParser())
        mgr = MagicMock()
        mgr.get_unlocked_vaults.side_effect = RemoteError("KeyError")
        conn = mgr.get_pipe.return_value
        with patch("bwm.__main__.get_auth", return_value=(1, b"k")), \
                patch("bwm.__main__.port_in_use", return_value=True), \
                patch("bwm.__main__.client", return_value=mgr), \
                patch("bwm.reload_config"):
            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 1
        conn.send.assert_not_called()
        mgr.set_event.assert_not_called()
        assert "without --show support" in capsys.readouterr().err


class TestBackgrounding:
    """The daemon outlives the invocation, so unlocking is paid once."""

    def _patches(self, dmenu):
        """Patch out everything run() would really start."""
        return (
            patch("bwm.__main__.Server"),
            patch("bwm.__main__.DmenuRunner", return_value=dmenu),
            patch("bwm.__main__.multiprocessing.Manager"),
        )

    def _dmenu(self):
        dmenu = MagicMock()
        dmenu.vault.entries = []
        dmenu.vault.folders = {}
        return dmenu

    def test_background_does_not_join(self):
        """Joining would block the shell for the daemon's whole lifetime."""
        from bwm.__main__ import run

        dmenu = self._dmenu()
        srv, dm, mgr = self._patches(dmenu)
        with srv as mock_server, dm, mgr:
            run(foreground=False)
        instance = mock_server.return_value
        instance.start.assert_called_once()
        instance.join.assert_not_called()
        # Daemonic children are killed when the parent exits
        assert dmenu.daemon is False

    def test_foreground_joins(self):
        from bwm.__main__ import run

        dmenu = self._dmenu()
        srv, dm, mgr = self._patches(dmenu)
        with srv as mock_server, dm, mgr:
            run(foreground=True)
        mock_server.return_value.join.assert_called_once()
        assert dmenu.daemon is True

    def test_show_suppresses_the_startup_menu(self):
        """Starting a daemon to answer --show must not pop the entry menu."""
        from bwm.__main__ import run

        dmenu = self._dmenu()
        srv, dm, mgr = self._patches(dmenu)
        with srv as mock_server, dm, mgr, \
                patch("bwm.__main__.show_fields", return_value="hunter2"):
            result = run(foreground=False, show="github")
        mock_server.return_value.start_flag.clear.assert_called_once()
        assert result == "hunter2"

    def test_no_show_leaves_the_menu_armed(self):
        from bwm.__main__ import run

        dmenu = self._dmenu()
        srv, dm, mgr = self._patches(dmenu)
        with srv as mock_server, dm, mgr:
            run(foreground=False)
        mock_server.return_value.start_flag.clear.assert_not_called()

    def test_auth_file_kept_for_the_daemon(self, tmp_path):
        """The daemon removes it on exit; run() must not yank it early."""
        import bwm
        from bwm.__main__ import run

        auth = tmp_path / ".bwm-auth"
        auth.write_text("x")
        dmenu = self._dmenu()
        srv, dm, mgr = self._patches(dmenu)
        with patch.object(bwm, "AUTH_FILE", str(auth)), srv, dm, mgr:
            run(foreground=False)
        assert auth.exists()

    def test_auth_file_removed_if_startup_failed(self, tmp_path):
        """Nothing is left running to clean up after itself."""
        import bwm
        from bwm.__main__ import run

        auth = tmp_path / ".bwm-auth"
        auth.write_text("x")
        with patch.object(bwm, "AUTH_FILE", str(auth)), \
                patch("bwm.__main__.Server"), \
                patch("bwm.__main__.multiprocessing.Manager"), \
                patch("bwm.__main__.DmenuRunner", side_effect=SystemExit(1)):
            with pytest.raises(SystemExit):
                run(foreground=False)
        assert not auth.exists()


class TestLeave:
    """os._exit vs sys.exit: the difference between returning and hanging."""

    def test_attached_uses_sys_exit(self):
        from bwm.__main__ import leave

        with pytest.raises(SystemExit) as exc:
            leave(3, detached=False)
        assert exc.value.code == 3

    def test_detached_uses_os_exit(self):
        """sys.exit() would block on multiprocessing's atexit join."""
        from bwm.__main__ import leave

        with patch("bwm.__main__.os._exit") as mock_exit:
            leave(1, detached=True)
        mock_exit.assert_called_once_with(1)

    def test_detached_flushes_first(self):
        """os._exit skips buffer flushing, so output would be lost."""
        from bwm.__main__ import leave

        with patch("bwm.__main__.os._exit"), \
                patch("sys.stdout") as out:
            leave(0, detached=True)
        out.flush.assert_called()


class TestMainStartsDaemon:
    """main() -> run() wiring, which unit-testing run() alone can't catch."""

    def _main(self, monkeypatch, argv, tmp_path):
        import bwm
        from bwm.__main__ import main

        monkeypatch.setattr(sys, "argv", argv)
        monkeypatch.setattr(bwm, "CONF", configparser.ConfigParser())
        with patch("bwm.__main__.get_auth", return_value=(1, b"k")), \
                patch("bwm.__main__.port_in_use", return_value=False), \
                patch("bwm.reload_config"), \
                patch("bwm.__main__.leave", side_effect=SystemExit(0)), \
                patch("bwm.__main__.run", return_value=None) as mock_run:
            with pytest.raises(SystemExit):
                main()
        return mock_run

    def test_foreground_flag_passed_once(self, monkeypatch, tmp_path):
        """argparse already puts 'foreground' in args; passing it again
        alongside **args is a TypeError."""
        mock_run = self._main(
            monkeypatch, ["bwm", "--foreground"], tmp_path
        )
        assert mock_run.call_args.kwargs.get("foreground") is True

    def test_backgrounds_by_default(self, monkeypatch, tmp_path):
        mock_run = self._main(monkeypatch, ["bwm"], tmp_path)
        # No flags at all collapses args to {}, so run() uses its own default
        assert mock_run.call_args.kwargs.get("foreground", False) is False

    def test_show_passes_through(self, monkeypatch, tmp_path):
        mock_run = self._main(monkeypatch, ["bwm", "-s", "github"], tmp_path)
        assert mock_run.call_args.kwargs["show"] == "github"
        assert mock_run.call_args.kwargs.get("foreground") is False


class TestLockWithoutDaemon:
    """`bwm -k` must never start a daemon.

    Falling through to run() unlocked the vault and left a daemon behind -
    the exact opposite of locking - whenever no daemon was already up, e.g.
    after the session timeout had expired.

    """

    def _main(self, monkeypatch, lock_ok=True):
        import bwm
        from bwm.__main__ import main

        monkeypatch.setattr(sys, "argv", ["bwm", "-k"])
        monkeypatch.setattr(bwm, "CONF", configparser.ConfigParser())
        with patch("bwm.__main__.get_auth", return_value=(1, b"k")), \
                patch("bwm.__main__.port_in_use", return_value=False), \
                patch("bwm.reload_config"), \
                patch("bwm.__main__.bwcli.lock", return_value=lock_ok) as lock, \
                patch("bwm.__main__.run") as run_:
            with pytest.raises(SystemExit) as exc:
                main()
        return lock, run_, exc.value.code

    def test_locks_without_starting_a_daemon(self, monkeypatch):
        lock, run_, code = self._main(monkeypatch)
        lock.assert_called_once()
        run_.assert_not_called()
        assert code == 0

    def test_failed_lock_exits_nonzero(self, monkeypatch, capsys):
        lock, run_, code = self._main(monkeypatch, lock_ok=False)
        lock.assert_called_once()
        run_.assert_not_called()
        assert code == 1
        assert "Could not lock" in capsys.readouterr().err

    def test_running_daemon_is_told_instead(self, monkeypatch):
        """With a daemon up, -k goes through the pipe as before."""
        import bwm
        from bwm.__main__ import main

        monkeypatch.setattr(sys, "argv", ["bwm", "-k"])
        monkeypatch.setattr(bwm, "CONF", configparser.ConfigParser())
        mgr = MagicMock()
        with patch("bwm.__main__.get_auth", return_value=(1, b"k")), \
                patch("bwm.__main__.port_in_use", return_value=True), \
                patch("bwm.reload_config"), \
                patch("bwm.__main__.bwcli.lock") as lock, \
                patch("bwm.__main__.client", return_value=mgr):
            main()
        lock.assert_not_called()          # the daemon runs bw lock itself
        mgr.get_pipe.return_value.send.assert_called_once()
        mgr.set_event.assert_called_once()


class TestClipboardIsClientSide:
    """The clipboard belongs to the invoking session, not the daemon's.

    A daemon started from a tty has no DISPLAY or WAYLAND_DISPLAY, so a copy
    performed there hunts for X11 tools even when the caller is on Wayland -
    reporting 'xsel or xclip needed' no matter which terminal you use.

    """

    def test_copies_instead_of_printing(self, capsys):
        from bwm.__main__ import deliver_show_result

        with patch("bwm.__main__.type_clipboard", return_value=True) as clip:
            with pytest.raises(SystemExit) as exc:
                deliver_show_result("hunter2", clipboard=True)
        # detach=True or the 30 second clear dies with this process and the
        # password stays on the clipboard forever
        clip.assert_called_once_with("hunter2", detach=True)
        assert exc.value.code == 0
        assert capsys.readouterr().out == ""      # secret not echoed

    def test_missing_tool_is_reported_here(self, capsys):
        from bwm.__main__ import deliver_show_result

        with patch("bwm.__main__.type_clipboard", return_value=False):
            with pytest.raises(SystemExit) as exc:
                deliver_show_result("hunter2", clipboard=True)
        assert exc.value.code == 1
        assert "needed for clipboard" in capsys.readouterr().err

    def test_errors_are_not_copied(self, capsys):
        """An ERROR: string must reach stderr, not the clipboard."""
        from bwm.__main__ import deliver_show_result

        with patch("bwm.__main__.type_clipboard") as clip:
            with pytest.raises(SystemExit) as exc:
                deliver_show_result("ERROR: no match", clipboard=True)
        clip.assert_not_called()
        assert exc.value.code == 1
        assert "no match" in capsys.readouterr().err

    def test_without_the_flag_it_still_prints(self, capsys):
        from bwm.__main__ import deliver_show_result

        with patch("bwm.__main__.type_clipboard") as clip:
            with pytest.raises(SystemExit):
                deliver_show_result("hunter2", clipboard=False)
        clip.assert_not_called()
        assert capsys.readouterr().out == "hunter2\n"
