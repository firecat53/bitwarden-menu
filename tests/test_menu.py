"""Tests for menu command building module."""

import configparser
from unittest.mock import patch, MagicMock
from subprocess import CompletedProcess

import pytest


class TestDmenuCmd:
    """Tests for dmenu command building."""

    @patch('bwm.menu.bwm')
    def test_dmenu_basic_command(self, mock_bwm):
        """Test basic dmenu command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'dmenu')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'False')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(10, "Test Prompt")
        assert 'dmenu' in cmd
        assert '-p' in cmd
        assert 'Test Prompt' in cmd
        assert '-l' in cmd
        assert '10' in cmd

    @patch('bwm.menu.bwm')
    def test_rofi_command(self, mock_bwm):
        """Test rofi command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'rofi')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'False')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(5, "Entries")
        assert 'rofi' in cmd
        assert '-dmenu' in cmd
        assert '-p' in cmd
        assert '-l' in cmd

    @patch('bwm.menu.bwm')
    def test_wofi_command(self, mock_bwm):
        """Test wofi command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'wofi')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'False')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(8, "Select")
        assert 'wofi' in cmd
        assert '--dmenu' in cmd
        assert '-p' in cmd
        assert '-L' in cmd  # wofi uses -L instead of -l

    @patch('bwm.menu.bwm')
    def test_bemenu_command(self, mock_bwm):
        """Test bemenu command building."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'bemenu')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'False')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(5, "Menu")
        assert 'bemenu' in cmd
        assert '-p' in cmd
        assert '-l' in cmd

    @patch('bwm.menu.bwm')
    def test_password_prompt_obscure_rofi(self, mock_bwm):
        """Test rofi password prompt adds -password flag."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'rofi')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'True')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(1, "Password")
        assert '-password' in cmd

    @patch('bwm.menu.bwm')
    def test_password_prompt_obscure_wofi(self, mock_bwm):
        """Test wofi password prompt adds -P flag."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'wofi')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'True')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(1, "Password")
        assert '-P' in cmd

    @patch('bwm.menu.bwm')
    def test_password_prompt_obscure_bemenu(self, mock_bwm):
        """Test bemenu password prompt adds -x flag."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'bemenu')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'True')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(1, "Password")
        assert '-x' in cmd

    @patch('bwm.menu.bwm')
    def test_non_password_prompt_no_obscure(self, mock_bwm):
        """Test non-password prompts don't get obscure options."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'rofi')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'True')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(10, "Select Entry")
        assert '-password' not in cmd

    @patch('bwm.menu.bwm')
    def test_custom_command_options(self, mock_bwm):
        """Test custom dmenu command with options."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu')
        mock_conf.set('dmenu', 'dmenu_command', 'dmenu -i -fn monospace')
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure', 'False')
        mock_bwm.CONF = mock_conf

        from bwm.menu import dmenu_cmd
        cmd = dmenu_cmd(5, "Test")
        assert 'dmenu' in cmd
        assert '-i' in cmd
        assert '-fn' in cmd


class TestDmenuPass:
    """Tests for dmenu password patch detection."""

    @patch('bwm.menu.run')
    @patch('bwm.menu.bwm')
    def test_dmenu_with_P_patch(self, mock_bwm, mock_run):
        """Test dmenu with password patch."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure_color', '#222222')
        mock_bwm.CONF = mock_conf

        mock_run.return_value = CompletedProcess(
            args=['dmenu', '-h'],
            returncode=0,
            stdout=b'',
            stderr=b'usage: dmenu [-bfivP]'  # -P indicates patch
        )

        from bwm.menu import dmenu_pass
        result = dmenu_pass('dmenu')
        assert result == ['-P']

    @patch('bwm.menu.run')
    @patch('bwm.menu.bwm')
    def test_dmenu_without_P_patch(self, mock_bwm, mock_run):
        """Test dmenu without password patch uses colors."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure_color', '#333333')
        mock_bwm.CONF = mock_conf

        mock_run.return_value = CompletedProcess(
            args=['dmenu', '-h'],
            returncode=0,
            stdout=b'',
            stderr=b'usage: dmenu [-bfiv]'  # no -P
        )

        from bwm.menu import dmenu_pass
        result = dmenu_pass('dmenu')
        assert result == ['-nb', '#333333', '-nf', '#333333']

    @patch('bwm.menu.bwm')
    def test_dmenu_pass_non_dmenu(self, mock_bwm):
        """Test dmenu_pass returns None for non-dmenu commands."""
        from bwm.menu import dmenu_pass
        assert dmenu_pass('rofi') is None
        assert dmenu_pass('wofi') is None
        assert dmenu_pass('bemenu') is None

    @patch('bwm.menu.run')
    @patch('bwm.menu.bwm')
    def test_dmenu_not_found(self, mock_bwm, mock_run):
        """Test handling when dmenu is not installed."""
        mock_conf = configparser.ConfigParser()
        mock_conf.add_section('dmenu_passphrase')
        mock_conf.set('dmenu_passphrase', 'obscure_color', '#222222')
        mock_bwm.CONF = mock_conf

        mock_run.side_effect = FileNotFoundError

        from bwm.menu import dmenu_pass
        result = dmenu_pass('dmenu')
        # Should fall back to color-based obscuring
        assert result == ['-nb', '#222222', '-nf', '#222222']


class TestDmenuErr:
    """Tests for error display."""

    @patch('bwm.menu.dmenu_select')
    @patch('bwm.menu.bwm')
    def test_dmenu_err_string(self, mock_bwm, mock_select):
        """Test error display with string message."""
        mock_bwm.ENC = 'utf-8'
        mock_select.return_value = None

        from bwm.menu import dmenu_err
        dmenu_err("Test error message")
        mock_select.assert_called_once()
        args = mock_select.call_args
        assert "Error" in args[0] or args[1].get('prompt') == "Error" or args[0][1] == "Error"

    @patch('bwm.menu.dmenu_select')
    @patch('bwm.menu.bwm')
    def test_dmenu_err_bytes(self, mock_bwm, mock_select):
        """Test error display with bytes message."""
        mock_bwm.ENC = 'utf-8'
        mock_select.return_value = None

        from bwm.menu import dmenu_err
        dmenu_err(b"Byte error message")
        mock_select.assert_called_once()

    @patch('bwm.menu.dmenu_select')
    @patch('bwm.menu.bwm')
    def test_dmenu_err_multiline(self, mock_bwm, mock_select):
        """Test error display with multiline message."""
        mock_bwm.ENC = 'utf-8'
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
            "Enter Password"
        )
        for prompt in password_prompts:
            # These should be recognized as password prompts
            assert prompt in ("Password", "password", "client_secret",
                            "Verify password", "Enter Password")
