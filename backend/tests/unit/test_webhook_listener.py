from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

MODULE_PATH = Path(__file__).resolve().parents[2] / "src" / "triggers" / "webhook_listener.py"


class DummyFlask:
    def __init__(self, _name: str):
        self.routes: dict[tuple[str, tuple[str, ...]], object] = {}

    def route(self, path: str, methods: list[str] | None = None):
        methods_tuple = tuple(methods or ["GET"])

        def decorator(func):
            self.routes[(path, methods_tuple)] = func
            return func

        return decorator

    def before_request(self, func):
        return func

    def after_request(self, func):
        return func


def load_webhook_module(monkeypatch, api_key: str = "test-key"):
    monkeypatch.setenv("WEBHOOK_API_KEY", api_key)

    # Mock flask
    fake_flask = types.ModuleType("flask")
    fake_flask.Flask = DummyFlask
    fake_flask.jsonify = lambda payload: payload
    fake_flask.request = types.SimpleNamespace(headers={})
    fake_flask.send_file = lambda path, **kw: (path, 200)
    monkeypatch.setitem(sys.modules, "flask", fake_flask)

    # Mock flask_cors
    fake_cors = types.ModuleType("flask_cors")
    fake_cors.CORS = lambda app, **kwargs: None
    monkeypatch.setitem(sys.modules, "flask_cors", fake_cors)

    # Mock supabase
    fake_supabase = types.ModuleType("supabase")
    fake_supabase.create_client = lambda url, key: None
    monkeypatch.setitem(sys.modules, "supabase", fake_supabase)

    # Mock google_form_builder
    fake_gb_mod = types.ModuleType("backend.src.core.google_form_builder")
    fake_gb_mod.GoogleFormBuilder = object
    monkeypatch.setitem(sys.modules, "backend.src.core.google_form_builder", fake_gb_mod)

    # Mock sheet_ingestor
    fake_si_mod = types.ModuleType("backend.src.core.sheet_ingestor")
    fake_si_mod.SheetIngestor = object
    monkeypatch.setitem(sys.modules, "backend.src.core.sheet_ingestor", fake_si_mod)

    # Mock form_ingestor
    fake_fi_mod = types.ModuleType("backend.src.core.form_ingestor")
    fake_fi_mod.FormIngestor = object
    monkeypatch.setitem(sys.modules, "backend.src.core.form_ingestor", fake_fi_mod)

    # Mock form_analyzer
    fake_fa_mod = types.ModuleType("backend.src.core.form_analyzer")
    fake_fa_mod.FormAnalyzer = object
    monkeypatch.setitem(sys.modules, "backend.src.core.form_analyzer", fake_fa_mod)

    # Mock custom_scoring_proposer
    fake_csp_mod = types.ModuleType("backend.src.core.custom_scoring_proposer")
    fake_csp_mod.CustomScoringProposer = object
    monkeypatch.setitem(sys.modules, "backend.src.core.custom_scoring_proposer", fake_csp_mod)

    # Mock poster_composer
    fake_pc_mod = types.ModuleType("backend.src.core.poster_composer")
    fake_pc_mod.PosterComposer = object
    monkeypatch.setitem(sys.modules, "backend.src.core.poster_composer", fake_pc_mod)

    # Mock dev_users_pool
    fake_dup_mod = types.ModuleType("backend.src.core.dev_users_pool")
    fake_dup_mod.get_random_users = lambda n: []
    monkeypatch.setitem(sys.modules, "backend.src.core.dev_users_pool", fake_dup_mod)

    # Mock scoring_engine
    fake_se_mod = types.ModuleType("backend.src.scoring_engine")
    fake_se_mod.execute_scoring = lambda open_mic_id: {}
    monkeypatch.setitem(sys.modules, "backend.src.scoring_engine", fake_se_mod)

    module_name = "test_webhook_listener_module"
    spec = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ingest_requires_api_key(monkeypatch):
    module = load_webhook_module(monkeypatch)

    module.request.headers = {}
    response = module.ingest()

    assert response == ({"status": "error", "message": "unauthorized"}, 401)


def test_scoring_returns_script_json_stdout(monkeypatch):
    module = load_webhook_module(monkeypatch)
    expected_payload = {"status": "ok", "lineup": ["ana", "luis"]}

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(expected_payload),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.request.headers = {module.API_KEY_HEADER: "test-key"}
    response = module.scoring()

    assert response == (expected_payload, 200)


def test_scoring_returns_500_when_script_fails(monkeypatch):
    module = load_webhook_module(monkeypatch)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="partial output",
            stderr="boom",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.request.headers = {module.API_KEY_HEADER: "test-key"}
    response = module.scoring()

    assert response == (
        {
            "status": "error",
            "message": "scoring script execution failed",
            "stdout": "partial output",
            "stderr": "boom",
        },
        500,
    )


def test_scoring_returns_500_when_stdout_is_not_json(monkeypatch):
    module = load_webhook_module(monkeypatch)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="not-json",
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module.request.headers = {module.API_KEY_HEADER: "test-key"}
    body, status = module.scoring()

    assert status == 500
    assert body["status"] == "error"
    assert body["message"] == "invalid JSON output from scoring script"
    assert body["stdout"] == "not-json"
    assert "Expecting value" in body["details"]
