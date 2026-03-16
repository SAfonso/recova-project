"""Lineup validation endpoints."""

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from backend.src.triggers.shared import (
    FRONTEND_URL,
    _is_authorized,
    _next_event_datetime,
    _sb_client,
    execute_scoring,
)

bp = Blueprint("lineup", __name__)


@bp.route("/api/lineup/prepare-validation", methods=["POST"])
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
    rows = sb.schema("silver").from_("open_mics").select("id,config,proveedor_id").eq("id", open_mic_id).execute()
    if not rows.data:
        return jsonify({"status": "error", "message": "open mic no encontrado"}), 404
    proveedor_id = rows.data[0].get("proveedor_id", "")
    member_check = (
        sb.schema("silver")
        .from_("organization_members")
        .select("user_id")
        .eq("user_id", host_id)
        .eq("proveedor_id", proveedor_id)
        .execute()
    )
    if not member_check.data:
        return jsonify({"status": "error", "message": "forbidden"}), 403
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


@bp.route("/api/validate-view/lineup", methods=["GET"])
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


@bp.route("/api/validate-view/validate", methods=["POST"])
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
