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
        "https://10.0.0.1/image.png",
        "https://192.168.1.10/image.png",
        "https://172.16.0.5/image.png",
    ]

    for url in blocked_urls:
        result = validate_reference_image(url)
        assert result["status"] is False
        assert result["error_code"] == ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK


def test_magic_bytes_rejects_fake_png_with_exe_header() -> None:
    fake_exe_header = b"MZ" + b"\x00" * 30

    with patch("backend.src.core.security.requests.get", return_value=MockResponse([fake_exe_header])):
        result = validate_reference_image("https://cdn.recova.com/not-really-png.png")

    assert result["status"] is False
    assert result["error_code"] == ERR_INVALID_FILE_TYPE


def test_network_failures_are_classified() -> None:
    with patch("backend.src.core.security.requests.get", side_effect=requests.Timeout("timeout")):
        timeout_result = validate_reference_image("https://cdn.recova.com/slow.png")

    with patch("backend.src.core.security.requests.get", side_effect=requests.RequestException("boom")):
        error_result = validate_reference_image("https://cdn.recova.com/error.png")

    assert timeout_result["status"] is False
    assert timeout_result["error_code"] == ERR_NETWORK_TIMEOUT
    assert error_result["status"] is False
    assert error_result["error_code"] == ERR_NETWORK_ERROR
