"""Flask webhook listener — app factory que registra blueprints + CORS."""

import logging

from flask import Flask, request

from backend.src.triggers.shared import _cors_headers, api_error

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health")
def _health():
    return {"status": "ok"}, 200


@app.before_request
def _handle_options():
    if request.method == "OPTIONS":
        return "", 204, _cors_headers()


@app.after_request
def _add_cors(response):
    for k, v in _cors_headers().items():
        response.headers[k] = v
    return response


@app.errorhandler(404)
def _handle_404(exc):
    return api_error("RESOURCE_NOT_FOUND", "ruta no encontrada", 404)


@app.errorhandler(405)
def _handle_405(exc):
    return api_error("VALIDATION_ERROR", "método no permitido", 405)


@app.errorhandler(500)
def _handle_500(exc):
    logger.exception("Internal server error: %s", exc)
    return api_error("INTERNAL_ERROR", "error interno del servidor", 500)


from backend.src.triggers.blueprints.n8n import bp as n8n_bp           # noqa: E402
from backend.src.triggers.blueprints.ingestion import bp as ingestion_bp  # noqa: E402
from backend.src.triggers.blueprints.form import bp as form_bp          # noqa: E402
from backend.src.triggers.blueprints.lineup import bp as lineup_bp      # noqa: E402
from backend.src.triggers.blueprints.mcp_agent import bp as mcp_bp     # noqa: E402
from backend.src.triggers.blueprints.telegram import bp as telegram_bp  # noqa: E402
from backend.src.triggers.blueprints.dev import bp as dev_bp           # noqa: E402
from backend.src.triggers.blueprints.poster import bp as poster_bp     # noqa: E402

for _bp in [n8n_bp, ingestion_bp, form_bp, lineup_bp, mcp_bp, telegram_bp, dev_bp, poster_bp]:
    app.register_blueprint(_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
