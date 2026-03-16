"""Form submission and ingestion endpoints."""

import subprocess
import sys

from flask import Blueprint, jsonify, request
from supabase import create_client

from backend.src.core.form_ingestor import FormIngestor
from backend.src.core.sheet_ingestor import SheetIngestor
from backend.src.triggers.shared import (
    INGEST_SCRIPT_PATH,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    _CANONICAL_TO_BRONZE,
    _is_authorized,
    run_ingestion_async,
)

bp = Blueprint("ingestion", __name__)


@bp.route("/api/form-submission", methods=["POST"])
def form_submission():
    """Recibe datos de Google Form via Apps Script y los ingesta en bronze."""
    if not _is_authorized():
        return jsonify({"error": "unauthorized"}), 401
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
    run_ingestion_async()

    return jsonify({"status": "ok"}), 200


@bp.route("/api/ingest-from-sheets", methods=["POST"])
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
        run_ingestion_async()
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

    run_ingestion_async()

    return jsonify({
        "status": "ok",
        "open_mics_processed": open_mics_processed,
        "rows_ingested": rows_ingested,
    }), 200


@bp.route("/api/ingest-from-forms", methods=["POST"])
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
        run_ingestion_async()
        return jsonify({"status": "ok", "open_mics_processed": 0, "rows_ingested": 0}), 200

    try:
        ingestor = FormIngestor()
    except ValueError:
        return jsonify({"error": "Error al inicializar el ingestor de formularios"}), 500

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

    run_ingestion_async()

    return jsonify({
        "status": "ok",
        "open_mics_processed": open_mics_processed,
        "rows_ingested": rows_ingested,
    }), 200
