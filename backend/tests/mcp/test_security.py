from __future__ import annotations

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
        for chunk in self._chunks:
            yield chunk


def test_is_secure_url():
    assert is_secure_url("https://cdn.recova.com/lineup.png") is True
    assert is_secure_url("file:///etc/passwd") is False
    assert is_secure_url("ftp://example.com/poster.jpg") is False


def test_block_wrappers():
    blocked_google_drive = "https://drive.google.com/file/d/abc123/view?usp=sharing"
    blocked_dropbox = "https://www.dropbox.com/scl/fi/abc123/poster.png?rlkey=xyz&dl=0"

    assert validate_reference_image(blocked_google_drive)["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK
    assert validate_reference_image(blocked_dropbox)["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK


def test_magic_bytes_validation(monkeypatch):
    png_signature = bytes.fromhex("89504E470D0A1A0A") + b"\x00" * 24
    fake_jpg_text = b"This is text, not a jpeg header"

    def mock_get_png(*args, **kwargs):
        return MockResponse([png_signature])

    def mock_get_text(*args, **kwargs):
        return MockResponse([fake_jpg_text])

    monkeypatch.setattr(requests, "get", mock_get_png)
    result_ok = validate_reference_image("https://cdn.recova.com/ok.png")
    assert result_ok["status"] is True

    monkeypatch.setattr(requests, "get", mock_get_text)
    result_bad = validate_reference_image("https://cdn.recova.com/fake.jpg")
    assert result_bad["status"] is False
    assert result_bad["error_code"] == ERR_INVALID_FILE_TYPE


def test_network_timeout(monkeypatch):
    def mock_timeout(*args, **kwargs):
        raise requests.Timeout("network timeout")

    monkeypatch.setattr(requests, "get", mock_timeout)

    result = validate_reference_image("https://cdn.recova.com/slow.png")
    assert result["status"] is False
    assert result["error_code"] == ERR_NETWORK_TIMEOUT
    assert result["recovery_action"] == "USE_ACTIVE_TEMPLATE"
