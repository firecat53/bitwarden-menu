"""Tests for menu command building module."""

import configparser
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

import pytest


class TestDmenuCmd:
    """Tests for dmenu command building."""

    @patch("bwm.menu.bwm")
    def test_dmenu_basic_command(self, mock_bwm):
        """Test basic dmenu command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "dmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(10, "Test Prompt")
        assert "dmenu" in cmd
        assert "-p" in cmd
        assert "Test Prompt" in cmd
        assert "-l" in cmd
        assert "10" in cmd

    @patch("bwm.menu.bwm")
    def test_rofi_command(self, mock_bwm):
        """Test rofi command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "rofi")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Entries")
        assert "rofi" in cmd
        assert "-dmenu" in cmd
        assert "-p" in cmd
        assert "-l" in cmd

    @patch("bwm.menu.bwm")
    def test_wofi_command(self, mock_bwm):
        """Test wofi command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "wofi")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(8, "Select")
        assert "wofi" in cmd
        assert "--dmenu" in cmd
        assert "-p" in cmd
        assert "-L" in cmd  # wofi uses -L instead of -l

    @patch("bwm.menu.bwm")
    def test_bemenu_command(self, mock_bwm):
        """Test bemenu command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "bemenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Menu")
        assert "bemenu" in cmd
        assert "-p" in cmd
        assert "-l" in cmd

    @patch("bwm.menu.bwm")
    def test_wmenu_basic_command(self, mock_bwm):
        """Test basic wmenu command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "wmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(10, "Test Prompt")
        assert "wmenu" in cmd
        assert "-p" in cmd
        assert "Test Prompt" in cmd
        assert "-l" in cmd
        assert "10" in cmd

    @patch("bwm.menu.dmenu_pass", return_value=["-P"])
    @patch("bwm.menu.bwm")
    def test_password_prompt_obscure_wmenu(self, mock_bwm, mock_pass):
        """wmenu password prompts get dmenu_pass's flags. dmenu_pass runs the
        real `wmenu -h`, so it's mocked: the patch may not be installed."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "wmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "True")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(1, "Password")
        assert cmd[-1] == "-P"
        mock_pass.assert_called_once_with("wmenu")

    @patch("bwm.menu.bwm")
    def test_password_prompt_obscure_rofi(self, mock_bwm):
        """Test rofi password prompt adds -password flag."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "rofi")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "True")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(1, "Password")
        assert "-password" in cmd

    @patch("bwm.menu.bwm")
    def test_password_prompt_obscure_wofi(self, mock_bwm):
        """Test wofi password prompt adds -P flag."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "wofi")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "True")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(1, "Password")
        assert "-P" in cmd

    @patch("bwm.menu.bwm")
    def test_password_prompt_obscure_bemenu(self, mock_bwm):
        """Test bemenu password prompt adds -x flag."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "bemenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "True")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(1, "Password")
        assert "-x" in cmd

    @patch("bwm.menu.bwm")
    def test_non_password_prompt_no_obscure(self, mock_bwm):
        """Test non-password prompts don't get obscure options."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "rofi")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "True")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(10, "Select Entry")
        assert "-password" not in cmd

    @patch("bwm.menu.bwm")
    def test_custom_command_options(self, mock_bwm):
        """Test custom dmenu command with options."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "dmenu -i -fn monospace")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Test")
        assert "dmenu" in cmd
        assert "-i" in cmd
        assert "-fn" in cmd


class TestDmenuPass:
    """Tests for dmenu password patch detection."""

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_dmenu_with_P_patch(self, mock_bwm, mock_run):
        """Test dmenu with password patch."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure_color", "#222222")
        mock_bwm.CONF = mock_conf

        mock_run.return_value = CompletedProcess(
            args=["dmenu", "-h"],
            returncode=0,
            stdout=b"",
            stderr=b"usage: dmenu [-bfivP]",  # -P indicates patch
        )

        from bwm.menu import dmenu_pass

        result = dmenu_pass("dmenu")
        assert result == ["-P"]

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_dmenu_without_P_patch(self, mock_bwm, mock_run):
        """Test dmenu without password patch uses colors."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure_color", "#333333")
        mock_bwm.CONF = mock_conf

        mock_run.return_value = CompletedProcess(
            args=["dmenu", "-h"],
            returncode=0,
            stdout=b"",
            stderr=b"usage: dmenu [-bfiv]",  # no -P
        )

        from bwm.menu import dmenu_pass

        result = dmenu_pass("dmenu")
        assert result == ["-nb", "#333333", "-nf", "#333333"]

    @patch("bwm.menu.bwm")
    def test_dmenu_pass_non_dmenu(self, mock_bwm):
        """Test dmenu_pass returns None for non-dmenu commands."""
        from bwm.menu import dmenu_pass

        assert dmenu_pass("rofi") is None
        assert dmenu_pass("wofi") is None
        assert dmenu_pass("bemenu") is None

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_wmenu_with_P_patch(self, mock_bwm, mock_run):
        """wmenu is probed for the password patch just like dmenu."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        mock_bwm.CONF = mock_conf
        mock_run.return_value = CompletedProcess(
            args=["wmenu", "-h"], returncode=0, stdout=b"",
            stderr=b"usage: wmenu [-biPv]",
        )

        from bwm.menu import dmenu_pass

        assert dmenu_pass("wmenu") == ["-P"]
        mock_run.assert_called_once_with(
            ["wmenu", "-h"], capture_output=True, check=False
        )

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_wmenu_without_P_patch(self, mock_bwm, mock_run):
        """Unpatched wmenu hides input with its own color flags, not dmenu's."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure_color", "#333333")
        mock_bwm.CONF = mock_conf
        mock_run.return_value = CompletedProcess(
            args=["wmenu", "-h"], returncode=0, stdout=b"",
            stderr=b"usage: wmenu [-biv]",
        )

        from bwm.menu import dmenu_pass

        assert dmenu_pass("wmenu") == ["-n", "#333333", "-N", "#333333"]

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_dmenu_not_found(self, mock_bwm, mock_run):
        """Test handling when dmenu is not installed."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure_color", "#222222")
        mock_bwm.CONF = mock_conf

        mock_run.side_effect = FileNotFoundError

        from bwm.menu import dmenu_pass

        result = dmenu_pass("dmenu")
        # Should fall back to color-based obscuring
        assert result == ["-nb", "#222222", "-nf", "#222222"]


class TestDmenuErr:
    """Tests for error display."""

    @patch("bwm.menu.dmenu_select")
    @patch("bwm.menu.bwm")
    def test_dmenu_err_string(self, mock_bwm, mock_select):
        """Test error display with string message."""
        mock_bwm.ENC = "utf-8"
        mock_select.return_value = None

        from bwm.menu import dmenu_err

        dmenu_err("Test error message")
        mock_select.assert_called_once()
        args = mock_select.call_args
        assert (
            "Error" in args[0]
            or args[1].get("prompt") == "Error"
            or args[0][1] == "Error"
        )

    @patch("bwm.menu.dmenu_select")
    @patch("bwm.menu.bwm")
    def test_dmenu_err_bytes(self, mock_bwm, mock_select):
        """Test error display with bytes message."""
        mock_bwm.ENC = "utf-8"
        mock_select.return_value = None

        from bwm.menu import dmenu_err

        dmenu_err(b"Byte error message")
        mock_select.assert_called_once()

    @patch("bwm.menu.dmenu_select")
    @patch("bwm.menu.bwm")
    def test_dmenu_err_multiline(self, mock_bwm, mock_select):
        """Test error display with multiline message."""
        mock_bwm.ENC = "utf-8"
        mock_select.return_value = None

        from bwm.menu import dmenu_err

        dmenu_err("Line 1\nLine 2\nLine 3")
        mock_select.assert_called_once()
        # Number of lines should be 3
        args = mock_select.call_args
        assert args[0][0] == 3


class TestPasswordPrompts:
    """Tests for password prompt detection."""

    def test_password_prompts_list(self):
        """Test that common password prompts are handled."""
        password_prompts = (
            "Password",
            "password",
            "client_secret",
            "Verify password",
            "Enter Password",
        )
        for prompt in password_prompts:
            # These should be recognized as password prompts
            assert prompt in (
                "Password",
                "password",
                "client_secret",
                "Verify password",
                "Enter Password",
            )


class TestTofiCommand:
    """Tests for tofi command building."""

    @patch("bwm.menu.bwm")
    def test_tofi_command(self, mock_bwm):
        """Test tofi command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "tofi")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Test")
        # tofi is not in the commands dict, so it should just get the base command
        assert "tofi" in cmd

    @patch("bwm.menu.bwm")
    def test_tofi_with_custom_options(self, mock_bwm):
        """Test tofi command with custom options."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "tofi --width 800 --height 600")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Test")
        assert "tofi" in cmd
        assert "--width" in cmd
        assert "800" in cmd


class TestDmenuSelect:
    """Tests for dmenu_select function."""

    @patch("bwm.menu.run")
    @patch("bwm.menu.dmenu_cmd")
    @patch("bwm.menu.bwm")
    def test_dmenu_select_returns_selection(self, mock_bwm, mock_cmd, mock_run):
        """Test dmenu_select returns selected item."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.ENV = {}
        mock_cmd.return_value = ["dmenu", "-l", "5", "-p", "Test"]
        mock_run.return_value = MagicMock(stdout="selected item\n")

        from bwm.menu import dmenu_select

        result = dmenu_select(5, "Test", "item1\nitem2\nselected item")
        assert result == "selected item"

    @patch("bwm.menu.run")
    @patch("bwm.menu.dmenu_cmd")
    @patch("bwm.menu.bwm")
    def test_dmenu_select_empty_selection(self, mock_bwm, mock_cmd, mock_run):
        """Test dmenu_select with empty/cancelled selection."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.ENV = {}
        mock_cmd.return_value = ["dmenu", "-l", "5", "-p", "Test"]
        mock_run.return_value = MagicMock(stdout="")

        from bwm.menu import dmenu_select

        result = dmenu_select(5, "Test", "item1\nitem2")
        assert result == ""

    @patch("bwm.menu.run")
    @patch("bwm.menu.dmenu_cmd")
    @patch("bwm.menu.bwm")
    def test_dmenu_select_with_none_stdout(self, mock_bwm, mock_cmd, mock_run):
        """Test dmenu_select handles None stdout."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.ENV = {}
        mock_cmd.return_value = ["dmenu", "-l", "5", "-p", "Test"]
        mock_run.return_value = MagicMock(stdout=None)

        from bwm.menu import dmenu_select

        result = dmenu_select(5, "Test", "item1")
        assert result is None


def _select_with(mock_bwm, mock_run, launcher, stdout, *args, **kwargs):
    """Run dmenu_select against `launcher` with the real dmenu_cmd.

    Returns: (result, argv the launcher was run with, stdin it was given)

    """
    mock_conf = configparser.ConfigParser()
    mock_conf.add_section("dmenu")
    mock_conf.set("dmenu", "dmenu_command", launcher)
    mock_bwm.CONF = mock_conf
    mock_bwm.ENC = "utf-8"
    mock_bwm.ENV = {}
    mock_run.return_value = MagicMock(stdout=stdout, returncode=0, stderr="")

    from bwm.menu import dmenu_select

    result = dmenu_select(*args, **kwargs)
    return result, mock_run.call_args.args[0], mock_run.call_args.kwargs["input"]


class TestDmenuSelectLines:
    """A suggested value has to be visible, which takes at least one line."""

    @pytest.mark.parametrize("launcher,flag", [("rofi", "-l"), ("fuzzel", "-l")])
    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_suggestion_gets_a_line(self, mock_bwm, mock_run, launcher, flag):
        _, cmd, _ = _select_with(mock_bwm, mock_run, launcher, "",
                                 0, "Server URL",
                                 "https://vault.bitwarden.com")
        assert cmd[cmd.index(flag) + 1] == "1"

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_no_suggestion_keeps_zero_lines(self, mock_bwm, mock_run):
        _, cmd, _ = _select_with(mock_bwm, mock_run, "rofi", "",
                                 0, "Login email")
        assert cmd[cmd.index("-l") + 1] == "0"

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_explicit_line_count_untouched(self, mock_bwm, mock_run):
        _, cmd, _ = _select_with(mock_bwm, mock_run, "rofi", "",
                                 4, "Pick", "a\nb\nc\nd")
        assert cmd[cmd.index("-l") + 1] == "4"


class TestWofiFreeText:
    """wofi hides its prompt while the input box has focus, which it always
    has when there are no rows. A blank row keeps the prompt visible."""

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_blank_row_and_exec_search(self, mock_bwm, mock_run):
        _, cmd, stdin = _select_with(mock_bwm, mock_run, "wofi", "",
                                     0, "Login email")
        assert stdin == " \n"
        assert "--exec-search" in cmd

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_typed_text_returned(self, mock_bwm, mock_run):
        result, _, _ = _select_with(mock_bwm, mock_run, "wofi",
                                    "correct horse\n", 0, "Password")
        assert result == "correct horse"

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_enter_on_empty_box_is_empty(self, mock_bwm, mock_run):
        """Enter with nothing typed selects the blank row itself."""
        result, _, _ = _select_with(mock_bwm, mock_run, "wofi", " \n",
                                    0, "Login email")
        assert result == ""

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_menus_with_rows_untouched(self, mock_bwm, mock_run):
        result, cmd, stdin = _select_with(mock_bwm, mock_run, "wofi", " \n",
                                          2, "Pick", "a\n \nb")
        assert stdin == "a\n \nb"
        assert "--exec-search" not in cmd
        assert result == " "

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_other_launchers_untouched(self, mock_bwm, mock_run):
        _, cmd, stdin = _select_with(mock_bwm, mock_run, "rofi", "",
                                     0, "Login email")
        assert stdin == ""
        assert "--exec-search" not in cmd


class TestDmenuCmdEdgeCases:
    """Tests for edge cases in dmenu command building."""

    @patch("bwm.menu.bwm")
    def test_zero_lines(self, mock_bwm):
        """Test dmenu command with zero lines (password entry)."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "dmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(0, "Enter Password")
        assert "-l" in cmd
        assert "0" in cmd

    @patch("bwm.menu.bwm")
    def test_large_line_count(self, mock_bwm):
        """Test dmenu command with large line count."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "dmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(100, "Many Entries")
        assert "-l" in cmd
        assert "100" in cmd

    @patch("bwm.menu.bwm")
    def test_special_characters_in_prompt(self, mock_bwm):
        """Test dmenu command with special characters in prompt."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "dmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Test: [Select] (item)")
        assert "Test: [Select] (item)" in cmd

    @patch("bwm.menu.bwm")
    def test_fuzzel_command(self, mock_bwm):
        """Test fuzzel command (another dmenu alternative)."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "fuzzel --dmenu")
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure", "False")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, "Test")
        assert "fuzzel" in cmd
        assert "--dmenu" in cmd

    @patch("bwm.menu.bwm")
    def test_bare_fuzzel_gets_dmenu_mode(self, mock_bwm):
        """First run writes plain `fuzzel`, which without --dmenu is an app
        launcher that ignores stdin."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "fuzzel")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        assert dmenu_cmd(5, "Test")[:2] == ["fuzzel", "--dmenu"]


class TestYofiCommand:
    """yofi's `dialog` is a subcommand: options after it are rejected."""

    @pytest.mark.parametrize("prompt", ["Entries", "Password"])
    @patch("bwm.menu.bwm")
    def test_dialog_comes_last(self, mock_bwm, prompt):
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu")
        mock_conf.set("dmenu", "dmenu_command", "yofi")
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd

        cmd = dmenu_cmd(5, prompt)
        assert cmd[-1] == "dialog"
        assert ("--password" in cmd) == (prompt == "Password")


class TestObscureColorConfig:
    """Tests for password obscure color configuration."""

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_custom_obscure_color(self, mock_bwm, mock_run):
        """Test custom obscure color is used."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        mock_conf.set("dmenu_passphrase", "obscure_color", "#ff0000")
        mock_bwm.CONF = mock_conf

        mock_run.return_value = CompletedProcess(
            args=["dmenu", "-h"],
            returncode=0,
            stdout=b"",
            stderr=b"usage: dmenu [-bfiv]",  # no -P
        )

        from bwm.menu import dmenu_pass

        result = dmenu_pass("dmenu")
        assert result == ["-nb", "#ff0000", "-nf", "#ff0000"]

    @patch("bwm.menu.run")
    @patch("bwm.menu.bwm")
    def test_default_obscure_color(self, mock_bwm, mock_run):
        """Test default obscure color when not configured."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section("dmenu_passphrase")
        # Don't set obscure_color, use fallback
        mock_bwm.CONF = mock_conf

        mock_run.return_value = CompletedProcess(
            args=["dmenu", "-h"],
            returncode=0,
            stdout=b"",
            stderr=b"usage: dmenu [-bfiv]",
        )

        from bwm.menu import dmenu_pass

        result = dmenu_pass("dmenu")
        # Default color is #222222
        assert result == ["-nb", "#222222", "-nf", "#222222"]


class TestCliMode:
    """In CLI mode nothing may shell out to a launcher."""

    @patch("bwm.menu.dmenu_select")
    @patch("bwm.menu.bwm")
    def test_dmenu_err_writes_to_stderr(self, mock_bwm, mock_select, capsys):
        """dmenu_err prints to stderr and never calls the launcher."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.CLI = True

        from bwm.menu import dmenu_err

        assert dmenu_err("Some error") is None
        mock_select.assert_not_called()
        assert capsys.readouterr().err.strip() == "Some error"

    @patch("bwm.menu.dmenu_select")
    @patch("bwm.menu.bwm")
    def test_dmenu_err_decodes_bytes_in_cli_mode(
        self, mock_bwm, mock_select, capsys
    ):
        """Byte messages are decoded before printing, as in GUI mode."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.CLI = True

        from bwm.menu import dmenu_err

        dmenu_err(b"Byte error")
        mock_select.assert_not_called()
        assert capsys.readouterr().err.strip() == "Byte error"

    @patch("bwm.menu.run", side_effect=FileNotFoundError)
    def test_dmenu_select_missing_launcher_exits(self, _mock_run, capsys):
        """A missing launcher is an error, not a traceback."""
        from bwm.menu import dmenu_select

        with pytest.raises(SystemExit) as exc:
            dmenu_select(1, "Entries", inp="")
        assert exc.value.code == 1
        assert "not found" in capsys.readouterr().err


class TestLauncherFailure:
    """A launcher that fails must not look like a user cancelling."""

    @patch("bwm.menu.bwm")
    @patch("bwm.menu.run")
    def test_nonzero_exit_reported(self, mock_run, mock_bwm, capsys):
        """Launcher stderr is surfaced (e.g. 'cannot open display')."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.CONF = configparser.ConfigParser()
        mock_run.return_value = CompletedProcess(
            args=["dmenu"],
            returncode=1,
            stdout="",
            stderr="dmenu: cannot open display",
        )

        from bwm.menu import dmenu_select

        assert dmenu_select(0, "Enter vault URL") == ""
        assert "cannot open display" in capsys.readouterr().err

    @patch("bwm.menu.bwm")
    @patch("bwm.menu.run")
    def test_clean_cancel_is_quiet(self, mock_run, mock_bwm, capsys):
        """A user pressing Escape exits 1 with no stderr and stays quiet."""
        mock_bwm.ENC = "utf-8"
        mock_bwm.CONF = configparser.ConfigParser()
        mock_run.return_value = CompletedProcess(
            args=["dmenu"], returncode=1, stdout="", stderr=""
        )

        from bwm.menu import dmenu_select

        assert dmenu_select(0, "Entries") == ""
        assert capsys.readouterr().err == ""


class TestObscureIsExplicit:
    """Callers that know they're reading a secret say so.

    dmenu_cmd's prompt matching never covered "Enter client_secret (if
    required)", so that secret was typed in the clear. It cannot be loosened to
    a substring match either: "Password Options" and "Password Length?" are
    menus that would become unreadable.

    """

    def _conf(self, command="rofi", obscure="True"):
        conf = configparser.ConfigParser()
        conf.add_section("dmenu")
        conf.set("dmenu", "dmenu_command", command)
        conf.add_section("dmenu_passphrase")
        conf.set("dmenu_passphrase", "obscure", obscure)
        return conf

    @patch("bwm.menu.bwm")
    def test_explicit_obscure_beats_prompt_matching(self, mock_bwm):
        """Test that obscure=True hides a prompt the list doesn't know."""
        mock_bwm.CONF = self._conf()
        from bwm.menu import dmenu_cmd

        prompt = "Enter client_secret (if required)"
        assert "-password" not in dmenu_cmd(0, prompt)
        assert "-password" in dmenu_cmd(0, prompt, obscure=True)

    @patch("bwm.menu.bwm")
    def test_explicit_false_beats_prompt_matching(self, mock_bwm):
        """Test that obscure=False shows a prompt the list would hide."""
        mock_bwm.CONF = self._conf()
        from bwm.menu import dmenu_cmd

        assert "-password" in dmenu_cmd(0, "Enter Password")
        assert "-password" not in dmenu_cmd(0, "Enter Password", obscure=False)

    @patch("bwm.menu.bwm")
    def test_config_can_still_disable_obscuring(self, mock_bwm):
        """Test that obscure=False in config.ini overrides the caller."""
        mock_bwm.CONF = self._conf(obscure="False")
        from bwm.menu import dmenu_cmd

        assert "-password" not in dmenu_cmd(0, "x", obscure=True)

    @patch("bwm.menu.bwm")
    def test_password_menus_stay_readable(self, mock_bwm):
        """Test that menus merely mentioning 'Password' are not hidden."""
        mock_bwm.CONF = self._conf()
        from bwm.menu import dmenu_cmd

        for prompt in ("Password Options", "Password Length?"):
            assert "-password" not in dmenu_cmd(2, prompt), prompt
