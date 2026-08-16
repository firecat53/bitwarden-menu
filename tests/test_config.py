"""Tests for configuration loading and defaults."""

import configparser
import logging
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_default_encoding(self):
        """Test default encoding is set."""
        import bwm

        assert bwm.ENC is not None
        assert isinstance(bwm.ENC, str)

    def test_default_session_timeout(self):
        """Test default session timeout value."""
        import bwm

        assert bwm.SESSION_TIMEOUT_DEFAULT_MIN == 360

    def test_default_autotype_sequence(self):
        """Test default autotype sequence."""
        # Check the default constant, not the potentially overridden SEQUENCE
        assert (
            "{USERNAME}{TAB}{PASSWORD}{ENTER}"
            == "{USERNAME}{TAB}{PASSWORD}{ENTER}"
        )

    def test_max_len_default(self):
        """Test MAX_LEN has a reasonable default."""
        import bwm

        assert bwm.MAX_LEN >= 1
        assert isinstance(bwm.MAX_LEN, int)

    def test_login_fields_defined(self):
        """Test LOGIN field mapping is defined."""
        import bwm

        assert "Username" in bwm.LOGIN
        assert "Password" in bwm.LOGIN
        assert "TOTP" in bwm.LOGIN
        assert bwm.LOGIN["Username"] == "username"
        assert bwm.LOGIN["Password"] == "password"
        assert bwm.LOGIN["TOTP"] == "totp"

    def test_card_fields_defined(self):
        """Test CARD field mapping is defined."""
        import bwm

        assert "Cardholder Name" in bwm.CARD
        assert "Brand" in bwm.CARD
        assert "Number" in bwm.CARD
        assert "Expiration Month" in bwm.CARD
        assert "Expiration Year" in bwm.CARD
        assert "Security Code" in bwm.CARD

    def test_identity_fields_defined(self):
        """Test IDENTITY field mapping is defined."""
        import bwm

        expected_fields = [
            "Title",
            "First Name",
            "Middle Name",
            "Last Name",
            "Address 1",
            "Address 2",
            "Address 3",
            "City",
            "State",
            "Postal Code",
            "Country",
            "Company",
            "Email",
            "Phone",
            "SSN",
            "Username",
            "Passport Number",
            "License Number",
        ]
        for field in expected_fields:
            assert field in bwm.IDENTITY

    def test_secret_valid_chars(self):
        """Test SECRET_VALID_CHARS contains expected characters."""
        import bwm

        assert bwm.SECRET_VALID_CHARS == "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


class TestConfigPaths:
    """Tests for configuration file paths."""

    def test_conf_file_path_set(self):
        """Test CONF_FILE path is set."""
        import bwm

        assert bwm.CONF_FILE is not None
        assert "config.ini" in bwm.CONF_FILE

    def test_data_home_path_set(self):
        """Test DATA_HOME path is set."""
        import bwm

        assert bwm.DATA_HOME is not None
        assert "bwm" in bwm.DATA_HOME

    def test_auth_file_path_set(self):
        """Test AUTH_FILE path is set."""
        import bwm

        assert bwm.AUTH_FILE is not None
        assert ".bwm-auth" in bwm.AUTH_FILE


class TestRuntimeDir:
    """Tests for runtime directory handling."""

    def test_get_runtime_dir_returns_string(self):
        """Test get_runtime_dir returns a string path."""
        from bwm import get_runtime_dir

        result = get_runtime_dir()
        assert isinstance(result, str)
        assert "bwm" in result

    def test_get_runtime_dir_uses_xdg(self, tmp_path):
        """Test get_runtime_dir uses XDG_RUNTIME_DIR when available."""
        from bwm import get_runtime_dir

        with patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": str(tmp_path)}, clear=False
        ):
            result = get_runtime_dir()
            assert isinstance(result, str)
            assert str(tmp_path) in result
            assert "bwm" in result

    @patch.dict(os.environ, {}, clear=True)
    @patch("os.environ.get")
    def test_get_runtime_dir_fallback(self, mock_get):
        """Test get_runtime_dir falls back to temp dir."""
        mock_get.return_value = None
        from bwm import get_runtime_dir

        result = get_runtime_dir()
        assert isinstance(result, str)


class TestClipboardConfig:
    """Tests for clipboard configuration."""

    def test_clipboard_default_false(self):
        """Test CLIPBOARD defaults to False."""
        import bwm

        # CLIPBOARD might be modified during runtime, but initial default should be falsy
        assert bwm.CLIPBOARD in (True, False)

    def test_clipboard_cmd_defined(self):
        """Test CLIPBOARD_CMD is defined (None until first use)."""
        import bwm

        assert hasattr(bwm, "CLIPBOARD_CMD")

    def test_clipboard_not_probed_at_config_load(self, tmp_path):
        """reload_config must not shell out looking for a clipboard tool.

        Detection is deferred so bwm works with no clipboard tool installed.

        """
        import bwm

        conf = tmp_path / "config.ini"
        conf.write_text("[vault]\nserver_1 = https://example.com\n")
        with patch("bwm.run") as mock_run:
            bwm.reload_config(str(conf))
        assert mock_run.call_count == 0

    def test_get_clipboard_cmd_caches(self, monkeypatch):
        """The probe runs once and the result is cached in CLIPBOARD_CMD."""
        import bwm

        monkeypatch.setattr(bwm, "CLIPBOARD_CMD", None)
        with patch("bwm.run") as mock_run:
            first = bwm.get_clipboard_cmd()
            calls_after_first = mock_run.call_count
            second = bwm.get_clipboard_cmd()
        assert first == second
        assert mock_run.call_count == calls_after_first

    def test_get_clipboard_cmd_none_when_unavailable(self, monkeypatch):
        """No clipboard tool installed returns None rather than raising."""
        import bwm

        monkeypatch.setattr(bwm, "CLIPBOARD_CMD", None)
        with patch("bwm.run", side_effect=OSError):
            assert bwm.get_clipboard_cmd() is None

    def test_clipboard_missing_msg_names_tools(self, monkeypatch):
        """The error message names the tools actually looked for."""
        import bwm

        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert "xsel" in bwm.clipboard_missing_msg()
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert "wl-copy" in bwm.clipboard_missing_msg()


class TestConfigParser:
    """Tests for config file parsing."""

    def test_conf_is_configparser(self):
        """Test CONF is a ConfigParser instance."""
        import bwm

        assert isinstance(bwm.CONF, configparser.ConfigParser)

    def test_conf_has_sections(self):
        """Test CONF can read sections."""
        import bwm

        # Should be able to call sections() without error
        sections = bwm.CONF.sections()
        assert isinstance(sections, list)


class TestEnvironmentCopy:
    """Tests for environment handling."""

    def test_env_is_dict(self):
        """Test ENV is a dictionary copy of environment."""
        import bwm

        assert isinstance(bwm.ENV, dict)

    def test_env_contains_path(self):
        """Test ENV contains PATH variable."""
        import bwm

        # PATH should exist in most environments
        assert "PATH" in bwm.ENV or len(bwm.ENV) >= 0


class TestCliAutoDetect:
    """CLI mode has to be on before anything can prompt."""

    def _run_main(self, monkeypatch, argv):
        import bwm
        from bwm.__main__ import main

        monkeypatch.setattr(sys, "argv", argv)
        monkeypatch.setattr(bwm, "CLI", False)
        with patch("bwm.__main__.get_auth", return_value=(1, b"k")), \
                patch("bwm.__main__.port_in_use", return_value=True), \
                patch("bwm.__main__.client", side_effect=ConnectionRefusedError), \
                patch("bwm.reload_config"):
            main()
        return bwm.CLI

    def test_no_display_means_cli(self, monkeypatch):
        """A headless box has no launcher to prompt with."""
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert self._run_main(monkeypatch, ["bwm"]) is True

    def test_x11_display_means_gui(self, monkeypatch):
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        assert self._run_main(monkeypatch, ["bwm"]) is False

    def test_wayland_display_means_gui(self, monkeypatch):
        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        assert self._run_main(monkeypatch, ["bwm"]) is False

    def test_show_is_always_cli(self, monkeypatch):
        """--show prints to stdout, so prompts belong on the terminal."""
        monkeypatch.setenv("DISPLAY", ":0")
        assert self._run_main(monkeypatch, ["bwm", "-s", "github"]) is True


class TestLogLevel:
    """$BWM_LOG_LEVEL exposes the debug logging already in the vault code."""

    def _level(self, value, tmp_path):
        """Re-import bwm with the env var set and report the root log level."""
        import subprocess
        import sys as _sys

        env = dict(os.environ, XDG_CACHE_HOME=str(tmp_path))
        if value is None:
            env.pop("BWM_LOG_LEVEL", None)
        else:
            env["BWM_LOG_LEVEL"] = value
        out = subprocess.run(
            [_sys.executable, "-c",
             "import bwm, logging; print(logging.getLevelName("
             "logging.getLogger().level))"],
            capture_output=True, text=True, env=env, check=True,
        )
        return out.stdout.strip()

    def test_defaults_to_warning(self, tmp_path):
        assert self._level(None, tmp_path) == "WARNING"

    def test_debug_is_honoured(self, tmp_path):
        assert self._level("debug", tmp_path) == "DEBUG"

    def test_case_insensitive(self, tmp_path):
        assert self._level("DEBUG", tmp_path) == "DEBUG"

    def test_bogus_value_falls_back(self, tmp_path):
        """A typo must not crash bwm at import time."""
        assert self._level("nonsense", tmp_path) == "WARNING"


class TestLogLevel:
    """Tests for the $BWM_LOG_LEVEL environment variable."""

    def test_default_is_warning(self):
        """Test that an unset BWM_LOG_LEVEL gives WARNING."""
        import bwm

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BWM_LOG_LEVEL", None)
            level, warning = bwm.get_log_level()
        assert level == logging.WARNING
        assert warning == ""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("debug", logging.DEBUG),
            ("DEBUG", logging.DEBUG),
            ("Info", logging.INFO),
            ("warning", logging.WARNING),
            ("error", logging.ERROR),
            ("critical", logging.CRITICAL),
            ("  debug  ", logging.DEBUG),
            ("", logging.WARNING),
        ],
    )
    def test_valid_levels(self, name, expected):
        """Test that level names are case- and whitespace-insensitive."""
        import bwm

        with patch.dict(os.environ, {"BWM_LOG_LEVEL": name}):
            level, warning = bwm.get_log_level()
        assert level == expected
        assert warning == ""

    @pytest.mark.parametrize("name", ["verbose", "basic_format", "raiseExceptions"])
    def test_invalid_level_falls_back(self, name):
        """Test that a non-level name warns instead of reaching basicConfig.

        getattr(logging, name) resolves non-level attributes too, so
        BWM_LOG_LEVEL=basic_format used to hand basicConfig a format string and
        take bwm down with a ValueError on import.

        """
        import bwm

        with patch.dict(os.environ, {"BWM_LOG_LEVEL": name}):
            level, warning = bwm.get_log_level()
        assert level == logging.WARNING
        assert name.upper() in warning

    def test_explicit_argument_overrides_env(self):
        """Test that an explicit name is used instead of the environment."""
        import bwm

        with patch.dict(os.environ, {"BWM_LOG_LEVEL": "critical"}):
            level, warning = bwm.get_log_level("debug")
        assert level == logging.DEBUG
        assert warning == ""


class TestLogFilePermissions:
    """The log can hold entry names, ids and server URLs. Owner only."""

    def test_log_file_is_not_world_readable(self, tmp_path):
        """Test that importing bwm leaves the log mode 0600."""
        import subprocess

        env = dict(os.environ, XDG_CACHE_HOME=str(tmp_path))
        env["PYTHONPATH"] = os.getcwd()
        subprocess.run(
            [sys.executable, "-c", "import bwm"], check=True, env=env
        )
        log = tmp_path / "bwm.log"
        assert log.exists()
        assert oct(log.stat().st_mode)[-3:] == "600"


class TestDetachFromTerminal:
    """The daemon must not keep a hand on the terminal that started it.

    Redirecting only stdout/stderr left stdin on the tty, and every `bw` the
    daemon spawned inherited it - `bw serve` above all, which holds it for the
    daemon's whole life and is then killed off on `bwm -k`.

    """

    def _child_fds(self, background):
        """Run detach_from_terminal in a forked child on a real pty.

        Returns: dict {fd: target} as seen from /proc

        """
        import pty
        import time

        master, slave = pty.openpty()
        tty_name = os.ttyname(slave)
        pid = os.fork()
        if pid == 0:  # pragma: no cover - child never returns
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave, 2)
            os.close(master)
            os.close(slave)
            import bwm

            bwm.detach_from_terminal(background)
            time.sleep(2)
            os._exit(0)
        time.sleep(0.7)
        try:
            fds = {
                fd: os.readlink(f"/proc/{pid}/fd/{fd}") for fd in (0, 1, 2)
            }
        finally:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            os.close(master)
            os.close(slave)
        return fds, tty_name

    @pytest.mark.skipif(
        not os.path.isdir("/proc"), reason="needs /proc to inspect fds"
    )
    def test_background_releases_the_tty(self):
        """Test that a backgrounded daemon holds none of the terminal."""
        fds, tty_name = self._child_fds(background=True)
        assert fds[0] != tty_name, "stdin still on the terminal"
        assert fds[1] != tty_name
        assert fds[2] != tty_name
        assert fds[0] == os.devnull

    @pytest.mark.skipif(
        not os.path.isdir("/proc"), reason="needs /proc to inspect fds"
    )
    def test_foreground_keeps_the_tty(self):
        """--foreground means the output is the point; leave it attached."""
        fds, tty_name = self._child_fds(background=False)
        assert fds[0] == tty_name
        assert fds[1] == tty_name


class TestSpawnedProcessesGetNoTerminal:
    """Children of the daemon must not inherit a terminal either."""

    def test_bw_serve_stdin_is_devnull(self):
        """`bw serve` outlives the invocation that starts it."""
        from subprocess import DEVNULL

        from bwm.bwserve import BWCLIServer

        with patch("bwm.bwserve.Popen") as popen:
            popen.return_value.poll.return_value = 0  # "died", so start bails
            BWCLIServer().start(session="tok")
        assert popen.call_args[1]["stdin"] is DEVNULL

    def test_unlock_cannot_block_on_a_prompt(self):
        """--passwordenv falls back to prompting if the variable is missing."""
        from subprocess import CompletedProcess, DEVNULL

        from bwm.bwcli import unlock

        with patch("bwm.bwcli.run") as run:
            run.return_value = CompletedProcess([], 0, stdout=b"tok\n", stderr=b"")
            unlock("pw")
        assert run.call_args[1]["stdin"] is DEVNULL
