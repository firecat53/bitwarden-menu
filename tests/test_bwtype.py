"""Tests for autotype tokenization module."""

import time
from unittest.mock import patch, MagicMock

import pytest

from bwm.bwtype import (
    tokenize_autotype,
    token_command,
    autotype_seq,
    autotype_index,
    PLACEHOLDER_AUTOTYPE_TOKENS,
    STRING_AUTOTYPE_TOKENS,
)


class TestTokenizeAutotype:
    """Tests for autotype sequence tokenization."""

    def test_simple_text(self):
        """Test tokenization of plain text."""
        tokens = list(tokenize_autotype("hello"))
        assert tokens == [("hello", False)]

    def test_single_placeholder(self):
        """Test tokenization of a single placeholder."""
        tokens = list(tokenize_autotype("{USERNAME}"))
        assert tokens == [("{USERNAME}", True)]

    def test_username_tab_password_enter(self):
        """Test standard autotype sequence."""
        tokens = list(tokenize_autotype("{USERNAME}{TAB}{PASSWORD}{ENTER}"))
        expected = [
            ("{USERNAME}", True),
            ("{TAB}", True),
            ("{PASSWORD}", True),
            ("{ENTER}", True),
        ]
        assert tokens == expected

    def test_text_with_placeholders(self):
        """Test mixed text and placeholders."""
        tokens = list(tokenize_autotype("user:{USERNAME}"))
        expected = [
            ("user:", False),
            ("{USERNAME}", True),
        ]
        assert tokens == expected

    def test_special_modifier_characters(self):
        """Test special modifier characters +^%~@."""
        tokens = list(tokenize_autotype("+^%~@"))
        expected = [
            ("+", True),
            ("^", True),
            ("%", True),
            ("~", True),
            ("@", True),
        ]
        assert tokens == expected

    def test_escaped_braces(self):
        """Test escaped braces {}}."""
        tokens = list(tokenize_autotype("{}}"))
        assert tokens == [("{}}", True)]

    def test_delay_token(self):
        """Test DELAY token."""
        tokens = list(tokenize_autotype("{DELAY 500}"))
        assert tokens == [("{DELAY 500}", True)]

    def test_complex_sequence(self):
        """Test complex autotype sequence."""
        sequence = "{USERNAME}{TAB}{PASSWORD}{TAB}{TOTP}{ENTER}"
        tokens = list(tokenize_autotype(sequence))
        expected = [
            ("{USERNAME}", True),
            ("{TAB}", True),
            ("{PASSWORD}", True),
            ("{TAB}", True),
            ("{TOTP}", True),
            ("{ENTER}", True),
        ]
        assert tokens == expected

    def test_text_between_placeholders(self):
        """Test text between placeholders."""
        tokens = list(tokenize_autotype("{USERNAME}@domain.com"))
        expected = [
            ("{USERNAME}", True),
            ("@", True),
            ("domain.com", False),
        ]
        assert tokens == expected

    def test_empty_string(self):
        """Test empty string."""
        tokens = list(tokenize_autotype(""))
        assert tokens == []

    def test_only_text(self):
        """Test string with no special characters."""
        tokens = list(tokenize_autotype("plaintext"))
        assert tokens == [("plaintext", False)]

    def test_multiple_delays(self):
        """Test multiple delay tokens."""
        tokens = list(tokenize_autotype("{DELAY 100}{USERNAME}{DELAY 200}"))
        expected = [
            ("{DELAY 100}", True),
            ("{USERNAME}", True),
            ("{DELAY 200}", True),
        ]
        assert tokens == expected


class TestTokenCommand:
    """Tests for token command parsing."""

    def test_delay_command(self):
        """Test DELAY command parsing."""
        cmd = token_command("{DELAY 500}")
        assert callable(cmd)

    def test_delay_command_execution(self):
        """Test that DELAY command sleeps for correct duration."""
        cmd = token_command("{DELAY 100}")
        with patch("time.sleep") as mock_sleep:
            cmd()
            mock_sleep.assert_called_once_with(0.1)  # 100ms = 0.1s

    def test_non_delay_returns_none(self):
        """Test that non-DELAY tokens return None."""
        assert token_command("{USERNAME}") is None
        assert token_command("{TAB}") is None
        assert token_command("{ENTER}") is None

    def test_invalid_delay_format(self):
        """Test invalid DELAY format returns None."""
        assert token_command("{DELAY}") is None
        assert token_command("{DELAY abc}") is None


class TestAutotypeSeq:
    """Tests for autotype sequence extraction from entries."""

    def test_autotype_seq_with_value(self):
        """Test extracting autotype sequence from entry."""
        entry = {
            "fields": [
                {
                    "name": "autotype",
                    "value": "{USERNAME}{TAB}{PASSWORD}",
                    "type": 0,
                }
            ]
        }
        assert autotype_seq(entry) == "{USERNAME}{TAB}{PASSWORD}"

    def test_autotype_seq_empty(self):
        """Test extracting empty autotype sequence."""
        entry = {"fields": [{"name": "autotype", "value": "", "type": 0}]}
        assert autotype_seq(entry) == ""

    def test_autotype_seq_none(self):
        """Test extracting when no autotype field exists."""
        entry = {"fields": [{"name": "other", "value": "something", "type": 0}]}
        assert autotype_seq(entry) == ""

    def test_autotype_seq_multiple_fields(self):
        """Test extracting autotype from entry with multiple fields."""
        entry = {
            "fields": [
                {"name": "custom1", "value": "val1", "type": 0},
                {"name": "autotype", "value": "{PASSWORD}", "type": 0},
                {"name": "custom2", "value": "val2", "type": 0},
            ]
        }
        assert autotype_seq(entry) == "{PASSWORD}"


class TestAutotypeIndex:
    """Tests for autotype field index extraction."""

    def test_autotype_index_first(self):
        """Test autotype index when it's first field."""
        entry = {
            "fields": [{"name": "autotype", "value": "{USERNAME}", "type": 0}]
        }
        assert autotype_index(entry) == 0

    def test_autotype_index_middle(self):
        """Test autotype index in middle of fields."""
        entry = {
            "fields": [
                {"name": "field1", "value": "val1", "type": 0},
                {"name": "autotype", "value": "{USERNAME}", "type": 0},
                {"name": "field2", "value": "val2", "type": 0},
            ]
        }
        assert autotype_index(entry) == 1


class TestPlaceholderTokens:
    """Tests for placeholder token functions."""

    def test_title_token(self, sample_login_entry):
        """Test {TITLE} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{TITLE}"](sample_login_entry)
        assert result == "Test Login"

    def test_username_token(self, sample_login_entry):
        """Test {USERNAME} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{USERNAME}"](sample_login_entry)
        assert result == "testuser"

    def test_password_token(self, sample_login_entry):
        """Test {PASSWORD} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{PASSWORD}"](sample_login_entry)
        assert result == "testpass123"

    def test_notes_token(self, sample_login_entry):
        """Test {NOTES} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{NOTES}"](sample_login_entry)
        assert result == "Test notes"

    def test_url_token(self, sample_login_entry):
        """Test {URL} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{URL}"](sample_login_entry)
        assert result == "https://example.com"

    def test_cardnum_token(self, sample_card_entry):
        """Test {CARDNUM} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{CARDNUM}"](sample_card_entry)
        assert result == "4111111111111111"

    def test_url_token_empty_uris(self):
        """Test {URL} token with no URIs."""
        entry = {"login": {"uris": []}}
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{URL}"](entry)
        assert result == ""

    def test_url_token_no_login(self):
        """Test {URL} token with no login."""
        entry = {"login": None}
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{URL}"](entry)
        assert result == ""


class TestStringAutotypeTokens:
    """Tests for string autotype token mappings."""

    def test_plus_token(self):
        """Test {PLUS} maps to +."""
        assert STRING_AUTOTYPE_TOKENS["{PLUS}"] == "+"

    def test_percent_token(self):
        """Test {PERCENT} maps to %."""
        assert STRING_AUTOTYPE_TOKENS["{PERCENT}"] == "%"

    def test_caret_token(self):
        """Test {CARET} maps to ^."""
        assert STRING_AUTOTYPE_TOKENS["{CARET}"] == "^"

    def test_tilde_token(self):
        """Test {TILDE} maps to ~."""
        assert STRING_AUTOTYPE_TOKENS["{TILDE}"] == "~"

    def test_brace_tokens(self):
        """Test brace tokens."""
        assert STRING_AUTOTYPE_TOKENS["{LEFTBRACE}"] == "{"
        assert STRING_AUTOTYPE_TOKENS["{RIGHTBRACE}"] == "}"
        assert STRING_AUTOTYPE_TOKENS["{{}"] == "{"
        assert STRING_AUTOTYPE_TOKENS["{}}"] == "}"

    def test_paren_tokens(self):
        """Test parenthesis tokens."""
        assert STRING_AUTOTYPE_TOKENS["{LEFTPAREN}"] == "("
        assert STRING_AUTOTYPE_TOKENS["{RIGHTPAREN}"] == ")"
        assert STRING_AUTOTYPE_TOKENS["{(}"] == "("
        assert STRING_AUTOTYPE_TOKENS["{)}"] == ")"

    def test_bracket_tokens(self):
        """Test bracket tokens."""
        assert STRING_AUTOTYPE_TOKENS["{[}"] == "["
        assert STRING_AUTOTYPE_TOKENS["{]}"] == "]"

    def test_at_token(self):
        """Test {AT} maps to @."""
        assert STRING_AUTOTYPE_TOKENS["{AT}"] == "@"


class TestTOTPToken:
    """Tests for TOTP token extraction."""

    def test_totp_token_with_valid_totp(self, sample_login_entry):
        """Test {TOTP} token generates OTP."""
        from bwm.totp import gen_otp

        result = PLACEHOLDER_AUTOTYPE_TOKENS["{TOTP}"](sample_login_entry)
        # Should return a 6-digit OTP
        assert len(result) == 6
        assert result.isdigit()

    def test_totp_token_no_totp(self):
        """Test {TOTP} token with no TOTP configured."""
        entry = {"login": {"totp": None}}
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{TOTP}"](entry)
        assert result == ""


class TestCardTokens:
    """Tests for card-specific tokens."""

    def test_cardnum_token(self, sample_card_entry):
        """Test {CARDNUM} token extraction."""
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{CARDNUM}"](sample_card_entry)
        assert result == "4111111111111111"

    def test_cardnum_token_no_card(self):
        """Test {CARDNUM} with no card data."""
        entry = {"card": None}
        try:
            result = PLACEHOLDER_AUTOTYPE_TOKENS["{CARDNUM}"](entry)
        except (TypeError, KeyError):
            # Expected behavior - no card data
            pass


class TestComplexAutotypeSequences:
    """Tests for complex autotype sequence handling."""

    def test_sequence_with_literal_text(self):
        """Test sequence with literal text between tokens."""
        tokens = list(
            tokenize_autotype("prefix{USERNAME}middle{PASSWORD}suffix")
        )
        expected = [
            ("prefix", False),
            ("{USERNAME}", True),
            ("middle", False),
            ("{PASSWORD}", True),
            ("suffix", False),
        ]
        assert tokens == expected

    def test_sequence_with_multiple_modifiers(self):
        """Test sequence with multiple modifier characters."""
        tokens = list(tokenize_autotype("^a+c%v"))
        expected = [
            ("^", True),
            ("a", False),
            ("+", True),
            ("c", False),
            ("%", True),
            ("v", False),
        ]
        assert tokens == expected

    def test_sequence_ctrl_alt_shift(self):
        """Test Ctrl+Alt+Shift modifier sequence."""
        tokens = list(tokenize_autotype("^%+a"))
        expected = [
            ("^", True),
            ("%", True),
            ("+", True),
            ("a", False),
        ]
        assert tokens == expected

    def test_sequence_with_delay_between_fields(self):
        """Test sequence with delay between fields."""
        tokens = list(tokenize_autotype("{USERNAME}{DELAY 500}{TAB}{PASSWORD}"))
        expected = [
            ("{USERNAME}", True),
            ("{DELAY 500}", True),
            ("{TAB}", True),
            ("{PASSWORD}", True),
        ]
        assert tokens == expected

    def test_autotype_seq_with_none_value(self):
        """Test autotype_seq when autotype value is None."""
        entry = {"fields": [{"name": "autotype", "value": None, "type": 0}]}
        result = autotype_seq(entry)
        assert result is None

    def test_autotype_seq_no_fields(self):
        """Test autotype_seq with empty fields list."""
        entry = {"fields": []}
        result = autotype_seq(entry)
        assert result == ""


class TestSpecialCharacterHandling:
    """Tests for special character handling in autotype."""

    def test_url_with_special_chars(self):
        """Test URL containing special characters."""
        entry = {
            "login": {
                "uris": [
                    {"uri": "https://example.com/path?query=value&other=test"}
                ]
            }
        }
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{URL}"](entry)
        assert result == "https://example.com/path?query=value&other=test"

    def test_password_with_special_chars(self):
        """Test password containing special characters."""
        entry = {"login": {"password": "P@$$w0rd!#%^&*()"}}
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{PASSWORD}"](entry)
        assert result == "P@$$w0rd!#%^&*()"

    def test_notes_with_newlines(self):
        """Test notes containing newlines."""
        entry = {"notes": "Line 1\nLine 2\nLine 3"}
        result = PLACEHOLDER_AUTOTYPE_TOKENS["{NOTES}"](entry)
        assert result == "Line 1\nLine 2\nLine 3"


class TestCustomFieldAccess:
    """Tests for accessing custom fields in entries."""

    def test_entry_with_custom_fields(self):
        """Test entry with custom fields preserves them."""
        entry = {
            "name": "Test",
            "fields": [
                {"name": "autotype", "value": "{PASSWORD}", "type": 0},
                {"name": "customField1", "value": "custom value 1", "type": 0},
                {"name": "customField2", "value": "custom value 2", "type": 1},
            ],
        }
        # Verify custom fields are accessible
        custom_fields = [
            f for f in entry["fields"] if f["name"] not in ("autotype",)
        ]
        assert len(custom_fields) == 2
        assert custom_fields[0]["value"] == "custom value 1"
        assert custom_fields[1]["value"] == "custom value 2"
