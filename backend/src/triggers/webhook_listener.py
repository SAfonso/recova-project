"""Flask webhook listener for n8n ingestion trigger."""

import os
import subprocess
from dotenv import load_dotenv

from flask import Flask, jsonify, request

app = Flask(__name__)

load_dotenv()
SCRIPT_PATH = "/root/AI_LineUp_Architect/backend/src/bronze_to_silver_ingestion.py"
API_KEY_HEADER = "X-API-KEY"
EXPECTED_API_KEY = os.getenv("WEBHOOK_API_KEY", "")


@app.route("/ingest", methods=["POST"])
def ingest() -> tuple:
    """Trigger Bronze -> Silver ingestion script through a protected webhook."""
    provided_api_key = request.headers.get(API_KEY_HEADER, "")

    if not EXPECTED_API_KEY or provided_api_key != EXPECTED_API_KEY:
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    result = subprocess.run(
        ["python3", SCRIPT_PATH],
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
