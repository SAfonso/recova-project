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

app = Flask(__name__)
CORS(app)

load_dotenv()
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
