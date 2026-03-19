from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = PROJECT_ROOT / "workflows" / "n8n"


def _workflow_text(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_n8n_workflow_exports_are_valid_json():
    workflow_files = sorted(WORKFLOWS_DIR.glob("*.json"))
    assert workflow_files, "No se encontraron exports en workflows/n8n"

    for path in workflow_files:
        json.loads(path.read_text(encoding="utf-8"))


def test_n8n_workflows_do_not_contain_known_hardcoded_secrets_or_hosts():
    import os

    forbidden_literals = [
        "sb_publishable_",
        # Webhook API key literal (cargada desde env en CI)
        os.getenv("WEBHOOK_API_KEY", ""),
        # Prefijo JWT del service role (cargado desde env en CI)
        os.getenv("_TEST_JWT_PREFIX", ""),
        # IP del servidor hardcodeada (cargada desde env en CI)
        os.getenv("_TEST_SERVER_IP", ""),
    ]
    # Filtrar strings vacías (cuando la env var no está definida, no chequear)
    forbidden_literals = [v for v in forbidden_literals if v]

    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        content = path.read_text(encoding="utf-8")
        for literal in forbidden_literals:
            assert literal not in content, f"{path.name} contiene literal prohibido: {literal}"


def test_n8n_workflows_use_env_references_for_sensitive_values():
    ingesta = _workflow_text("This.Ingesta-Solicitudes 3.json")
    scoring = _workflow_text("This.Scoring & Draft 2.json")
    render = _workflow_text("This.Render 2.json")
    test_bot = _workflow_text("This.Test BOT 3.json")

    assert "$env.BACKEND_URL" in ingesta
    assert "$env.WEBHOOK_API_KEY" in ingesta
    assert "$env.SUPABASE_URL }}/rest/v1/comicos" in ingesta
    assert "$env.SUPABASE_KEY" in ingesta
    assert "'Bearer ' + $env.SUPABASE_KEY" in ingesta

    # Scoring & Draft reconstruido (multi-tenant, Sprint 5): usa BACKEND_URL y SUPABASE_URL
    assert "$env.BACKEND_URL" in scoring
    assert "$env.SUPABASE_URL" in scoring
    assert "$env.WEBHOOK_API_KEY" in scoring

    assert "$env.SUPABASE_URL }}/rest/v1/lineup_candidates" in render
    assert "$env.SUPABASE_SERVICE_KEY" in render
    assert "'Bearer ' + $env.SUPABASE_SERVICE_KEY" in render

    # Test BOT.json debe usar env vars para todas las keys sensibles
    assert "$env.WEBHOOK_API_KEY" in test_bot
    assert "$env.SUPABASE_SERVICE_KEY" in test_bot
    assert "$env.BACKEND_URL" in test_bot
    assert "$env.SUPABASE_URL" in test_bot
