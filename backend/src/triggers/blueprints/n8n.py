"""n8n webhook endpoints (/ingest, /scoring) — llamadas directas al pipeline."""

from flask import Blueprint, jsonify, request

from backend.src.bronze_to_silver_ingestion import run_pipeline
from backend.src.triggers.shared import api_error, require_api_key, execute_scoring

bp = Blueprint("n8n", __name__)


@bp.route("/ingest", methods=["POST"])
def ingest() -> tuple:
    """Trigger Bronze -> Silver ingestion via direct call to run_pipeline()."""
    err = require_api_key()
    if err:
        return err

    try:
        result = run_pipeline()
        return jsonify({
            "status": "success",
            "output": result,
        }), 200
    except Exception as exc:
        return api_error("INTERNAL_ERROR", "ingestion execution failed", 500, details=str(exc))


@bp.route("/scoring", methods=["POST"])
def scoring() -> tuple:
    """Trigger scoring engine via direct call to execute_scoring()."""
    err = require_api_key()
    if err:
        return err

    try:
        result = execute_scoring()
        return jsonify(result), 200
    except Exception as exc:
        return api_error("INTERNAL_ERROR", "scoring execution failed", 500, details=str(exc))
