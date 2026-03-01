"""Security guards for validating reference images before rendering.

This module implements SDD security requirements for URL hardening and Magic
Bytes validation using a non-blocking failure contract.
"""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import parse_qs, urlparse

import requests

ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK = "ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK"
ERR_INVALID_FILE_TYPE = "ERR_INVALID_FILE_TYPE"
ERR_NETWORK_TIMEOUT = "ERR_NETWORK_TIMEOUT"
ERR_NETWORK_ERROR = "ERR_NETWORK_ERROR"

RECOVERY_ACTION_USE_ACTIVE_TEMPLATE = "USE_ACTIVE_TEMPLATE"
VALIDATION_TIMEOUT_SECONDS = 5
HEADER_BYTES_TO_READ = 32

PNG_MAGIC = bytes.fromhex("89504E470D0A1A0A")
JPEG_MAGIC = bytes.fromhex("FFD8FF")
WEBP_RIFF_MAGIC = b"RIFF"
WEBP_WEBP_MAGIC = b"WEBP"


def _failure_response(error_code: str) -> dict[str, str | bool]:
    """Return the SDD non-blocking failure object."""
    return {
        "status": False,
        "error_code": error_code,
        "recovery_action": RECOVERY_ACTION_USE_ACTIVE_TEMPLATE,
    }


def is_secure_url(url: str) -> bool:
    """Validate URL scheme according to security policy.

    Only HTTPS URLs are accepted. Other schemes (e.g., file://, ftp://) are
    rejected.
    """
    parsed = urlparse(url)
    return parsed.scheme.lower() == "https"




def _is_private_or_local_host(host: str) -> bool:
    """Block localhost and private/link-local loopback IP ranges."""
    hostname = host.strip().lower()
    if not hostname:
        return True

    if hostname in {"localhost", "::1"}:
        return True

    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]

    try:
        addr = ip_address(hostname)
    except ValueError:
        return False

    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_unspecified
        or addr.is_reserved
        or addr.is_multicast
    )

def _is_blocked_wrapper_url(url: str) -> bool:
    """Detect non-direct file wrapper URLs from Google Drive and Dropbox."""
    parsed = urlparse(url)
    host = parsed.hostname.lower() if parsed.hostname else ""

    if _is_private_or_local_host(host):
        return True
    path = parsed.path.lower()
    query = parse_qs(parsed.query)

    if "drive.google.com" in host or "docs.google.com" in host:
        return True

    if "dropbox.com" in host and "dropboxusercontent.com" not in host:
        dl_values = {value.lower() for value in query.get("dl", [])}
        raw_values = {value.lower() for value in query.get("raw", [])}
        is_direct = "1" in dl_values or "1" in raw_values
        return not is_direct

    return path.endswith("/preview")


def _matches_allowed_magic(header_bytes: bytes) -> bool:
    """Validate image signature against PNG, JPEG and WebP."""
    if header_bytes.startswith(PNG_MAGIC):
        return True

    if header_bytes.startswith(JPEG_MAGIC):
        return True

    if header_bytes.startswith(WEBP_RIFF_MAGIC) and len(header_bytes) >= 12:
        return header_bytes[8:12] == WEBP_WEBP_MAGIC

    return False


def validate_reference_image(url: str) -> dict[str, str | bool]:
    """Validate URL safety and file signature for external reference images.

    The function performs a streaming request and inspects only the first
    32 bytes to identify allowed formats (PNG, JPEG, WebP).
    """
    if not is_secure_url(url) or _is_blocked_wrapper_url(url):
        return _failure_response(ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK)

    try:
        with requests.get(url, stream=True, timeout=VALIDATION_TIMEOUT_SECONDS) as response:
            header = b""
            for chunk in response.iter_content(chunk_size=HEADER_BYTES_TO_READ):
                if not chunk:
                    continue
                header += chunk
                if len(header) >= HEADER_BYTES_TO_READ:
                    break

        if not _matches_allowed_magic(header[:HEADER_BYTES_TO_READ]):
            return _failure_response(ERR_INVALID_FILE_TYPE)

        return {"status": True, "error_code": None, "recovery_action": None}
    except requests.Timeout:
        return _failure_response(ERR_NETWORK_TIMEOUT)
    except requests.RequestException:
        return _failure_response(ERR_NETWORK_ERROR)
