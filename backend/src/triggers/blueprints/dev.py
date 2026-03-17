"""Dev tools endpoints (seed, trigger-ingest, trigger-scoring)."""

from datetime import date, timedelta

from flask import Blueprint, jsonify, request

from backend.src.core.dev_users_pool import get_random_users
from backend.src.triggers.shared import (
    _is_authenticated_user,
    _sb_client,
    execute_scoring,
    run_ingestion_async,
    validate_json,
)

bp = Blueprint("dev", __name__)


@bp.route("/api/dev/seed-open-mic", methods=["POST"])
@validate_json({"open_mic_id": str})
def dev_seed_open_mic():
    """Siembra 10 usuarios de prueba en un open mic. Protegido por Supabase JWT."""
    user = _is_authenticated_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    open_mic_id = data.get("open_mic_id")

    sb = _sb_client()
    silver = sb.schema("silver")

    result = silver.from_("open_mics").select("id, proveedor_id, config").eq("id", open_mic_id).execute()
    if not result.data:
        return jsonify({"error": "open mic no encontrado"}), 404

    om = result.data[0]
    config = om.get("config") or {}
    if config.get("seed_used"):
        return jsonify({"error": "este open mic ya fue sembrado"}), 409

    proveedor_id = om["proveedor_id"]
    member_check = (
        silver.from_("organization_members")
        .select("user_id")
        .eq("user_id", user["sub"])
        .eq("proveedor_id", proveedor_id)
        .execute()
    )
    if not member_check.data:
        return jsonify({"error": "forbidden"}), 403
    bronze = sb.schema("bronze")
    users = get_random_users(10)

    today = date.today()
    # Generar las próximas 4 fechas (viernes, sábado, el siguiente viernes, el siguiente sábado)
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

    run_ingestion_async()

    silver.rpc(
        "update_open_mic_config_keys",
        {"p_open_mic_id": open_mic_id, "p_keys": {"seed_used": True}},
    ).execute()

    return jsonify({"status": "ok", "seeded": len(users)}), 200


@bp.route("/api/dev/trigger-ingest", methods=["POST"])
def dev_trigger_ingest():
    """Lanza ingesta de sheets y forms en background. Protegido por Supabase JWT."""
    if not _is_authenticated_user():
        return jsonify({"error": "unauthorized"}), 401

    run_ingestion_async()
    return jsonify({"status": "ok", "message": "ingesta lanzada en background"}), 200


@bp.route("/api/dev/trigger-scoring", methods=["POST"])
@validate_json({"open_mic_id": str})
def dev_trigger_scoring():
    """Ejecuta scoring para un open mic. Protegido por Supabase JWT."""
    user = _is_authenticated_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    open_mic_id = data.get("open_mic_id")

    sb = _sb_client()
    om = sb.schema("silver").from_("open_mics").select("proveedor_id").eq("id", open_mic_id).execute()
    if not om.data:
        return jsonify({"error": "open mic no encontrado"}), 404
    member_check = (
        sb.schema("silver")
        .from_("organization_members")
        .select("user_id")
        .eq("user_id", user["sub"])
        .eq("proveedor_id", om.data[0]["proveedor_id"])
        .execute()
    )
    if not member_check.data:
        return jsonify({"error": "forbidden"}), 403

    result = execute_scoring(open_mic_id)
    return jsonify({"status": "ok", "result": result}), 200
