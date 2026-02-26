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
