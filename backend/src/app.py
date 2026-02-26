"""Flask API de producción para render y publicación de lineups."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape
import re
import time
import uuid
from typing import Any

from flask import Flask, jsonify, request

from playwright_renderer import PlaywrightRenderer

_SCHEMA_VERSION = "1.0"
_ALLOWED_TIMEZONE = "Europe/Madrid"
_ALLOWED_TEMPLATE_ID = "lineup_default_v1"
_ALLOWED_RENDER_FORMAT = "png"
_ALLOWED_THEME = "default"

_ERROR_HTTP_MAP = {
    "INVALID_INPUT_SCHEMA": 400,
    "INVALID_LINEUP_DATA": 422,
    "TEMPLATE_NOT_FOUND": 404,
    "PLAYWRIGHT_BROWSER_LAUNCH_FAILED": 500,
    "PLAYWRIGHT_TEMPLATE_INJECTION_FAILED": 500,
    "PLAYWRIGHT_RENDER_TIMEOUT": 504,
    "PLAYWRIGHT_SCREENSHOT_FAILED": 500,
    "STORAGE_UPLOAD_FAILED": 502,
    "UNEXPECTED_INTERNAL_ERROR": 500,
}


def create_app() -> Flask:
    app = Flask(__name__)
    renderer = PlaywrightRenderer()
    _configure_absolute_template_loader(renderer)

    @app.post("/render-lineup")
    def render_lineup() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if payload is None:
            return _error_response(
                request_id=None,
                code="INVALID_INPUT_SCHEMA",
                message="Body inválido: se requiere JSON.",
                stage="validation",
                retryable=False,
                http_status=400,
            )

        validation_error = _validate_input_payload(payload)
        if validation_error is not None:
            request_id = payload.get("request_id") if isinstance(payload, dict) else None
            return _error_response(
                request_id=request_id,
                code="INVALID_INPUT_SCHEMA",
                message=validation_error,
                stage="validation",
                retryable=False,
                http_status=400,
            )

        if hasattr(renderer, "_normalize_lineup") and hasattr(renderer, "_render_html"):
            result = _render_with_set_content(renderer, payload)
        else:
            result = renderer.render(payload)
        if result.get("status") == "error":
            code = str(result.get("error", {}).get("code") or "UNEXPECTED_INTERNAL_ERROR")
            status_code = _ERROR_HTTP_MAP.get(code, 500)
            return jsonify(result), status_code

        public_url = result.get("storage", {}).get("public_url")
        return (
            jsonify(
                {
                    "status": "success",
                    "request_id": result.get("request_id"),
                    "public_url": public_url,
                    "mcp": result,
                }
            ),
            200,
        )

    return app


def _configure_absolute_template_loader(renderer: PlaywrightRenderer) -> None:
    template_root = "/root/RECOVA/backend/src/templates"
    renderer._jinja = Environment(  # noqa: SLF001
        loader=FileSystemLoader(template_root),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _render_with_set_content(renderer: PlaywrightRenderer, payload: dict[str, Any]) -> dict[str, Any]:
    started_at = time.perf_counter()
    request_id = payload.get("request_id")

    normalized_lineup, warnings = renderer._normalize_lineup(payload["lineup"])  # noqa: SLF001
    if not normalized_lineup:
        return renderer._error_output(  # noqa: SLF001
            code="INVALID_LINEUP_DATA",
            message="El lineup no contiene cómicos válidos para renderizar.",
            request_id=request_id,
            stage="validation",
            retryable=False,
            started_at=started_at,
        )

    template_name = "lineup_v1.html"

    browser_launch_start = time.perf_counter()
    browser = renderer._launch_browser()  # noqa: SLF001
    browser_launch_ms = renderer._to_ms(time.perf_counter() - browser_launch_start)  # noqa: SLF001

    html_injection_start = time.perf_counter()
    try:
        html = renderer._render_html(template_name, payload, normalized_lineup)  # noqa: SLF001
        page = browser.new_page()
        page.set_viewport_size(
            {
                "width": int(payload["template"]["width"]),
                "height": int(payload["template"]["height"]),
            }
        )
        page.set_content(html, timeout=int(payload["render"]["timeout_ms"]))
    except Exception as exc:
        browser.close()
        return renderer._error_output(  # noqa: SLF001
            code="PLAYWRIGHT_TEMPLATE_INJECTION_FAILED",
            message=f"Falló la inyección de datos en la plantilla: {exc}",
            request_id=request_id,
            stage="data_bind",
            retryable=False,
            started_at=started_at,
        )
    html_injection_ms = renderer._to_ms(time.perf_counter() - html_injection_start)  # noqa: SLF001

    screenshot_start = time.perf_counter()
    try:
        png_bytes = page.screenshot(
            type="png",
            full_page=True,
            timeout=int(payload["render"]["timeout_ms"]),
        )
    except Exception as exc:
        browser.close()
        return renderer._error_output(  # noqa: SLF001
            code="PLAYWRIGHT_SCREENSHOT_FAILED",
            message=f"Falló la captura de pantalla: {exc}",
            request_id=request_id,
            stage="screenshot",
            retryable=True,
            started_at=started_at,
        )
    finally:
        browser.close()
    screenshot_ms = renderer._to_ms(time.perf_counter() - screenshot_start)  # noqa: SLF001

    upload_start = time.perf_counter()
    try:
        storage_path, public_url = renderer._upload_to_supabase(  # noqa: SLF001
            png_bytes=png_bytes,
            event_date=payload["event"]["date"],
            request_id=request_id,
        )
    except Exception as exc:
        return renderer._error_output(  # noqa: SLF001
            code="STORAGE_UPLOAD_FAILED",
            message=f"Falló la subida a Supabase Storage: {exc}",
            request_id=request_id,
            stage="upload",
            retryable=True,
            started_at=started_at,
        )
    upload_ms = renderer._to_ms(time.perf_counter() - upload_start)  # noqa: SLF001

    checksum = hashlib.sha256(png_bytes).hexdigest()
    execution_time_ms = renderer._to_ms(time.perf_counter() - started_at)  # noqa: SLF001
    render_id = str(uuid.uuid4())

    return {
        "status": "success",
        "request_id": request_id,
        "render_id": render_id,
        "storage": {
            "provider": "supabase",
            "bucket": "posters",
            "path": storage_path,
            "storage_url": public_url,
            "public_url": public_url,
            "public": True,
        },
        "artifact": {
            "format": "png",
            "dimensions": {
                "width": int(payload["template"]["width"]),
                "height": int(payload["template"]["height"]),
            },
            "size_bytes": len(png_bytes),
            "checksum_sha256": checksum,
        },
        "timing": {
            "execution_time_ms": execution_time_ms,
            "browser_launch_ms": browser_launch_ms,
            "html_injection_ms": html_injection_ms,
            "screenshot_ms": screenshot_ms,
            "upload_ms": upload_ms,
        },
        "warnings": warnings,
        "meta": {
            "schema_version": _SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engine": "playwright-chromium",
            "engine_version": renderer._engine_version(),  # noqa: SLF001
        },
    }


def _validate_input_payload(payload: dict[str, Any]) -> str | None:
    if not isinstance(payload, dict):
        return "Payload inválido: se esperaba un objeto JSON."

    request_id = payload.get("request_id")
    try:
        uuid.UUID(str(request_id))
    except Exception:
        return "request_id es obligatorio y debe ser UUID válido."

    if payload.get("schema_version") != _SCHEMA_VERSION:
        return "schema_version inválido; valor permitido: 1.0"

    event = payload.get("event")
    if not isinstance(event, dict):
        return "event es obligatorio y debe ser objeto."

    event_date = str(event.get("date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event_date):
        return "event.date es obligatorio con formato YYYY-MM-DD."
    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        return "event.date no representa una fecha válida del calendario."

    if event.get("timezone") != _ALLOWED_TIMEZONE:
        return "event.timezone inválido; valor permitido: Europe/Madrid."

    lineup = payload.get("lineup")
    if not isinstance(lineup, list) or not (1 <= len(lineup) <= 8):
        return "lineup debe ser un array de 1 a 8 elementos."

    used_orders: set[int] = set()
    for index, comic in enumerate(lineup, start=1):
        if not isinstance(comic, dict):
            return f"lineup[{index}] debe ser un objeto."

        order = comic.get("order")
        if not isinstance(order, int) or order <= 0:
            return f"lineup[{index}].order debe ser entero positivo."
        if order in used_orders:
            return "lineup[].order no puede tener duplicados."
        used_orders.add(order)

        name = comic.get("name")
        if not isinstance(name, str) or not name.strip():
            return f"lineup[{index}].name es obligatorio y no puede estar vacío."

        instagram = comic.get("instagram")
        if instagram is not None:
            if not isinstance(instagram, str):
                return f"lineup[{index}].instagram debe ser string o null."
            cleaned = instagram.strip()
            if cleaned.startswith("@") or "instagram.com" in cleaned.lower() or "/" in cleaned:
                return f"lineup[{index}].instagram debe venir limpio (sin @ ni URL)."

    template = payload.get("template")
    if not isinstance(template, dict):
        return "template es obligatorio y debe ser objeto."

    if template.get("template_id") != _ALLOWED_TEMPLATE_ID:
        return "template.template_id inválido; valor permitido: lineup_default_v1."

    if not isinstance(template.get("width"), int) or int(template["width"]) <= 0:
        return "template.width debe ser entero > 0."

    if not isinstance(template.get("height"), int) or int(template["height"]) <= 0:
        return "template.height debe ser entero > 0."

    if template.get("theme") != _ALLOWED_THEME:
        return "template.theme inválido; valor permitido: default."

    render = payload.get("render")
    if not isinstance(render, dict):
        return "render es obligatorio y debe ser objeto."

    if render.get("format") != _ALLOWED_RENDER_FORMAT:
        return "render.format inválido; valor permitido: png."

    timeout_ms = render.get("timeout_ms")
    if not isinstance(timeout_ms, int) or not (3000 <= timeout_ms <= 60000):
        return "render.timeout_ms debe estar entre 3000 y 60000."

    quality = render.get("quality")
    if not isinstance(quality, int) or not (1 <= quality <= 100):
        return "render.quality debe ser entero entre 1 y 100."

    scale = render.get("scale")
    if not isinstance(scale, int) or scale <= 0:
        return "render.scale debe ser entero positivo."

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return "metadata es obligatorio y debe ser objeto."

    initiated_at = metadata.get("initiated_at")
    if not isinstance(initiated_at, str):
        return "metadata.initiated_at es obligatorio en formato ISO-8601."
    try:
        datetime.fromisoformat(initiated_at.replace("Z", "+00:00"))
    except ValueError:
        return "metadata.initiated_at debe tener formato ISO-8601 válido."

    trace_id = metadata.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        return "metadata.trace_id es obligatorio y no puede estar vacío."

    return None


def _error_response(
    request_id: str | None,
    code: str,
    message: str,
    stage: str,
    retryable: bool,
    http_status: int,
) -> tuple[Any, int]:
    return (
        jsonify(
            {
                "status": "error",
                "request_id": request_id,
                "error": {
                    "code": code,
                    "message": message,
                    "details": {
                        "stage": stage,
                        "retryable": retryable,
                    },
                },
                "meta": {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "schema_version": _SCHEMA_VERSION,
                },
            }
        ),
        http_status,
    )


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
