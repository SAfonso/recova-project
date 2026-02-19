import json
from types import SimpleNamespace

import pytest

import canva_builder as builder


def test_parse_cli_payload_accepts_fecha_and_exactly_five_comics():
    payload = {
        "fecha": "2026-02-22",
        "comicos": [
            {"nombre": "A", "instagram": "@a"},
            {"nombre": "B", "instagram": "@b"},
            {"nombre": "C", "instagram": "@c"},
            {"nombre": "D", "instagram": "@d"},
            {"nombre": "E", "instagram": "@e"},
        ],
    }

    parsed = builder.parse_cli_payload(json.dumps(payload))

    assert parsed.fecha == "2026-02-22"
    assert len(parsed.comicos) == 5
    assert parsed.comicos[0].instagram == "a"


def test_parse_cli_payload_rejects_if_not_five_comics():
    payload = {
        "fecha_evento": "2026-02-22",
        "comicos": [{"nombre": "A", "instagram": "@a"}],
    }

    with pytest.raises(ValueError, match="exactamente 5"):
        builder.parse_cli_payload(json.dumps(payload))


def test_build_autofill_payload_supports_field_overrides(monkeypatch):
    monkeypatch.setenv("CANVA_TEMPLATE_ID", "tpl_123")
    monkeypatch.setenv(
        "CANVA_FIELD_OVERRIDES_JSON",
        json.dumps({"comico_1_nombre": "texto_nombre_1", "fecha": "fecha_evento"}),
    )
    request_payload = builder.PosterRequest(
        fecha="2026-02-22",
        comicos=[
            builder.ComicEntry(nombre="A", instagram="a"),
            builder.ComicEntry(nombre="B", instagram="b"),
            builder.ComicEntry(nombre="C", instagram="c"),
            builder.ComicEntry(nombre="D", instagram="d"),
            builder.ComicEntry(nombre="E", instagram="e"),
        ],
    )

    result = builder.build_autofill_payload(request_payload)

    assert result["template_id"] == "tpl_123"
    assert result["data"]["texto_nombre_1"] == "A"
    assert result["data"]["fecha_evento"] == "2026-02-22"
    assert "comico_1_nombre" not in result["data"]


def test_extract_design_url_handles_nested_payload():
    payload = {"result": {"design": {"url": "https://www.canva.com/design/abc"}}}

    assert builder.extract_design_url(payload) == "https://www.canva.com/design/abc"


def test_resolve_access_token_uses_fresh_token_from_refresh(monkeypatch):
    monkeypatch.setattr(
        builder,
        "refresh_access_token",
        lambda **_: SimpleNamespace(access_token="fresh_token"),
    )
    monkeypatch.setattr(builder, "get_cached_access_token", lambda: "cached_token")

    assert builder.resolve_access_token() == "fresh_token"


def test_resolve_access_token_falls_back_to_cached_token_if_refresh_fails(monkeypatch):
    def _raise_refresh_error(**_):
        raise builder.CanvaAuthError("refresh temporal", requires_reauthorization=False)

    monkeypatch.setattr(builder, "refresh_access_token", _raise_refresh_error)
    monkeypatch.setattr(builder, "get_cached_access_token", lambda: "cached_token")
    monkeypatch.delenv("CANVA_AUTHORIZATION_CODE", raising=False)

    assert builder.resolve_access_token() == "cached_token"
