"""Tests for first run launcher/terminal/type_library detection."""

import configparser
import io
import os
from unittest import mock

import pytest

import bwm
from bwm import firstrun, menu
# Bound here, at import time, so conftest's no_first_run fixture (which patches
# bwm.__main__.first_run_setup) doesn't replace the function under test.
from bwm.__main__ import first_run_setup


@pytest.fixture(autouse=True)
def x11_session(monkeypatch):
    """Default every test to a plain X11 session unless it says otherwise."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)


def installed(*names):
    """which() that reports only `names` as installed."""
    return lambda name: f"/usr/bin/{name}" if name in names else None


class TestLauncherDetection:
    """Which launchers get offered, and in what order."""

    def test_x11_drops_wayland_only_launchers(self):
        """Wayland only launchers can't open a window under X11 at all."""
        with mock.patch.object(
            firstrun, "which", installed("fuzzel", "wofi", "rofi", "dmenu")
        ):
            assert firstrun.installed_launchers() == ["rofi", "dmenu"]

    def test_wayland_ranks_native_launchers_first(self, monkeypatch):
        """X11 launchers still work through XWayland, they just rank lower."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        with mock.patch.object(
            firstrun, "which", installed("dmenu", "rofi", "wofi", "fuzzel")
        ):
            assert firstrun.installed_launchers() == [
                "fuzzel",
                "wofi",
                "rofi",
                "dmenu",
            ]

    def test_preference_order_within_a_group(self):
        """dmenu is last: it's as often a dependency as it is a choice."""
        with mock.patch.object(
            firstrun, "which", installed("dmenu", "bemenu", "rofi")
        ):
            assert firstrun.installed_launchers() == ["rofi", "bemenu", "dmenu"]

    def test_nothing_installed(self):
        with mock.patch.object(firstrun, "which", installed()):
            assert firstrun.installed_launchers() == []
            assert firstrun.pick("?", [], interactive=False) is None

    @pytest.mark.parametrize("obscure", [False, True])
    def test_every_detected_launcher_has_menu_flags(self, monkeypatch, obscure):
        """Detection must never write a launcher dmenu_cmd can't drive."""
        conf = configparser.ConfigParser()
        conf.add_section("dmenu")
        monkeypatch.setattr(bwm, "CONF", conf)
        monkeypatch.setattr(menu, "dmenu_pass", lambda launcher: ["-P"])
        for name in firstrun.LAUNCHERS:
            conf.set("dmenu", "dmenu_command", name)
            assert len(menu.dmenu_cmd(10, "Entries", obscure=obscure)) > 1, name


class TestTerminalDetection:
    """Terminals bwedit can run an editor in and wait for."""

    def test_x11_drops_wayland_only_terminals(self):
        with mock.patch.object(
            firstrun, "which", installed("foot", "footclient", "xterm")
        ):
            assert firstrun.installed_terminals() == ["xterm"]

    def test_wayland_keeps_foot_first(self, monkeypatch):
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        with mock.patch.object(
            firstrun, "which", installed("xterm", "footclient", "foot")
        ):
            assert firstrun.installed_terminals() == [
                "foot", "footclient", "xterm"]

    def test_single_string_e_terminals_never_offered(self):
        """Their -e takes one command string, not `-e editor file`."""
        for name in ("gnome-terminal", "xfce4-terminal", "terminator"):
            assert name not in firstrun.TERMINALS


class TestTypeLibraryDetection:
    """pynput, the default, types nothing at all on Wayland."""

    def test_only_set_on_wayland(self, monkeypatch):
        with mock.patch.object(
            firstrun, "which", installed("wtype", "ydotool")
        ):
            assert firstrun.detect_type_library() is None
            monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
            assert firstrun.detect_type_library() == "wtype"

    def test_none_when_no_backend_installed(self, monkeypatch):
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        with mock.patch.object(firstrun, "which", installed("dmenu")):
            assert firstrun.detect_type_library() is None

    @pytest.mark.parametrize("desktop", ["GNOME", "ubuntu:GNOME", "KDE"])
    def test_no_wtype_without_virtual_keyboard(self, monkeypatch, desktop):
        """GNOME and KDE lack the protocol wtype types through."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
        with mock.patch.object(
            firstrun, "which", installed("wtype", "ydotool")
        ):
            assert firstrun.installed_type_libraries() == ["ydotool"]
            assert firstrun.detect_type_library() == "ydotool"

    def test_only_wtype_on_gnome_leaves_the_default(self, monkeypatch):
        """Better pynput, which at least works under XWayland, than a backend
        that can't work at all."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
        with mock.patch.object(firstrun, "which", installed("wtype")):
            assert firstrun.detect_type_library() is None

    def test_wtype_first_elsewhere(self, monkeypatch):
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "sway")
        with mock.patch.object(
            firstrun, "which", installed("wtype", "ydotool")
        ):
            assert firstrun.installed_type_libraries() == ["wtype", "ydotool"]

    def test_asks_with_requirements(self, monkeypatch, capsys):
        """Each backend is listed with what it needs to work."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        with mock.patch.object(
            firstrun, "which", installed("wtype", "ydotool")
        ), mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", io.StringIO("2\n")):
            assert firstrun.detect_type_library(interactive=True) == "ydotool"
        out = capsys.readouterr().err
        for lib, note in firstrun.WAYLAND_TYPE_LIBRARIES.items():
            assert f"{lib} - {note}" in out

    def test_detect_asks_for_type_library(self, monkeypatch, capsys):
        """Asked even when launcher and terminal are unambiguous."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        with mock.patch.object(
            firstrun, "which", installed("fuzzel", "foot", "wtype", "ydotool")
        ), mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", io.StringIO("2\n")):
            choices = firstrun.detect(interactive=True)
        assert choices == {"launcher": "fuzzel", "terminal": "foot",
                           "type_library": "ydotool"}
        assert "Setting up bwm" in capsys.readouterr().err


class TestPick:
    """Asking, and the much more common case of having nobody to ask."""

    def test_takes_the_first_without_a_tty(self):
        """The usual case: bwm started from a keybinding."""
        with mock.patch.object(firstrun, "has_tty", return_value=False):
            assert (
                firstrun.pick("?", ["rofi", "dmenu"], interactive=True)
                == "rofi"
            )

    def test_asks_when_interactive(self, capsys):
        with mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", io.StringIO("2\n")):
            assert (
                firstrun.pick("?", ["rofi", "dmenu"], interactive=True)
                == "dmenu"
            )
        assert "dmenu" in capsys.readouterr().err

    def test_questions_stay_off_stdout(self, capsys):
        """stdout may be `pw=$(bwm --show x)` collecting the secret."""
        with mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", io.StringIO("2\n")):
            firstrun.pick("?", ["rofi", "dmenu"], interactive=True)
        out, err = capsys.readouterr()
        assert out == ""
        assert "Choice [1-2" in err

    def test_eof_takes_the_default(self, capsys):
        with mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", io.StringIO("")):
            assert firstrun.pick("?", ["rofi", "dmenu"], interactive=True) == "rofi"
        capsys.readouterr()

    def test_ctrl_c_is_not_swallowed(self, capsys):
        stdin = mock.Mock(readline=mock.Mock(side_effect=KeyboardInterrupt))
        with mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", stdin):
            with pytest.raises(KeyboardInterrupt):
                firstrun.pick("?", ["rofi", "dmenu"], interactive=True)
        capsys.readouterr()

    def test_needs_stderr_to_be_a_tty(self):
        """The questions go to stderr, so there's nobody to ask without it."""
        tty = mock.Mock(isatty=mock.Mock(return_value=True))
        pipe = mock.Mock(isatty=mock.Mock(return_value=False))
        with mock.patch.object(firstrun.sys, "stdin", tty), \
                mock.patch.object(firstrun.sys, "stderr", pipe):
            assert firstrun.has_tty() is False
        with mock.patch.object(firstrun.sys, "stdin", tty), \
                mock.patch.object(firstrun.sys, "stderr", tty):
            assert firstrun.has_tty() is True

    def test_empty_answer_takes_the_default(self, capsys):
        with mock.patch.object(
            firstrun, "has_tty", return_value=True
        ), mock.patch.object(firstrun.sys, "stdin", io.StringIO("\n")):
            assert (
                firstrun.pick("?", ["rofi", "dmenu"], interactive=True)
                == "rofi"
            )
        capsys.readouterr()


class TestGeneratedConfig:
    """What ends up in a config file written on first run."""

    def test_valid_and_private(self, tmp_path):
        conf_file = str(tmp_path / "sub" / "config.ini")
        bwm.write_config(
            conf_file,
            launcher="fuzzel",
            terminal="foot",
            type_library="wtype",
        )
        assert os.stat(conf_file).st_mode & 0o777 == 0o600
        conf = configparser.ConfigParser()
        conf.read(conf_file)
        assert conf.get("dmenu", "dmenu_command") == "fuzzel"
        assert conf.get("vault", "terminal") == "foot"
        assert conf.get("vault", "type_library") == "wtype"
        # get_initial_vault() fills these in on the first unlock
        assert conf.get("vault", "server_1") == ""
        assert conf.getint("vault", "session_timeout_min") == 360

    def test_omits_undetected_options(self, tmp_path):
        """An empty terminal/type_library would override the code defaults."""
        conf_file = str(tmp_path / "config.ini")
        bwm.write_config(
            conf_file, launcher=None, terminal=None, type_library=None
        )
        conf = configparser.ConfigParser()
        conf.read(conf_file)
        assert conf.get("dmenu", "dmenu_command") == "dmenu"
        assert not conf.has_option("vault", "terminal")
        assert not conf.has_option("vault", "type_library")


class TestFirstRunSetup:
    """The interactive entry point, which runs in the client."""

    def test_leaves_an_existing_config_alone(self, tmp_path):
        conf_file = tmp_path / "config.ini"
        conf_file.write_text("[dmenu]\ndmenu_command = wofi\n")
        first_run_setup(str(conf_file))
        assert conf_file.read_text() == "[dmenu]\ndmenu_command = wofi\n"

    def test_writes_a_config_when_there_is_none(self, tmp_path, capsys):
        conf_file = tmp_path / "config.ini"
        with mock.patch.object(
            firstrun, "which", installed("rofi", "xterm")
        ), mock.patch.object(firstrun, "has_tty", return_value=False):
            first_run_setup(str(conf_file))
        capsys.readouterr()
        conf = configparser.ConfigParser()
        conf.read(str(conf_file))
        assert conf.get("dmenu", "dmenu_command") == "rofi"
        assert conf.get("vault", "terminal") == "xterm"


    def test_ctrl_c_writes_nothing(self, tmp_path, capsys):
        conf_file = tmp_path / "config.ini"
        with mock.patch(
            "bwm.__main__.detect", side_effect=KeyboardInterrupt
        ), pytest.raises(SystemExit) as exc:
            first_run_setup(str(conf_file))
        assert exc.value.code == 1
        assert not conf_file.exists()
        assert "cancelled" in capsys.readouterr().err


class TestBwCliCheck:
    """bwm runs every vault operation through the Bitwarden CLI."""

    def test_message_only_when_missing(self):
        with mock.patch.object(firstrun, "which", installed("bw")):
            assert firstrun.bw_cli_missing_msg() is None
        with mock.patch.object(firstrun, "which", installed()):
            assert "bw" in firstrun.bw_cli_missing_msg()

# vim: set et ts=4 sw=4 :
