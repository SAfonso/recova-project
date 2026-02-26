from __future__ import annotations

import os
import uuid

import pytest
import requests

from playwright_renderer import PlaywrightRenderer


pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"),
    reason="Requiere credenciales SUPABASE_URL y SUPABASE_KEY para test de integración.",
)

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00"
    b"\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_supabase_storage_upload_returns_public_url_with_http_200():
    renderer = PlaywrightRenderer()
    request_id = str(uuid.uuid4())

    storage_path, public_url = renderer._upload_to_supabase(
        png_bytes=_PNG_1X1,
        event_date="2026-02-26",
        request_id=request_id,
    )

    assert storage_path == f"2026-02-26/lineup_{request_id}.png"
    assert "posters" in public_url

    response = requests.get(public_url, timeout=15)
    assert response.status_code == 200
