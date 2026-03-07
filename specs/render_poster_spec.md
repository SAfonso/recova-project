# SDD — Render Poster Endpoint (Sprint 11, v0.16.0)

---

## Objetivo

Exponer el render de carteles (PosterComposer) como endpoint HTTP en el backend Flask,
para que el workflow n8n `LineUp` pueda llamarlo directamente sin necesitar
el servidor MCP (puerto 5050) corriendo por separado.

---

## Cambios

| Archivo | Cambio |
|---------|--------|
| `backend/src/triggers/webhook_listener.py` | Nuevo endpoint `POST /api/render-poster` |
| `backend/tests/test_render_poster.py` | Tests TDD (5 tests) |
| `workflows/n8n/LineUp.json` | Reescrito: env vars, llama backend, Telegram binario |
| `backend/tests/unit/test_n8n_workflows_security.py` | Contrato actualizado para LineUp |

---

## Endpoint: `POST /api/render-poster`

### Auth
`X-API-KEY` header requerido.

### Request body

```json
{
  "event_id": "2026-04-15",
  "lineup": [
    {"order": 1, "name": "Ana García",   "instagram": "anagarcia"},
    {"order": 2, "name": "Bruno Torres", "instagram": "brunotorres"}
  ],
  "date": "15 ABR"
}
```

| Campo | Requerido | Descripción |
|-------|-----------|-------------|
| `event_id` | no | Identificador del evento (default: `"evento"`) |
| `lineup` | sí | Lista de cómicos `{order, name, instagram}` |
| `date` | no | Texto de fecha para el footer (default: `event_id`) |

### Respuesta exitosa — 200

Content-Type: `image/png` — binario del cartel renderizado.

### Errores

| Código | Condición |
|--------|-----------|
| 400 | `lineup` vacío o ausente |
| 401 | Sin X-API-KEY |
| 500 | Error interno de PosterComposer |

### Implementación

Llama directamente a `PosterComposer().render()` (síncrono, Pillow).
Escribe el PNG a `/tmp/render_{event_id}.png` y lo devuelve con `send_file`.
No se necesita el servidor MCP (mcp_server.py) en producción para este flujo.

---

## Workflow n8n: `LineUp.json`

### Trigger

`POST /webhook/generar-poster-lineup`

Body esperado:
```json
{
  "fecha": "2026-04-15",
  "telegram_user_id": "4088898",
  "open_mic_id": "om-uuid"
}
```

### Flujo

```
Webhook
  → Get Approved Comics   (Supabase gold.lineup_candidates, filtro fecha + estado)
  → Map Payload           (construye body para /api/render-poster)
  → HTTP (render)         (POST /api/render-poster, response format: file → binary "cartel")
  → Telegram (enviar)     (sendPhoto con binary "cartel")
```

### Variables de entorno requeridas

| Variable | Uso |
|----------|-----|
| `SUPABASE_URL` | Base URL de Supabase |
| `SUPABASE_KEY` | Service key |
| `RECOVA_BACKEND_URL` | URL del backend Flask |
| `WEBHOOK_API_KEY` | Auth del backend |

---

## Tests TDD

| Test | Descripción |
|------|-------------|
| `test_render_poster_requires_api_key` | 401 sin X-API-KEY |
| `test_render_poster_requires_lineup` | 400 si lineup vacío o ausente |
| `test_render_poster_returns_png` | 200, Content-Type image/png |
| `test_render_poster_calls_composer_with_correct_args` | PosterComposer.render llamado con lineup/date/event_id |
| `test_render_poster_returns_500_on_render_error` | 500 si PosterComposer lanza excepción |
