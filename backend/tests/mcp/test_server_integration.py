"""Integration contract tests for MCP server orchestration (SDD §14).

Estas pruebas validan el flujo end-to-end del Agnostic Renderer a nivel de
contrato. Están diseñadas en modo TDD: actualmente `backend/src/mcp_server.py`
no implementa la API esperada, por lo que el estado esperado es ROJO.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from backend.src import mcp_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def valid_request_payload() -> dict:
    return {
        "event_id": "c7f4d80f-8b66-4ff9-95d3-2b042dbb1c79",
        "metadata": {
            "date_text": "Jueves 12 de Marzo · 21:30h",
            "venue": "RECOVA Comedy Club",
        },
        "lineup": [
            {"name": "Ada Torres", "instagram": "adatorres"},
            {"name": "Bruno Gil", "instagram": "brunogil"},
        ],
        "intent": {
            "template_id": "lineup_bold_v1",
            "reference_image_url": "https://cdn.recova.com/reference.png",
        },
    }


async def test_full_render_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, valid_request_payload: dict) -> None:
    """Debe orquestar binder + render + salida PNG en flujo exitoso."""
    validate_mock = Mock(return_value={"status": True, "error_code": None, "recovery_action": None})

    generated_png = tmp_path / "rendered_lineup.png"

    async def fake_render(*, payload: dict):
        generated_png.write_bytes(b"\x89PNG\r\n\x1a\n")
        return {
            "status": "success",
            "output": {"public_url": str(generated_png)},
            "trace": {
                "engine": "pillow-freetype",
                "generation_mode": "direct_composite",
                "template_id": payload["intent"]["template_id"],
                "warnings": [],
            },
        }

    monkeypatch.setattr(mcp_server, "validate_reference_image", validate_mock)
    monkeypatch.setattr(mcp_server, "execute_render", fake_render)

    result = await mcp_server.orchestrate_render(valid_request_payload, workdir=tmp_path)

    validate_mock.assert_called_once_with(valid_request_payload["intent"]["reference_image_url"])
    assert generated_png.exists()
    assert result["output"]["public_url"].endswith(".png")


async def test_recovery_on_security_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, valid_request_payload: dict) -> None:
    """Si falla seguridad, debe recuperar con plantilla active + recovery_notes."""
    malicious_payload = {
        **valid_request_payload,
        "intent": {
            "template_id": "lineup_bold_v1",
            "reference_image_url": "https://drive.google.com/file/d/evil/view",
        },
    }

    monkeypatch.setattr(
        mcp_server,
        "validate_reference_image",
        Mock(
            return_value={
                "status": False,
                "error_code": "ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK",
                "recovery_action": "USE_ACTIVE_TEMPLATE",
            }
        ),
    )

    fallback_mock = AsyncMock(
        return_value={
            "status": "success",
            "output": {"public_url": str(tmp_path / "fallback_render.png")},
            "trace": {
                "generation_mode": "template_catalog",
                "template_id": "catalog/active/default",
                "recovery_notes": "Imagen de referencia inválida, se usó plantilla activa",
                "warnings": ["SYSTEM_FALLBACK_TRIGGERED"],
            },
        }
    )

    monkeypatch.setattr(mcp_server, "execute_render", fallback_mock)

    result = await mcp_server.orchestrate_render(malicious_payload, workdir=tmp_path)

    assert result["status"] == "success"
    assert result["trace"]["generation_mode"] == "template_catalog"
    assert "recovery_notes" in result["trace"]
    assert "inválida" in result["trace"]["recovery_notes"].lower()


async def test_concurrency_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, valid_request_payload: dict) -> None:
    """Debe serializar peticiones concurrentes para evitar picos de RAM."""
    order: list[str] = []

    # Añade esta línea: Fuerza a usar un lock del bucle de eventos actual
    monkeypatch.setattr(mcp_server, "render_lock", asyncio.Lock())
    
    monkeypatch.setattr(mcp_server, "validate_reference_image", Mock(return_value={"status": True}))

    async def fake_render(*, payload: dict):
        order.append(f"start:{payload['event_id']}")
        await asyncio.sleep(0.05)
        order.append(f"end:{payload['event_id']}")
        return {
            "status": "success",
            "output": {"public_url": str(tmp_path / f"{payload['event_id']}.png")},
            "trace": {"warnings": []},
        }

    monkeypatch.setattr(mcp_server, "execute_render", fake_render)

    payload_a = {**valid_request_payload, "event_id": "00000000-0000-0000-0000-000000000001"}
    payload_b = {**valid_request_payload, "event_id": "00000000-0000-0000-0000-000000000002"}

    await asyncio.gather(
        mcp_server.orchestrate_render(payload_a, workdir=tmp_path),
        mcp_server.orchestrate_render(payload_b, workdir=tmp_path),
    )

    assert order == [
        "start:00000000-0000-0000-0000-000000000001",
        "end:00000000-0000-0000-0000-000000000001",
        "start:00000000-0000-0000-0000-000000000002",
        "end:00000000-0000-0000-0000-000000000002",
    ]


async def test_pure_black_box_invariant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, valid_request_payload: dict) -> None:
    """La respuesta no debe filtrar score ni IDs internos de base de datos."""
    monkeypatch.setattr(mcp_server, "validate_reference_image", Mock(return_value={"status": True}))

    render_mock = AsyncMock(
        return_value={
            "status": "success",
            "output": {"public_url": str(tmp_path / "black_box.png")},
            "trace": {
                "engine": "pillow-freetype",
                "warnings": [],
            },
        }
    )
    monkeypatch.setattr(mcp_server, "execute_render", render_mock)

    result = await mcp_server.orchestrate_render(valid_request_payload, workdir=tmp_path)

    rendered_text = str(result).lower()
    for forbidden_fragment in ("score", "internal_id", "comico_id", "silver_id", "gold_id"):
        assert forbidden_fragment not in rendered_text
