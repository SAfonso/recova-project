"""Flask webhook listener for n8n ingestion trigger."""

import json
import os
import sys
import subprocess
from dotenv import load_dotenv

from flask import Flask, jsonify, request

app = Flask(__name__)

load_dotenv()
INGEST_SCRIPT_PATH = "/root/RECOVA/backend/src/bronze_to_silver_ingestion.py"
SCORING_SCRIPT_PATH = "/root/RECOVA/backend/src/scoring_engine.py"
API_KEY_HEADER = "X-API-KEY"
EXPECTED_API_KEY = os.getenv("WEBHOOK_API_KEY", "")


def _is_authorized() -> bool:
    """Validate request API key using shared webhook header logic."""
    provided_api_key = request.headers.get(API_KEY_HEADER, "")
    return bool(EXPECTED_API_KEY and provided_api_key == EXPECTED_API_KEY)


@app.route("/ingest", methods=["POST"])
def ingest() -> tuple:
    """Trigger Bronze -> Silver ingestion script through a protected webhook."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    result = subprocess.run(
        [sys.executable, INGEST_SCRIPT_PATH],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        return jsonify(
            {
                "status": "success",
                "output": result.stdout.strip(),
            }
        ), 200

    return (
        jsonify(
            {
                "status": "error",
                "error": result.stderr.strip() or result.stdout.strip(),
            }
        ),
        500,
    )


@app.route("/scoring", methods=["POST"])
def scoring() -> tuple:
    """Trigger scoring engine script and return its JSON stdout payload."""
    if not _is_authorized():
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    result = subprocess.run(
        [sys.executable, SCORING_SCRIPT_PATH],
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout.strip()
    if result.returncode != 0:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "scoring script execution failed",
                    "stdout": output,
                    "stderr": result.stderr.strip(),
                }
            ),
            500,
        )

    try:
        parsed_output = json.loads(output)
    except json.JSONDecodeError as exc:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "invalid JSON output from scoring script",
                    "stdout": output,
                    "details": str(exc),
                }
            ),
            500,
        )

    return jsonify(parsed_output), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
