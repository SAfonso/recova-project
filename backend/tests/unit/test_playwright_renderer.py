from __future__ import annotations

import uuid
from copy import deepcopy


from playwright_renderer import PlaywrightRenderer



def _valid_payload() -> dict:
    return {
        "request_id": str(uuid.uuid4()),
        "schema_version": "1.0",
        "event": {
            "date": "2026-02-26",
            "venue": "Sala Recova",
            "city": "Madrid",
            "title": "LineUp Semanal",
            "timezone": "Europe/Madrid",
        },
        "lineup": [
            {"order": 1, "name": "Comica Uno", "instagram": "comica_uno"},
            {"order": 2, "name": "Comico Dos", "instagram": "comico_dos"},
            {"order": 3, "name": "Comica Tres", "instagram": "comica_tres"},
            {"order": 4, "name": "Comico Cuatro", "instagram": "comico_cuatro"},
            {"order": 5, "name": "Comica Cinco", "instagram": "comica_cinco"},
        ],
        "template": {
            "template_id": "lineup_default_v1",
            "width": 1080,
            "height": 1350,
            "theme": "default",
        },
        "render": {
            "format": "png",
            "quality": 100,
            "scale": 2,
            "timeout_ms": 15000,
        },
        "metadata": {
            "source": "n8n.LineUp",
            "initiated_at": "2026-02-26T10:00:00Z",
            "trace_id": "trace-1234",
        },
    }



def _assert_success_output_contract(result: dict, request_id: str) -> None:
    assert result["status"] == "success"
    assert result["request_id"] == request_id
    assert isinstance(result["render_id"], str) and result["render_id"]

    storage = result["storage"]
    assert set(["provider", "path", "storage_url", "public"]).issubset(storage)

    artifact = result["artifact"]
    assert artifact["format"] == "png"
    assert set(["dimensions", "size_bytes", "checksum_sha256"]).issubset(artifact)
    assert artifact["dimensions"]["width"] == 1080
    assert artifact["dimensions"]["height"] == 1350

    timing = result["timing"]
    assert set(
        ["execution_time_ms", "browser_launch_ms", "html_injection_ms", "screenshot_ms"]
    ).issubset(timing)

    assert isinstance(result["warnings"], list)

    meta = result["meta"]
    assert meta["schema_version"] == "1.0"
    assert isinstance(meta["generated_at"], str) and meta["generated_at"]
    assert meta["engine"] == "playwright-chromium"
    assert isinstance(meta["engine_version"], str) and meta["engine_version"]



def test_schema_validation_accepts_valid_payload_from_spec_2_2():
    payload = _valid_payload()

    renderer = PlaywrightRenderer()
    result = renderer.render(payload)

    _assert_success_output_contract(result, payload["request_id"])



def test_lineup_under_minimum_returns_non_blocking_warning_code():
    payload = _valid_payload()
    payload["lineup"] = payload["lineup"][:4]

    renderer = PlaywrightRenderer()
    result = renderer.render(payload)

    assert result["status"] == "success"
    warnings = result["warnings"]
    assert any(warning["code"] == "LINEUP_UNDER_MINIMUM" for warning in warnings)

    under_minimum_warning = next(
        warning for warning in warnings if warning["code"] == "LINEUP_UNDER_MINIMUM"
    )
    assert under_minimum_warning["details"]["current_count"] == 4
    assert under_minimum_warning["details"]["minimum_required"] == 5



def test_name_longer_than_32_chars_is_truncated_with_ellipsis():
    payload = _valid_payload()
    payload["lineup"][0]["name"] = "Nombre Excesivamente Largo Para Un Slot Del Poster"

    renderer = PlaywrightRenderer()
    result = renderer.render(payload)

    assert result["status"] == "success"
    normalized_lineup = result["normalized_lineup"]
    first_name = normalized_lineup[0]["name"]

    assert len(first_name) <= 32
    assert first_name.endswith("…")



def test_playwright_launch_failure_maps_to_error_output_from_spec_3_2(monkeypatch):
    payload = _valid_payload()

    def _raise_launch_error(*_args, **_kwargs):
        raise RuntimeError("browser launch failed")

    monkeypatch.setattr(PlaywrightRenderer, "_launch_browser", _raise_launch_error)

    renderer = PlaywrightRenderer()
    result = renderer.render(payload)

    assert result["status"] == "error"
    assert result["request_id"] == payload["request_id"]
    assert result["error"]["code"] == "PLAYWRIGHT_BROWSER_LAUNCH_FAILED"
    assert isinstance(result["error"]["message"], str) and result["error"]["message"]
    assert result["error"]["details"]["stage"] == "browser_launch"
    assert result["error"]["details"]["retryable"] is True
    assert isinstance(result["meta"]["generated_at"], str) and result["meta"]["generated_at"]
    assert result["meta"]["schema_version"] == "1.0"



def test_success_output_contract_is_mcp_rich_structure_from_spec_3_1():
    payload = _valid_payload()

    renderer = PlaywrightRenderer()
    result = renderer.render(deepcopy(payload))

    _assert_success_output_contract(result, payload["request_id"])
