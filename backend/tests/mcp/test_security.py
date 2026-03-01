from __future__ import annotations

from unittest.mock import patch

import requests

from backend.src.core.security import (
    ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK,
    ERR_INVALID_FILE_TYPE,
    ERR_NETWORK_TIMEOUT,
    is_secure_url,
    validate_reference_image,
)


class MockResponse:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def iter_content(self, chunk_size: int = 32):
        del chunk_size
        for chunk in self._chunks:
            yield chunk


def test_is_secure_url():
    assert is_secure_url("https://cdn.recova.com/lineup.png") is True
    assert is_secure_url("http://cdn.recova.com/lineup.png") is True
    assert is_secure_url("file:///etc/passwd") is False
    assert is_secure_url("ftp://example.com/poster.jpg") is False


def test_block_wrappers_and_localhost():
    blocked_google_drive = "https://drive.google.com/file/d/abc123/view?usp=sharing"
    blocked_dropbox = "https://www.dropbox.com/scl/fi/abc123/poster.png?rlkey=xyz&dl=0"
    blocked_localhost = "http://localhost/poster.png"

    assert validate_reference_image(blocked_google_drive)["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK
    assert validate_reference_image(blocked_dropbox)["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK
    assert validate_reference_image(blocked_localhost)["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK


def test_magic_bytes_validation_with_requests_patch():
    png_signature = bytes.fromhex("89504E470D0A1A0A") + b"\x00" * 24
    fake_exe_header = b"MZ" + b"\x00" * 30

    with patch("requests.get", return_value=MockResponse([png_signature])):
        result_ok = validate_reference_image("https://cdn.recova.com/ok.png")
    assert result_ok["status"] is True

    with patch("requests.get", return_value=MockResponse([fake_exe_header])):
        result_bad = validate_reference_image("https://cdn.recova.com/fake.jpg")
    assert result_bad["status"] is False
    assert result_bad["error_code"] == ERR_INVALID_FILE_TYPE


def test_network_timeout():
    with patch("requests.get", side_effect=requests.Timeout("network timeout")):
        result = validate_reference_image("https://cdn.recova.com/slow.png")
    assert result["status"] is False
    assert result["error_code"] == ERR_NETWORK_TIMEOUT
    assert result["recovery_action"] == "USE_ACTIVE_TEMPLATE"
