"""Render poster endpoint — absorbe lógica de mcp_server.py convertida a sync."""

import glob
import logging
import os
import re
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_file

from backend.src.core.poster_composer import PosterComposer
from backend.src.core.poster_detector_base import render_on_anchors
from backend.src.core.poster_detector_gemini import GeminiDetector
from backend.src.core.security import validate_reference_image
from backend.src.triggers.shared import api_error, require_api_key

bp = Blueprint("poster", __name__)

logger = logging.getLogger("backend.poster")

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


def _safe_event_slug(event_id: str) -> str:
    return "".join(c if c.isalnum() or c in {"-", "_"} else "_" for c in event_id)


def _resolve_font_by_name(font_name: str, fallback: Path) -> Path:
    """Busca la fuente por nombre: sistema → sustitución → Google Fonts CSS → GitHub fonts → fallback."""
    if not font_name:
        return fallback

    key = font_name.lower().strip()
    if key in _FONT_SUBSTITUTIONS:
        substitute = _FONT_SUBSTITUTIONS[key]
        logger.info("Sustitución de fuente: '%s' → '%s'", font_name, substitute)
        font_name = substitute

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

    # 2. Google Fonts
    for css_url in [
        f"https://fonts.googleapis.com/css?family={family}",
        f"https://fonts.googleapis.com/css2?family={family}:wght@400;700",
    ]:
        result = _fetch_css_ttf(css_url, "Google Fonts")
        if result:
            return result

    # 3. Bunny Fonts
    for css_url in [
        f"https://fonts.bunny.net/css?family={family_lower}",
        f"https://fonts.bunny.net/css2?family={family_lower}:wght@400;700",
    ]:
        result = _fetch_css_ttf(css_url, "Bunny Fonts")
        if result:
            return result

    # 4. FontShare
    fontshare_url = f"https://api.fontshare.com/v2/css?f[]={family_lower}@400,700&display=swap"
    result = _fetch_css_ttf(fontshare_url, "FontShare")
    if result:
        return result

    # 5. GitHub google/fonts
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
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    urllib.request.urlretrieve(url, tmp.name)
    return Path(tmp.name)


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


def execute_render(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Render del cartel (sync). Pipeline A (Gemini) o B (PosterComposer)."""
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

    base_image_url  = payload.get("intent", {}).get("reference_image_url")
    dirty_image_url = None

    open_mic_id = payload.get("open_mic_id")
    if open_mic_id:
        try:
            from backend.src.triggers.shared import _sb_client
            _sb = _sb_client()
            row = _sb.schema("silver").from_("open_mics").select("config").eq("id", open_mic_id).single().execute()
            cfg = (row.data or {}).get("config") or {}
            poster_cfg = cfg.get("poster") or {}
            base_image_url  = base_image_url or poster_cfg.get("base_image_url")
            dirty_image_url = poster_cfg.get("dirty_image_url")
        except Exception as exc:
            logger.warning("No se pudo cargar config del open_mic: %s", exc)

    tmp_files: list[Path] = []

    try:
        # Pipeline A: Gemini detecta anchors del cartel sucio
        if dirty_image_url and base_image_url and lineup:
            try:
                dirty_path = _download_tmp(dirty_image_url)
                tmp_files.append(dirty_path)
                clean_path = _download_tmp(base_image_url)
                tmp_files.append(clean_path)

                detector = GeminiDetector()
                anchors  = detector.detect(dirty_path)

                from PIL import Image as _PILImg
                with _PILImg.open(dirty_path) as _di:
                    dirty_w, dirty_h = _di.size
                with _PILImg.open(clean_path) as _ci:
                    clean_w, clean_h = _ci.size
                scale_x = clean_w / dirty_w if dirty_w else 1.0
                scale_y = clean_h / dirty_h if dirty_h else 1.0
                if scale_x != 1.0 or scale_y != 1.0:
                    for a in anchors:
                        a.center_x  = int(a.center_x  * scale_x)
                        a.center_y  = int(a.center_y  * scale_y)
                        a.font_size = int(a.font_size  * scale_y)

                comic_anchors = [a for a in anchors if a.slot >= 1]
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
                    date_anchor_obj = next((a for a in anchors if a.slot == 0), None)
                    date_anchor    = (date_anchor_obj.center_x, date_anchor_obj.center_y) if date_anchor_obj else (540, 80)
                    date_font_size = date_anchor_obj.font_size if date_anchor_obj else 60
                    render_on_anchors(
                        clean_path=clean_path,
                        assignments=assignments,
                        font_path=font_path,
                        date=date_text,
                        date_anchor=date_anchor,
                        date_font_size=date_font_size,
                        output_path=output_path,
                    )
                    return _render_success(output_path, payload)
                else:
                    logger.warning("Gemini no detectó anchors — fallback a PosterComposer")
            except Exception as exc:
                logger.warning("Pipeline A falló (%s) — fallback a PosterComposer", exc)

        # Pipeline B: PosterComposer con imagen limpia o template
        base_image_path = None
        if base_image_url:
            try:
                tmp_clean = _download_tmp(base_image_url)
                tmp_files.append(tmp_clean)
                base_image_path = tmp_clean
            except Exception as exc:
                logger.warning("No se pudo descargar base_image_url: %s", exc)

        composer = PosterComposer(base_image_path=base_image_path)
        composer.render(
            lineup=lineup,
            date=date_text,
            event_id=event_id,
            output_path=output_path,
        )

    finally:
        for f in tmp_files:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

    return _render_success(output_path, payload)


def orchestrate_render(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida, aplica security gate y delega a execute_render (sync)."""
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

    try:
        render_result = execute_render(payload=safe_payload)
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
    except Exception as exc:
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


@bp.route("/api/render-poster", methods=["POST"])
def render_poster() -> tuple:
    """Renderiza el cartel del lineup usando el pipeline Gemini+render_on_anchors."""
    err = require_api_key()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    lineup = data.get("lineup") or []

    if not lineup:
        return api_error("VALIDATION_ERROR", "lineup requerido", 400)

    payload = {
        "event_id": str(data.get("event_id") or "evento"),
        "open_mic_id": data.get("open_mic_id"),
        "lineup": lineup,
        "date": data.get("date"),
    }

    try:
        result = orchestrate_render(payload)
    except Exception as exc:
        return api_error("INTERNAL_ERROR", "error al renderizar el poster", 500, details=str(exc))

    if result.get("status") != "success":
        msg = result.get("output", {}).get("message", "render error")
        return api_error("INTERNAL_ERROR", msg, 500)

    output_path = result.get("image_path") or result.get("output", {}).get("image_path", "")
    if not output_path or not Path(output_path).exists():
        return api_error("INTERNAL_ERROR", "archivo no generado", 500)

    return send_file(str(output_path), mimetype="image/png")
