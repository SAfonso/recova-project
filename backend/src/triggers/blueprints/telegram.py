"""Telegram registration endpoints."""

import logging
import os
import random
import string
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from backend.src.triggers.shared import api_error, rate_limit, require_api_key, require_authenticated_user, _sb_client, validate_json

bp = Blueprint("telegram", __name__)

logger = logging.getLogger(__name__)


@bp.route("/api/telegram/generate-code", methods=["POST"])
@validate_json({"proveedor_id": str})
def telegram_generate_code() -> tuple:
    """Genera un código temporal para self-registration del bot de Telegram."""
    user, err = require_authenticated_user()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    host_id = user["sub"]
    proveedor_id = body.get("proveedor_id", "").strip()
    if not proveedor_id:
        return api_error("VALIDATION_ERROR", "proveedor_id es obligatorio", 400)

    # Verificar membresía
    try:
        sb_check = _sb_client()
        member_check = (
            sb_check.schema("silver")
            .from_("organization_members")
            .select("user_id")
            .eq("user_id", host_id)
            .eq("proveedor_id", proveedor_id)
            .execute()
        )
        if not member_check.data:
            return api_error("FORBIDDEN", "forbidden", 403)
    except Exception as exc:
        logger.exception("telegram_generate_code: error verificando membresía")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al verificar membresía", 502)

    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    code = f"RCV-{suffix}"

    bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "")
    qr_url = f"https://t.me/{bot_username}?start={code}"

    try:
        sb = _sb_client()
        sb.schema("silver").from_("telegram_registration_codes").insert({
            "code": code,
            "host_id": host_id,
        }).execute()
    except Exception as exc:
        logger.exception("telegram_generate_code: error Supabase")
        return api_error("EXTERNAL_SERVICE_ERROR", "error al generar código", 502)

    return jsonify({"code": code, "qr_url": qr_url}), 200


@bp.route("/api/telegram/register", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=60)
@validate_json({"code": str})
def telegram_register() -> tuple:
    """Procesa /start RCV-XXXX: valida codigo y registra host en telegram_users."""
    err = require_api_key()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    telegram_user_id = body.get("telegram_user_id")
    code = body.get("code", "").strip() if body.get("code") else ""

    if not telegram_user_id:
        return api_error("VALIDATION_ERROR", "telegram_user_id es obligatorio", 400)
    if not code:
        return api_error("VALIDATION_ERROR", "code es obligatorio", 400)

    sb = _sb_client()
    silver = sb.schema("silver")

    # 1. Buscar el codigo
    code_res = silver.from_("telegram_registration_codes").select("code,host_id,used,expires_at").eq("code", code).execute()
    if not code_res.data:
        return api_error("RESOURCE_NOT_FOUND", "codigo no encontrado", 404)
    code_row = code_res.data[0]
    host_id = code_row["host_id"]

    # 2. Comprobar si el usuario ya esta registrado
    user_res = silver.from_("telegram_users").select("telegram_user_id").eq("telegram_user_id", telegram_user_id).execute()
    already_registered = bool(user_res.data)

    if already_registered:
        # Actualizar host_id por si el usuario cambió de proveedor/cuenta
        silver.from_("telegram_users").update({"host_id": host_id}).eq("telegram_user_id", telegram_user_id).execute()
        # Marcar codigo como usado si todavia no lo estaba
        if not code_row["used"]:
            silver.from_("telegram_registration_codes").update({"used": True}).eq("code", code).execute()
        return jsonify({"host_id": host_id, "already_registered": True}), 200

    # 3. Validar estado del codigo (solo si el usuario NO estaba registrado)
    if code_row["used"]:
        return api_error("CONFLICT", "codigo ya usado", 409)

    expires_at = code_row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if expires_at <= datetime.now(timezone.utc):
        return api_error("RESOURCE_EXPIRED", "codigo expirado", 410)

    # 4. Registrar usuario
    silver.from_("telegram_users").insert({"telegram_user_id": telegram_user_id, "host_id": host_id}).execute()

    # 5. Marcar codigo como usado
    silver.from_("telegram_registration_codes").update({"used": True}).eq("code", code).execute()

    return jsonify({"host_id": host_id, "already_registered": False}), 200
