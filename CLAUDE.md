# CLAUDE.md — Instrucciones para Claude Code

## Proyecto
SaaS multi-tenant para gestión de open mics de comedia. Stack: React+Vite (frontend), Python/Flask (backend), Supabase (DB/auth), n8n (workflows). Arquitectura Medallion Bronze/Silver/Gold.

## Convenciones
- Idioma commits: español, con `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
- Push siempre a `dev`; merge a `main` solo cuando se pida explícitamente
- SDD: spec primero, luego implementación
- Respuestas cortas y directas

## Reglas de desarrollo

### Python — patches en tests
- **NUNCA parchear `backend.src.triggers.shared._sb_client` directamente en tests de blueprints.** Cuando un blueprint hace `from shared import _sb_client`, Python vincula el nombre localmente. El patch debe apuntar al módulo del blueprint: `backend.src.triggers.blueprints.ingestion._sb_client`, NO `backend.src.triggers.shared._sb_client`.
- **Singleton `_SB_SINGLETON` se filtra entre tests.** Siempre usar la fixture `_reset_sb_singleton` de `conftest.py` (ya es `autouse=True`). Si se crea un nuevo singleton en `shared.py`, añadir su reset a la misma fixture.

### Python — mocking psycopg2
- **psycopg2 devuelve JSONB como `dict`, NO como `str`.** En mocks de cursor, `fetchone()` para columnas JSONB debe devolver `({"key": "value"},)`, no `('{"key": "value"}',)`.
- **El orden de columnas en `fetchall()` debe coincidir exactamente** con el SELECT de la query real. Verificar siempre contra la función que consume el cursor (ej: `fetch_silver_requests` espera `solicitud_id` en posición 0, `comico_id` en posición 1).

### Python — validación de endpoints
- Todos los endpoints POST usan `@validate_json({"campo": tipo})` de `shared.py`. NO duplicar validación manual dentro del endpoint.
- Usar `request.get_json(silent=True)` (no `force=True`) cuando el decorador ya valida el body.

### Tests — aserciones de mensajes
- **NO hacer assert de mensajes en español/inglés específicos** (ej: `"obligatorio" in msg`). En su lugar, verificar el campo relevante: `"field_name" in msg`. Esto evita roturas al cambiar idioma o formato del mensaje de error.

### Frontend — Joyride targets
- Los `data-tutorial="..."` deben estar en elementos que **siempre estén en el DOM**, no dentro de condicionales React. Si el elemento es condicional, envolver en un `<div data-tutorial="...">` siempre renderizado.

### Flask — CORS
- NO usar `flask-cors` (la v6.x está rota silenciosamente). Usar handlers manuales `@before_request`/`@after_request` con `_cors_headers()` dinámico en `shared.py`.
- Origins permitidos: `FRONTEND_URL` (Vercel) + `localhost:5173` + `localhost:3000`.

### Scoring — constantes
- `_SINGLE_DATE_BONUS` está en `scoring_config.py`. Siempre referenciar la constante, nunca hardcodear el literal `40`.
- `score_breakdown` en `build_ranking()` debe usar valores dinámicos del `ScoringConfig`, no literales.

### Supabase
- RPCs en schema `silver`: siempre `sb.schema("silver").rpc(...)`, NUNCA `sb.rpc(...)`.
- Frontend: `supabase.schema('silver').rpc(...)`.

## Estructura clave
```
backend/src/triggers/
├── webhook_listener.py   # App factory (~36 líneas)
├── shared.py             # Auth, CORS, _sb_client singleton, validate_json, helpers
└── blueprints/           # 8 blueprints por dominio
```
- `scoring_engine.py` — motor scoring con `score_breakdown` JSONB audit trail
- `bronze_to_silver_ingestion.py` — ingesta con `infer_gender()` cascada INE→gender-guesser→genderize.io
- `backend/tests/conftest.py` — fixture `_reset_sb_singleton` autouse

## Tests
```bash
PYTHONPATH=. pytest backend/tests/   # 356 tests
cd frontend && npm test              # 44 tests
```
