"""MCP server — endpoint HTTP de render de lineup para n8n.

Motor: PosterComposer (Pillow + FreeType).
Expone POST /tools/render_lineup y GET /healthz.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from backend.src.core.poster_composer import PosterComposer
from backend.src.core.security import validate_reference_image


class FastMCP:
    """Shim mínimo de FastMCP para entornos sin librería MCP instalada."""

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


try:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _RuntimeFastMCP
except Exception:  # noqa: BLE001
    RuntimeFastMCP = FastMCP
else:
    RuntimeFastMCP = _RuntimeFastMCP


mcp = RuntimeFastMCP("recova-mcp-renderer")
render_lock = asyncio.Lock()

MCP_LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "mcp_render.log"
MCP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("backend.mcp_http")
if not logger.handlers:
    file_handler = logging.FileHandler(MCP_LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def _safe_event_slug(event_id: str) -> str:
    return "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in event_id)


async def execute_render(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Render del cartel con PosterComposer y devuelve payload estructurado."""
    event_id = payload["event_id"]
    lineup   = payload.get("lineup", [])

    event_data = payload.get("event", {})
    metadata   = payload.get("metadata", {})
    date_text = (
        payload.get("date")
        or event_data.get("date")
        or metadata.get("date_text")
        or event_id
    )

    output_path = Path("/tmp") / f"render_{_safe_event_slug(event_id)}.png"

    loop = asyncio.get_running_loop()
    composer = PosterComposer()
    await loop.run_in_executor(
        None,
        lambda: composer.render(
            lineup=lineup,
            date=date_text,
            event_id=event_id,
            output_path=output_path,
        ),
    )

    return {
        "status": "success",
        "output": {
            "public_url": str(output_path),
            "image_path": str(output_path),
        },
        "trace": {
            "engine": "pillow-freetype",
            "generation_mode": "direct_composite",
            "template_id": payload.get("intent", {}).get("template_id", "base_poster"),
            "warnings": [],
            "recovery_notes": "",
        },
    }


async def orchestrate_render(
    payload: dict[str, Any],
    workdir: Path | None = None,
) -> dict[str, Any]:
    """Valida, aplica security gate y delega a execute_render con lock global."""
    del workdir  # Reservado para futuras políticas de almacenamiento.

    event_id = str(payload.get("event_id", "unknown-event"))
    trace: dict[str, Any] = {
        "engine": "pillow-freetype",
        "generation_mode": "direct_composite",
        "template_id": payload.get("intent", {}).get("template_id", "base_poster"),
        "warnings": [],
        "recovery_notes": "",
    }

    safe_payload = {
        "event_id": event_id,
        "lineup": payload.get("lineup", []),
        "date": payload.get("date"),
        "event": payload.get("event", {}),
        "metadata": payload.get("metadata", {}),
        "intent": {
            "template_id": payload.get("intent", {}).get("template_id", "base_poster"),
            "reference_image_url": payload.get("intent", {}).get("reference_image_url"),
        },
    }

    reference_image_url = safe_payload["intent"].get("reference_image_url")
    if reference_image_url:
        security_result = validate_reference_image(reference_image_url)
        if not security_result.get("status", False):
            trace["warnings"].append("SYSTEM_FALLBACK_TRIGGERED")
            trace["recovery_notes"] = (
                "Imagen de referencia inválida, se usó plantilla activa "
                f"({security_result.get('error_code', 'UNKNOWN_ERROR')})"
            )

    async with render_lock:
        try:
            render_result = await execute_render(payload=safe_payload)
            merged_trace = {**trace, **render_result.get("trace", {})}
            if trace.get("warnings"):
                merged_trace["warnings"] = [
                    *list(render_result.get("trace", {}).get("warnings", [])),
                    *trace["warnings"],
                ]
            if trace.get("recovery_notes"):
                merged_trace["recovery_notes"] = trace["recovery_notes"]
            return {
                "status": render_result.get("status", "success"),
                "event_id": event_id,
                "output": render_result.get("output", {}),
                "image_path": render_result.get("output", {}).get("image_path"),
                "trace": merged_trace,
            }
        except Exception as exc:  # noqa: BLE001
            notes = trace.get("recovery_notes", "")
            trace["recovery_notes"] = (notes + " | " if notes else "") + str(exc)
            trace["warnings"].append("RENDER_EXECUTION_FAILED")
            return {
                "status": "error",
                "event_id": event_id,
                "image_path": None,
                "output": {
                    "public_url": None,
                    "error_code": "ERR_RENDER_ENGINE_CRASH",
                    "message": str(exc),
                },
                "trace": trace,
            }


@mcp.tool(name="render_lineup")
async def render_lineup(
    event_id: str,
    lineup: list[dict[str, Any]],
    reference_image_url: str | None = None,
    template_id: str = "base_poster",
) -> dict[str, Any]:
    """MCP tool entrypoint para render de lineup."""
    payload = {
        "event_id": event_id,
        "lineup": lineup,
        "intent": {
            "template_id": template_id,
            "reference_image_url": reference_image_url,
        },
    }
    return await orchestrate_render(payload)


def _build_http_app():
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import FileResponse
    except Exception:  # noqa: BLE001
        logger.warning("FastAPI no disponible; servidor HTTP no inicializado")
        return None

    app = FastAPI(title="recova-mcp-renderer")

    @app.middleware("http")
    async def request_log_middleware(request: Request, call_next):
        event_id = "unknown-event"
        if request.method.upper() == "POST":
            try:
                body = await request.json()
            except Exception:  # noqa: BLE001
                body = {}
            event_id = str(body.get("event_id", event_id))
        logger.info("HTTP %s %s event_id=%s", request.method, request.url.path, event_id)
        return await call_next(request)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tools/render_lineup")
    async def render_lineup_http(payload: dict[str, Any]):
        if not isinstance(payload.get("lineup"), list) or not payload.get("event_id"):
            raise HTTPException(status_code=422, detail="Invalid payload for render_lineup")

        event_id = str(payload.get("event_id", "unknown-event"))
        logger.info("render_lineup event_id=%s", event_id)

        render_result = await orchestrate_render(payload)

        if render_result.get("status") != "success":
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Render engine failed",
                    "details": (
                        render_result.get("trace", {}).get("recovery_notes")
                        or render_result.get("output", {}).get("message")
                        or "Unknown render failure"
                    ),
                },
            )

        output_path = str(
            render_result.get("image_path")
            or render_result.get("output", {}).get("image_path")
            or ""
        )
        if not output_path or not os.path.exists(output_path):
            raise HTTPException(status_code=500, detail="El archivo no se generó correctamente")

        return FileResponse(
            path=output_path,
            media_type="image/png",
            filename="cartel.png",
        )

    try:
        mcp_http_app = mcp.streamable_http_app()
    except Exception:  # noqa: BLE001
        logger.info("FastMCP streamable_http_app no disponible; solo REST activo")
    else:
        app.mount("/mcp", mcp_http_app)
        logger.info("FastMCP streamable_http_app habilitado en /mcp")

    return app


app = _build_http_app()


def run_http_server(host: str = "127.0.0.1", port: int = 5050) -> None:
    if app is None:
        raise RuntimeError("FastAPI/uvicorn no instalados.")

    import uvicorn

    print("[RECOVA-RENDER] Servidor escuchando en http://127.0.0.1:5050.")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_http_server(
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "5050")),
    )
