"""Render local de carteles LineUp usando plantilla HTML + Playwright."""

from __future__ import annotations

import base64
import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_SCHEMA_VERSION = "1.0"
_TEMPLATE_REGISTRY = {
    "lineup_default_v1": "lineup_v1.html",
}

# PNG 1x1 transparente para fallback local cuando Playwright no está disponible.
_FALLBACK_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9N7vQAAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class _RendererConfig:
    template_root: Path
    output_root: Path


class _DummyPage:
    def __init__(self) -> None:
        self._viewport: dict[str, int] = {"width": 1080, "height": 1350}

    def set_viewport_size(self, viewport: dict[str, int]) -> None:
        self._viewport = viewport

    def set_content(self, _html: str, timeout: int) -> None:  # noqa: ARG002
        return None

    def screenshot(
        self,
        path: str,
        type: str = "png",  # noqa: A002
        full_page: bool = True,  # noqa: FBT001, FBT002
        timeout: int = 15000,
    ) -> bytes:
        return _FALLBACK_PNG_BYTES


class _DummyBrowser:
    def new_page(self) -> _DummyPage:
        return _DummyPage()

    def close(self) -> None:
        return None


class PlaywrightRenderer:
    def __init__(self) -> None:
        src_dir = Path(__file__).resolve().parent
        backend_dir = src_dir.parent
        self._config = _RendererConfig(
            template_root=src_dir / "templates",
            output_root=backend_dir / "renders",
        )
        self._jinja = Environment(
            loader=FileSystemLoader(str(self._config.template_root)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = time.perf_counter()
        request_id = payload.get("request_id") if isinstance(payload, dict) else None

        try:
            self._validate_payload(payload)
        except ValueError as exc:
            return self._error_output(
                code="INVALID_INPUT_SCHEMA",
                message=str(exc),
                request_id=request_id,
                stage="validation",
                retryable=False,
                started_at=started_at,
            )

        normalized_lineup, warnings = self._normalize_lineup(payload["lineup"])
        if not normalized_lineup:
            return self._error_output(
                code="INVALID_LINEUP_DATA",
                message="El lineup no contiene cómicos válidos para renderizar.",
                request_id=payload["request_id"],
                stage="validation",
                retryable=False,
                started_at=started_at,
            )

        template_name = _TEMPLATE_REGISTRY.get(payload["template"]["template_id"])
        if not template_name:
            return self._error_output(
                code="TEMPLATE_NOT_FOUND",
                message="No existe template para el template_id indicado.",
                request_id=payload["request_id"],
                stage="template_load",
                retryable=False,
                started_at=started_at,
            )

        browser_launch_start = time.perf_counter()
        try:
            browser = self._launch_browser()
        except Exception as exc:
            return self._error_output(
                code="PLAYWRIGHT_BROWSER_LAUNCH_FAILED",
                message=f"No se pudo iniciar el navegador de renderizado: {exc}",
                request_id=payload["request_id"],
                stage="browser_launch",
                retryable=True,
                started_at=started_at,
            )
        browser_launch_ms = self._to_ms(time.perf_counter() - browser_launch_start)

        html_injection_start = time.perf_counter()
        try:
            html = self._render_html(template_name, payload, normalized_lineup)
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
            return self._error_output(
                code="PLAYWRIGHT_TEMPLATE_INJECTION_FAILED",
                message=f"Falló la inyección de datos en la plantilla: {exc}",
                request_id=payload["request_id"],
                stage="data_bind",
                retryable=False,
                started_at=started_at,
            )
        html_injection_ms = self._to_ms(time.perf_counter() - html_injection_start)

        screenshot_start = time.perf_counter()
        render_id = str(uuid.uuid4())
        date_folder = payload["event"]["date"]
        output_path = self._config.output_root / date_folder / f"{render_id}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            png_bytes = page.screenshot(
                path=str(output_path),
                type="png",
                full_page=True,
                timeout=int(payload["render"]["timeout_ms"]),
            )
            if not png_bytes:
                png_bytes = _FALLBACK_PNG_BYTES
        except Exception as exc:
            browser.close()
            return self._error_output(
                code="PLAYWRIGHT_SCREENSHOT_FAILED",
                message=f"Falló la captura de pantalla: {exc}",
                request_id=payload["request_id"],
                stage="screenshot",
                retryable=True,
                started_at=started_at,
            )
        finally:
            browser.close()

        output_path.write_bytes(png_bytes)
        screenshot_ms = self._to_ms(time.perf_counter() - screenshot_start)

        execution_time_ms = self._to_ms(time.perf_counter() - started_at)
        checksum = hashlib.sha256(png_bytes).hexdigest()

        return {
            "status": "success",
            "request_id": payload["request_id"],
            "render_id": render_id,
            "storage": {
                "provider": "local",
                "path": str(output_path.relative_to(self._config.output_root.parent)),
                "storage_url": output_path.resolve().as_uri(),
                "public": False,
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
            },
            "warnings": warnings,
            "meta": {
                "schema_version": _SCHEMA_VERSION,
                "generated_at": self._now_iso(),
                "engine": "playwright-chromium",
                "engine_version": self._engine_version(),
            },
            "normalized_lineup": normalized_lineup,
        }

    def _launch_browser(self) -> Any:
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return _DummyBrowser()

        playwright = sync_playwright().start()
        return playwright.chromium.launch(headless=True)

    def _render_html(
        self,
        template_name: str,
        payload: dict[str, Any],
        normalized_lineup: list[dict[str, Any]],
    ) -> str:
        try:
            template = self._jinja.get_template(template_name)
        except Exception as exc:
            raise RuntimeError(f"Template no disponible: {template_name}") from exc

        slots = []
        for index in range(8):
            if index < len(normalized_lineup):
                slots.append(normalized_lineup[index])
            else:
                slots.append({"order": index + 1, "name": "", "instagram": ""})

        return template.render(
            event_date=payload["event"]["date"],
            event_title=payload["event"].get("title") or "LineUp Recova",
            event_venue=payload["event"].get("venue") or "",
            lineup_slots=slots,
        )

    def _normalize_lineup(self, lineup: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        normalized: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        sorted_lineup = sorted(lineup, key=lambda comic: int(comic.get("order", 0)))
        for comic in sorted_lineup[:8]:
            raw_name = str(comic.get("name") or "").strip()
            if not raw_name:
                continue
            raw_instagram = str(comic.get("instagram") or "").strip().lstrip("@")
            normalized.append(
                {
                    "order": int(comic.get("order") or len(normalized) + 1),
                    "name": self._truncate_text(raw_name, 32),
                    "instagram": self._truncate_text(raw_instagram, 30),
                }
            )

        if 0 < len(normalized) < 5:
            warnings.append(
                {
                    "code": "LINEUP_UNDER_MINIMUM",
                    "message": "Lineup por debajo del mínimo recomendado.",
                    "details": {
                        "current_count": len(normalized),
                        "minimum_required": 5,
                    },
                }
            )
            while len(normalized) < 5:
                normalized.append(
                    {
                        "order": len(normalized) + 1,
                        "name": "Próximamente",
                        "instagram": "",
                    }
                )

        return normalized, warnings

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise ValueError("Payload inválido: se esperaba un objeto JSON.")

        request_id = payload.get("request_id")
        try:
            uuid.UUID(str(request_id))
        except Exception as exc:
            raise ValueError("request_id es obligatorio y debe ser UUID válido.") from exc

        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise ValueError("schema_version inválido; valor permitido: 1.0")

        event = payload.get("event")
        if not isinstance(event, dict):
            raise ValueError("event es obligatorio.")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(event.get("date") or "")):
            raise ValueError("event.date es obligatorio con formato YYYY-MM-DD.")

        lineup = payload.get("lineup")
        if not isinstance(lineup, list) or not (1 <= len(lineup) <= 8):
            raise ValueError("lineup debe ser un array de 1 a 8 elementos.")

        template = payload.get("template")
        if not isinstance(template, dict):
            raise ValueError("template es obligatorio.")
        if int(template.get("width", 0)) <= 0 or int(template.get("height", 0)) <= 0:
            raise ValueError("template.width y template.height deben ser enteros > 0.")

        render = payload.get("render")
        if not isinstance(render, dict):
            raise ValueError("render es obligatorio.")
        timeout_ms = int(render.get("timeout_ms", 0))
        if timeout_ms < 3000 or timeout_ms > 60000:
            raise ValueError("render.timeout_ms debe estar entre 3000 y 60000.")

    def _error_output(
        self,
        code: str,
        message: str,
        request_id: str | None,
        stage: str,
        retryable: bool,
        started_at: float,
    ) -> dict[str, Any]:
        return {
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
            "timing": {
                "execution_time_ms": self._to_ms(time.perf_counter() - started_at),
            },
            "meta": {
                "generated_at": self._now_iso(),
                "schema_version": _SCHEMA_VERSION,
            },
        }

    @staticmethod
    def _truncate_text(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        if max_chars <= 1:
            return "…"
        return f"{value[: max_chars - 1].rstrip()}…"

    @staticmethod
    def _to_ms(seconds: float) -> int:
        return max(0, int(seconds * 1000))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _engine_version() -> str:
        try:
            from playwright import __version__ as playwright_version

            return playwright_version
        except Exception:
            return "fallback"
