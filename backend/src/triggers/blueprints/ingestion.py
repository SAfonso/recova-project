"""Form submission and ingestion endpoints."""

import logging

from flask import Blueprint, jsonify, request

from backend.src.core.form_ingestor import FormIngestor
from backend.src.core.sheet_ingestor import SheetIngestor
from backend.src.triggers.shared import (
    INGEST_SCRIPT_PATH,
    _CANONICAL_TO_BRONZE,
    api_error,
    rate_limit,
    require_api_key,
    _sb_client,
    run_ingestion_async,
    validate_json,
)

bp = Blueprint("ingestion", __name__)

logger = logging.getLogger(__name__)


@bp.route("/api/form-submission", methods=["POST"])
@rate_limit(max_requests=5, window_seconds=60)
@validate_json({"open_mic_id": str})
def form_submission() -> tuple:
    """Recibe datos de Google Form via Apps Script y los ingesta en bronze."""
    err = require_api_key()
    if err:
        return err
    data = request.get_json(silent=True) or {}

    open_mic_id = data.get("open_mic_id")

    try:
        sb = _sb_client()
        silver = sb.schema("silver")

        # 1. Lookup proveedor_id desde silver.open_mics
        result = silver.from_("open_mics").select("proveedor_id").eq("id", open_mic_id).execute()
        if not result.data:
            return api_error("RESOURCE_NOT_FOUND", "open_mic not found", 404)
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
    except Exception as exc:
        logger.exception("form_submission failed")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al procesar la solicitud", 502, details=str(exc))

    # 3. Lanzar bronze → silver en background
    run_ingestion_async()

    return jsonify({"status": "ok"}), 200


@bp.route("/api/ingest-from-sheets", methods=["POST"])
def ingest_from_sheets() -> tuple:
    """Lee todas las Sheets de open mics activos e ingesta filas nuevas en bronze."""
    err = require_api_key()
    if err:
        return err

    try:
        sb = _sb_client()
        open_mics = (
            sb.schema("silver")
            .from_("open_mics")
            .select("id, proveedor_id, config")
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.exception("ingest_from_sheets: error al consultar open_mics")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar open_mics", 502, details=str(exc))

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
            logger.exception("ingest_from_sheets: sheet %s inaccesible", sheet_id)
            continue

        for row in pending:
            try:
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
            except Exception:
                logger.exception("ingest_from_sheets: error insertando fila en bronze")
                continue

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
def ingest_from_forms() -> tuple:
    """Lee respuestas de Google Forms de todos los open mics activos e ingesta en bronze."""
    err = require_api_key()
    if err:
        return err

    try:
        sb = _sb_client()
        silver = sb.schema("silver")

        open_mics = (
            silver
            .from_("open_mics")
            .select("id, proveedor_id, config")
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.exception("ingest_from_forms: error al consultar open_mics")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar open_mics", 502, details=str(exc))

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
        return api_error("INTERNAL_ERROR", "error al inicializar el ingestor de formularios", 500)

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
            logger.exception("ingest_from_forms: form %s inaccesible", form_id)
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
            try:
                bronze.from_("solicitudes").insert(row).execute()
            except Exception:
                logger.exception("ingest_from_forms: error insertando fila en bronze")
                continue
            submitted_at = resp.get("_submitted_at", "")
            if submitted_at > max_submitted_at:
                max_submitted_at = submitted_at
            rows_ingested += 1

        if new_responses:
            try:
                silver.rpc(
                    "update_open_mic_config_keys",
                    {
                        "p_open_mic_id": open_mic_id,
                        "p_keys": {"last_form_ingestion_at": max_submitted_at},
                    },
                ).execute()
            except Exception:
                logger.exception("ingest_from_forms: error actualizando config")

    run_ingestion_async()

    return jsonify({
        "status": "ok",
        "open_mics_processed": open_mics_processed,
        "rows_ingested": rows_ingested,
    }), 200
