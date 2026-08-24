"""Tests for TOTP generation module."""

import time
from unittest.mock import patch

import pytest

from bwm.totp import hotp, totp, gen_otp, otp_params


class TestHOTP:
    """Tests for HMAC-based OTP generation."""

    def test_hotp_basic(self):
        """Test basic HOTP generation with known values."""
        # Test vector from RFC 4226
        secret = "GEZDGNBVGY3TQOJQ"  # Base32 encoded "12345678901234567890"
        # Counter 0 should produce a valid 6-digit OTP
        result = hotp(secret, 0)
        assert len(result) == 6
        assert result.isdigit()

    def test_hotp_different_counters(self):
        """Test that different counters produce different OTPs."""
        secret = "JBSWY3DPEHPK3PXP"
        otp1 = hotp(secret, 0)
        otp2 = hotp(secret, 1)
        otp3 = hotp(secret, 2)
        # Different counters should produce different OTPs
        assert otp1 != otp2 or otp2 != otp3

    def test_hotp_custom_digits(self):
        """Test HOTP with custom digit length."""
        secret = "JBSWY3DPEHPK3PXP"
        result = hotp(secret, 0, digits=8)
        assert len(result) == 8
        assert result.isdigit()

    def test_hotp_padding(self):
        """Test HOTP with secret that needs padding."""
        # Secret without full padding
        secret = "JBSWY3DP"
        result = hotp(secret, 0)
        assert len(result) == 6

    def test_hotp_steam(self):
        """Test Steam-style HOTP generation."""
        secret = "JBSWY3DPEHPK3PXP"
        result = hotp(secret, 0, digits=5, steam=True)
        assert len(result) == 5
        # Steam tokens use alphanumeric characters
        valid_chars = "23456789BCDFGHJKMNPQRTVWXY"
        for char in result:
            assert char in valid_chars


class TestTOTP:
    """Tests for Time-based OTP generation."""

    def test_totp_basic(self):
        """Test basic TOTP generation."""
        secret = "JBSWY3DPEHPK3PXP"
        result = totp(secret)
        assert len(result) == 6
        assert result.isdigit()

    def test_totp_consistency(self):
        """Test that TOTP returns consistent value within time window."""
        secret = "JBSWY3DPEHPK3PXP"
        result1 = totp(secret)
        result2 = totp(secret)
        # Should be the same within the same time step
        assert result1 == result2

    def test_totp_custom_time_step(self):
        """Test TOTP with custom time step."""
        secret = "JBSWY3DPEHPK3PXP"
        result = totp(secret, time_step=60)
        assert len(result) == 6

    @patch("time.time")
    def test_totp_changes_over_time(self, mock_time):
        """Test that TOTP changes with different time values."""
        secret = "JBSWY3DPEHPK3PXP"

        mock_time.return_value = 0
        result1 = totp(secret)

        mock_time.return_value = 30
        result2 = totp(secret)

        # Different time steps should produce different OTPs
        assert result1 != result2


class TestGenOTP:
    """Tests for OTP generation from URL format."""

    def test_gen_otp_valid_url(self):
        """Test OTP generation from a valid otpauth URL."""
        otp_url = "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&period=30&digits=6&issuer=Test"
        result = gen_otp(otp_url)
        assert len(result) == 6
        assert result.isdigit()

    def test_gen_otp_missing_secret(self):
        """Test that a URL with no secret returns empty string."""
        otp_url = "otpauth://totp/Test:user@example.com?period=30&digits=6&issuer=Test"
        result = gen_otp(otp_url)
        assert result == ""

    def test_gen_otp_missing_period_defaults_to_30(self):
        """Test that a URL with no period uses the RFC 6238 default."""
        secret = "JBSWY3DPEHPK3PXP"
        otp_url = (
            f"otpauth://totp/Test:user@example.com?secret={secret}&digits=6"
        )
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(otp_url)
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected

    def test_gen_otp_missing_digits_defaults_to_6(self):
        """Test that a URL with no digits uses the RFC 6238 default."""
        secret = "JBSWY3DPEHPK3PXP"
        otp_url = (
            f"otpauth://totp/Test:user@example.com?secret={secret}&period=30"
        )
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(otp_url)
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected

    def test_gen_otp_secret_only(self):
        """Test a URL carrying nothing but the secret.

        The Bitwarden clients write this when the scanned QR code omits the
        optional parameters.

        """
        secret = "JBSWY3DPEHPK3PXP"
        otp_url = (
            f"otpauth://totp/Test:user@example.com?secret={secret}&issuer=Test"
        )
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(otp_url)
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected

    def test_gen_otp_unparseable_period_and_digits(self):
        """Test that junk in period/digits falls back to the defaults."""
        secret = "JBSWY3DPEHPK3PXP"
        otp_url = (
            f"otpauth://totp/Test:user@example.com?secret={secret}"
            "&period=soon&digits=lots"
        )
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(otp_url)
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected

    def test_gen_otp_steam_encoder(self):
        """Test OTP generation with steam encoder."""
        otp_url = "otpauth://totp/Steam:user?secret=JBSWY3DPEHPK3PXP&period=30&digits=5&encoder=steam"
        result = gen_otp(otp_url)
        assert len(result) == 5
        valid_chars = "23456789BCDFGHJKMNPQRTVWXY"
        for char in result:
            assert char in valid_chars

    def test_gen_otp_8_digits(self):
        """Test OTP generation with 8 digits."""
        otp_url = "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&period=30&digits=8&issuer=Test"
        result = gen_otp(otp_url)
        assert len(result) == 8
        assert result.isdigit()

    def test_gen_otp_60_second_period(self):
        """Test OTP generation with 60 second period."""
        otp_url = "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&period=60&digits=6&issuer=Test"
        result = gen_otp(otp_url)
        assert len(result) == 6
        assert result.isdigit()


class TestGenOTPNonURL:
    """Tests for the TOTP values that aren't otpauth:// URLs.

    Bitwarden stores the TOTP field as it was entered, so it also holds a
    bare base32 secret or a steam:// URL.

    """

    def test_gen_otp_bare_secret(self):
        """Test a bare base32 secret, as stored by pasting a key."""
        secret = "JBSWY3DPEHPK3PXP"
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(secret)
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected

    def test_gen_otp_bare_secret_with_spaces(self):
        """Test that the spacing Bitwarden preserves in a key is ignored."""
        secret = "JBSWY3DPEHPK3PXP"
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp("JBSW Y3DP EHPK 3PXP")
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected

    def test_gen_otp_steam_url(self):
        """Test a steam:// URL, which implies a 5 character steam token."""
        secret = "JBSWY3DPEHPK3PXP"
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(f"steam://{secret}")
            expected = totp(secret, 30, 5, "sha1", steam=True)
        assert result == expected
        assert len(result) == 5
        for char in result:
            assert char in "23456789BCDFGHJKMNPQRTVWXY"

    @pytest.mark.parametrize("value", ["", "   ", "not a secret!", "1"])
    def test_gen_otp_unusable_value_returns_empty(self, value):
        """Test that a value no code can be made from returns empty string.

        A TOTP field holding something unreadable must not raise out of
        gen_otp() and take down the caller.

        """
        assert gen_otp(value) == ""

    def test_gen_otp_unknown_algorithm_returns_empty(self):
        """Test that an algorithm hashlib doesn't know returns empty string."""
        otp_url = (
            "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP"
            "&period=30&digits=6&algorithm=sha3"
        )
        assert gen_otp(otp_url) == ""


class TestOTPParams:
    """Tests for the parsed parameters used to prefill the edit menu."""

    def test_otp_params_secret_from_each_form(self):
        """Test that the secret is recovered from all three stored forms."""
        secret = "JBSWY3DPEHPK3PXP"
        for value in (
            secret,
            f"steam://{secret}",
            f"otpauth://totp/Test:user?secret={secret}&period=30&digits=6",
        ):
            assert otp_params(value)["key"] == secret

    def test_otp_params_empty_when_unusable(self):
        """Test that a value with no secret parses to an empty dict."""
        assert otp_params("otpauth://totp/Test:user?issuer=Test") == {}
        assert otp_params("") == {}


class TestGenOTPAlgorithm:
    """Tests that the algorithm in the otpauth URL is honored.

    A typo ('algorihm') previously made every entry fall back to sha1,
    producing codes the server rejects for SHA-256/SHA-512 entries.

    """

    @pytest.mark.parametrize("algorithm", ["SHA256", "SHA512"])
    def test_gen_otp_honors_algorithm(self, algorithm):
        """Test that a non-sha1 algorithm changes the generated code."""
        secret = "JBSWY3DPEHPK3PXP"
        base = (
            f"otpauth://totp/Test:user@example.com?secret={secret}"
            "&period=30&digits=6"
        )
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(f"{base}&algorithm={algorithm}")
            expected = totp(secret, 30, 6, algorithm.lower())
            sha1_result = gen_otp(base)
        assert result == expected
        assert result != sha1_result

    def test_gen_otp_defaults_to_sha1(self):
        """Test that a URL with no algorithm still uses sha1."""
        secret = "JBSWY3DPEHPK3PXP"
        otp_url = (
            f"otpauth://totp/Test:user@example.com?secret={secret}"
            "&period=30&digits=6"
        )
        with patch("bwm.totp.time.time", return_value=1700000000):
            result = gen_otp(otp_url)
            expected = totp(secret, 30, 6, "sha1")
        assert result == expected
