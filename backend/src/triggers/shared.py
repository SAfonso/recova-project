"""Shared helpers, constants and auth for all webhook blueprints."""

import functools
import os
import time
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import jsonify, request
from supabase import create_client

from backend.src.scoring_engine import execute_scoring  # noqa: F401 — re-export

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ROOT_ENV = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ROOT_ENV, override=False)

INGEST_SCRIPT_PATH = str(_PROJECT_ROOT / "backend" / "src" / "bronze_to_silver_ingestion.py")
SCORING_SCRIPT_PATH = str(_PROJECT_ROOT / "backend" / "src" / "scoring_engine.py")

API_KEY_HEADER = "X-API-KEY"
EXPECTED_API_KEY = os.getenv("WEBHOOK_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")

_ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000",
]

def _cors_origin() -> str:
    """Devuelve el origin permitido si coincide con la request, o el FRONTEND_URL por defecto."""
    origin = request.headers.get("Origin", "")
    if origin in _ALLOWED_ORIGINS:
        return origin
    return FRONTEND_URL

_CORS_HEADERS_BASE = {
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-KEY, Accept",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
}

def _cors_headers() -> dict:
    """CORS headers con origin dinámico basado en la request."""
    return {**_CORS_HEADERS_BASE, "Access-Control-Allow-Origin": _cors_origin()}


def api_error(code: str, message: str, status: int, details: str | None = None) -> tuple:
    """Genera una respuesta de error con formato unificado."""
    body: dict = {"status": "error", "error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status


# ---------------------------------------------------------------------------
# Rate limiting — in-memory por IP
# ---------------------------------------------------------------------------

_rate_limit_store: dict[str, list[float]] = {}
_rate_limit_lock = threading.Lock()


def _cleanup_timestamps(timestamps: list[float], window: float, now: float) -> list[float]:
    """Purga timestamps fuera de la ventana."""
    cutoff = now - window
    return [t for t in timestamps if t > cutoff]


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """Decorador que limita requests por IP con ventana deslizante.

    Devuelve 429 si se excede el límite. Añade headers X-RateLimit-* a cada respuesta.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            key = f"{fn.__name__}:{ip}"
            now = time.monotonic()

            with _rate_limit_lock:
                timestamps = _rate_limit_store.get(key, [])
                timestamps = _cleanup_timestamps(timestamps, window_seconds, now)

                remaining = max(0, max_requests - len(timestamps))

                if len(timestamps) >= max_requests:
                    _rate_limit_store[key] = timestamps
                    resp = api_error("RATE_LIMITED", "Too many requests", 429)
                    response = resp[0]  # jsonify object
                    response.headers["Retry-After"] = str(window_seconds)
                    response.headers["X-RateLimit-Limit"] = str(max_requests)
                    response.headers["X-RateLimit-Remaining"] = "0"
                    response.headers["X-RateLimit-Reset"] = str(window_seconds)
                    return response, resp[1]

                timestamps.append(now)
                _rate_limit_store[key] = timestamps
                remaining = max(0, max_requests - len(timestamps))

            response = fn(*args, **kwargs)

            # Inyectar headers en la respuesta
            if isinstance(response, tuple):
                resp_obj, status = response[0], response[1]
            else:
                resp_obj, status = response, 200

            resp_obj.headers["X-RateLimit-Limit"] = str(max_requests)
            resp_obj.headers["X-RateLimit-Remaining"] = str(remaining)
            resp_obj.headers["X-RateLimit-Reset"] = str(window_seconds)

            return resp_obj, status

        return wrapper
    return decorator


def validate_json(required: dict[str, type] | None = None):
    """Decorador que valida JSON body: parseo + campos obligatorios + tipos.

    Uso: @validate_json({"open_mic_id": str, "nombre": str})
    Devuelve 400 con mensaje claro si falla.
    Si required es None, solo valida que el body sea JSON válido.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            body = request.get_json(silent=True)
            if body is None:
                return api_error("INVALID_JSON", "Body must be valid JSON", 400)
            if required:
                missing = [k for k in required if k not in body or body[k] is None]
                if missing:
                    return api_error(
                        "MISSING_FIELDS",
                        f"Missing required fields: {', '.join(missing)}",
                        400,
                    )
                wrong_type = [
                    k for k, t in required.items()
                    if k in body and body[k] is not None and not isinstance(body[k], t)
                ]
                if wrong_type:
                    expected = {k: required[k].__name__ for k in wrong_type}
                    return api_error(
                        "INVALID_FIELD_TYPE",
                        f"Wrong field types: {expected}",
                        400,
                    )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_api_key() -> tuple | None:
    """Valida API key; devuelve api_error si falla, None si ok."""
    provided = request.headers.get(API_KEY_HEADER, "")
    if not EXPECTED_API_KEY or provided != EXPECTED_API_KEY:
        return api_error("UNAUTHORIZED", "unauthorized", 401)
    return None


def _is_authorized() -> bool:
    """Validate request API key using shared webhook header logic."""
    provided_api_key = request.headers.get(API_KEY_HEADER, "")
    return bool(EXPECTED_API_KEY and provided_api_key == EXPECTED_API_KEY)


def _is_authenticated_user() -> dict | None:
    """Verifica el Supabase JWT del request via auth.get_user (soporta ES256 y HS256)."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        response = _sb_client().auth.get_user(token)
        user = response.user
        if not user:
            return None
        return {"sub": user.id, "email": user.email}
    except Exception:
        return None


_SB_SINGLETON = None

def _sb_client():
    """Singleton Supabase client — reutiliza la misma instancia en todo el proceso."""
    global _SB_SINGLETON
    if _SB_SINGLETON is None:
        _SB_SINGLETON = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _SB_SINGLETON


# ---------------------------------------------------------------------------
# Helpers — calculo de proximo evento
# ---------------------------------------------------------------------------

_DIA_SEMANA_MAP = {
    "Lunes": 0, "Martes": 1, "Miércoles": 2, "Miercoles": 2,
    "Jueves": 3, "Viernes": 4, "Sábado": 5, "Sabado": 5, "Domingo": 6,
}


def _next_event_datetime(dia_semana: str, hora: str, now: datetime = None):
    """
    Devuelve el datetime UTC del proximo show futuro.
    Retorna None si el show de hoy ya empezo (→ 409 en el endpoint).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    target_weekday = _DIA_SEMANA_MAP.get(dia_semana)
    if target_weekday is None:
        raise ValueError(f"Dia no reconocido: {dia_semana}")
    h, m = map(int, hora.split(":"))
    days_ahead = (target_weekday - now.weekday() + 7) % 7
    candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if days_ahead == 0:
        if candidate <= now:
            return None  # show de hoy ya empezo
    else:
        candidate += timedelta(days=days_ahead)
    return candidate


# Mapeo campo canónico (FormAnalyzer) → columna bronze.solicitudes
_CANONICAL_TO_BRONZE = {
    "nombre_artistico":            "nombre_raw",
    "instagram":                   "instagram_raw",
    "whatsapp":                    "telefono_raw",
    "experiencia":                 "experiencia_raw",
    "fechas_disponibles":          "fechas_seleccionadas_raw",
    "backup":                      "disponibilidad_ultimo_minuto",
    "show_proximo":                "info_show_cercano",
    "como_nos_conociste":          "origen_conocimiento",
}


def run_ingestion_async():
    """Lanza el pipeline de ingesta bronze→silver en un thread daemon."""
    import sys
    from backend.src.bronze_to_silver_ingestion import run_pipeline

    def _run():
        try:
            run_pipeline()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
