from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

try:
    import pytest_asyncio
except ModuleNotFoundError:  # pragma: no cover - entorno local sin plugin
    pytest_asyncio = pytest

from backend.src import mcp_server

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def cleanup_tmp_artifacts() -> None:
    yield
    for artifact in Path("/tmp").glob("render_test_mcp_*.png"):
        artifact.unlink(missing_ok=True)


@pytest.fixture
def mcp_app():
    if mcp_server.app is None:
        pytest.skip("FastAPI no está disponible en este entorno")
    return mcp_server.app


@pytest_asyncio.fixture
async def http_client(mcp_app):
    transport = httpx.ASGITransport(app=mcp_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_healthz_endpoint(http_client: httpx.AsyncClient) -> None:
    response = await http_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_render_lineup_endpoint(
    http_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_path = Path("/tmp/render_test_mcp_success.png")

    async def fake_orchestrate(payload: dict, workdir: Path | None = None) -> dict:
        del workdir
        generated_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        return {
            "status": "success",
            "event_id": payload["event_id"],
            "image_path": str(generated_path),
            "output": {
                "public_url": str(generated_path),
                "image_path": str(generated_path),
            },
            "trace": {"warnings": []},
        }

    monkeypatch.setattr(mcp_server, "orchestrate_render", fake_orchestrate)

    payload = {
        "event_id": "qa-event-http-01",
        "lineup": [
            {"name": "Ada Torres", "instagram": "adatorres"},
            {"name": "Bruno Gil", "instagram": "brunogil"},
        ],
        "intent": {"template_id": "active", "reference_image_url": None},
    }

    response = await http_client.post("/tools/render_lineup", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


async def test_mcp_lock_concurrency(
    http_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    async def fake_execute_render(*, payload: dict) -> dict:
        event_id = payload["event_id"]
        order.append(f"start:{event_id}")
        await asyncio.sleep(0.05)
        output_path = Path(f"/tmp/render_test_mcp_{event_id}.png")
        output_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        order.append(f"end:{event_id}")
        return {
            "status": "success",
            "output": {
                "public_url": str(output_path),
                "image_path": str(output_path),
            },
            "trace": {"warnings": []},
        }

    monkeypatch.setattr(mcp_server, "validate_reference_image", lambda _: {"status": True})
    monkeypatch.setattr(mcp_server, "execute_render", fake_execute_render)

    payload_a = {
        "event_id": "qa-concurrency-a",
        "lineup": [{"name": "A", "instagram": "a"}],
        "intent": {"template_id": "active", "reference_image_url": None},
    }
    payload_b = {
        "event_id": "qa-concurrency-b",
        "lineup": [{"name": "B", "instagram": "b"}],
        "intent": {"template_id": "active", "reference_image_url": None},
    }

    response_a, response_b = await asyncio.gather(
        http_client.post("/tools/render_lineup", json=payload_a),
        http_client.post("/tools/render_lineup", json=payload_b),
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.headers["content-type"].startswith("image/png")
    assert response_b.headers["content-type"].startswith("image/png")
    assert response_a.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response_b.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert order == [
        "start:qa-concurrency-a",
        "end:qa-concurrency-a",
        "start:qa-concurrency-b",
        "end:qa-concurrency-b",
    ]


async def test_render_lineup_http_500_on_engine_failure(
    http_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_orchestrate(payload: dict, workdir: Path | None = None) -> dict:
        del payload, workdir
        return {
            "status": "error",
            "event_id": "qa-error",
            "image_path": None,
            "output": {"message": "Playwright render execution failed"},
            "trace": {"recovery_notes": "browser crashed"},
        }

    monkeypatch.setattr(mcp_server, "orchestrate_render", fake_orchestrate)

    payload = {
        "event_id": "qa-event-http-error",
        "lineup": [{"name": "Ada Torres", "instagram": "adatorres"}],
        "intent": {"template_id": "active", "reference_image_url": None},
    }

    response = await http_client.post("/tools/render_lineup", json=payload)

    assert response.status_code == 500
    assert response.json()["detail"]["error"] == "Render engine failed"
    assert "browser crashed" in response.json()["detail"]["details"]


async def test_render_invalid_payload(http_client: httpx.AsyncClient) -> None:
    response = await http_client.post("/tools/render_lineup", json={"lineup": "bad-payload"})

    assert response.status_code in {400, 422}
