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
from backend.src.core.poster_detector_base import render_on_anchors
from backend.src.core.poster_detector_gemini import GeminiDetector
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


mcp = RuntimeFastMCP("recova_mcp_renderer")
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


# Fuentes comerciales/no libres → sustitución con la alternativa libre más parecida
_FONT_SUBSTITUTIONS: dict[str, str] = {
    "badaboom bb": "Bangers",
    "badaboombb": "Bangers",
    "blambot": "Bangers",
    "comic sans ms": "Comic Neue",
    "helvetica": "Inter",
    "helvetica neue": "Inter",
    "futura": "Nunito",
    "gotham": "Montserrat",
    "brandon grotesque": "Raleway",
    "proxima nova": "Nunito Sans",
}


def _resolve_font_by_name(font_name: str, fallback: Path) -> Path:
    """Busca la fuente por nombre: sistema → sustitución → Google Fonts CSS → GitHub fonts → fallback."""
    if not font_name:
        return fallback

    # Sustitución de fuentes comerciales por alternativas libres
    key = font_name.lower().strip()
    if key in _FONT_SUBSTITUTIONS:
        substitute = _FONT_SUBSTITUTIONS[key]
        logger.info("Sustitución de fuente: '%s' → '%s'", font_name, substitute)
        font_name = substitute

    import glob
    import re
    import tempfile
    import urllib.request

    slug = font_name.lower().replace(" ", "").replace("-", "").replace("_", "")

    # 1. Buscar en fuentes del sistema
    font_dirs = ["/usr/share/fonts", "/usr/local/share/fonts", str(Path.home() / ".fonts")]
    for d in font_dirs:
        for ext in ("ttf", "otf", "TTF", "OTF"):
            for path in glob.glob(f"{d}/**/*.{ext}", recursive=True):
                stem = Path(path).stem.lower().replace(" ", "").replace("-", "").replace("_", "")
                if slug in stem or stem in slug:
                    logger.info("Fuente del sistema: %s", path)
                    return Path(path)

    def _download_url(url: str, suffix: str = ".ttf") -> Path | None:
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            urllib.request.urlretrieve(url, tmp.name)
            logger.info("Fuente descargada: %s", url)
            return Path(tmp.name)
        except Exception as exc:
            logger.warning("Descarga fallida %s: %s", url, exc)
            return None

    family = font_name.strip().replace(" ", "+")
    family_lower = font_name.strip().replace(" ", "-").lower()

    def _fetch_css_ttf(css_url: str, source_name: str) -> Path | None:
        """Descarga CSS de una fuente API y extrae la URL TTF."""
        try:
            req = urllib.request.Request(
                css_url,
                headers={"User-Agent": "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"},
            )
            css = urllib.request.urlopen(req, timeout=6).read().decode()
            match = re.search(r"url\(['\"]?(https://[^'\")]+\.ttf)['\"]?\)", css)
            if match:
                result = _download_url(match.group(1))
                if result:
                    logger.info("Fuente de %s: %s", source_name, font_name)
                    return result
        except Exception as exc:
            logger.warning("%s fallido (%s): %s", source_name, css_url, exc)
        return None

    # 2. Google Fonts (CSS v1 y v2 con UA antiguo → devuelve TTF)
    for css_url in [
        f"https://fonts.googleapis.com/css?family={family}",
        f"https://fonts.googleapis.com/css2?family={family}:wght@400;700",
    ]:
        result = _fetch_css_ttf(css_url, "Google Fonts")
        if result:
            return result

    # 3. Bunny Fonts (mirror privado de Google Fonts, misma API)
    for css_url in [
        f"https://fonts.bunny.net/css?family={family_lower}",
        f"https://fonts.bunny.net/css2?family={family_lower}:wght@400;700",
    ]:
        result = _fetch_css_ttf(css_url, "Bunny Fonts")
        if result:
            return result

    # 4. FontShare (fuentes de alta calidad, acceso libre)
    fontshare_url = f"https://api.fontshare.com/v2/css?f[]={family_lower}@400,700&display=swap"
    result = _fetch_css_ttf(fontshare_url, "FontShare")
    if result:
        return result

    # 5. Repo oficial google/fonts en GitHub (TTF directos, varios licencias)
    github_slug = font_name.lower().replace(" ", "").replace("-", "")
    github_name = font_name.replace(" ", "")
    for license_dir in ("ofl", "apache", "ufl"):
        for style in ("Regular", "Bold", ""):
            suffix = f"-{style}" if style else ""
            url = f"https://github.com/google/fonts/raw/main/{license_dir}/{github_slug}/{github_name}{suffix}.ttf"
            result = _download_url(url)
            if result and result.stat().st_size > 1000:
                logger.info("Fuente de GitHub google/fonts (%s): %s", license_dir, font_name)
                return result

    logger.info("Usando fuente fallback para '%s'", font_name)
    return fallback


def _download_tmp(url: str, suffix: str = ".png") -> Path:
    """Descarga una URL a un archivo temporal y devuelve su Path."""
    import tempfile
    import urllib.request
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    urllib.request.urlretrieve(url, tmp.name)
    return Path(tmp.name)


async def execute_render(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Render del cartel y devuelve payload estructurado.

    Pipeline A (preferido): dirty_image_url disponible
        GeminiDetector detecta anchors → render_on_anchors estampa nombres
        con la tipografía, tamaño y posición del diseño original.

    Pipeline B (fallback): solo base_image_url o template local
        PosterComposer con layout adaptativo propio.
    """
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

    # ── Obtener URLs de imágenes del config del open_mic ──────────────
    base_image_url  = payload.get("intent", {}).get("reference_image_url")
    dirty_image_url = None

    open_mic_id = payload.get("open_mic_id")
    if open_mic_id:
        try:
            from supabase import create_client as _create_client
            _sb = _create_client(
                os.getenv("SUPABASE_URL", ""),
                os.getenv("SUPABASE_SERVICE_KEY", ""),
            )
            row = _sb.schema("silver").from_("open_mics").select("config").eq("id", open_mic_id).single().execute()
            cfg = (row.data or {}).get("config") or {}
            poster_cfg = cfg.get("poster") or {}
            base_image_url  = base_image_url or poster_cfg.get("base_image_url")
            dirty_image_url = poster_cfg.get("dirty_image_url")
        except Exception as exc:
            logger.warning("No se pudo cargar config del open_mic: %s", exc)

    loop = asyncio.get_running_loop()
    tmp_files: list[Path] = []

    try:
        # ── Pipeline A: Gemini detecta anchors del cartel sucio ───────
        if dirty_image_url and base_image_url and lineup:
            try:
                dirty_path = await loop.run_in_executor(None, lambda: _download_tmp(dirty_image_url))
                tmp_files.append(dirty_path)
                clean_path = await loop.run_in_executor(None, lambda: _download_tmp(base_image_url))
                tmp_files.append(clean_path)

                detector = GeminiDetector()
                anchors  = await loop.run_in_executor(None, lambda: detector.detect(dirty_path))

                # Escalar coordenadas si dirty y clean tienen distinto tamaño
                from PIL import Image as _PILImg
                with _PILImg.open(dirty_path) as _di:
                    dirty_w, dirty_h = _di.size
                with _PILImg.open(clean_path) as _ci:
                    clean_w, clean_h = _ci.size
                scale_x = clean_w / dirty_w if dirty_w else 1.0
                scale_y = clean_h / dirty_h if dirty_h else 1.0
                if scale_x != 1.0 or scale_y != 1.0:
                    logger.info(
                        "Escalando anchors dirty(%dx%d)→clean(%dx%d): sx=%.3f sy=%.3f",
                        dirty_w, dirty_h, clean_w, clean_h, scale_x, scale_y,
                    )
                    for a in anchors:
                        a.center_x  = int(a.center_x  * scale_x)
                        a.center_y  = int(a.center_y  * scale_y)
                        a.font_size = int(a.font_size  * scale_y)

                logger.info(
                    "Anchors detectados: %s",
                    [(a.slot, a.center_x, a.center_y, a.font_size) for a in anchors],
                )

                comic_anchors = [a for a in anchors if a.slot >= 1]
                # Normalizar posiciones Y: si hay anchors con spacing < 40px
                # (detección errónea de Gemini), redistribuir equitativamente
                if len(comic_anchors) >= 2:
                    sorted_by_y = sorted(comic_anchors, key=lambda a: a.center_y)
                    min_spacing = min(
                        sorted_by_y[i+1].center_y - sorted_by_y[i].center_y
                        for i in range(len(sorted_by_y) - 1)
                    )
                    if min_spacing < 40:
                        y_min = sorted_by_y[0].center_y
                        y_max = sorted_by_y[-1].center_y
                        y_range = max(y_max - y_min, 60 * (len(sorted_by_y) - 1))
                        step = y_range // (len(sorted_by_y) - 1)
                        for i, a in enumerate(sorted_by_y):
                            a.center_y = y_min + i * step
                        logger.info(
                            "Anchors Y normalizados (spacing mín %dpx < 40): step=%dpx",
                            min_spacing, step,
                        )
                if comic_anchors:
                    names = [c.get("name", "") for c in lineup]
                    assignments = [
                        (names[a.slot - 1], a)
                        for a in comic_anchors
                        if 1 <= a.slot <= len(names)
                    ]
                    fallback_font = PosterComposer()._resolve_font(None)
                    detected_font_name = comic_anchors[0].font_name
                    font_path = _resolve_font_by_name(detected_font_name, fallback_font)
                    if detected_font_name:
                        logger.info("Fuente detectada por Gemini: '%s'", detected_font_name)
                    # Fecha: usar anchor detectado (slot=0) o fallback
                    date_anchor_obj = next((a for a in anchors if a.slot == 0), None)
                    date_anchor    = (date_anchor_obj.center_x, date_anchor_obj.center_y) if date_anchor_obj else (540, 80)
                    date_font_size = date_anchor_obj.font_size if date_anchor_obj else 60
                    await loop.run_in_executor(
                        None,
                        lambda: render_on_anchors(
                            clean_path=clean_path,
                            assignments=assignments,
                            font_path=font_path,
                            date=date_text,
                            date_anchor=date_anchor,
                            date_font_size=date_font_size,
                            output_path=output_path,
                        ),
                    )
                    logger.info("Pipeline A (Gemini anchors): %d anchors detectados", len(anchors))
                    return _render_success(output_path, payload)
                else:
                    logger.warning("Gemini no detectó anchors — fallback a PosterComposer")
            except Exception as exc:
                logger.warning("Pipeline A falló (%s) — fallback a PosterComposer", exc)

        # ── Pipeline B: PosterComposer con imagen limpia o template ───
        base_image_path = None
        if base_image_url:
            try:
                tmp_clean = await loop.run_in_executor(None, lambda: _download_tmp(base_image_url))
                tmp_files.append(tmp_clean)
                base_image_path = tmp_clean
                logger.info("Pipeline B: usando base_image_url")
            except Exception as exc:
                logger.warning("No se pudo descargar base_image_url: %s", exc)

        composer = PosterComposer(base_image_path=base_image_path)
        await loop.run_in_executor(
            None,
            lambda: composer.render(
                lineup=lineup,
                date=date_text,
                event_id=event_id,
                output_path=output_path,
            ),
        )

    finally:
        for f in tmp_files:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

    return _render_success(output_path, payload)


def _render_success(output_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
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
        "open_mic_id": payload.get("open_mic_id"),
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
