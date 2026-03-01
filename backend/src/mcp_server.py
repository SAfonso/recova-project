"""MCP server orchestration for lineup rendering (SDD §14/§15).

This module exposes an async render tool and a programmatic orchestration
function used by integration tests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, async_playwright

from backend.src.core.data_binder import generate_injection_js
from backend.src.core.security import validate_reference_image


class FastMCP:
    """Minimal FastMCP-compatible registry used by this project tests.

    The runtime can replace this shim with the actual FastMCP implementation
    without changing the module contract.
    """

    def __init__(self, name: str):
        self.name = name
        self.tools: dict[str, Any] = {}

    def tool(self, fn: Any | None = None, *, name: str | None = None):
        def decorator(func: Any):
            self.tools[name or func.__name__] = func
            return func

        if fn is not None:
            return decorator(fn)
        return decorator


mcp = FastMCP("recova-mcp-renderer")
render_lock = asyncio.Lock()


def _safe_event_slug(event_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in event_id)


async def execute_render(
    *,
    payload: dict[str, Any],
    injection_script: str,
    browser_context: BrowserContext | None = None,
) -> dict[str, Any]:
    """Run Playwright rendering flow and return a structured success payload."""
    intent = payload.get("intent", {})
    template_id = intent.get("template_id", "active")
    event_id = payload["event_id"]

    template_html = (
        Path(__file__).resolve().parent
        / "templates"
        / "catalog"
        / str(template_id)
        / "template.html"
    )

    if not template_html.exists():
        raise FileNotFoundError(f"Template HTML not found: {template_html}")

    screenshot_path = Path("/tmp") / f"render_{_safe_event_slug(event_id)}.png"
    page = None

    if browser_context is not None:
        page = await browser_context.new_page()
        await page.goto(template_html.resolve().as_uri())
        await page.add_script_tag(content=injection_script)
        await page.wait_for_function("window.renderReady === true")
        await page.screenshot(path=str(screenshot_path), full_page=True)
        await page.close()
    else:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(template_html.resolve().as_uri())
            await page.add_script_tag(content=injection_script)
            await page.wait_for_function("window.renderReady === true")
            await page.screenshot(path=str(screenshot_path), full_page=True)
            await context.close()
            await browser.close()

    return {
        "status": "success",
        "output": {
            "public_url": str(screenshot_path),
            "image_path": str(screenshot_path),
        },
        "trace": {
            "engine": "playwright-chromium",
            "generation_mode": "template_catalog",
            "template_id": template_id,
            "warnings": [],
            "recovery_notes": "",
        },
    }


async def orchestrate_render(payload: dict[str, Any], workdir: Path | None = None) -> dict[str, Any]:
    """Apply validation + rendering with global lock and non-blocking failures."""
    del workdir  # Reserved for future storage abstractions.

    event_id = str(payload.get("event_id", "unknown-event"))
    trace: dict[str, Any] = {
        "engine": "playwright-chromium",
        "generation_mode": "template_catalog",
        "template_id": payload.get("intent", {}).get("template_id", "active"),
        "warnings": [],
        "recovery_notes": "",
    }

    safe_payload = {
        "event_id": event_id,
        "lineup": payload.get("lineup", []),
        "intent": {
            "template_id": payload.get("intent", {}).get("template_id", "active"),
            "reference_image_url": payload.get("intent", {}).get("reference_image_url"),
        },
    }

    reference_image_url = safe_payload["intent"].get("reference_image_url")
    if reference_image_url:
        security_result = validate_reference_image(reference_image_url)
        if not security_result.get("status", False):
            safe_payload["intent"]["template_id"] = "active"
            trace["template_id"] = "active"
            trace["warnings"].append("SYSTEM_FALLBACK_TRIGGERED")
            trace["recovery_notes"] = (
                "Imagen de referencia inválida, se usó plantilla activa "
                f"({security_result.get('error_code', 'UNKNOWN_ERROR')})"
            )

    injection_script = generate_injection_js(safe_payload.get("lineup", []))

    async with render_lock:
        try:
            render_result = await execute_render(payload=safe_payload, injection_script=injection_script)
            merged_trace = {**trace, **render_result.get("trace", {})}
            if trace.get("warnings"):
                existing = list(merged_trace.get("warnings", []))
                merged_trace["warnings"] = [*existing, *trace["warnings"]]
            if trace.get("recovery_notes"):
                merged_trace["recovery_notes"] = trace["recovery_notes"]
            return {
                "status": render_result.get("status", "success"),
                "event_id": event_id,
                "output": render_result.get("output", {}),
                "image_path": render_result.get("output", {}).get("image_path")
                or render_result.get("output", {}).get("public_url"),
                "trace": merged_trace,
            }
        except Exception as exc:  # noqa: BLE001 - hard requirement: non-blocking server behavior.
            error_notes = trace.get("recovery_notes", "")
            trace["recovery_notes"] = (error_notes + " | " if error_notes else "") + str(exc)
            trace["warnings"].append("RENDER_EXECUTION_FAILED")
            return {
                "status": "error",
                "event_id": event_id,
                "image_path": None,
                "output": {
                    "public_url": None,
                    "error_code": "ERR_RENDER_ENGINE_CRASH",
                    "message": "Playwright render execution failed",
                },
                "trace": trace,
            }


@mcp.tool(name="render_lineup")
async def render_lineup(
    event_id: str,
    lineup: list[dict[str, Any]],
    reference_image_url: str | None = None,
    template_id: str = "active",
) -> dict[str, Any]:
    """MCP tool entrypoint for lineup rendering."""
    payload = {
        "event_id": event_id,
        "lineup": lineup,
        "intent": {
            "template_id": template_id,
            "reference_image_url": reference_image_url,
        },
    }
    return await orchestrate_render(payload)
