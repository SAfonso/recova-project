"""n8n webhook endpoints (/ingest, /scoring) — llamadas directas al pipeline."""

import json

from flask import Blueprint, jsonify, request

from backend.src.bronze_to_silver_ingestion import run_pipeline
from backend.src.triggers.shared import _is_authorized, execute_scoring

bp = Blueprint("n8n", __name__)


@bp.route("/ingest", methods=["POST"])
def ingest() -> tuple:
    """Trigger Bronze -> Silver ingestion via direct call to run_pipeline()."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    try:
        result = run_pipeline()
        return jsonify({
            "status": "success",
            "output": result,
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "error": str(exc),
        }), 500


@bp.route("/scoring", methods=["POST"])
def scoring() -> tuple:
    """Trigger scoring engine via direct call to execute_scoring()."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    try:
        result = execute_scoring()
        return jsonify(result), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": "scoring execution failed",
            "details": str(exc),
        }), 500
