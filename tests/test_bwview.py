"""Tests for entry viewing module."""

from unittest.mock import patch, MagicMock

import pytest

from bwm.bwview import (
    obj_name,
    view_all_entries,
    view_entry,
    make_url_entries,
    view_login,
    view_note,
    view_card,
    view_ident,
    view_notes,
)


class TestObjName:
    """Tests for object name extraction."""

    def test_obj_name_regular_folder(self, sample_folders):
        """Test extracting regular folder name."""
        name = obj_name(sample_folders, "folder-id-1")
        assert name == "Personal"

    def test_obj_name_no_folder(self, sample_folders):
        """Test extracting 'No Folder' returns '/'."""
        name = obj_name(sample_folders, None)
        assert name == "/"

    def test_obj_name_nested_folder(self, sample_folders):
        """Test extracting nested folder path."""
        name = obj_name(sample_folders, "folder-id-3")
        assert name == "Work/Projects"

    def test_obj_name_collection(self, sample_collections):
        """Test extracting collection name."""
        name = obj_name(sample_collections, "coll-id-1")
        assert name == "Team Collection"


class TestMakeUrlEntries:
    """Tests for URL entry formatting."""

    def test_make_url_entries_single_url(self, sample_login_entry):
        """Test formatting single URL."""
        urls = make_url_entries(sample_login_entry)
        assert len(urls) == 1
        assert "URL1: https://example.com" in urls[0]

    def test_make_url_entries_no_login(self):
        """Test URL formatting with no login field."""
        entry = {"login": None}
        urls = make_url_entries(entry)
        assert urls == ["URL: None"]

    def test_make_url_entries_empty_uris(self):
        """Test URL formatting with empty URIs list."""
        entry = {"login": {"uris": []}}
        urls = make_url_entries(entry)
        assert urls == ["URL: None"]

    def test_make_url_entries_multiple_urls(self):
        """Test formatting multiple URLs."""
        entry = {
            "login": {
                "uris": [
                    {"uri": "https://example.com"},
                    {"uri": "https://example.org"},
                    {"uri": "https://example.net"},
                ]
            }
        }
        urls = make_url_entries(entry)
        assert len(urls) == 3
        assert "URL1: https://example.com" in urls[0]
        assert "URL2: https://example.org" in urls[1]
        assert "URL3: https://example.net" in urls[2]


class TestViewAllEntries:
    """Tests for viewing all entries."""

    @patch("bwm.bwview.dmenu_select")
    def test_view_all_entries_login(
        self, mock_select, sample_login_entry, sample_folders
    ):
        """Test viewing login entries."""
        mock_select.return_value = "0(l) - /Test Login"
        entries = [sample_login_entry]

        result = view_all_entries([], entries, sample_folders)

        mock_select.assert_called_once()
        # Check the input contains expected format
        call_kwargs = mock_select.call_args
        assert "(l)" in call_kwargs[1]["inp"]

    @patch("bwm.bwview.dmenu_select")
    def test_view_all_entries_card(
        self, mock_select, sample_card_entry, sample_folders
    ):
        """Test viewing card entries."""
        mock_select.return_value = "0(c) - /Test Card"
        entries = [sample_card_entry]

        result = view_all_entries([], entries, sample_folders)

        mock_select.assert_called_once()
        call_kwargs = mock_select.call_args
        assert "(c)" in call_kwargs[1]["inp"]

    @patch("bwm.bwview.dmenu_select")
    def test_view_all_entries_identity(
        self, mock_select, sample_identity_entry, sample_folders
    ):
        """Test viewing identity entries."""
        mock_select.return_value = "0(i) - /Test Identity"
        entries = [sample_identity_entry]

        result = view_all_entries([], entries, sample_folders)

        mock_select.assert_called_once()
        call_kwargs = mock_select.call_args
        assert "(i)" in call_kwargs[1]["inp"]

    @patch("bwm.bwview.dmenu_select")
    def test_view_all_entries_with_options(
        self, mock_select, sample_login_entry, sample_folders
    ):
        """Test viewing entries with options menu."""
        mock_select.return_value = "View/Type Individual entries"
        entries = [sample_login_entry]
        options = {"View/Type Individual entries": None, "Edit entries": None}

        result = view_all_entries(options, entries, sample_folders)

        mock_select.assert_called_once()
        call_kwargs = mock_select.call_args
        # Options should be at the top
        assert call_kwargs[1]["inp"].startswith("View/Type")


class TestViewEntry:
    """Tests for viewing individual entries."""

    @patch("bwm.bwview.view_login")
    def test_view_entry_login(
        self, mock_view, sample_login_entry, sample_folders
    ):
        """Test view_entry dispatches to view_login for type 1."""
        mock_view.return_value = "test"
        view_entry(sample_login_entry, sample_folders)
        mock_view.assert_called_once_with(sample_login_entry, sample_folders)

    @patch("bwm.bwview.view_note")
    def test_view_entry_note(self, mock_view, sample_folders):
        """Test view_entry dispatches to view_note for type 2."""
        entry = {"type": 2, "name": "Note", "notes": "test", "folderId": None}
        mock_view.return_value = "test"
        view_entry(entry, sample_folders)
        mock_view.assert_called_once()

    @patch("bwm.bwview.view_card")
    def test_view_entry_card(
        self, mock_view, sample_card_entry, sample_folders
    ):
        """Test view_entry dispatches to view_card for type 3."""
        mock_view.return_value = "test"
        view_entry(sample_card_entry, sample_folders)
        mock_view.assert_called_once_with(sample_card_entry, sample_folders)

    @patch("bwm.bwview.view_ident")
    def test_view_entry_identity(
        self, mock_view, sample_identity_entry, sample_folders
    ):
        """Test view_entry dispatches to view_ident for type 4."""
        mock_view.return_value = "test"
        view_entry(sample_identity_entry, sample_folders)
        mock_view.assert_called_once_with(sample_identity_entry, sample_folders)


class TestViewLogin:
    """Tests for viewing login entries."""

    @patch("bwm.bwview.dmenu_select")
    def test_view_login_returns_username(
        self, mock_select, sample_login_entry, sample_folders
    ):
        """Test selecting username returns username value."""
        mock_select.return_value = "Username: testuser"
        result = view_login(sample_login_entry, sample_folders)
        assert result == "testuser"

    @patch("bwm.bwview.dmenu_select")
    def test_view_login_returns_password(
        self, mock_select, sample_login_entry, sample_folders
    ):
        """Test selecting password returns actual password."""
        mock_select.return_value = "Password: **********"
        result = view_login(sample_login_entry, sample_folders)
        assert result == "testpass123"

    @patch("bwm.bwview.gen_otp")
    @patch("bwm.bwview.dmenu_select")
    def test_view_login_returns_totp(
        self, mock_select, mock_otp, sample_login_entry, sample_folders
    ):
        """Test selecting TOTP generates and returns OTP."""
        mock_select.return_value = "TOTP: ******"
        mock_otp.return_value = "123456"
        result = view_login(sample_login_entry, sample_folders)
        assert result == "123456"
        mock_otp.assert_called_once()

    @patch("bwm.bwview.dmenu_select")
    def test_view_login_none_field(
        self, mock_select, sample_login_entry, sample_folders
    ):
        """Test selecting None field returns empty string."""
        mock_select.return_value = "Something: None"
        result = view_login(sample_login_entry, sample_folders)
        assert result == ""

    @patch("bwm.bwview.webbrowser")
    @patch("bwm.bwview.dmenu_select")
    def test_view_login_opens_url(
        self, mock_select, mock_browser, sample_login_entry, sample_folders
    ):
        """Test selecting URL opens browser."""
        mock_select.return_value = "URL1: https://example.com"
        result = view_login(sample_login_entry, sample_folders)
        mock_browser.open.assert_called_once_with("https://example.com")
        assert result == ""


class TestViewNote:
    """Tests for viewing secure note entries."""

    @patch("bwm.bwview.dmenu_select")
    def test_view_note_title(self, mock_select, sample_folders):
        """Test viewing note title."""
        entry = {
            "type": 2,
            "name": "My Note",
            "notes": "Note content",
            "folderId": None,
        }
        mock_select.return_value = "Title: My Note"
        result = view_note(entry, sample_folders)
        assert result == "My Note"

    @patch("bwm.bwview.view_notes")
    @patch("bwm.bwview.dmenu_select")
    def test_view_note_content(
        self, mock_select, mock_view_notes, sample_folders
    ):
        """Test viewing note content."""
        entry = {
            "type": 2,
            "name": "My Note",
            "notes": "Note content here",
            "folderId": None,
        }
        mock_select.return_value = "Notes: <Enter to view>"
        mock_view_notes.return_value = "Selected line"
        result = view_note(entry, sample_folders)
        mock_view_notes.assert_called_once_with("Note content here")


class TestViewCard:
    """Tests for viewing card entries."""

    @patch("bwm.bwview.bwm")
    @patch("bwm.bwview.dmenu_select")
    def test_view_card_number(
        self, mock_select, mock_bwm, sample_card_entry, sample_folders
    ):
        """Test viewing card number."""
        mock_bwm.CARD = {
            "Number": "number",
            "Brand": "brand",
        }
        mock_select.return_value = "Number: 4111111111111111"
        result = view_card(sample_card_entry, sample_folders)
        assert result == "4111111111111111"

    @patch("bwm.bwview.bwm")
    @patch("bwm.bwview.dmenu_select")
    def test_view_card_brand(
        self, mock_select, mock_bwm, sample_card_entry, sample_folders
    ):
        """Test viewing card brand."""
        mock_bwm.CARD = {"Brand": "brand"}
        mock_select.return_value = "Brand: Visa"
        result = view_card(sample_card_entry, sample_folders)
        assert result == "Visa"


class TestViewIdent:
    """Tests for viewing identity entries."""

    @patch("bwm.bwview.bwm")
    @patch("bwm.bwview.dmenu_select")
    def test_view_ident_email(
        self, mock_select, mock_bwm, sample_identity_entry, sample_folders
    ):
        """Test viewing identity email."""
        mock_bwm.IDENTITY = {"Email": "email"}
        mock_select.return_value = "Email: john@example.com"
        result = view_ident(sample_identity_entry, sample_folders)
        assert result == "john@example.com"

    @patch("bwm.bwview.bwm")
    @patch("bwm.bwview.dmenu_select")
    def test_view_ident_phone(
        self, mock_select, mock_bwm, sample_identity_entry, sample_folders
    ):
        """Test viewing identity phone."""
        mock_bwm.IDENTITY = {"Phone": "phone"}
        mock_select.return_value = "Phone: 555-1234"
        result = view_ident(sample_identity_entry, sample_folders)
        assert result == "555-1234"


class TestViewNotes:
    """Tests for viewing notes field."""

    @patch("bwm.bwview.dmenu_select")
    def test_view_notes_single_line(self, mock_select):
        """Test viewing single line notes."""
        mock_select.return_value = "This is a note"
        result = view_notes("This is a note")
        assert result == "This is a note"

    @patch("bwm.bwview.dmenu_select")
    def test_view_notes_multiline(self, mock_select):
        """Test viewing multiline notes."""
        notes = "Line 1\nLine 2\nLine 3"
        mock_select.return_value = "Line 2"
        result = view_notes(notes)
        assert result == "Line 2"
        # Check that dmenu was called with correct line count
        mock_select.assert_called_once()
        call_args = mock_select.call_args
        assert call_args[1]["inp"] == notes
