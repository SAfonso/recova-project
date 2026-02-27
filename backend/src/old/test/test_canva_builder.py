import json
from types import SimpleNamespace

import pytest
import requests

import canva_builder as builder


def test_parse_cli_payload_accepts_fecha_and_keeps_five_comics():
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


def test_parse_cli_payload_pads_if_less_than_five_comics():
    payload = {
        "fecha_evento": "2026-02-22",
        "comicos": [{"nombre": "A", "instagram": "@a"}],
    }

    parsed = builder.parse_cli_payload(json.dumps(payload))

    assert len(parsed.comicos) == 5
    assert parsed.comicos[0] == builder.ComicEntry(nombre="A", instagram="a")
    assert parsed.comicos[4] == builder.ComicEntry(nombre=" ", instagram=" ")


def test_parse_cli_payload_rejects_if_more_than_five_comics():
    payload = {
        "fecha": "2026-02-22",
        "comicos": [
            {"nombre": "A", "instagram": "@a"},
            {"nombre": "B", "instagram": "@b"},
            {"nombre": "C", "instagram": "@c"},
            {"nombre": "D", "instagram": "@d"},
            {"nombre": "E", "instagram": "@e"},
            {"nombre": "F", "instagram": "@f"},
        ],
    }

    with pytest.raises(ValueError, match="como máximo 5"):
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

    assert result["brand_template_id"] == "tpl_123"
    assert "title" not in result
    assert result["data"]["texto_nombre_1"] == {
        "type": "text",
        "text": "A",
    }
    assert result["data"]["fecha_evento"] == {
        "type": "text",
        "text": "2026-02-22",
    }
    assert "comico_1_nombre" not in result["data"]


def test_build_autofill_payload_sanitizes_and_uses_fallback(monkeypatch):
    monkeypatch.setenv("CANVA_TEMPLATE_ID", "tpl_123")
    monkeypatch.delenv("CANVA_FIELD_OVERRIDES_JSON", raising=False)

    request_payload = builder.PosterRequest(
        fecha="2026-02-22 😀",
        comicos=[
            builder.ComicEntry(nombre="😀", instagram="  "),
            builder.ComicEntry(nombre="B", instagram="@b"),
            builder.ComicEntry(nombre="C", instagram="c"),
            builder.ComicEntry(nombre="D", instagram="d"),
            builder.ComicEntry(nombre="E", instagram="e"),
        ],
    )

    result = builder.build_autofill_payload(request_payload)

    assert result["data"]["fecha"]["text"] == "2026-02-22"
    assert result["data"]["comico_1_nombre"]["text"] == " "
    assert result["data"]["comico_1_instagram"]["text"] == " "


def test_extract_design_url_handles_nested_payload():
    payload = {"result": {"design": {"url": "https://www.canva.com/design/abc"}}}

    assert builder.extract_design_url(payload) == "https://www.canva.com/design/abc"


def test_request_canva_autofill_sends_required_headers(monkeypatch):
    captured = {}

    class _Response:
        status_code = 201

        @staticmethod
        def json():
            return {"job": {"id": "job_123"}}

        text = "ok"

    def _post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(builder.requests, "post", _post)

    payload = {"brand_template_id": "tpl", "data": {"fecha": {"type": "text", "text": "hoy"}}}
    response = builder.request_canva_autofill("token", payload)

    assert response["job"]["id"] == "job_123"
    assert captured["url"] == builder.CANVA_AUTOFILL_URL
    assert captured["headers"]["User-Agent"] == "recova-canva-builder/1.0"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_request_canva_autofill_status_sends_required_headers(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "in_progress"}

        text = "ok"

    def _get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(builder.requests, "get", _get)

    response = builder.request_canva_autofill_status("token", "job_123")

    assert response["status"] == "in_progress"
    assert captured["url"] == f"{builder.CANVA_AUTOFILL_URL}/job_123"
    assert captured["headers"]["User-Agent"] == "recova-canva-builder/1.0"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_wait_for_autofill_completion_polls_until_success(monkeypatch, capsys):
    statuses = iter(
        [
            {"status": "in_progress"},
            {"status": "success", "result": {"design": {"url": "https://www.canva.com/design/final"}}},
        ]
    )

    monkeypatch.setattr(
        builder,
        "request_canva_autofill_status",
        lambda access_token, job_id: next(statuses),
    )
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)

    result = builder.wait_for_autofill_completion(
        "token", {"job": {"id": "job_123"}}
    )

    assert result["status"] == "success"
    output = capsys.readouterr().out
    assert "Esperando a Canva..." in output
    assert "Estado: in_progress" in output


def test_wait_for_autofill_completion_raises_on_failed(monkeypatch):
    monkeypatch.setattr(
        builder,
        "request_canva_autofill_status",
        lambda access_token, job_id: {"status": "failed", "error": "bad_data"},
    )

    with pytest.raises(RuntimeError, match="Autofill job falló"):
        builder.wait_for_autofill_completion("token", {"job": {"id": "job_123"}})


def test_wait_for_autofill_completion_aborts_after_unknown_status_threshold(monkeypatch):
    monkeypatch.setattr(
        builder,
        "request_canva_autofill_status",
        lambda access_token, job_id: {"status": ""},
    )
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="job_id=job_123"):
        builder.wait_for_autofill_completion("token", {"job": {"id": "job_123"}})


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


def test_wait_for_autofill_completion_retries_on_timeout(monkeypatch, capsys):
    calls = iter(
        [
            requests.exceptions.Timeout("slow network"),
            {"status": "success", "result": {"design": {"url": "https://www.canva.com/design/final"}}},
        ]
    )

    def _status(*_args, **_kwargs):
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(builder, "request_canva_autofill_status", _status)
    monkeypatch.setattr(builder.time, "sleep", lambda _: None)

    result = builder.wait_for_autofill_completion("token", {"job": {"id": "job_123"}})

    assert result["status"] == "success"
    output = capsys.readouterr().out
    assert "Red lenta, reintentando..." in output
