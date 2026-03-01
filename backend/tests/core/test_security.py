from __future__ import annotations

from unittest.mock import patch

import requests

from backend.src.core.security import (
    ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK,
    ERR_INVALID_FILE_TYPE,
    ERR_NETWORK_ERROR,
    ERR_NETWORK_TIMEOUT,
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


def test_url_hardening_blocks_localhost_and_private_hosts() -> None:
    blocked_urls = [
        "http://localhost/image.png",
        "https://127.0.0.1/image.png",
        "https://192.168.1.10/image.png",
    ]

    for url in blocked_urls:
        result = validate_reference_image(url)
        assert result["status"] is False
        assert result["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK


def test_magic_bytes_rejects_exe_header_with_requests_patch() -> None:
    fake_exe_header = b"MZ" + b"\x00" * 30

    with patch("requests.get", return_value=MockResponse([fake_exe_header])):
        result = validate_reference_image("https://cdn.recova.com/not-really-png.png")

    assert result["status"] is False
    assert result["error_code"] == ERR_INVALID_FILE_TYPE


def test_magic_bytes_accepts_real_png_with_requests_patch() -> None:
    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24

    with patch("requests.get", return_value=MockResponse([png_header])):
        result = validate_reference_image("https://cdn.recova.com/real.png")

    assert result["status"] is True
    assert result["error_code"] is None


def test_network_failures_are_classified() -> None:
    with patch("requests.get", side_effect=requests.Timeout("timeout")):
        timeout_result = validate_reference_image("https://cdn.recova.com/slow.png")

    with patch("requests.get", side_effect=requests.RequestException("boom")):
        error_result = validate_reference_image("https://cdn.recova.com/error.png")

    assert timeout_result["status"] is False
    assert timeout_result["error_code"] == ERR_NETWORK_TIMEOUT
    assert error_result["status"] is False
    assert error_result["error_code"] == ERR_NETWORK_ERROR
