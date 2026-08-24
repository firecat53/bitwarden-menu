"""TOTP generation"""

import base64
import hmac
import logging
import struct
import time
from urllib import parse

logger = logging.getLogger("bwm")


def hotp(key, counter, digits=6, digest="sha1", steam=False):
    """Generates HMAC OTP.  Taken from https://github.com/susam/mintotp

    Args: key - Secret key
          counter - Moving factor
          digits - The number of characters/digits that the otp should have
          digest - Algorithm to use to generate the otp
          steam - whether or not to use steam settings

    Returns: otp

    """
    key = base64.b32decode(key.upper() + "=" * ((8 - len(key)) % 8))
    counter = struct.pack(">Q", counter)
    mac = hmac.new(key, counter, digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">L", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    code = ""

    if steam:
        chars = "23456789BCDFGHJKMNPQRTVWXY"
        full_code = int(binary)
        for _ in range(digits):
            code += chars[full_code % len(chars)]
            full_code //= len(chars)
    else:
        code = str(binary)[-digits:].rjust(digits, "0")

    return code


def totp(key, time_step=30, digits=6, digest="sha1", steam=False):
    """Generates Time Based OTP

    Args: key - Secret key
          counter - The length of time in seconds each otp is valid for
          digits - The number of characters/digits that the otp should have
          digest - Algorithm to use to generate the otp
          steam - whether or not to use steam settings

    Returns: otp

    """
    return hotp(key, int(time.time() / time_step), digits, digest, steam)


def otp_params(otp_url):
    """Parses an entry's TOTP value into keyword arguments for totp()

    Args: otp_url - the entry's TOTP value. Bitwarden accepts an
                    otpauth:// URL, a steam:// URL or a bare base32 secret.
    Returns: dict, empty if no secret could be found

    """
    parsed_otp_url = parse.urlparse(otp_url)
    params = {}

    if parsed_otp_url.scheme == "otpauth":
        query_string = parse.parse_qs(parsed_otp_url.query)
        if "secret" not in query_string:
            return {}
        params["key"] = query_string["secret"][0]
        try:
            params["time_step"] = int(query_string["period"][0])
        except (KeyError, ValueError):
            pass
        try:
            params["digits"] = int(query_string["digits"][0])
        except (KeyError, ValueError):
            pass
        try:
            params["digest"] = query_string["algorithm"][0].lower()
        except KeyError:
            pass
        try:
            params["steam"] = query_string["encoder"][0] == "steam"
        except KeyError:
            pass
    elif parsed_otp_url.scheme == "steam":
        # steam://<secret>, as written by the Bitwarden clients
        params["key"] = parsed_otp_url.netloc or parsed_otp_url.path
        params["digits"] = 5
        params["steam"] = True
    else:
        # A bare secret, which is what pasting a key into the web vault stores
        params["key"] = otp_url

    # Bitwarden keeps the spacing of a key as it was entered
    params["key"] = "".join(params["key"].split())
    return params if params["key"] else {}


def gen_otp(otp_url):
    """Generates one time password

    Args: otp_url - the entry's TOTP value, see otp_params()
    Returns: otp, empty string if no code can be generated

    """
    params = otp_params(otp_url)
    if not params:
        return ""
    try:
        return totp(**params)
    except ValueError as err:
        # An unparseable secret or an algorithm hashlib doesn't know about
        logger.debug(f"Could not generate a TOTP code: {err}")
        return ""
