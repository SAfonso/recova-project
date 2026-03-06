# Spec: Telegram QR Self-Registration (v0.9.0)

**Módulo:** `backend/src/triggers/webhook_listener.py` + `frontend/src/components/OpenMicSelector.jsx`
**Estado:** implementado
**Sprint:** 4a

---

## 1. Contexto

Los hosts deben poder vincular su cuenta de Telegram sin intervención manual en la base de datos.
El flujo existente (Sprint 3) requería un INSERT manual en `silver.telegram_users`.
Esta feature añade un flujo de self-registration mediante código temporal y QR.

Las tablas `silver.telegram_registration_codes` y `silver.telegram_users` ya existen
(migración `specs/sql/migrations/20260305_telegram_users.sql`).

---

## 2. Flujo completo

```
1. Host abre OpenMicSelector
2. Ve el icono de Telegram con tooltip "¡Click Me!" (solo la primera vez)
3. Hace clic en el icono
4. Frontend llama POST /api/telegram/generate-code con su host_id
5. Backend genera código RCV-XXXX, inserta en silver.telegram_registration_codes
6. Backend devuelve { code, qr_url }
7. Frontend muestra modal con QR y código
8. Host escanea el QR con el móvil → Telegram abre el bot con /start RCV-XXXX
9. Host pulsa Enviar (un tap)
10. n8n recibe /start RCV-XXXX:
    → valida código (no expirado, no usado)
    → INSERT INTO silver.telegram_users (telegram_user_id, host_id)
    → marca el código como used = true
11. Bot responde: "Cuenta conectada."
```

---

## 3. Endpoint backend

### `POST /api/telegram/generate-code`

**Auth:** `X-API-KEY` (misma cabecera que todos los endpoints internos).

**Request body:**
```json
{ "host_id": "<uuid>" }
```

**Response 200:**
```json
{ "code": "RCV-A3X9", "qr_url": "https://t.me/<BOT_USERNAME>?start=RCV-A3X9" }
```

**Errores:**

| Código | Condición |
|--------|-----------|
| 401    | `X-API-KEY` ausente o incorrecta |
| 400    | `host_id` ausente o vacío |
| 500    | Error al insertar en la BD |

**Formato del código:**
- Prefijo fijo: `RCV-`
- Sufijo: 4 caracteres aleatorios `[A-Z0-9]` (mayúsculas y dígitos)
- Ejemplos: `RCV-A3X9`, `RCV-Z0QW`

**Side-effect en BD:**
```sql
INSERT INTO silver.telegram_registration_codes (code, host_id)
VALUES ('RCV-XXXX', '<host_id>');
-- expires_at se genera por DEFAULT (now() + interval '15 minutes')
-- used se genera por DEFAULT (false)
```

**Variable de entorno requerida:**
```
TELEGRAM_BOT_USERNAME=nombre_del_bot  # sin @
```

---

## 4. Frontend — `OpenMicSelector`

### 4.1 Botón de Telegram

- Icono circular azul Telegram (`#229ED9`), `h-11 w-11`, fuera del `paper-drop` card.
- Posición: entre el card de open mics y el botón de "Cerrar sesión".

### 4.2 Tooltip "¡Click Me!"

- Visible solo si `localStorage.getItem('tg_btn_seen')` es `null`.
- Se elimina al hacer clic (se escribe `tg_btn_seen = '1'` en localStorage).
- Diseño: burbuja azul con flecha hacia el botón, animación `animate-bounce`.

### 4.3 Modal

Se abre al hacer clic en el botón. Contiene:

| Elemento | Detalle |
|----------|---------|
| Título | "Conecta el bot" |
| QR code | `<QRCodeSVG value={qr_url} size={160} level="M" />` vía `qrcode.react` |
| Código | `RCV-XXXX` en `font-mono`, dentro de un recuadro con borde dashed |
| Instrucciones | 3 pasos: escanea → Enviar → bot confirma |
| Nota | "El código expira en 15 minutos" |
| Botón cerrar | Cierra el modal |

- El QR solo se genera una vez por sesión (el estado `tgData` persiste mientras el componente esté montado).
- Mientras espera la respuesta del backend: mensaje "Generando...".
- Si el backend falla: mensaje de error visible.

---

## 5. Variables de entorno

```
# backend/.env
TELEGRAM_BOT_USERNAME=nombre_del_bot_sin_arroba

# frontend/.env (ya existen)
VITE_BACKEND_URL=...
VITE_WEBHOOK_API_KEY=...
```

---

## 6. Tests requeridos

Archivo: `backend/tests/test_telegram_generate_code.py`

| Test | Cubre |
|------|-------|
| `test_generate_code_returns_code_and_qr_url` | Happy path: 200 + campos correctos |
| `test_generate_code_format` | Código cumple `RCV-[A-Z0-9]{4}` |
| `test_generate_code_inserts_into_db` | Side-effect: INSERT llamado con code y host_id |
| `test_generate_code_requires_api_key` | Sin X-API-KEY → 401 |
| `test_generate_code_requires_host_id` | Body sin host_id → 400 |

---

## 7. Restricciones

- El endpoint NO valida que `host_id` exista en `silver.organization_members`. La validación de existencia queda en manos de la FK de la tabla de códigos (o en n8n al procesar el `/start`).
- El frontend no verifica si el host ya está registrado en `silver.telegram_users` — la pantalla de QR es siempre accesible. Si ya estaba registrado, n8n manejará el duplicado.
- `used` y `expires_at` son gestionados exclusivamente por n8n al procesar el `/start`.
