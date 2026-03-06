"""Flask webhook listener for n8n ingestion trigger."""

import json
import os
import sys
import subprocess
from dotenv import load_dotenv

from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client

from backend.src.core.google_form_builder import GoogleFormBuilder
from backend.src.scoring_engine import execute_scoring

app = Flask(__name__)
CORS(app)

# Busca .env en: backend/.env → raíz del repo → CWD
_HERE = os.path.dirname(__file__)
_ENV_CANDIDATES = [
    os.path.join(_HERE, "../../../backend/.env"),
    os.path.join(_HERE, "../../.env"),
    os.path.join(_HERE, "../../../.env"),
]
for _env_path in _ENV_CANDIDATES:
    if os.path.exists(_env_path):
        load_dotenv(dotenv_path=_env_path, override=False)
        break
load_dotenv(override=False)
INGEST_SCRIPT_PATH = "/root/RECOVA/backend/src/bronze_to_silver_ingestion.py"
SCORING_SCRIPT_PATH = "/root/RECOVA/backend/src/scoring_engine.py"
API_KEY_HEADER = "X-API-KEY"
EXPECTED_API_KEY = os.getenv("WEBHOOK_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def _is_authorized() -> bool:
    """Validate request API key using shared webhook header logic."""
    provided_api_key = request.headers.get(API_KEY_HEADER, "")
    return bool(EXPECTED_API_KEY and provided_api_key == EXPECTED_API_KEY)


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
    rows = (
        sb.schema("silver")
        .from_("open_mics")
        .select("id, nombre, config")
        .eq("host_id", host_id)
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
