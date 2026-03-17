"""Tests for the validate_json decorator in shared.py."""

import os

os.environ.setdefault("WEBHOOK_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "http://fake-supabase")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")

from flask import Flask, jsonify

from backend.src.triggers.shared import validate_json

app = Flask(__name__)


@app.route("/test-no-required", methods=["POST"])
@validate_json()
def endpoint_no_required():
    return jsonify({"ok": True}), 200


@app.route("/test-required", methods=["POST"])
@validate_json({"name": str, "age": int})
def endpoint_required():
    return jsonify({"ok": True}), 200


@app.route("/test-optional-type", methods=["POST"])
@validate_json({"ids": list})
def endpoint_list():
    return jsonify({"ok": True}), 200


class TestValidateJsonDecorator:
    """Tests para @validate_json."""

    def test_no_json_body_returns_400(self):
        with app.test_client() as c:
            resp = c.post("/test-no-required", data="not json", content_type="text/plain")
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_JSON"
        assert "valid JSON" in resp.get_json()["error"]["message"]

    def test_valid_json_no_requirements_passes(self):
        with app.test_client() as c:
            resp = c.post("/test-no-required", json={"anything": "goes"})
        assert resp.status_code == 200

    def test_empty_json_no_requirements_passes(self):
        with app.test_client() as c:
            resp = c.post("/test-no-required", json={})
        assert resp.status_code == 200

    def test_missing_required_field_returns_400(self):
        with app.test_client() as c:
            resp = c.post("/test-required", json={"name": "Ana"})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["error"]["code"] == "MISSING_FIELDS"
        assert "age" in body["error"]["message"]

    def test_null_required_field_returns_400(self):
        with app.test_client() as c:
            resp = c.post("/test-required", json={"name": "Ana", "age": None})
        assert resp.status_code == 400
        assert "age" in resp.get_json()["error"]["message"]

    def test_wrong_type_returns_400(self):
        with app.test_client() as c:
            resp = c.post("/test-required", json={"name": "Ana", "age": "twenty"})
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "INVALID_FIELD_TYPE"
        assert "Wrong field types" in resp.get_json()["error"]["message"]

    def test_all_required_fields_correct_passes(self):
        with app.test_client() as c:
            resp = c.post("/test-required", json={"name": "Ana", "age": 25})
        assert resp.status_code == 200

    def test_extra_fields_allowed(self):
        with app.test_client() as c:
            resp = c.post("/test-required", json={"name": "Ana", "age": 25, "extra": "ok"})
        assert resp.status_code == 200

    def test_list_type_validation(self):
        with app.test_client() as c:
            resp = c.post("/test-optional-type", json={"ids": "not-a-list"})
        assert resp.status_code == 400
        assert "Wrong field types" in resp.get_json()["error"]["message"]

    def test_list_type_passes(self):
        with app.test_client() as c:
            resp = c.post("/test-optional-type", json={"ids": [1, 2, 3]})
        assert resp.status_code == 200

    def test_multiple_missing_fields(self):
        with app.test_client() as c:
            resp = c.post("/test-required", json={})
        assert resp.status_code == 400
        msg = resp.get_json()["error"]["message"]
        assert "name" in msg
        assert "age" in msg
