# Spec: Telegram Lineup Agent (v0.8.0)

**Módulo:** `backend/src/mcp/lineup_mcp_server.py`
**Estado:** pendiente de implementación
**Versión:** 0.8.0
**Sprint:** 3

---

## 1. Contexto y motivación

El host necesita poder consultar y gestionar el lineup desde cualquier lugar, sin abrir la app web. El canal natural es Telegram (ya lo usan para coordinación). Un agente LLM permite lenguaje natural sin recordar comandos.

**Casos de uso cubiertos:**

| Mensaje del host | Acción |
|---|---|
| "¿quién está en el lineup del viernes?" | `get_lineup` → lista confirmados |
| "pasa el scoring" | `run_scoring` → ejecuta engine |
| "reabre el lineup del 20 de marzo" | `reopen_lineup` → reset slots |
| "¿quiénes son los mejores candidatos?" | `get_candidates` → top scoring |
| "¿qué open mics tengo?" | `list_open_mics` → lista del host |

---

## 2. Arquitectura

```
Telegram (host)
    ↓ mensaje
n8n workflow "telegram-lineup-agent"
    ↓ POST Telegram webhook
    ↓ llama Claude API (claude-sonnet-4-6)
       con tool_definitions apuntando al MCP server
    ↓ Claude decide qué tool llamar
    ↓ n8n ejecuta la tool (HTTP call → Flask :5000/mcp/...)
    ↓ resultado vuelve a Claude
    ↓ Claude genera respuesta en lenguaje natural
    ↓ n8n envía respuesta por Telegram
```

**Por qué no MCP nativo (stdio/SSE):** n8n orquesta el flujo vía HTTP; los tools se exponen como endpoints REST en el backend Flask existente bajo `/mcp/*`. Claude recibe las definiciones de tool en el system prompt/tools array. Mismo resultado, sin proceso extra.

---

## 3. Endpoints Flask nuevos (`/mcp/*`)

Todos en `backend/src/triggers/webhook_listener.py`.
Autenticados con `X-API-Key` (mismo mecanismo existente).

### 3.1 `GET /mcp/open-mics?host_id=<uuid>`

Devuelve los open mics del host.

**Response:**
```json
{
  "open_mics": [
    {"id": "...", "nombre": "Recova Open Mic", "icon": "mic"}
  ]
}
```

### 3.2 `GET /mcp/lineup?open_mic_id=<uuid>&fecha_evento=<YYYY-MM-DD>`

Devuelve el lineup confirmado actual (desde `silver.lineup_slots`).

**Response:**
```json
{
  "open_mic_id": "...",
  "fecha_evento": "2026-03-20",
  "slots": [
    {"slot_order": 1, "nombre": "Ada Torres", "instagram": "adatorres", "categoria": "priority"},
    ...
  ],
  "total": 6,
  "validado": true
}
```

### 3.3 `GET /mcp/candidates?open_mic_id=<uuid>&limit=<int>`

Devuelve candidatos ordenados por score desde `gold.lineup_candidates`.

**Response:**
```json
{
  "candidates": [
    {"nombre": "...", "instagram": "...", "score_final": 80, "penalizado": false, "categoria": "priority"},
    ...
  ]
}
```

### 3.4 `POST /mcp/run-scoring`

Ejecuta `execute_scoring(open_mic_id)`.

**Body:** `{"open_mic_id": "..."}`

**Response:** resultado directo de `execute_scoring()` (ver scoring_engine_v3_spec.md §3).

### 3.5 `POST /mcp/reopen-lineup`

Ejecuta `silver.reset_lineup_slots(open_mic_id, fecha_evento)`.

**Body:** `{"open_mic_id": "...", "fecha_evento": "YYYY-MM-DD"}`

**Response:**
```json
{"status": "ok", "message": "Lineup reabierto para 2026-03-20"}
```

---

## 4. Autenticación Telegram → Host

El host debe estar mapeado en Supabase para que el agente sepa qué `host_id` usar.

### Tabla nueva: `silver.telegram_users`

```sql
CREATE TABLE silver.telegram_users (
  telegram_user_id  bigint  PRIMARY KEY,
  host_id           uuid    NOT NULL REFERENCES silver.organization_members(user_id),
  created_at        timestamptz DEFAULT now()
);
```

El `telegram_user_id` se extrae del payload de Telegram en n8n (`message.from.id`).
Si no existe en la tabla, el agente responde: "No estás registrado como host."

### Registro MVP (manual):

```sql
-- Insertar directamente en Supabase:
INSERT INTO silver.telegram_users (telegram_user_id, host_id)
VALUES (<tu_telegram_id>, '<tu_host_uuid>');
```

### Registro futuro — Self-registration con QR

Flujo completo sin intervención manual:

```
1. Host pulsa "Conectar Telegram" en la web app
2. Backend genera código temporal (ej: RCV-4829), lo guarda en
   silver.telegram_registration_codes (code, host_id, expires_at, used)
3. Frontend construye la URL: https://t.me/<BotUsername>?start=RCV-4829
4. Frontend renderiza un QR de esa URL (librería: qrcode.react)
5. Host escanea el QR con el móvil → Telegram se abre con /start RCV-4829 pre-rellenado
6. Host pulsa "Enviar" (un tap)
7. n8n recibe /start RCV-4829:
   → busca el código en silver.telegram_registration_codes
   → valida que no ha expirado y no ha sido usado
   → INSERT INTO silver.telegram_users (telegram_user_id, host_id)
   → marca el código como used=true
8. Bot responde: "Cuenta conectada. Ya puedes gestionar tus lineups."
```

**Tabla adicional necesaria (futuro):**

```sql
CREATE TABLE silver.telegram_registration_codes (
  code       text        PRIMARY KEY,
  host_id    uuid        NOT NULL,
  expires_at timestamptz NOT NULL DEFAULT now() + interval '15 minutes',
  used       boolean     NOT NULL DEFAULT false
);
```

**Endpoint backend necesario (futuro):**
`POST /api/telegram/generate-code` → devuelve `{code, qr_url}`

---

## 5. Definición de tools para Claude

Enviadas en el array `tools` de la Claude API:

```json
[
  {
    "name": "list_open_mics",
    "description": "Lista los open mics del host autenticado.",
    "input_schema": {
      "type": "object",
      "properties": {
        "host_id": {"type": "string", "description": "UUID del host"}
      },
      "required": ["host_id"]
    }
  },
  {
    "name": "get_lineup",
    "description": "Obtiene el lineup confirmado para un open mic y fecha.",
    "input_schema": {
      "type": "object",
      "properties": {
        "open_mic_id": {"type": "string"},
        "fecha_evento": {"type": "string", "description": "Formato YYYY-MM-DD"}
      },
      "required": ["open_mic_id", "fecha_evento"]
    }
  },
  {
    "name": "get_candidates",
    "description": "Lista los mejores candidatos por score para un open mic.",
    "input_schema": {
      "type": "object",
      "properties": {
        "open_mic_id": {"type": "string"},
        "limit": {"type": "integer", "default": 10}
      },
      "required": ["open_mic_id"]
    }
  },
  {
    "name": "run_scoring",
    "description": "Ejecuta el motor de scoring para calcular y actualizar puntuaciones.",
    "input_schema": {
      "type": "object",
      "properties": {
        "open_mic_id": {"type": "string"}
      },
      "required": ["open_mic_id"]
    }
  },
  {
    "name": "reopen_lineup",
    "description": "Reabre el lineup (resetea los slots confirmados) para permitir cambios.",
    "input_schema": {
      "type": "object",
      "properties": {
        "open_mic_id": {"type": "string"},
        "fecha_evento": {"type": "string", "description": "Formato YYYY-MM-DD"}
      },
      "required": ["open_mic_id", "fecha_evento"]
    }
  }
]
```

---

## 6. System prompt del agente

```
Eres el asistente de gestión de lineups para open mics de comedia.
Tienes acceso a herramientas para consultar y modificar lineups.
Responde siempre en español, de forma concisa y clara.
El host_id del usuario actual es: {host_id}
Fecha de hoy: {today}
```

---

## 7. Flujo n8n (workflow: `telegram-lineup-agent`)

```
[Telegram Trigger]
    → extrae telegram_user_id
    → lookup host_id en silver.telegram_users (Supabase node)
    → si no existe: responde "No registrado"
    → llama Claude API con tools + system prompt + mensaje del host
    → loop tool_use:
        → HTTP Request al endpoint /mcp/* correspondiente
        → devuelve resultado a Claude (tool_result)
    → Claude genera respuesta final (text)
    → Telegram: envía respuesta al chat
```

---

## 8. Variables de entorno nuevas

```
# backend/.env
ANTHROPIC_API_KEY=<key>          # Para llamadas directas desde n8n (no backend)

# n8n credentials
TELEGRAM_BOT_TOKEN=<token>       # Bot de Telegram
ANTHROPIC_API_KEY=<key>          # Claude API en n8n
RECOVA_BACKEND_URL=http://...    # URL del backend Flask
RECOVA_API_KEY=<key>             # X-API-Key existente
```

---

## 9. Tests requeridos

Archivo: `backend/tests/mcp/test_lineup_mcp_endpoints.py`

| Test | Cubre |
|---|---|
| `test_get_lineup_returns_slots` | endpoint `/mcp/lineup` con datos |
| `test_get_lineup_empty_when_no_slots` | lineup no validado → slots vacíos |
| `test_get_candidates_returns_sorted` | `/mcp/candidates` ordenado por score |
| `test_run_scoring_calls_engine` | `/mcp/run-scoring` delega a `execute_scoring` |
| `test_reopen_lineup_calls_reset_rpc` | `/mcp/reopen-lineup` llama RPC reset |
| `test_list_open_mics_filters_by_host` | `/mcp/open-mics` filtra por host_id |
| `test_mcp_endpoints_require_api_key` | todos los endpoints verifican auth |

---

## 10. Restricciones

- `reopen_lineup` no valida ni confirma nada; solo borra `lineup_slots` — la confirmación sigue siendo exclusiva de la app web
- El agente NO puede crear ni eliminar open mics
- El agente opera en modo lectura + acciones reversibles únicamente
- `run_scoring` no dispara el webhook de render; solo recalcula scores
- Telegram bot token se gestiona exclusivamente en n8n (no en backend)
