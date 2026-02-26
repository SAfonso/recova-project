from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from storage3 import create_client


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "posters"

pytestmark = pytest.mark.skipif(
    not SUPABASE_URL or not SUPABASE_KEY,
    reason="Requiere SUPABASE_URL y SUPABASE_KEY en .env para test de integración.",
)

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDATx\x9cc``\x00\x00\x00"
    b"\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_supabase_storage_upload_to_public_posters_bucket():
    storage = create_client(
        url=f"{SUPABASE_URL}/storage/v1",
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
        },
        is_async=False,
        timeout=20,
    )

    object_path = f"integration-tests/{uuid.uuid4()}.png"
    upload_response = storage.from_(BUCKET_NAME).upload(
        path=object_path,
        file=_PNG_1X1,
        file_options={"content-type": "image/png", "upsert": "true"},
    )

    # La subida debe devolver metadata del objeto creado/actualizado.
    assert upload_response is not None
    assert getattr(upload_response, "path", "") == object_path

    public_url = storage.from_(BUCKET_NAME).get_public_url(object_path)
    assert public_url
    print(f"Supabase public_url: {public_url}")

    response = requests.get(public_url, timeout=15)
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("image/png")
