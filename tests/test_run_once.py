"""Tests for entry search and field extraction (--show/--field)."""

import pytest

import bwm
from bwm.run_once import (
    custom_fields,
    entry_fields,
    get_field,
    list_fields,
    normalize_field,
    search_entries,
    show_fields,
)


@pytest.fixture(autouse=True)
def reset_cli_mode(monkeypatch):
    """run_once() sets bwm.CLI globally; don't let it leak between tests."""
    monkeypatch.setattr(bwm, "CLI", False)


class TestNormalizeField:
    """Field names are forgiving, except custom fields."""

    def test_token_names(self):
        for name in (
            "title",
            "username",
            "url",
            "password",
            "notes",
            "cardnum",
            "totp",
        ):
            assert normalize_field(name) == name

    def test_case_and_separator_insensitive(self):
        for name in (
            "Security Code",
            "security code",
            "security_code",
            "security-code",
            "securitycode",
            "SECURITYCODE",
            "  Security Code  ",
        ):
            assert normalize_field(name) == "security code"

    def test_braces_optional(self):
        assert normalize_field("{PASSWORD}") == "password"
        assert normalize_field("{password}") == "password"

    def test_per_type_fields(self):
        assert normalize_field("expiration month") == "expiration month"
        assert normalize_field("ssn") == "ssn"
        assert normalize_field("first name") == "first name"
        assert normalize_field("cardholder name") == "cardholder name"

    def test_all(self):
        assert normalize_field("all") == "all"
        assert normalize_field("ALL") == "all"

    def test_custom_fields_stay_exact(self):
        """S:<name> is case sensitive - the user chose that name."""
        assert normalize_field("S:Recovery Code") == "S:Recovery Code"
        assert normalize_field("s:Recovery Code") == "S:Recovery Code"
        assert normalize_field("{S:Recovery Code}") == "S:Recovery Code"

    def test_unknown_field(self):
        for name in ("bogus", "", "S:", "{}"):
            with pytest.raises(ValueError):
                normalize_field(name)

    def test_error_names_valid_fields(self):
        with pytest.raises(ValueError, match="security code"):
            normalize_field("bogus")


class TestTitleCollision:
    """`title` is the entry name on every type, including identities."""

    def test_title_is_entry_name(self, sample_identity_entry):
        assert normalize_field("title") == "title"
        assert get_field(sample_identity_entry, "title") == "Test Identity"

    def test_honorific_has_its_own_name(self, sample_identity_entry):
        assert normalize_field("identity title") == "identity title"
        assert get_field(sample_identity_entry, "identity title") == "Mr"

    def test_honorific_appears_in_all(self, sample_identity_entry):
        labels = list_fields(sample_identity_entry)
        assert "title" in labels
        assert "identity title" in labels


class TestGetField:
    """Every field of every entry type is reachable."""

    def test_login_fields(self, sample_login_entry):
        assert get_field(sample_login_entry, "title") == "Test Login"
        assert get_field(sample_login_entry, "username") == "testuser"
        assert get_field(sample_login_entry, "password") == "testpass123"
        assert get_field(sample_login_entry, "url") == "https://example.com"
        assert get_field(sample_login_entry, "notes") == "Test notes"

    def test_login_totp_is_generated(self, sample_login_entry):
        totp = get_field(sample_login_entry, "totp")
        assert totp.isdigit() and len(totp) == 6

    def test_card_fields_including_cvv(self, sample_card_entry):
        """The CVV is entry['card']['code'], reachable as 'security code'."""
        assert get_field(sample_card_entry, "security code") == "123"
        assert get_field(sample_card_entry, "number") == "4111111111111111"
        assert get_field(sample_card_entry, "cardnum") == "4111111111111111"
        assert get_field(sample_card_entry, "expiration month") == "12"
        assert get_field(sample_card_entry, "expiration year") == "2025"
        assert get_field(sample_card_entry, "cardholder name") == "John Doe"
        assert get_field(sample_card_entry, "brand") == "Visa"

    def test_identity_fields(self, sample_identity_entry):
        assert get_field(sample_identity_entry, "ssn") == "123-45-6789"
        assert get_field(sample_identity_entry, "first name") == "John"
        assert get_field(sample_identity_entry, "last name") == "Public"
        assert get_field(sample_identity_entry, "email") == "john@example.com"
        assert get_field(sample_identity_entry, "postal code") == "12345"

    def test_missing_field_is_empty(self, sample_card_entry):
        """A token that doesn't apply to this type returns '', not an error."""
        assert get_field(sample_card_entry, "password") == ""
        assert get_field(sample_card_entry, "totp") == ""

    def test_custom_field(self, sample_login_entry):
        sample_login_entry["fields"].append(
            {"name": "Recovery Code", "value": "abc-123", "type": 0}
        )
        assert get_field(sample_login_entry, "S:Recovery Code") == "abc-123"
        assert get_field(sample_login_entry, "S:nonexistent") == ""

    def test_autotype_pseudo_field_hidden(self, sample_login_entry):
        """'autotype' is bwm bookkeeping, not a user field."""
        assert "autotype" not in custom_fields(sample_login_entry)
        assert "S:autotype" not in entry_fields(sample_login_entry)


class TestListFields:
    """`-f all` shows only fields that have a value."""

    def test_only_non_empty(self, sample_identity_entry):
        sample_identity_entry["identity"]["address3"] = ""
        assert "address 3" not in list_fields(sample_identity_entry)
        assert "address 1" in list_fields(sample_identity_entry)

    def test_note_entry(self, sample_login_entry):
        note = dict(sample_login_entry, type=2, login=None, name="A Note")
        assert list_fields(note) == ["title", "notes"]


class TestSearchEntries:
    """Search matches folder/name, username and URL."""

    def test_by_name(self, entries, sample_folders):
        res = search_entries(entries, sample_folders, "Test Card")
        assert len(res) == 1 and res[0]["type"] == 3

    def test_by_folder_path(self, entries, sample_folders):
        res = search_entries(entries, sample_folders, "Personal/Test Login")
        assert len(res) == 1 and res[0]["name"] == "Test Login"

    def test_by_username(self, entries, sample_folders):
        res = search_entries(entries, sample_folders, "testuser")
        assert len(res) == 1 and res[0]["name"] == "Test Login"

    def test_by_url(self, entries, sample_folders):
        res = search_entries(entries, sample_folders, "example.com")
        assert len(res) == 1 and res[0]["name"] == "Test Login"

    def test_multiple_terms(self, entries, sample_folders):
        res = search_entries(entries, sample_folders, "personal login")
        assert len(res) == 1 and res[0]["name"] == "Test Login"

    def test_case_insensitive(self, entries, sample_folders):
        assert len(search_entries(entries, sample_folders, "TEST CARD")) == 1

    def test_no_match(self, entries, sample_folders):
        assert search_entries(entries, sample_folders, "nonexistent") == []

    def test_multiple_matches(self, entries, sample_folders):
        assert len(search_entries(entries, sample_folders, "Test")) == 3


class TestShowFields:
    """Output shape of --show/--field."""

    def test_defaults_to_password(self, entries, sample_folders):
        assert show_fields(entries, sample_folders, "Test Login") == (
            True,
            "testpass123",
        )

    def test_ordered_bare_values(self, entries, sample_folders):
        ok, out = show_fields(
            entries,
            sample_folders,
            "Test Login",
            fields=["password", "username"],
        )
        assert ok is True
        assert out == "testpass123\ntestuser"

    def test_all_is_labeled(self, entries, sample_folders):
        ok, out = show_fields(
            entries, sample_folders, "Test Card", fields=["all"]
        )
        assert ok is True
        assert "security code: 123" in out
        assert "title: Test Card" in out
        assert out.startswith("title: ")

    def test_no_match_error(self, entries, sample_folders):
        ok, out = show_fields(entries, sample_folders, "nonexistent")
        assert ok is False
        assert out.startswith("No entries found")

    def test_multiple_match_error_lists_them(self, entries, sample_folders):
        ok, out = show_fields(entries, sample_folders, "Test")
        assert ok is False
        assert out.startswith("Multiple entries found")
        assert "Test Card" in out and "Test Login" in out

    def test_unknown_field_error(self, entries, sample_folders):
        ok, out = show_fields(
            entries,
            sample_folders,
            "Test Login",
            fields=["bogus"],
        )
        assert ok is False
        assert out.startswith("Unknown field")

    def test_errors_are_not_printed_here(
        self, entries, sample_folders, capsys
    ):
        """show_fields reports; the caller decides where it goes.

        It runs in the daemon as often as in the client, and the daemon's
        stderr is /dev/null.

        """
        ok, _ = show_fields(entries, sample_folders, "nonexistent")
        assert ok is False
        captured = capsys.readouterr()
        assert captured.err == "" and captured.out == ""

    def test_a_value_that_looks_like_an_error_is_still_a_value(
        self, entries, sample_folders
    ):
        """A password starting with 'ERROR:' must be delivered, not reported.

        Errors used to be signalled by that prefix on the returned string, so
        such a password was indistinguishable from a failure.

        """
        entries[0]["login"]["password"] = "ERROR: not really"
        ok, out = show_fields(entries, sample_folders, "Test Login")
        assert ok is True
        assert out == "ERROR: not really"

    def test_returns_text_for_the_caller_to_deliver(
        self, entries, sample_folders
    ):
        """Clipboard handling lives in the client, not here.

        The daemon's environment has no DISPLAY/WAYLAND_DISPLAY when it was
        started from a tty, so a copy done here looks for the wrong tool.

        """
        import bwm.run_once

        ok, out = show_fields(
            entries, sample_folders, "Test Login", fields=["username"]
        )
        assert (ok, out) == (True, "testuser")
        # Not merely unused here - the module has no way to reach it
        assert not hasattr(bwm.run_once, "type_clipboard")
