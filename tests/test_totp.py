"""Tests for TOTP generation module."""

import time
from unittest.mock import patch

import pytest

from bwm.totp import hotp, totp, gen_otp


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
        """Test that missing secret returns empty string."""
        otp_url = "otpauth://totp/Test:user@example.com?period=30&digits=6&issuer=Test"
        result = gen_otp(otp_url)
        assert result == ""

    def test_gen_otp_missing_period(self):
        """Test that missing period returns empty string."""
        otp_url = "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&digits=6&issuer=Test"
        result = gen_otp(otp_url)
        assert result == ""

    def test_gen_otp_missing_digits(self):
        """Test that missing digits returns empty string."""
        otp_url = "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&period=30&issuer=Test"
        result = gen_otp(otp_url)
        assert result == ""

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
