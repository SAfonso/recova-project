"""Flask webhook listener for n8n ingestion trigger."""

import json
import os
import random
import string
import sys
import subprocess
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

import re
import tempfile
import urllib.request
from pathlib import Path as _Path

import jwt

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from supabase import create_client

from backend.src.core.poster_composer import PosterComposer
from backend.src.core.dev_users_pool import get_random_users
from backend.src.core.google_form_builder import GoogleFormBuilder
from backend.src.core.sheet_ingestor import SheetIngestor
from backend.src.core.form_ingestor import FormIngestor
from backend.src.core.form_analyzer import FormAnalyzer
from backend.src.core.custom_scoring_proposer import CustomScoringProposer
from backend.src.scoring_engine import execute_scoring

app = Flask(__name__)
CORS(app)

from pathlib import Path
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=_ROOT_ENV, override=False)
INGEST_SCRIPT_PATH = "/root/RECOVA/backend/src/bronze_to_silver_ingestion.py"
SCORING_SCRIPT_PATH = "/root/RECOVA/backend/src/scoring_engine.py"
API_KEY_HEADER = "X-API-KEY"
EXPECTED_API_KEY = os.getenv("WEBHOOK_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


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


@app.route("/ingest", methods=["POST"])
def ingest() -> tuple:
    """Trigger Bronze -> Silver ingestion script through a protected webhook."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    result = subprocess.run(
        [sys.executable, INGEST_SCRIPT_PATH],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        return jsonify(
            {
                "status": "success",
                "output": result.stdout.strip(),
            }
        ), 200

    return (
        jsonify(
            {
                "status": "error",
                "error": result.stderr.strip() or result.stdout.strip(),
            }
        ),
        500,
    )


@app.route("/scoring", methods=["POST"])
def scoring() -> tuple:
    """Trigger scoring engine script and return its JSON stdout payload."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    result = subprocess.run(
        [sys.executable, SCORING_SCRIPT_PATH],
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout.strip()
    if result.returncode != 0:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "scoring script execution failed",
                    "stdout": output,
                    "stderr": result.stderr.strip(),
                }
            ),
            500,
        )

    try:
        parsed_output = json.loads(output)
    except json.JSONDecodeError as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid JSON output from scoring script",
                    "stdout": output,
                    "details": str(exc),
                }
            ),
            500,
        )

    return jsonify(parsed_output), 200


@app.route("/api/open-mic/create-form", methods=["POST"])
def create_form() -> tuple:
    """Crea un Google Form para un open mic y guarda form_url/sheet_id en su config."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id", "").strip()
    nombre = body.get("nombre", "").strip()

    if not open_mic_id or not nombre:
        return jsonify({"status": "error", "message": "open_mic_id y nombre son obligatorios"}), 400

    # Comprobar si ya tiene form creado
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return jsonify({"status": "error", "message": "SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados"}), 500

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    existing = (
        sb.schema("silver")
        .from_("open_mics")
        .select("config")
        .eq("id", open_mic_id)
        .single()
        .execute()
    )
    if existing.data and existing.data.get("config", {}).get("form"):
        return jsonify({"status": "error", "message": "Este open mic ya tiene un form creado"}), 409

    try:
        builder = GoogleFormBuilder()
        result = builder.create_form_for_open_mic(open_mic_id=open_mic_id, nombre=nombre)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

    # Guardar en config del open mic
    current_config = (existing.data or {}).get("config") or {}
    current_config["form"] = {
        "form_id": result.form_id,
        "form_url": result.form_url,
        "sheet_id": result.sheet_id,
        "sheet_url": result.sheet_url,
    }
    sb.schema("silver").from_("open_mics").update({"config": current_config}).eq("id", open_mic_id).execute()

    return jsonify({
        "status": "success",
        "form_url": result.form_url,
        "sheet_id": result.sheet_id,
        "sheet_url": result.sheet_url,
        "form_id": result.form_id,
    }), 200


# ---------------------------------------------------------------------------
# MCP endpoints — Telegram Lineup Agent
# ---------------------------------------------------------------------------

def _sb_client():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@app.route("/mcp/open-mics", methods=["GET"])
def mcp_list_open_mics():
    """Lista los open mics del host."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    host_id = request.args.get("host_id", "").strip()
    if not host_id:
        return jsonify({"status": "error", "message": "host_id es obligatorio"}), 400

    sb = _sb_client()
    # host_id es user_id en organization_members; open_mics usa proveedor_id
    members = (
        sb.schema("silver")
        .from_("organization_members")
        .select("proveedor_id")
        .eq("user_id", host_id)
        .execute()
    ).data or []
    proveedor_ids = [m["proveedor_id"] for m in members if m.get("proveedor_id")]
    if not proveedor_ids:
        return jsonify({"open_mics": []}), 200
    rows = (
        sb.schema("silver")
        .from_("open_mics")
        .select("id, nombre, config")
        .in_("proveedor_id", proveedor_ids)
        .execute()
    ).data or []

    open_mics = []
    for row in rows:
        config = row.get("config") or {}
        open_mics.append({
            "id":     row.get("id"),
            "nombre": row.get("nombre"),
            "icon":   (config.get("info") or {}).get("icon", "mic"),
        })

    return jsonify({"open_mics": open_mics}), 200


@app.route("/mcp/lineup", methods=["GET"])
def mcp_get_lineup():
    """Devuelve el lineup confirmado para un open mic y fecha."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    open_mic_id  = request.args.get("open_mic_id", "").strip()
    fecha_evento = request.args.get("fecha_evento", "").strip()
    if not open_mic_id or not fecha_evento:
        return jsonify({"status": "error", "message": "open_mic_id y fecha_evento son obligatorios"}), 400

    sb = _sb_client()
    rows = (
        sb.schema("silver")
        .from_("lineup_slots")
        .select("slot_order, solicitud_id, silver_solicitudes(categoria_silver, silver_comicos(nombre, instagram))")
        .eq("open_mic_id", open_mic_id)
        .eq("fecha_evento", fecha_evento)
        .eq("status", "confirmed")
        .order("slot_order")
        .execute()
    ).data or []

    slots = []
    for row in rows:
        sol  = row.get("silver_solicitudes") or {}
        comic = sol.get("silver_comicos") or {}
        slots.append({
            "slot_order": row.get("slot_order"),
            "nombre":     comic.get("nombre"),
            "instagram":  comic.get("instagram"),
            "categoria":  sol.get("categoria_silver"),
        })

    return jsonify({
        "open_mic_id":  open_mic_id,
        "fecha_evento": fecha_evento,
        "slots":        slots,
        "total":        len(slots),
        "validado":     len(slots) > 0,
    }), 200


@app.route("/mcp/candidates", methods=["GET"])
def mcp_get_candidates():
    """Devuelve candidatos ordenados por score para un open mic."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    open_mic_id = request.args.get("open_mic_id", "").strip()
    limit       = int(request.args.get("limit", 10))
    if not open_mic_id:
        return jsonify({"status": "error", "message": "open_mic_id es obligatorio"}), 400

    sb = _sb_client()
    rows = (
        sb.schema("gold")
        .from_("solicitudes")
        .select("score_aplicado, estado, categoria, gold_comicos(nombre, instagram)")
        .eq("open_mic_id", open_mic_id)
        .order("score_aplicado", desc=True)
        .limit(limit)
        .execute()
    ).data or []

    candidates = []
    for row in rows:
        comic = row.get("gold_comicos") or {}
        candidates.append({
            "nombre":      comic.get("nombre"),
            "instagram":   comic.get("instagram"),
            "score_final": row.get("score_aplicado"),
            "categoria":   row.get("categoria"),
            "estado":      row.get("estado"),
        })

    return jsonify({"candidates": candidates}), 200


@app.route("/mcp/run-scoring", methods=["POST"])
def mcp_run_scoring():
    """Ejecuta el motor de scoring para un open mic."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id", "").strip()
    if not open_mic_id:
        return jsonify({"status": "error", "message": "open_mic_id es obligatorio"}), 400

    try:
        result = execute_scoring(open_mic_id)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

    return jsonify(result), 200


@app.route("/mcp/reopen-lineup", methods=["POST"])
def mcp_reopen_lineup():
    """Resetea los slots confirmados de un lineup para permitir cambios."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    open_mic_id  = body.get("open_mic_id", "").strip()
    fecha_evento = body.get("fecha_evento", "").strip()
    if not open_mic_id or not fecha_evento:
        return jsonify({"status": "error", "message": "open_mic_id y fecha_evento son obligatorios"}), 400

    sb = _sb_client()
    sb.rpc("reset_lineup_slots", {"p_open_mic_id": open_mic_id, "p_fecha_evento": fecha_evento})

    return jsonify({
        "status":  "ok",
        "message": f"Lineup reabierto para {fecha_evento}",
    }), 200


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
    dia_semana: "Lunes"..."Domingo"
    hora: "HH:MM" en 24h
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


# ---------------------------------------------------------------------------
# Lineup Validation endpoints
# ---------------------------------------------------------------------------

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://recova-project-z5zp.vercel.app")


@app.route("/api/lineup/prepare-validation", methods=["POST"])
def lineup_prepare_validation():
    """Calcula el proximo show, ejecuta scoring, genera token y devuelve lineup + link."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    host_id = body.get("host_id", "").strip()
    open_mic_id = body.get("open_mic_id", "").strip()
    if not host_id or not open_mic_id:
        return jsonify({"status": "error", "message": "host_id y open_mic_id son obligatorios"}), 400

    sb = _sb_client()

    # 1. Leer config del open mic
    rows = sb.schema("silver").from_("open_mics").select("id,config").eq("id", open_mic_id).execute()
    if not rows.data:
        return jsonify({"status": "error", "message": "open mic no encontrado"}), 404
    config = (rows.data[0] or {}).get("config") or {}
    info = config.get("info") or {}
    dia_semana = info.get("dia_semana", "").strip()
    hora = info.get("hora", "").strip()
    if not dia_semana or not hora:
        return jsonify({"status": "error", "message": "El open mic no tiene dia_semana u hora configurados"}), 404

    # 2. Calcular proximo evento
    try:
        show_dt = _next_event_datetime(dia_semana, hora)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    if show_dt is None:
        return jsonify({"status": "error", "message": "El show de esta semana ya empezo"}), 409

    fecha_evento = show_dt.strftime("%Y-%m-%d")

    # 3. Ejecutar scoring (no bloqueante)
    try:
        execute_scoring(open_mic_id)
    except Exception:
        pass

    # 4. Obtener candidatos
    candidates_res = (
        sb.schema("gold")
        .from_("lineup_candidates")
        .select("solicitud_id,nombre,instagram,score_aplicado")
        .eq("open_mic_id", open_mic_id)
        .eq("fecha_evento", fecha_evento)
        .order("score_aplicado", desc=True)
        .execute()
    )
    candidates = candidates_res.data or []

    # 5. Insertar token (expira cuando empieza el show)
    token_res = (
        sb.schema("silver")
        .from_("validation_tokens")
        .insert({
            "host_id": host_id,
            "open_mic_id": open_mic_id,
            "fecha_evento": fecha_evento,
            "expires_at": show_dt.isoformat(),
        })
        .execute()
    )
    token = ((token_res.data or [{}])[0]).get("token", "")

    return jsonify({
        "fecha_evento": fecha_evento,
        "show_datetime": show_dt.isoformat(),
        "validate_url": f"{FRONTEND_URL}/validate?token={token}",
        "lineup": [
            {
                "solicitud_id": c.get("solicitud_id"),
                "nombre": c.get("nombre"),
                "instagram": c.get("instagram"),
                "score": c.get("score_aplicado"),
            }
            for c in candidates
        ],
    }), 200


@app.route("/api/validate-view/lineup", methods=["GET"])
def validate_view_lineup():
    """Devuelve el lineup para la vista standalone de validacion."""
    token = request.args.get("token", "").strip()
    if not token:
        return jsonify({"status": "error", "message": "token es obligatorio"}), 400

    sb = _sb_client()

    token_res = (
        sb.schema("silver")
        .from_("validation_tokens")
        .select("token,host_id,open_mic_id,fecha_evento,expires_at")
        .eq("token", token)
        .execute()
    )
    if not token_res.data:
        return jsonify({"status": "error", "message": "token no encontrado"}), 404

    token_row = token_res.data[0]
    expires_at = token_row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        return jsonify({"status": "error", "message": "token expirado"}), 410

    open_mic_id = token_row["open_mic_id"]
    fecha_evento = token_row["fecha_evento"]

    candidates_res = (
        sb.schema("gold")
        .from_("lineup_candidates")
        .select("solicitud_id,nombre,instagram,score_aplicado")
        .eq("open_mic_id", open_mic_id)
        .eq("fecha_evento", fecha_evento)
        .order("score_aplicado", desc=True)
        .execute()
    )

    slots_res = (
        sb.schema("silver")
        .from_("lineup_slots")
        .select("id")
        .eq("open_mic_id", open_mic_id)
        .eq("fecha_evento", fecha_evento)
        .eq("status", "confirmed")
        .execute()
    )

    return jsonify({
        "open_mic_id": open_mic_id,
        "fecha_evento": str(fecha_evento),
        "show_datetime": expires_at.isoformat(),
        "is_validated": len(slots_res.data or []) > 0,
        "candidates": [
            {
                "solicitud_id": c.get("solicitud_id"),
                "nombre": c.get("nombre"),
                "instagram": c.get("instagram"),
                "score": c.get("score_aplicado"),
            }
            for c in (candidates_res.data or [])
        ],
    }), 200


@app.route("/api/validate-view/validate", methods=["POST"])
def validate_view_validate():
    """Valida el lineup desde la vista standalone."""
    body = request.get_json(silent=True) or {}
    token = body.get("token", "").strip()
    solicitud_ids = body.get("solicitud_ids", [])

    if not token:
        return jsonify({"status": "error", "message": "token es obligatorio"}), 400
    if not solicitud_ids:
        return jsonify({"status": "error", "message": "solicitud_ids no puede estar vacio"}), 400

    sb = _sb_client()

    token_res = (
        sb.schema("silver")
        .from_("validation_tokens")
        .select("token,host_id,open_mic_id,fecha_evento,expires_at")
        .eq("token", token)
        .execute()
    )
    if not token_res.data:
        return jsonify({"status": "error", "message": "token no encontrado"}), 404

    token_row = token_res.data[0]
    expires_at = token_row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        return jsonify({"status": "error", "message": "token expirado"}), 410

    open_mic_id = token_row["open_mic_id"]
    fecha_evento = str(token_row["fecha_evento"])

    selection = [{"solicitud_id": sid, "nuevo_estado": "aprobado"} for sid in solicitud_ids]
    sb.schema("gold").rpc("validate_lineup", {
        "p_selection": selection,
        "p_event_date": fecha_evento,
    }).execute()

    result = sb.schema("silver").rpc("upsert_confirmed_lineup", {
        "p_open_mic_id": open_mic_id,
        "p_fecha_evento": fecha_evento,
        "p_approved_solicitud_ids": solicitud_ids,
    }).execute()

    sb.schema("silver").from_("validation_tokens").delete().eq("token", token).execute()

    return jsonify({"status": "validated", "slots_created": result.data or 0}), 200


@app.route("/api/telegram/generate-code", methods=["POST"])
def telegram_generate_code():
    """Genera un código temporal para self-registration del bot de Telegram."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    host_id = body.get("host_id", "").strip()
    if not host_id:
        return jsonify({"status": "error", "message": "host_id es obligatorio"}), 400

    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    code = f"RCV-{suffix}"

    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "")
    qr_url = f"https://t.me/{bot_username}?start={code}"

    sb = _sb_client()
    sb.schema("silver").from_("telegram_registration_codes").insert({
        "code": code,
        "host_id": host_id,
    }).execute()

    return jsonify({"code": code, "qr_url": qr_url}), 200


@app.route("/api/telegram/register", methods=["POST"])
def telegram_register():
    """Procesa /start RCV-XXXX: valida codigo y registra host en telegram_users."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    telegram_user_id = body.get("telegram_user_id")
    code = body.get("code", "").strip() if body.get("code") else ""

    if not telegram_user_id:
        return jsonify({"status": "error", "message": "telegram_user_id es obligatorio"}), 400
    if not code:
        return jsonify({"status": "error", "message": "code es obligatorio"}), 400

    sb = _sb_client()
    silver = sb.schema("silver")

    # 1. Buscar el codigo
    code_res = silver.from_("telegram_registration_codes").select("code,host_id,used,expires_at").eq("code", code).execute()
    if not code_res.data:
        return jsonify({"status": "error", "message": "codigo no encontrado"}), 404
    code_row = code_res.data[0]
    host_id = code_row["host_id"]

    # 2. Comprobar si el usuario ya esta registrado
    user_res = silver.from_("telegram_users").select("telegram_user_id").eq("telegram_user_id", telegram_user_id).execute()
    already_registered = bool(user_res.data)

    if already_registered:
        # Marcar codigo como usado si todavia no lo estaba
        if not code_row["used"]:
            silver.from_("telegram_registration_codes").update({"used": True}).eq("code", code).execute()
        return jsonify({"host_id": host_id, "already_registered": True}), 200

    # 3. Validar estado del codigo (solo si el usuario NO estaba registrado)
    if code_row["used"]:
        return jsonify({"status": "error", "message": "codigo ya usado"}), 409

    expires_at = code_row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        return jsonify({"status": "error", "message": "codigo expirado"}), 410

    # 4. Registrar usuario
    silver.from_("telegram_users").insert({"telegram_user_id": telegram_user_id, "host_id": host_id}).execute()

    # 5. Marcar codigo como usado
    silver.from_("telegram_registration_codes").update({"used": True}).eq("code", code).execute()

    return jsonify({"host_id": host_id, "already_registered": False}), 200


# ---------------------------------------------------------------------------
# Form submission endpoint (multi-tenant ingesta via Apps Script)
# ---------------------------------------------------------------------------

@app.route("/api/form-submission", methods=["POST"])
def form_submission():
    """Recibe datos de Google Form via Apps Script y los ingesta en bronze."""
    data = request.get_json(force=True) or {}

    open_mic_id = data.get("open_mic_id")
    if not open_mic_id:
        return jsonify({"error": "open_mic_id required"}), 400

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    silver = sb.schema("silver")

    # 1. Lookup proveedor_id desde silver.open_mics
    result = silver.from_("open_mics").select("proveedor_id").eq("id", open_mic_id).execute()
    if not result.data:
        return jsonify({"error": "open_mic not found"}), 404
    proveedor_id = result.data[0]["proveedor_id"]

    # 2. INSERT en bronze.solicitudes
    # Nombres de campo coinciden con los títulos definidos en _FORM_QUESTIONS
    bronze = sb.schema("bronze")
    bronze.from_("solicitudes").insert({
        "proveedor_id":                 proveedor_id,
        "open_mic_id":                  open_mic_id,
        "nombre_raw":                   data.get("Nombre artístico"),
        "instagram_raw":                data.get("Instagram (sin @)"),
        "telefono_raw":                 data.get("WhatsApp"),
        "experiencia_raw":              data.get("¿Cuántas veces has actuado en un open mic?"),
        "fechas_seleccionadas_raw":     data.get("¿Qué fechas te vienen bien?"),
        "disponibilidad_ultimo_minuto": data.get("¿Estarías disponible si nos falla alguien de última hora?"),
        "info_show_cercano":            data.get("¿Tienes algún show próximo que quieras mencionar?"),
        "origen_conocimiento":          data.get("¿Cómo nos conociste?"),
    }).execute()

    # 3. Lanzar bronze → silver en background
    subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])

    return jsonify({"status": "ok"}), 200


@app.route("/api/ingest-from-sheets", methods=["POST"])
def ingest_from_sheets():
    """Lee todas las Sheets de open mics activos e ingesta filas nuevas en bronze."""
    if not _is_authorized():
        return jsonify({"error": "unauthorized"}), 401

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    open_mics = (
        sb.schema("silver")
        .from_("open_mics")
        .select("id, proveedor_id, config")
        .execute()
        .data or []
    )
    # Solo los que tienen sheet_id configurado
    open_mics = [
        om for om in open_mics
        if (om.get("config") or {}).get("form", {}).get("sheet_id")
    ]

    bronze = sb.schema("bronze")
    open_mics_processed = 0
    rows_ingested = 0

    if not open_mics:
        subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])
        return jsonify({"status": "ok", "open_mics_processed": 0, "rows_ingested": 0}), 200

    ingestor = SheetIngestor()

    for om in open_mics:
        sheet_id    = om["config"]["form"]["sheet_id"]
        open_mic_id = om["id"]
        proveedor_id = om["proveedor_id"]
        open_mics_processed += 1

        try:
            pending = ingestor.get_pending_rows(sheet_id)
        except Exception:
            continue  # Sheet inaccesible: continúa con los demás

        for row in pending:
            bronze.from_("solicitudes").insert({
                "proveedor_id":                 proveedor_id,
                "open_mic_id":                  open_mic_id,
                "nombre_raw":                   row.get("Nombre artístico"),
                "instagram_raw":                row.get("Instagram (sin @)"),
                "telefono_raw":                 row.get("WhatsApp"),
                "experiencia_raw":              row.get("¿Cuántas veces has actuado en un open mic?"),
                "fechas_seleccionadas_raw":     row.get("¿Qué fechas te vienen bien?"),
                "disponibilidad_ultimo_minuto": row.get("¿Estarías disponible si nos falla alguien de última hora?"),
                "info_show_cercano":            row.get("¿Tienes algún show próximo que quieras mencionar?"),
                "origen_conocimiento":          row.get("¿Cómo nos conociste?"),
            }).execute()

        if pending:
            ingestor.mark_rows_processed(sheet_id, [r["_row_number"] for r in pending])
            rows_ingested += len(pending)

    subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])

    return jsonify({
        "status": "ok",
        "open_mics_processed": open_mics_processed,
        "rows_ingested": rows_ingested,
    }), 200


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


@app.route("/api/ingest-from-forms", methods=["POST"])
def ingest_from_forms():
    """Lee respuestas de Google Forms de todos los open mics activos e ingesta en bronze."""
    if not _is_authorized():
        return jsonify({"error": "unauthorized"}), 401

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    silver = sb.schema("silver")

    open_mics = (
        silver
        .from_("open_mics")
        .select("id, proveedor_id, config")
        .execute()
        .data or []
    )
    # Solo open mics con external_form_id y field_mapping configurados
    open_mics = [
        om for om in open_mics
        if (om.get("config") or {}).get("external_form_id")
        and (om.get("config") or {}).get("field_mapping")
    ]

    if not open_mics:
        subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])
        return jsonify({"status": "ok", "open_mics_processed": 0, "rows_ingested": 0}), 200

    try:
        ingestor = FormIngestor()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500

    bronze = sb.schema("bronze")
    open_mics_processed = 0
    rows_ingested = 0

    for om in open_mics:
        config = om.get("config") or {}
        form_id = config["external_form_id"]
        field_mapping = config["field_mapping"]
        last_at = config.get("last_form_ingestion_at", "1970-01-01T00:00:00Z")
        open_mic_id = om["id"]
        proveedor_id = om["proveedor_id"]
        open_mics_processed += 1
        max_submitted_at = last_at

        try:
            responses = ingestor.get_responses(form_id, field_mapping)
        except Exception:
            continue

        new_responses = [
            r for r in responses
            if r.get("_submitted_at", "") > last_at
        ]

        for resp in new_responses:
            row = {"proveedor_id": proveedor_id, "open_mic_id": open_mic_id}
            for canonical, bronze_field in _CANONICAL_TO_BRONZE.items():
                if canonical in resp:
                    row[bronze_field] = resp[canonical]
            bronze.from_("solicitudes").insert(row).execute()
            submitted_at = resp.get("_submitted_at", "")
            if submitted_at > max_submitted_at:
                max_submitted_at = submitted_at
            rows_ingested += 1

        if new_responses:
            silver.rpc(
                "update_open_mic_config_keys",
                {
                    "p_open_mic_id": open_mic_id,
                    "p_keys": {"last_form_ingestion_at": max_submitted_at},
                },
            ).execute()

    subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])

    return jsonify({
        "status": "ok",
        "open_mics_processed": open_mics_processed,
        "rows_ingested": rows_ingested,
    }), 200


@app.route("/api/open-mic/analyze-form", methods=["POST"])
def analyze_form() -> tuple:
    """Analiza los campos de un Google Form y guarda el field_mapping en config."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id")
    form_id = body.get("form_id")

    if not open_mic_id or not form_id:
        return jsonify({"status": "error", "message": "open_mic_id y form_id son obligatorios"}), 400

    try:
        questions = FormIngestor().get_form_questions(form_id)
        question_titles = [q["title"] for q in questions]
        field_mapping = FormAnalyzer().analyze(question_titles)
    except ValueError as exc:
        return jsonify({"status": "error", "message": "Gemini devolvió JSON inválido", "raw": str(exc)}), 422

    # Guardar en config del open mic via RPC (schema silver)
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    sb.schema("silver").rpc("update_open_mic_config_keys", {
        "p_open_mic_id": open_mic_id,
        "p_keys": {"field_mapping": field_mapping, "external_form_id": form_id},
    }).execute()

    total = len(question_titles)
    unmapped = [t for t, v in field_mapping.items() if v is None]
    canonical_coverage = total - len(unmapped)

    return jsonify({
        "field_mapping": field_mapping,
        "canonical_coverage": canonical_coverage,
        "total_questions": total,
        "unmapped_fields": unmapped,
    }), 200


@app.route("/api/open-mic/propose-custom-rules", methods=["POST"])
def propose_custom_rules() -> tuple:
    """Propone reglas de scoring custom desde los campos no canónicos del form."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id")

    if not open_mic_id:
        return jsonify({"status": "error", "message": "open_mic_id es obligatorio"}), 400

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Cargar config del open mic
    result = (
        sb.schema("silver")
        .from_("open_mics")
        .select("config")
        .eq("id", open_mic_id)
        .single()
        .execute()
    )
    config = (result.data or {}).get("config") or {}

    if "field_mapping" not in config:
        return jsonify({
            "status": "error",
            "message": "El open mic no tiene field_mapping. Primero analiza el formulario.",
        }), 422

    unmapped_fields = [k for k, v in config["field_mapping"].items() if v is None]

    try:
        rules = CustomScoringProposer().propose(unmapped_fields)
    except ValueError as exc:
        return jsonify({"status": "error", "message": "Gemini devolvió JSON inválido", "raw": str(exc)}), 422

    # Guardar en config via RPC (schema silver)
    sb.schema("silver").rpc("update_open_mic_config_keys", {
        "p_open_mic_id": open_mic_id,
        "p_keys": {"custom_scoring_rules": rules},
    }).execute()

    return jsonify({
        "rules": rules,
        "unmapped_fields": unmapped_fields,
        "proposed_count": len(rules),
    }), 200


@app.route("/api/dev/seed-open-mic", methods=["POST"])
def dev_seed_open_mic():
    """Siembra 10 usuarios de prueba en un open mic. Protegido por Supabase JWT."""
    if not _is_authenticated_user():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True) or {}
    open_mic_id = data.get("open_mic_id")
    if not open_mic_id:
        return jsonify({"error": "open_mic_id requerido"}), 400

    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    silver = sb.schema("silver")

    result = silver.from_("open_mics").select("id, proveedor_id, config").eq("id", open_mic_id).execute()
    if not result.data:
        return jsonify({"error": "open mic no encontrado"}), 404

    om = result.data[0]
    config = om.get("config") or {}
    if config.get("seed_used"):
        return jsonify({"error": "este open mic ya fue sembrado"}), 409

    proveedor_id = om["proveedor_id"]
    bronze = sb.schema("bronze")
    users = get_random_users(10)

    from datetime import date, timedelta
    today = date.today()
    # Generar las próximas 4 fechas (viernes, sábado, el siguiente viernes, el siguiente sábado)
    # en formato DD-MM-YY que espera parse_event_dates
    def _next_weekday(d, weekday):  # 4=viernes, 5=sábado
        days_ahead = weekday - d.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return d + timedelta(days=days_ahead)

    dates = [
        _next_weekday(today, 4),
        _next_weekday(today, 5),
        _next_weekday(today + timedelta(weeks=1), 4),
        _next_weekday(today + timedelta(weeks=1), 5),
    ]
    fechas_raw = ", ".join(d.strftime("%d-%m-%y") for d in dates)

    for user in users:
        bronze.from_("solicitudes").insert({
            "proveedor_id":                 proveedor_id,
            "open_mic_id":                  open_mic_id,
            "nombre_raw":                   user["nombre"],
            "instagram_raw":                user["instagram"],
            "telefono_raw":                 user["telefono"],
            "experiencia_raw":              user["experiencia_raw"],
            "fechas_seleccionadas_raw":     fechas_raw,
            "disponibilidad_ultimo_minuto": user["disponibilidad_ultimo_minuto"],
            "origen_conocimiento":          user["origen_conocimiento"],
        }).execute()

    subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])

    silver.rpc(
        "update_open_mic_config_keys",
        {"p_open_mic_id": open_mic_id, "p_keys": {"seed_used": True}},
    ).execute()

    return jsonify({"status": "ok", "seeded": len(users)}), 200


@app.route("/api/dev/trigger-ingest", methods=["POST"])
def dev_trigger_ingest():
    """Lanza ingesta de sheets y forms en background. Protegido por Supabase JWT."""
    if not _is_authenticated_user():
        return jsonify({"error": "unauthorized"}), 401

    subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])
    return jsonify({"status": "ok", "message": "ingesta lanzada en background"}), 200


@app.route("/api/dev/trigger-scoring", methods=["POST"])
def dev_trigger_scoring():
    """Ejecuta scoring para un open mic. Protegido por Supabase JWT."""
    if not _is_authenticated_user():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True) or {}
    open_mic_id = data.get("open_mic_id")
    if not open_mic_id:
        return jsonify({"error": "open_mic_id requerido"}), 400

    result = execute_scoring(open_mic_id)
    return jsonify({"status": "ok", "result": result}), 200


@app.route("/api/render-poster", methods=["POST"])
def render_poster() -> tuple:
    """Renderiza el cartel del lineup con PosterComposer y devuelve PNG binario."""
    if not _is_authorized():
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True) or {}
    lineup = data.get("lineup") or []

    if not lineup:
        return jsonify({"error": "lineup requerido"}), 400

    event_id = str(data.get("event_id") or "evento")
    date_text = str(data.get("date") or event_id)
    open_mic_id = data.get("open_mic_id")

    safe_id = re.sub(r"[^\w-]", "_", event_id)
    output_path = _Path("/tmp") / f"render_{safe_id}.png"

    # Intentar obtener la imagen base del open_mic config
    base_image_path = None
    tmp_image_file = None
    if open_mic_id:
        try:
            sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            row = sb.schema("silver").from_("open_mics").select("config").eq("id", open_mic_id).single().execute()
            config = (row.data or {}).get("config") or {}
            poster_cfg = config.get("poster") or {}
            image_url = poster_cfg.get("base_image_url") or poster_cfg.get("dirty_image_url")
            if image_url:
                tmp_image_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                urllib.request.urlretrieve(image_url, tmp_image_file.name)
                base_image_path = _Path(tmp_image_file.name)
        except Exception:
            pass  # fallback a imagen local

    try:
        PosterComposer(base_image_path=base_image_path).render(
            lineup=lineup,
            date=date_text,
            event_id=event_id,
            output_path=output_path,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        if tmp_image_file:
            try:
                _Path(tmp_image_file.name).unlink(missing_ok=True)
            except Exception:
                pass

    return send_file(str(output_path), mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
