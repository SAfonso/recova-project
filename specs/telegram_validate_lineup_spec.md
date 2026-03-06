# Spec: Lineup Validation via Telegram (v0.10.0)

**Sprint:** 5
**Estado:** pendiente de implementacion

---

## 1. Contexto

Hasta ahora la validacion del lineup solo es posible desde la web app (con sesion
magic link). Este sprint cierra el flujo de gestion desde Telegram:

- El cron de `Scoring & Draft` envia a cada host registrado un enlace de validacion
  con el lineup del proximo show.
- Desde el bot (`Test BOT`), el host puede pedir el lineup en cualquier momento y
  recibe el mismo enlace.
- El enlace abre una **vista standalone** (sin navegacion) donde valida el lineup.
  La validacion escribe en la BD exactamente igual que la web app, de modo que al
  entrar por la app aparece el sello VALIDADO.

---

## 2. Arquitectura del flujo

```
[Cron / Bot]
     ↓
POST /api/lineup/prepare-validation  { host_id, open_mic_id }
     ↓ calcula proximo evento, ejecuta scoring, genera token
     ↓ devuelve { fecha_evento, show_datetime, lineup, validate_url }
     ↓
Telegram → mensaje con lineup en texto + link validate_url
     ↓
Host abre validate_url en el movil
     ↓
GET /api/validate-view/lineup?token=xxx
     → valida token, devuelve { open_mic_id, fecha_evento, candidates, is_validated }
     ↓
Host pulsa Validar
     ↓
POST /api/validate-view/validate  { token, solicitud_ids }
     → llama RPCs: validate_lineup + upsert_confirmed_lineup
     ↓
BD actualizada — web app muestra sello VALIDADO
```

---

## 3. Migracion SQL

Archivo: `specs/sql/migrations/20260306_validation_tokens.sql`

```sql
CREATE TABLE IF NOT EXISTS silver.validation_tokens (
  token        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  host_id      uuid        NOT NULL,
  open_mic_id  uuid        NOT NULL,
  fecha_evento date        NOT NULL,
  expires_at   timestamptz NOT NULL
);

ALTER TABLE silver.validation_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_service_role_all_validation_tokens ON silver.validation_tokens;
CREATE POLICY p_service_role_all_validation_tokens
  ON silver.validation_tokens FOR ALL TO service_role
  USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, DELETE ON silver.validation_tokens TO service_role;
```

> `expires_at` se calcula en el backend como la fecha+hora del proximo show.
> Tokens expirados pueden limpiarse con un DELETE periodico o en el propio endpoint.

---

## 4. Endpoints backend

### 4.1 `POST /api/lineup/prepare-validation`

Orquesta todo lo necesario para enviar el link de validacion por Telegram.

**Auth:** `X-API-KEY`

**Request:**
```json
{ "host_id": "<uuid>", "open_mic_id": "<uuid>" }
```

**Logica:**
```
1. SELECT config FROM silver.open_mics WHERE id = open_mic_id
2. Calcular proximo evento:
      dia_semana = config.info.dia_semana   (ej: "Lunes")
      hora       = config.info.hora         (ej: "21:00", formato HH:MM 24h)
      → next_event_dt = proxima fecha de ese dia_semana cuya hora aun no ha pasado
      → Si el show de esta semana ya empezo → siguiente semana
3. Si next_event_dt <= now() → 409 { "message": "no hay show proximo" }
4. POST /scoring con open_mic_id + fecha_evento   (ejecuta scoring engine)
5. GET gold.lineup_candidates WHERE open_mic_id = X AND fecha_evento = Y
      ORDER BY score DESC
6. INSERT INTO silver.validation_tokens
      (host_id, open_mic_id, fecha_evento, expires_at=next_event_dt)
      → devuelve token UUID
7. validate_url = FRONTEND_URL/validate?token=<uuid>
```

**Response 200:**
```json
{
  "fecha_evento": "2026-03-09",
  "show_datetime": "2026-03-09T21:00:00",
  "validate_url": "https://recova-project-z5zp.vercel.app/validate?token=<uuid>",
  "lineup": [
    { "nombre": "Carlos Ruiz", "instagram": "carlosruiz_comedy", "score": 85 }
  ]
}
```

**Errores:**

| Codigo | Condicion |
|--------|-----------|
| 400    | host_id o open_mic_id ausentes |
| 404    | open_mic sin config.info.dia_semana o config.info.hora |
| 409    | proximo show ya ha empezado |
| 500    | error en BD o scoring |

---

### 4.2 `GET /api/validate-view/lineup?token=<uuid>`

Devuelve el contexto de la vista standalone.

**Auth:** ninguna (el token es la autenticacion)

**Logica:**
```
1. SELECT * FROM silver.validation_tokens WHERE token = :token
2. Si no existe → 404
3. Si expires_at <= now() → 410
4. SELECT candidates FROM gold.lineup_candidates
      WHERE open_mic_id = token.open_mic_id AND fecha_evento = token.fecha_evento
      ORDER BY score DESC
5. SELECT COUNT(*) FROM silver.lineup_slots
      WHERE open_mic_id = X AND fecha_evento = Y AND status = 'confirmed'
      → is_validated = count > 0
```

**Response 200:**
```json
{
  "open_mic_id": "<uuid>",
  "fecha_evento": "2026-03-09",
  "show_datetime": "2026-03-09T21:00:00",
  "is_validated": false,
  "candidates": [
    { "solicitud_id": "<uuid>", "nombre": "Carlos Ruiz", "instagram": "carlosruiz", "score": 85 }
  ]
}
```

**Errores:** 404 (token no existe), 410 (token expirado)

---

### 4.3 `POST /api/validate-view/validate`

Valida el lineup desde la vista standalone.

**Auth:** ninguna (token en body)

**Request:**
```json
{
  "token": "<uuid>",
  "solicitud_ids": ["<uuid1>", "<uuid2>"]
}
```

**Logica:**
```
1. Validar token (misma logica que 4.2 pasos 1-3)
2. Llamar RPC gold.validate_lineup(p_selection, p_event_date)
3. Llamar RPC silver.upsert_confirmed_lineup(open_mic_id, fecha_evento, solicitud_ids)
4. Marcar token como usado: DELETE FROM silver.validation_tokens WHERE token = :token
```

**Response 200:**
```json
{ "status": "validated", "slots_created": 5 }
```

**Errores:** 400 (solicitud_ids vacio), 404/410 (token), 500 (error RPC)

---

## 5. Frontend — ruta `/validate`

### 5.1 Ruta nueva en main.jsx

```jsx
// Añadir al Router:
<Route path="/validate" element={<ValidateView />} />
```

### 5.2 Componente `ValidateView.jsx`

`frontend/src/components/ValidateView.jsx`

**Comportamiento:**
```
1. Leer token de URLSearchParams
2. Si no hay token → mostrar "Link invalido"
3. GET /api/validate-view/lineup?token=xxx
      → Loading spinner mientras carga
      → Error si 404 (link invalido) o 410 (link expirado)
4. Mostrar:
      - Nombre del open mic (del open_mic_id? o incluirlo en la respuesta)
      - Fecha del show
      - Lista de candidatos con nombre + instagram + score (misma UI que App.jsx)
      - Si is_validated: sello VALIDADO (igual que en App.jsx), sin boton
      - Si no: todos los candidatos seleccionados por defecto, boton "Validar Lineup"
5. Al pulsar Validar:
      - POST /api/validate-view/validate { token, solicitud_ids }
      - Mostrar sello VALIDADO
```

**Restricciones UI:**
- Sin navbar, sin boton de volver, sin acceso a otras vistas
- Mismo sistema de estilos papel (paper-drop / tape / rough)
- Responsive (se abre en movil desde Telegram)

---

## 6. n8n — Scoring & Draft (reconstruccion completa)

### 6.1 Flujo nuevo

```
Schedule Trigger (configurable — propuesta: diario a las 10:00)
      ↓
HTTP GET supabase: todos los hosts de silver.telegram_users
      ↓
SplitInBatches (un item por host)
      ↓
HTTP GET /mcp/open-mics?host_id={{ $json.host_id }}
      ↓
SplitInBatches (un item por open_mic)
      ↓
HTTP POST /api/lineup/prepare-validation { host_id, open_mic_id }
      ├─ 409 (no hay show proximo) → SKIP (no enviar nada)
      └─ 200 → Code node: formatear mensaje Telegram
                     ↓
               Telegram: enviar mensaje a telegram_user_id
```

### 6.2 Mensaje Telegram

```
Lineup para tu proximo show ({{ fecha_evento }}):

1. Carlos Ruiz @carlosruiz_comedy
2. Ana Lopez @analopez_stand
3. ...

Valida aqui antes de que empiece el show:
{{ validate_url }}
```

### 6.3 Cambios respecto al workflow original

| Antes | Despues |
|-------|---------|
| `chatId` hardcodeado `4088898` | `telegram_user_id` de `silver.telegram_users` |
| Un solo host | Itera todos los hosts registrados |
| Scoring generico sin open_mic_id | `prepare-validation` por open_mic |
| Mensaje estatico sin lineup | Lineup en texto + link de validacion |
| Sin check de fecha/hora show | `prepare-validation` devuelve 409 si no hay show proximo |

---

## 7. n8n — Test BOT (nueva tool)

Cuando el host pide el lineup al bot, el agente debe:
1. Llamar `Tool_Lineup_Link` con el `open_mic_id` del open mic que el host especifique
2. Responder con el lineup en texto + link de validacion

### 7.1 Nuevo tool `Tool_Lineup_Link`

```
Type: toolHttpRequest
Method: POST
URL: http://46.225.120.243:5000/api/lineup/prepare-validation
Headers: X-API-KEY
Body params:
  - host_id    (inyectado por el agente desde el system prompt)
  - open_mic_id (preguntado al host si tiene varios)
```

### 7.2 Actualizacion system prompt del AI Agent

Anadir al system prompt:

```
Cuando el host pida el lineup o quiera validarlo, usa la herramienta Tool_Lineup_Link
con su host_id y el open_mic_id del show. Responde con la lista de comicos y el link
de validacion que devuelva la herramienta. No inventes datos del lineup.
```

---

## 8. Tests requeridos

Archivo: `backend/tests/test_validate_lineup_view.py`

| Test | Cubre |
|------|-------|
| `test_prepare_validation_happy_path` | 200 + token + lineup + validate_url |
| `test_prepare_validation_no_upcoming_show` | show ya empezo → 409 |
| `test_prepare_validation_missing_config` | open_mic sin dia_semana/hora → 404 |
| `test_prepare_validation_requires_api_key` | → 401 |
| `test_lineup_view_happy_path` | GET lineup con token valido → 200 |
| `test_lineup_view_token_not_found` | → 404 |
| `test_lineup_view_token_expired` | → 410 |
| `test_validate_view_happy_path` | POST validate → 200, RPCs llamados |
| `test_validate_view_invalid_token` | → 404 |
| `test_validate_view_empty_solicitud_ids` | → 400 |

---

## 9. Migracion SQL

Ejecutar en Supabase antes de desplegar:
`specs/sql/migrations/20260306_validation_tokens.sql`

---

## 10. Variables de entorno

```
# backend/.env (ya existen)
WEBHOOK_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...

# nueva
FRONTEND_URL=https://recova-project-z5zp.vercel.app
```

---

## 11. Calculo de proximo evento (Python)

```python
from datetime import datetime, timedelta, timezone

DIA_SEMANA_MAP = {
    "Lunes": 0, "Martes": 1, "Miercoles": 2, "Miércoles": 2,
    "Jueves": 3, "Viernes": 4, "Sabado": 5, "Sábado": 5, "Domingo": 6,
}
# Python weekday(): 0=Lunes ... 6=Domingo

def next_event_datetime(dia_semana: str, hora: str, now: datetime = None) -> datetime:
    """
    Devuelve el datetime del proximo show (futuro) dado el dia de la semana y hora.
    dia_semana: "Lunes", "Martes", etc.
    hora: "HH:MM" en 24h
    """
    if now is None:
        now = datetime.now(timezone.utc)
    target_weekday = DIA_SEMANA_MAP[dia_semana]
    h, m = map(int, hora.split(":"))
    days_ahead = (target_weekday - now.weekday() + 7) % 7
    candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
    candidate += timedelta(days=days_ahead)
    if candidate <= now:
        candidate += timedelta(weeks=1)
    return candidate
```

> Esta funcion devuelve siempre una fecha futura. Si el show de hoy ya empezo,
> devuelve el de la semana siguiente. El endpoint devuelve 409 si
> `candidate <= now` antes del ajuste (show en curso), pero la funcion ya
> maneja el caso: si el resultado final esta en el futuro, hay show proximo.
> El endpoint debe comprobar: si `days_ahead == 0` y `candidate_sin_ajuste <= now`
> → el show de esta semana ya empezo → 409.
