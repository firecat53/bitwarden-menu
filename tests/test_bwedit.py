"""Tests for password generation and editing utilities."""

import string
from unittest.mock import patch, MagicMock

import pytest

from bwm.bwedit import gen_passwd, get_password_chars, obj_name


class TestGenPasswd:
    """Tests for password generation."""

    def test_gen_passwd_default_length(self):
        """Test password generation with default length."""
        chars = {
            "Letters+Digits": {
                "upper": string.ascii_uppercase,
                "lower": string.ascii_lowercase,
                "digits": string.digits,
            }
        }
        password = gen_passwd(chars)
        assert password is not False
        assert len(password) == 20

    def test_gen_passwd_custom_length(self):
        """Test password generation with custom length."""
        chars = {
            "Letters": {
                "upper": string.ascii_uppercase,
                "lower": string.ascii_lowercase,
            }
        }
        password = gen_passwd(chars, length=30)
        assert password is not False
        assert len(password) == 30

    def test_gen_passwd_minimum_length(self):
        """Test that password length must be >= number of character sets."""
        chars = {
            "preset": {
                "upper": string.ascii_uppercase,
                "lower": string.ascii_lowercase,
                "digits": string.digits,
                "punct": string.punctuation,
            }
        }
        # 4 character sets, so minimum length is 4
        password = gen_passwd(chars, length=4)
        assert password is not False
        assert len(password) == 4

    def test_gen_passwd_too_short(self):
        """Test that password generation fails when length is too short."""
        chars = {
            "preset": {
                "upper": string.ascii_uppercase,
                "lower": string.ascii_lowercase,
                "digits": string.digits,
                "punct": string.punctuation,
            }
        }
        # 4 sets but only 3 chars requested - should fail
        password = gen_passwd(chars, length=3)
        assert password is False

    def test_gen_passwd_empty_chars(self):
        """Test password generation with empty character dict."""
        password = gen_passwd({})
        assert password is False

    def test_gen_passwd_contains_required_sets(self):
        """Test that password contains at least one char from each set."""
        chars = {
            "preset": {
                "upper": "ABC",
                "lower": "xyz",
                "digits": "123",
            }
        }
        # Generate multiple passwords to verify sets
        for _ in range(10):
            password = gen_passwd(chars, length=10)
            assert password is not False
            has_upper = any(c in "ABC" for c in password)
            has_lower = any(c in "xyz" for c in password)
            has_digit = any(c in "123" for c in password)
            assert has_upper and has_lower and has_digit

    def test_gen_passwd_digits_only(self):
        """Test password generation with digits only."""
        chars = {
            "Digits": {
                "digits": string.digits,
            }
        }
        password = gen_passwd(chars, length=10)
        assert password is not False
        assert len(password) == 10
        assert all(c in string.digits for c in password)

    def test_gen_passwd_letters_only(self):
        """Test password generation with letters only."""
        chars = {
            "Letters": {
                "upper": string.ascii_uppercase,
                "lower": string.ascii_lowercase,
            }
        }
        password = gen_passwd(chars, length=15)
        assert password is not False
        assert len(password) == 15
        assert all(c in string.ascii_letters for c in password)

    def test_gen_passwd_multiple_presets(self):
        """Test password generation with multiple presets (union of chars)."""
        chars = {
            "preset1": {
                "upper": "ABC",
            },
            "preset2": {
                "lower": "xyz",
            },
        }
        password = gen_passwd(chars, length=10)
        assert password is not False
        # Password should contain chars from both presets
        all_chars = "ABCxyz"
        assert all(c in all_chars for c in password)

    def test_gen_passwd_randomness(self):
        """Test that passwords are randomized."""
        chars = {
            "preset": {
                "lower": string.ascii_lowercase,
            }
        }
        passwords = set()
        for _ in range(10):
            pw = gen_passwd(chars, length=20)
            passwords.add(pw)
        # Should have multiple unique passwords
        assert len(passwords) > 1


class TestObjName:
    """Tests for object name extraction."""

    def test_obj_name_folder(self, sample_folders):
        """Test extracting folder name by ID."""
        name = obj_name(sample_folders, "folder-id-1")
        assert name == "Personal"

    def test_obj_name_nested_folder(self, sample_folders):
        """Test extracting nested folder name."""
        name = obj_name(sample_folders, "folder-id-3")
        assert name == "Work/Projects"

    def test_obj_name_collection(self, sample_collections):
        """Test extracting collection name by ID."""
        name = obj_name(sample_collections, "coll-id-1")
        assert name == "Team Collection"

    def test_obj_name_no_folder(self, sample_folders):
        """Test extracting name for 'No Folder'."""
        name = obj_name(sample_folders, None)
        assert name == "No Folder"


class TestGetPasswordChars:
    """Tests for get_password_chars function."""

    @patch("bwm.bwedit.dmenu_select")
    @patch("bwm.bwedit.bwm")
    def test_get_password_chars_default(self, mock_bwm, mock_select):
        """Test getting default password characters."""
        mock_conf = MagicMock()
        mock_conf.has_section.return_value = False
        mock_bwm.CONF = mock_conf
        mock_select.return_value = "Letters+Digits"

        result = get_password_chars()
        # Should return selected character set
        assert isinstance(result, dict)
        assert "Letters+Digits" in result

    @patch("bwm.bwedit.dmenu_select")
    @patch("bwm.bwedit.bwm")
    def test_get_password_chars_cancelled(self, mock_bwm, mock_select):
        """Test get_password_chars returns False when cancelled."""
        mock_conf = MagicMock()
        mock_conf.has_section.return_value = False
        mock_bwm.CONF = mock_conf
        mock_select.return_value = ""

        result = get_password_chars()
        assert result is False

    @patch("bwm.bwedit.dmenu_select")
    @patch("bwm.bwedit.bwm")
    def test_get_password_chars_with_custom_config(self, mock_bwm, mock_select):
        """Test getting custom password characters from config."""
        mock_conf = MagicMock()
        mock_conf.has_section.side_effect = lambda s: s == "password_chars"
        mock_conf.items.return_value = [
            ("special", "!@#$"),
        ]
        mock_conf.options.return_value = []
        mock_bwm.CONF = mock_conf
        mock_select.return_value = "Letters"

        result = get_password_chars()
        assert isinstance(result, dict)


class TestPasswordStrength:
    """Tests for password strength characteristics."""

    def test_long_password(self):
        """Test generation of long passwords."""
        chars = {
            "All": {
                "upper": string.ascii_uppercase,
                "lower": string.ascii_lowercase,
                "digits": string.digits,
                "punct": string.punctuation,
            }
        }
        password = gen_passwd(chars, length=50)
        assert password is not False
        assert len(password) == 50

    def test_short_viable_password(self):
        """Test minimum viable password (length matches char sets)."""
        chars = {"Single": {"chars": "abc"}}
        password = gen_passwd(chars, length=1)
        assert password is not False
        assert len(password) == 1
        assert password in "abc"
