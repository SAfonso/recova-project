"""MCP Telegram Lineup Agent endpoints."""

import logging

from flask import Blueprint, jsonify, request

from backend.src.triggers.shared import api_error, require_api_key, _sb_client, execute_scoring, validate_json

bp = Blueprint("mcp_agent", __name__)

logger = logging.getLogger(__name__)


@bp.route("/mcp/open-mics", methods=["GET"])
def mcp_list_open_mics() -> tuple:
    """Lista los open mics del host."""
    err = require_api_key()
    if err:
        return err

    host_id = request.args.get("host_id", "").strip()
    if not host_id:
        return api_error("VALIDATION_ERROR", "host_id es obligatorio", 400)

    try:
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
    except Exception as exc:
        logger.exception("mcp_list_open_mics: error Supabase")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar open_mics", 502)

    open_mics = []
    for row in rows:
        config = row.get("config") or {}
        open_mics.append({
            "id":     row.get("id"),
            "nombre": row.get("nombre"),
            "icon":   (config.get("info") or {}).get("icon", "mic"),
        })

    return jsonify({"open_mics": open_mics}), 200


@bp.route("/mcp/lineup", methods=["GET"])
def mcp_get_lineup() -> tuple:
    """Devuelve el lineup confirmado para un open mic y fecha."""
    err = require_api_key()
    if err:
        return err

    open_mic_id  = request.args.get("open_mic_id", "").strip()
    fecha_evento = request.args.get("fecha_evento", "").strip()
    if not open_mic_id or not fecha_evento:
        return api_error("VALIDATION_ERROR", "open_mic_id y fecha_evento son obligatorios", 400)

    try:
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
    except Exception as exc:
        logger.exception("mcp_get_lineup: error Supabase")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar lineup", 502)

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


@bp.route("/mcp/candidates", methods=["GET"])
def mcp_get_candidates() -> tuple:
    """Devuelve candidatos ordenados por score para un open mic."""
    err = require_api_key()
    if err:
        return err

    open_mic_id = request.args.get("open_mic_id", "").strip()
    try:
        limit = int(request.args.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10
    if not open_mic_id:
        return api_error("VALIDATION_ERROR", "open_mic_id es obligatorio", 400)

    try:
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
    except Exception as exc:
        logger.exception("mcp_get_candidates: error Supabase")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al consultar candidatos", 502)

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


@bp.route("/mcp/run-scoring", methods=["POST"])
@validate_json({"open_mic_id": str})
def mcp_run_scoring() -> tuple:
    """Ejecuta el motor de scoring para un open mic."""
    err = require_api_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    open_mic_id = body.get("open_mic_id", "").strip()
    if not open_mic_id:
        return api_error("VALIDATION_ERROR", "open_mic_id es obligatorio", 400)

    try:
        result = execute_scoring(open_mic_id)
    except Exception as exc:
        return api_error("INTERNAL_ERROR", "error al ejecutar el scoring", 500)

    return jsonify(result), 200


@bp.route("/mcp/reopen-lineup", methods=["POST"])
@validate_json({"open_mic_id": str, "fecha_evento": str})
def mcp_reopen_lineup() -> tuple:
    """Resetea los slots confirmados de un lineup para permitir cambios."""
    err = require_api_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    open_mic_id  = body.get("open_mic_id", "").strip()
    fecha_evento = body.get("fecha_evento", "").strip()
    if not open_mic_id or not fecha_evento:
        return api_error("VALIDATION_ERROR", "open_mic_id y fecha_evento son obligatorios", 400)

    try:
        sb = _sb_client()
        sb.schema("silver").rpc("reset_lineup_slots", {"p_open_mic_id": open_mic_id, "p_fecha_evento": fecha_evento}).execute()
    except Exception as exc:
        logger.exception("mcp_reopen_lineup: error Supabase")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al reabrir lineup", 502)

    return jsonify({
        "status":  "ok",
        "message": f"Lineup reabierto para {fecha_evento}",
    }), 200
