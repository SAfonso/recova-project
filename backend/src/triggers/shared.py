"""Shared helpers, constants and auth for all webhook blueprints."""

import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import request
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

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-KEY, Accept",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
}


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
        sb = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_KEY", ""))
        response = sb.auth.get_user(token)
        user = response.user
        if not user:
            return None
        return {"sub": user.id, "email": user.email}
    except Exception:
        return None


def _sb_client():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


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
