"""Telegram registration endpoints."""

import os
import random
import string
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from backend.src.triggers.shared import _is_authorized, _sb_client, validate_json

bp = Blueprint("telegram", __name__)


@bp.route("/api/telegram/generate-code", methods=["POST"])
@validate_json({"host_id": str})
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


@bp.route("/api/telegram/register", methods=["POST"])
@validate_json({"code": str})
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
