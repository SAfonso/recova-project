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
    forbidden_literals = [
        "sb_publishable_",
        "46.225.120.243:5000",
        "cggciltvpffitognpnae.supabase.co/rest/v1",
    ]

    for path in sorted(WORKFLOWS_DIR.glob("*.json")):
        content = path.read_text(encoding="utf-8")
        for literal in forbidden_literals:
            assert literal not in content, f"{path.name} contiene literal prohibido: {literal}"


def test_n8n_workflows_use_env_references_for_sensitive_values():
    ingesta = _workflow_text("Ingesta-Solicitudes.json")
    scoring = _workflow_text("Scoring & Draft.json")
    lineup = _workflow_text("LineUp.json")

    assert "$env.N8N_BACKEND_INGEST_URL" in ingesta
    assert "$env.WEBHOOK_API_KEY" in ingesta
    assert "$env.SUPABASE_URL + '/rest/v1/comicos'" in ingesta
    assert "$env.SUPABASE_KEY" in ingesta
    assert "'Bearer ' + $env.SUPABASE_KEY" in ingesta

    # Scoring & Draft reconstruido (multi-tenant, Sprint 5): usa RECOVA_BACKEND_URL y SUPABASE_URL
    assert "$env.RECOVA_BACKEND_URL" in scoring
    assert "$env.SUPABASE_URL" in scoring
    assert "$env.WEBHOOK_API_KEY" in scoring

    assert "$env.SUPABASE_URL + '/rest/v1/lineup_candidates'" in lineup
    assert "$env.SUPABASE_KEY" in lineup
    assert "'Bearer ' + $env.SUPABASE_KEY" in lineup
    assert "$env.RECOVA_RENDERER_URL" in lineup  # render va a recova-renderer:5050
