# SDD — Dev Tools Panel (Sprint 12, v0.17.0)

---

## Objetivo

Panel de herramientas de prueba en la config del open mic (frontend) para poder
poblar datos, forzar ingesta y forzar scoring sin entrar en n8n ni en el servidor.
Endpoints protegidos por Supabase JWT (el host debe estar logueado).

---

## Cambios

| Archivo | Cambio |
|---------|--------|
| `requirements.txt` | Añadir `PyJWT>=2.8.0` |
| `backend/src/triggers/webhook_listener.py` | Helper `_is_authenticated_user` + 3 endpoints `/api/dev/*` |
| `backend/src/core/dev_users_pool.py` | Pool de 100 usuarios de prueba |
| `backend/tests/test_dev_tools.py` | Tests TDD |
| `frontend/src/components/DevToolsPanel.jsx` | Panel con 3 botones |
| `frontend/src/components/OpenMicDetail.jsx` | Tab "Dev" que monta `DevToolsPanel` |

---

## Auth: Supabase JWT

Nueva variable de entorno: `SUPABASE_JWT_SECRET` (disponible en Supabase → Settings → API).

Helper en Flask:
```python
def _is_authenticated_user(req) -> dict | None:
    """Verifica Supabase JWT. Devuelve payload o None si inválido."""
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError:
        return None
```

El frontend obtiene el token con `supabase.auth.getSession()` y lo envía como
`Authorization: Bearer <access_token>`.

---

## Pool de usuarios: `dev_users_pool.py`

Lista de 100 dicts con campos variados:

| Campo | Valores |
|-------|---------|
| `nombre` | 100 nombres españoles únicos |
| `instagram` | slug único derivado del nombre |
| `telefono` | móviles españoles (+34 6xx) |
| `experiencia_raw` | mix de los 4 niveles |
| `disponibilidad_ultimo_minuto` | ~50/50 Sí/No |
| `origen_conocimiento` | instagram/referido/whatsapp/amigos/cartel |

Función pública: `get_random_users(n: int) -> list[dict]` — devuelve n usuarios
aleatorios sin repetición del pool.

---

## Endpoints `/api/dev/*`

### `POST /api/dev/seed-open-mic`

**Auth:** Supabase JWT
**Body:** `{ "open_mic_id": "uuid" }`

1. Verifica JWT → 401 si inválido
2. Lee `config.seed_used` del open mic → 409 si ya se sembró
3. Llama `get_random_users(10)` del pool
4. Inserta 10 `bronze.solicitudes` con `procesado=false`
5. Lanza `bronze_to_silver_ingestion.py` en background
6. Marca `config.seed_used = true` via RPC `update_open_mic_config_keys`
7. Devuelve `{"status": "ok", "seeded": 10}`

**Respuestas:**
| Código | Condición |
|--------|-----------|
| 200 | OK |
| 400 | `open_mic_id` ausente |
| 401 | JWT inválido o ausente |
| 404 | open_mic no existe |
| 409 | ya sembrado (`seed_used: true`) |

### `POST /api/dev/trigger-ingest`

**Auth:** Supabase JWT
**Body:** `{ "open_mic_id": "uuid" }` (informativo, la ingesta es global)

1. Verifica JWT → 401
2. Lanza `ingest-from-sheets` + `ingest-from-forms` vía `subprocess.Popen`
   (los mismos scripts que llaman los endpoints internos)
3. Devuelve `{"status": "ok", "message": "ingesta lanzada en background"}`

### `POST /api/dev/trigger-scoring`

**Auth:** Supabase JWT
**Body:** `{ "open_mic_id": "uuid" }`

1. Verifica JWT → 401
2. Llama `execute_scoring(open_mic_id)` directamente (síncrono, devuelve resultado)
3. Devuelve `{"status": "ok", "result": {...}}`

---

## Frontend: `DevToolsPanel.jsx`

Sección colapsable "Herramientas de prueba" dentro del tab **Scoring** de `OpenMicDetail`.

```
┌─ Herramientas de prueba ──────────────────────────────┐
│  [Poblar datos de prueba]  ← disabled si seed_used    │
│  [Forzar ingesta]                                      │
│  [Forzar scoring]                                      │
└───────────────────────────────────────────────────────┘
```

- Cada botón muestra spinner mientras espera respuesta
- Toast de éxito/error tras cada acción
- "Poblar datos de prueba" queda permanentemente disabled tras éxito (actualiza config local)
- El panel solo se muestra si el usuario es el host del open mic

---

## Tests TDD

| Test | Descripción |
|------|-------------|
| `test_seed_requires_jwt` | 401 sin Authorization |
| `test_seed_invalid_jwt` | 401 con token inválido |
| `test_seed_requires_open_mic_id` | 400 sin open_mic_id |
| `test_seed_happy_path` | 200, inserta 10 bronze, lanza Popen, marca seed_used |
| `test_seed_already_seeded` | 409 si config.seed_used=true |
| `test_seed_open_mic_not_found` | 404 si open_mic no existe |
| `test_trigger_ingest_requires_jwt` | 401 sin Authorization |
| `test_trigger_ingest_happy_path` | 200, lanza Popen |
| `test_trigger_scoring_requires_jwt` | 401 sin Authorization |
| `test_trigger_scoring_happy_path` | 200, devuelve resultado de execute_scoring |
