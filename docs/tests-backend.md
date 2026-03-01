# Ejecucion de tests del backend

## Ubicacion
- Carpeta de tests: `backend/tests`
- Framework: `pytest`
- Configuracion: `pyproject.toml` (`testpaths = ["backend/tests"]`)

## Comandos
1. Ejecutar toda la suite:
   - `./.venv/bin/python -m pytest -q`
2. Ejecutar con detalle:
   - `./.venv/bin/python -m pytest -v`
3. Ejecutar solo unit tests:
   - `./.venv/bin/python -m pytest -q backend/tests/unit`
4. Ejecutar solo contratos SQL:
   - `./.venv/bin/python -m pytest -q backend/tests/sql`
5. Ejecutar un archivo concreto:
   - `./.venv/bin/python -m pytest -q backend/tests/unit/test_setup_db.py`
6. Ejecutar un test puntual:
   - `./.venv/bin/python -m pytest -q backend/tests/unit/test_setup_db.py::test_verify_enums_uses_expected_refs`
7. Ejecutar la suite SDD del renderer Playwright:
   - `./.venv/bin/python -m pytest -q backend/tests/unit/test_playwright_renderer.py`
8. Ejecutar test de integración de upload a Supabase Storage:
   - `./.venv/bin/python -m pytest -q backend/tests/integration/test_supabase_upload.py`

## Nota practica
Si `python3 -m pytest` falla por modulo no encontrado, usa el Python del entorno virtual con `./.venv/bin/python`.

9. Ejecutar verificación de limpieza local post-upload del renderer:
   - `./.venv/bin/python -m pytest -q backend/tests/unit/test_playwright_renderer.py::test_temp_file_is_deleted_after_upload`

10. Ejecutar tests de la API Flask de render:
   - `./.venv/bin/python -m pytest -q backend/tests/unit/test_app.py`

11. Ejecutar la suite TDD de seguridad MCP (URL + Magic Bytes + timeout):
   - `./.venv/bin/python -m pytest -q backend/tests/mcp/test_security.py`


## Requisito de entorno para renderer en VPS
Antes de validar tests o ejecutar render en producción:
- `playwright install chromium`
- `playwright install-deps`

Esto reduce fallos de arranque de navegador real y evita depender del fallback local.

12. Ejecutar la suite TDD de inyección Data Binder (slots + FitText + privacidad):
   - `./.venv/bin/python -m pytest -q backend/tests/mcp/test_data_binder.py`

13. Ejecutar la suite de integración del orquestador MCP (TDD asíncrono):
   - `./.venv/bin/python -m pytest -q backend/tests/mcp/test_server_integration.py`

14. Ejecutar solo la validación de lock de concurrencia MCP:
   - `./.venv/bin/python -m pytest -q backend/tests/mcp/test_server_integration.py::test_concurrency_lock`
15. Ejecutar unit tests del motor `core/render.py` (éxito, timeout y flags de Chromium):
   - `./.venv/bin/python -m pytest -q backend/tests/core/test_render.py`

16. Ejecutar integración HTTP del servidor MCP (`/healthz`, `/tools/render_lineup`, lock secuencial):
   - `./.venv/bin/python -m pytest -q backend/tests/mcp/test_mcp_server_http.py`


17. Ejecutar unit tests core de inyección visual (FitText + slots ocultos):
   - `./.venv/bin/python -m pytest -q backend/tests/core/test_data_binder.py`

18. Ejecutar unit tests core de seguridad (URL hardening + Magic Bytes):
   - `./.venv/bin/python -m pytest -q backend/tests/core/test_security.py`

19. Ejecutar la integración HTTP MCP con payload inválido controlado:
   - `./.venv/bin/python -m pytest -q backend/tests/mcp/test_mcp_server_http.py::test_render_invalid_payload`

20. Ejecutar cobertura enfocada en core y visualizar líneas Missing:
   - `./.venv/bin/python -m pytest --cov=backend/src --cov-report=term-missing backend/tests/core backend/tests/mcp`
