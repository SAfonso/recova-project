# Spec: Telegram Self-Registration — Procesamiento /start RCV-XXXX (v0.9.1)

**Modulo:** `backend/src/triggers/webhook_listener.py` + workflow n8n `telegram-lineup-agent`
**Estado:** pendiente de implementacion
**Sprint:** 4b

---

## 1. Contexto

El Sprint 4a añadio el flujo de generacion de QR en el frontend y el endpoint
`POST /api/telegram/generate-code`. Sin embargo, el paso final — procesar el
mensaje `/start RCV-XXXX` que envia Telegram cuando el host escanea el QR — no
estaba implementado.

Este spec cierra el loop: cuando el bot recibe `/start RCV-XXXX`, valida el
codigo, registra al host en `silver.telegram_users` y confirma al usuario.

Las tablas ya existen (migracion `specs/sql/migrations/20260305_telegram_users.sql`).

---

## 2. Flujo completo

```
1. Host escanea el QR con el movil
2. Telegram abre el bot con "/start RCV-XXXX" (deep link)
3. Host pulsa Enviar (un tap)
4. n8n recibe el mensaje via Telegram Trigger
5. Switch node: el texto empieza con "/start RCV-"? → Si
6. n8n llama POST /api/telegram/register
      { "telegram_user_id": 123456789, "code": "RCV-XXXX" }
7. Backend ejecuta la logica de validacion (ver seccion 3)
8. n8n envia al host el mensaje correspondiente al resultado
```

---

## 3. Endpoint backend

### `POST /api/telegram/register`

**Auth:** `X-API-KEY` (misma cabecera que todos los endpoints internos).

**Request body:**
```json
{ "telegram_user_id": 123456789, "code": "RCV-A3X9" }
```

**Response 200 — registro nuevo:**
```json
{ "host_id": "<uuid>", "already_registered": false }
```

**Response 200 — ya estaba registrado:**
```json
{ "host_id": "<uuid>", "already_registered": true }
```

**Errores:**

| Codigo | Condicion |
|--------|-----------|
| 401    | `X-API-KEY` ausente o incorrecta |
| 400    | `telegram_user_id` o `code` ausentes |
| 404    | Codigo no encontrado en la BD |
| 409    | Codigo ya usado (`used = true`) y el usuario NO estaba registrado |
| 410    | Codigo expirado (`expires_at <= now()`) y el usuario NO estaba registrado |
| 500    | Error al escribir en la BD |

**Logica (orden estricto):**

```
1. SELECT code, host_id, expires_at, used
   FROM silver.telegram_registration_codes WHERE code = :code
   → no existe: 404

2. SELECT 1 FROM silver.telegram_users WHERE telegram_user_id = :telegram_user_id
   → existe:
       si codigo no usado: UPDATE telegram_registration_codes SET used = true
       → 200 { host_id, already_registered: true }

3. codigo.used = true  → 409
4. codigo.expires_at <= now()  → 410

5. INSERT INTO silver.telegram_users (telegram_user_id, host_id)
   ON CONFLICT (telegram_user_id) DO NOTHING

6. UPDATE silver.telegram_registration_codes SET used = true WHERE code = :code

7. 200 { host_id, already_registered: false }
```

> El paso 2 garantiza que un host que ya registro su cuenta nunca recibe un
> error, aunque el codigo este expirado o ya usado. Reutilizar el QR es seguro.

---

## 4. Cambios en n8n — workflow `telegram-lineup-agent`

### 4.1 Nuevo Switch node (al inicio del workflow)

Insertar un nodo **Switch** inmediatamente despues del **Telegram Trigger**,
antes del nodo de validacion de host existente.

| Condicion | Valor |
|-----------|-------|
| `{{ $json.message.text }}` starts with | `/start RCV-` |

- **Output 0 (registro):** mensajes de registro → branch nuevo
- **Output 1 (agente):** resto de mensajes → flow existente sin cambios

### 4.2 Branch de registro (nodos nuevos)

```
Switch (output 0)
    ↓
HTTP Request — POST /api/telegram/register
    ├─ URL: {{ $env.RECOVA_BACKEND_URL }}/api/telegram/register
    ├─ Method: POST
    ├─ Headers: X-API-KEY: {{ $env.RECOVA_API_KEY }}
    ├─ Body (JSON):
    │    telegram_user_id: {{ $json.message.from.id }}
    │    code: {{ $json.message.text.split(' ')[1] }}
    └─ On error: continuar (capturar 4xx/5xx como datos)
    ↓
IF — registro exitoso?
    ├─ Condicion: {{ $json.statusCode === undefined || $json.statusCode === 200 }}
    ├─ TRUE
    │    └─ IF — already_registered?
    │         ├─ TRUE  → Telegram: "Tu cuenta ya estaba conectada."
    │         └─ FALSE → Telegram: "Cuenta conectada. Ya puedes gestionar tu lineup desde aqui."
    └─ FALSE → Switch por codigo de error
                  404 → "Codigo no encontrado."
                  409 → "Este codigo ya fue usado."
                  410 → "El codigo ha expirado. Genera uno nuevo desde la app."
                  otro → "Error inesperado. Intentalo de nuevo."
```

### 4.3 Mensajes de respuesta

| Caso | Texto |
|------|-------|
| Registro nuevo | `Cuenta conectada. Ya puedes gestionar tu lineup desde aqui.` |
| Ya registrado | `Tu cuenta ya estaba conectada.` |
| 404 | `Codigo no encontrado.` |
| 409 | `Este codigo ya fue usado.` |
| 410 | `El codigo ha expirado. Genera uno nuevo desde la app.` |
| otro | `Error inesperado. Intentalo de nuevo.` |

> Sin emojis ni tildes para evitar problemas de encoding en el bot.

---

## 5. Tests requeridos

Archivo: `backend/tests/test_telegram_register.py`

| Test | Cubre |
|------|-------|
| `test_register_happy_path` | 200 + `already_registered: false`; INSERT y UPDATE llamados |
| `test_register_already_registered_code_unused` | usuario ya en telegram_users + codigo no usado → 200 `already_registered: true` + UPDATE used |
| `test_register_already_registered_code_used` | usuario ya en telegram_users + codigo usado → 200 `already_registered: true` sin UPDATE |
| `test_register_already_registered_code_expired` | usuario ya en telegram_users + codigo expirado → 200 `already_registered: true` |
| `test_register_code_not_found` | codigo ausente en BD → 404 |
| `test_register_code_already_used` | codigo usado + usuario NO registrado → 409 |
| `test_register_code_expired` | codigo expirado + usuario NO registrado → 410 |
| `test_register_requires_api_key` | sin X-API-KEY → 401 |
| `test_register_missing_telegram_user_id` | body sin telegram_user_id → 400 |
| `test_register_missing_code` | body sin code → 400 |

---

## 6. Variables de entorno

```
# backend/.env (ya existen todas)
WEBHOOK_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...

# n8n (ya existen como credenciales/env)
RECOVA_BACKEND_URL=https://api.machango.org
RECOVA_API_KEY=...
```

---

## 7. Restricciones

- El endpoint no valida que `telegram_user_id` sea un entero valido de Telegram;
  confia en que n8n pasa el valor correcto desde `$json.message.from.id`.
- Si el host ya estaba registrado, el codigo se marca como `used = true`
  (si no lo estaba) para evitar reuso posterior por otra persona.
- No se implementa notificacion al frontend; el host vera el efecto la proxima
  vez que interactue con el bot.
