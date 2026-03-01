# Ejecución de tests backend

## Ubicación y runner
- Carpeta de tests: `backend/tests`
- Runner: `pytest`
- Config: `pyproject.toml` (`testpaths = ["backend/tests"]`)

## Comandos principales
1. Suite completa:
   - `./.venv/bin/python -m pytest -q`
2. Colección (diagnóstico import mismatch):
   - `./.venv/bin/python -m pytest -q --collect-only backend/tests`
3. Core (Regla del Espejo para `backend/src/core/*`):
   - `./.venv/bin/python -m pytest -q backend/tests/core`
4. MCP HTTP/orquestación:
   - `./.venv/bin/python -m pytest -q backend/tests/mcp`
5. Unit (ingesta, scoring, setup y webhook):
   - `./.venv/bin/python -m pytest -q backend/tests/unit`
6. Contratos SQL:
   - `./.venv/bin/python -m pytest -q backend/tests/sql`

## Comandos focalizados
- `./.venv/bin/python -m pytest -q backend/tests/core/test_data_binder.py`
- `./.venv/bin/python -m pytest -q backend/tests/core/test_security.py`
- `./.venv/bin/python -m pytest -q backend/tests/core/test_render.py`
- `./.venv/bin/python -m pytest -q backend/tests/mcp/test_mcp_server_http.py`
- `./.venv/bin/python -m pytest -q backend/tests/mcp/test_server_integration.py`

## Limpieza de caché (recomendado en CI/local)
```bash
find backend -type d -name "__pycache__" -prune -exec rm -rf {} +
find backend -type f -name "*.pyc" -delete
```

## Nota
Si `python3 -m pytest` falla por módulo no encontrado, usa el Python del entorno virtual:
- `./.venv/bin/python -m pytest ...`
