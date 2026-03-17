"""Form creation, analysis and custom rules endpoints."""

import logging

from flask import Blueprint, jsonify, request

from backend.src.core.custom_scoring_proposer import CustomScoringProposer
from backend.src.core.form_analyzer import FormAnalyzer
from backend.src.core.form_ingestor import FormIngestor
from backend.src.core.google_form_builder import GoogleFormBuilder
from backend.src.triggers.shared import (
    api_error,
    require_api_key,
    _sb_client,
    validate_json,
)

bp = Blueprint("form", __name__)

logger = logging.getLogger(__name__)


@bp.route("/api/open-mic/create-form", methods=["POST"])
@validate_json({"open_mic_id": str, "nombre": str})
def create_form() -> tuple:
    """Crea un Google Form para un open mic y guarda form_url/sheet_id en su config."""
    err = require_api_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id", "").strip()
    nombre = body.get("nombre", "").strip()

    try:
        # Comprobar si ya tiene form creado
        sb = _sb_client()
        existing = (
            sb.schema("silver")
            .from_("open_mics")
            .select("config")
            .eq("id", open_mic_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.exception("create_form: error al consultar open_mic")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar open_mic", 502, details=str(exc))

    if existing.data and existing.data.get("config", {}).get("form"):
        return api_error("CONFLICT", "este open mic ya tiene un form creado", 409)

    info = (existing.data or {}).get("config", {}).get("info", {})

    try:
        builder = GoogleFormBuilder()
        result = builder.create_form_for_open_mic(open_mic_id=open_mic_id, nombre=nombre, info=info)
    except Exception as exc:
        logger.exception("create_form: error al crear el formulario")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al crear el formulario", 502, details=str(exc))

    # Calcular last_date (última fecha de las opciones del form)
    dates = builder._build_date_options(info)
    last_date = dates[-1] if dates else None

    # Guardar en config del open mic
    current_config = (existing.data or {}).get("config") or {}
    current_config["form"] = {
        "form_id":      result.form_id,
        "form_url":     result.form_url,
        "sheet_id":     result.sheet_id,
        "sheet_url":    result.sheet_url,
        "bg_color":     result.bg_color,
        "info_changed": False,
        **({"last_date": last_date} if last_date else {}),
    }

    try:
        sb.schema("silver").from_("open_mics").update({"config": current_config}).eq("id", open_mic_id).execute()
    except Exception as exc:
        logger.exception("create_form: error al guardar config")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al guardar config", 502, details=str(exc))

    return jsonify({
        "status":   "success",
        "form_url": result.form_url,
        "sheet_id": result.sheet_id,
        "sheet_url": result.sheet_url,
        "form_id":  result.form_id,
        "bg_color": result.bg_color,
    }), 200


@bp.route("/api/open-mic/analyze-form", methods=["POST"])
@validate_json({"open_mic_id": str, "form_id": str})
def analyze_form() -> tuple:
    """Analiza los campos de un Google Form y guarda el field_mapping en config."""
    err = require_api_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id")
    form_id = body.get("form_id")

    try:
        questions = FormIngestor().get_form_questions(form_id)
        question_titles = [q["title"] for q in questions]
        field_mapping = FormAnalyzer().analyze(question_titles)
    except ValueError as exc:
        return api_error("UNPROCESSABLE_ENTITY", "Gemini devolvió JSON inválido", 422, details=str(exc))

    # Guardar en config del open mic via RPC (schema silver)
    try:
        sb = _sb_client()
        sb.schema("silver").rpc("update_open_mic_config_keys", {
            "p_open_mic_id": open_mic_id,
            "p_keys": {"field_mapping": field_mapping, "external_form_id": form_id},
        }).execute()
    except Exception as exc:
        logger.exception("analyze_form: error al guardar config")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al guardar config", 502, details=str(exc))

    total = len(question_titles)
    unmapped = [t for t, v in field_mapping.items() if v is None]
    canonical_coverage = total - len(unmapped)

    return jsonify({
        "field_mapping": field_mapping,
        "canonical_coverage": canonical_coverage,
        "total_questions": total,
        "unmapped_fields": unmapped,
    }), 200


@bp.route("/api/open-mic/propose-custom-rules", methods=["POST"])
@validate_json({"open_mic_id": str})
def propose_custom_rules() -> tuple:
    """Propone reglas de scoring custom desde los campos no canónicos del form."""
    err = require_api_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id")

    try:
        sb = _sb_client()

        # Cargar config del open mic
        result = (
            sb.schema("silver")
            .from_("open_mics")
            .select("config")
            .eq("id", open_mic_id)
            .single()
            .execute()
        )
    except Exception as exc:
        logger.exception("propose_custom_rules: error al consultar open_mic")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar open_mic", 502, details=str(exc))

    config = (result.data or {}).get("config") or {}

    if "field_mapping" not in config:
        return api_error(
            "UNPROCESSABLE_ENTITY",
            "El open mic no tiene field_mapping. Primero analiza el formulario.",
            422,
        )

    unmapped_fields = [k for k, v in config["field_mapping"].items() if v is None]

    try:
        rules = CustomScoringProposer().propose(unmapped_fields)
    except ValueError as exc:
        return api_error("UNPROCESSABLE_ENTITY", "Gemini devolvió JSON inválido", 422, details=str(exc))

    # Guardar en config via RPC (schema silver)
    try:
        sb.schema("silver").rpc("update_open_mic_config_keys", {
            "p_open_mic_id": open_mic_id,
            "p_keys": {"custom_scoring_rules": rules},
        }).execute()
    except Exception as exc:
        logger.exception("propose_custom_rules: error al guardar reglas")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al guardar reglas", 502, details=str(exc))

    return jsonify({
        "rules": rules,
        "unmapped_fields": unmapped_fields,
        "proposed_count": len(rules),
    }), 200
