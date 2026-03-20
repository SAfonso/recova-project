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
- **`_rate_limit_store` también se filtra entre tests.** La fixture `_reset_rate_limit_store` en `conftest.py` (autouse) lo limpia. Si se añade otro store global, añadir su reset.

### Python — mocking psycopg2
- **psycopg2 devuelve JSONB como `dict`, NO como `str`.** En mocks de cursor, `fetchone()` para columnas JSONB debe devolver `({"key": "value"},)`, no `('{"key": "value"}',)`.
- **El orden de columnas en `fetchall()` debe coincidir exactamente** con el SELECT de la query real. Verificar siempre contra la función que consume el cursor (ej: `fetch_silver_requests` espera `solicitud_id` en posición 0, `comico_id` en posición 1).

### Python — validación de endpoints
- Todos los endpoints POST usan `@validate_json({"campo": tipo})` de `shared.py`. NO duplicar validación manual dentro del endpoint.
- Usar `request.get_json(silent=True)` (no `force=True`) cuando el decorador ya valida el body. `force=True` anula la validación del decorador.
- **NUNCA interpolar nombres de columna en SQL con f-strings.** Usar whitelist o `sql.Identifier()` de psycopg2. Aplica a `register_ingestion_error()` en ingesta.

### Python — scoring y configuración
- Validar bounds de `ScoringConfig`: `available_slots > 0`, `penalty_points >= 0`. No confiar en que el host configure valores razonables.
- `infer_gender()` devuelve `None` si las 3 capas fallan. El frontend convierte a `'nb'`. Es una limitación conocida — documentar, no ocultar.

### Python — manejo de excepciones
- **NO usar `except Exception: continue` sin logging.** Si una operación de ingesta falla (Sheet 403, JSON corrupto, etc.), al menos logear `logger.exception(...)` antes de continuar. Los silent failures son imposibles de debuguear en producción.

### Tests — aserciones de mensajes
- **NO hacer assert de mensajes en español/inglés específicos** (ej: `"obligatorio" in msg`). En su lugar, verificar el campo relevante: `"field_name" in msg`. Esto evita roturas al cambiar idioma o formato del mensaje de error.

### Frontend — Joyride targets
- Los `data-tutorial="..."` deben estar en elementos que **siempre estén en el DOM**, no dentro de condicionales React. Si el elemento es condicional, envolver en un `<div data-tutorial="...">` siempre renderizado.

### Frontend — hooks y componentes
- `App.jsx` es orquestador puro (~120 líneas). Lógica de negocio vive en `hooks/useCandidates.js`, `hooks/useEdits.js`, `hooks/useValidation.js`.
- Componentes presentacionales en `components/open-mic/`: `LoadingSkeleton`, `ValidadoStamp`, `CambiarConfirmModal`, `RecoveryNotes`.
- `CATEGORY_OPTIONS` se exporta desde `hooks/useEdits.js`, no hardcodear en otros sitios.

### Frontend — tests con happy-dom
- **`alert()`, `confirm()`, `prompt()` no existen en happy-dom.** Si un hook los usa, el test debe hacer `globalThis.alert = vi.fn()` en `beforeEach`, o mejor reemplazar por callback/setError.
- **Cuidado con `?.prop !== false`**: `undefined !== false` es `true`. Al escribir tests, trazar el valor real con los datos mock antes de asumir defaults.

### Flask — Rate limiting
- Usar `@rate_limit(max_requests, window_seconds)` de `shared.py` en endpoints públicos o sensibles. El decorador va **antes** de `@validate_json` en el stack de decoradores.
- `rate_limit` acepta `key_fn` opcional (callable sin args → str) para discriminar por `host_id`/`open_mic_id` en lugar de por IP. Imprescindible en endpoints llamados desde n8n (IP fija).
- Límites actuales:
  - form-submission: 5/min por IP
  - telegram/register: 10/min por IP
  - validate-view/*: 30/min por IP
  - /mcp/open-mics, lineup, candidates: 20/min por `host_id`/`open_mic_id`
  - /mcp/run-scoring, reopen-lineup: 5/5min por `open_mic_id`
- No usar Redis — Docker corre un solo worker; el store in-memory es suficiente.

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

frontend/src/
├── hooks/                # useCandidates, useEdits, useValidation
├── components/open-mic/  # Header, NotebookSheet, ExpandedView, LoadingSkeleton, ValidadoStamp, CambiarConfirmModal, RecoveryNotes…
├── App.jsx               # Orquestador puro (~120 líneas)
└── test/                 # Vitest + happy-dom + @testing-library/react
```
- `scoring_engine.py` — motor scoring con `score_breakdown` JSONB audit trail
- `bronze_to_silver_ingestion.py` — ingesta con `infer_gender()` cascada INE→gender-guesser→genderize.io
- `backend/tests/conftest.py` — fixture `_reset_sb_singleton` autouse

## Tests
```bash
PYTHONPATH=. pytest backend/tests/   # 370 tests
cd frontend && npm test              # 70 tests
```
