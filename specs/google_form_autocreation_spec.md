# Spec: Auto-creación de Google Form al crear un Open Mic

**Afecta a:**
- `backend/src/triggers/webhook_listener.py` — endpoint `POST /api/open-mic/create-form`
- `backend/src/core/google_form_builder.py` — lógica de creación de Form + Sheet
- `frontend/src/components/OpenMicSelector.jsx` — auto-crea form al insertar open mic
- `frontend/src/components/OpenMicDetail.jsx` — botón manual fallback + display de links
- `silver.open_mics.config` — almacena `form_url`, `sheet_url`, `form_id`, `sheet_id`
- `workflows/n8n/Ingesta-Solicitudes.json` — Sheet ID viene del config del open mic

**Estado:** implementado (v1.1)
**Versión:** v1.1 — migración a OAuth2, Sheet propia

---

## 1. Contexto

Al crear un open mic, el host necesita un Google Form para recoger solicitudes de cómicos.
El form se crea automáticamente al crear el open mic, sin intervención manual del host.

### Limitaciones descubiertas en implementación (v1.0 → v1.1)

| Problema | Causa | Solución adoptada |
|----------|-------|-------------------|
| `forms().create()` devuelve HTTP 500 con service account | Bug conocido de Google Forms API | Migración a OAuth2 con refresh token |
| `drive.files().create()` devuelve 403 storage quota exceeded | Las service accounts tienen `quota: 0` en Drive | OAuth2 usa la cuenta real del host |
| `linkedSheetId` nunca se genera vía API | Forms API solo crea el linked sheet desde la UI | Sheet propia creada con Sheets API |

---

## 2. Arquitectura

```
OpenMicSelector (frontend)
    → INSERT silver.open_mics
    → POST /api/open-mic/create-form  (fire-and-forget, no bloquea UI)
        → GoogleFormBuilder (OAuth2)
            → Forms API   → forms().create()      → form_id
            → Forms API   → forms().batchUpdate() → añade 8 preguntas
            → Forms API   → forms().get()         → intentar leer linkedSheetId
            → Sheets API  → spreadsheets().create() → sheet propia (si no hay linkedSheetId)
            → Sheets API  → values().update()     → cabeceras en A1
            → Sheets API  → values().update()     → open_mic_id + ARRAYFORMULA en J1-J2
        → PATCH silver.open_mics SET config.form = { form_id, form_url, sheet_id, sheet_url }
    ← { status, form_url, sheet_url, form_id, sheet_id }

OpenMicDetail: muestra links o botón manual de creación (fallback)
n8n Ingesta: lee sheet_id desde config.form del open mic
```

---

## 3. Configuración Google Cloud

### 3.1 OAuth2 (cuenta del host)

1. Google Cloud Console → APIs y servicios → Credenciales → Crear ID de cliente OAuth 2.0
2. Tipo: **Aplicación de escritorio**
3. Descargar JSON de credenciales
4. Ejecutar script de autorización (una sola vez):
   ```bash
   python backend/scripts/google_oauth_setup.py --client-secrets /ruta/client_secret.json
   ```
5. Copiar los valores impresos al `.env`

### 3.2 APIs a habilitar en Google Cloud Console

- Google Forms API
- Google Sheets API
- Google Drive API

### 3.3 Variables de entorno (`backend/.env`)

```
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REFRESH_TOKEN=...
```

---

## 4. Campos del Google Form (contrato con ingesta)

Idénticos a `google_form_campos_spec.md §2`. El builder los crea en este orden:

| # | Título de pregunta                                                  | Tipo GF         | Obligatorio |
|---|---------------------------------------------------------------------|-----------------|-------------|
| 1 | `Nombre artístico`                                                  | SHORT_ANSWER    | Sí          |
| 2 | `Instagram (sin @)`                                                 | SHORT_ANSWER    | Sí          |
| 3 | `WhatsApp`                                                          | SHORT_ANSWER    | Sí          |
| 4 | `¿Cuántas veces has actuado en un open mic?`                        | RADIO           | Sí          |
| 5 | `¿Qué fechas te vienen bien?`                                       | SHORT_ANSWER    | Sí          |
| 6 | `¿Estarías disponible si nos falla alguien de última hora?`         | RADIO           | Sí          |
| 7 | `¿Tienes algún show próximo que quieras mencionar?`                 | PARAGRAPH       | No          |
| 8 | `¿Cómo nos conociste?`                                              | SHORT_ANSWER    | No          |

Opciones campo 4: `Es mi primera vez`, `He probado alguna vez`, `Llevo tiempo haciendo stand-up`, `Soy un profesional / tengo cachés`
Opciones campo 6: `Sí`, `No`

---

## 5. Módulo `backend/src/core/google_form_builder.py`

```python
@dataclass
class FormCreationResult:
    form_id: str
    form_url: str
    sheet_id: str
    sheet_url: str

class GoogleFormBuilder:
    def __init__(self) -> None:
        """Lee GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN del entorno.
        Refresca el access token. Construye clientes Forms, Sheets y Drive."""

    def create_form_for_open_mic(self, open_mic_id: str, nombre: str) -> FormCreationResult:
        """Flujo completo: crea form, añade preguntas, obtiene/crea sheet,
        inyecta columna open_mic_id. Devuelve FormCreationResult."""
```

### 5.1 Flujo interno

1. `_create_form(nombre)` — `forms().create()` con título `"Solicitudes — {nombre}"` → `form_id`
2. `_add_questions(form_id)` — `forms().batchUpdate()` con los 8 campos del §4
3. `_get_linked_sheet_id(form_id, nombre)`:
   - Intenta leer `linkedSheetId` del form (`forms().get()`)
   - Si no existe → `sheets.spreadsheets().create()` con título `"Respuestas — {nombre}"` y hoja `"Respuestas"` → escribe cabeceras (9 cols A-I) en `A1`
4. `_inject_open_mic_id_column(sheet_id, open_mic_id)`:
   - Lee el nombre de la primera hoja
   - Escribe en col J: cabecera `open_mic_id` en `J1` y ARRAYFORMULA en `J2`:
     ```
     =ARRAYFORMULA(IF(B2:B<>"","<open_mic_id>",""))
     ```
5. Construye URLs y devuelve `FormCreationResult`

### 5.2 Cabeceras de la Sheet (cols A-I)

```
A: Marca temporal
B: Nombre artístico
C: Instagram (sin @)
D: WhatsApp
E: ¿Cuántas veces has actuado en un open mic?
F: ¿Qué fechas te vienen bien?
G: ¿Estarías disponible si nos falla alguien de última hora?
H: ¿Tienes algún show próximo que quieras mencionar?
I: ¿Cómo nos conociste?
J: open_mic_id  (ARRAYFORMULA — col J)
```

> **Nota:** ARRAYFORMULA usa col B (`Nombre artístico`) como señal de fila no vacía.

---

## 6. Endpoint `POST /api/open-mic/create-form`

**Archivo:** `backend/src/triggers/webhook_listener.py`

```
POST /api/open-mic/create-form
Headers: X-API-KEY: <WEBHOOK_API_KEY>
         Content-Type: application/json
Body: { "open_mic_id": "<uuid>", "nombre": "<nombre del open mic>" }
```

**Respuesta OK (200):**
```json
{
  "status": "success",
  "form_id": "...",
  "form_url": "https://docs.google.com/forms/d/.../viewform",
  "sheet_id": "...",
  "sheet_url": "https://docs.google.com/spreadsheets/d/..."
}
```

**Errores:**
- `401` — API key inválida o ausente
- `400` — `open_mic_id` o `nombre` ausentes
- `409` — el open mic ya tiene `config.form` (no se sobreescribe)
- `500` — error en Google API o Supabase

**Tras éxito:** PATCH en `silver.open_mics` vía Supabase service role:
```json
config.form = {
  "form_id": "...",
  "form_url": "...",
  "sheet_id": "...",
  "sheet_url": "..."
}
```

---

## 7. Frontend

### 7.1 OpenMicSelector — auto-creación (fire-and-forget)

Al insertar el open mic, llama al endpoint sin await ni bloqueo de UI:
```js
fetch(`${VITE_BACKEND_URL}/api/open-mic/create-form`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-KEY': VITE_WEBHOOK_API_KEY },
  body: JSON.stringify({ open_mic_id: newMic.id, nombre: newMic.nombre }),
}).catch(() => {}); // silencioso si falla
```

### 7.2 OpenMicDetail — fallback manual

```
Si config.form existe:
  → Link "Abrir formulario →"   → form_url
  → Link "Ver respuestas (Sheet) →" → sheet_url

Si config.form NO existe:
  → Botón "Crear Google Form" → llama al endpoint
  → Estados: idle | creando... | error
```

Tras respuesta OK: `fetchOpenMic()` para refrescar y mostrar los links.

---

## 8. n8n — Ingesta Sheet dinámica

El workflow `Ingesta-Solicitudes.json` lee el `sheet_id` de `silver.open_mics.config.form.sheet_id`.
El trigger de Google Sheets se configura con ese ID (no hardcodeado en el workflow).

---

## 9. Criterios de aceptación

- [x] OAuth2 configurado con `GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN`
- [x] `GoogleFormBuilder` crea Form con los 8 campos del contrato
- [x] Sheet propia creada con cabeceras A-I cuando no hay `linkedSheetId`
- [x] Columna `open_mic_id` con ARRAYFORMULA en col J
- [x] Endpoint `POST /api/open-mic/create-form` devuelve `form_url`, `sheet_url`, `form_id`, `sheet_id`
- [x] `silver.open_mics.config.form` se actualiza tras la creación
- [x] Auto-creación en segundo plano al crear open mic desde `OpenMicSelector`
- [x] Botón manual en `OpenMicDetail` como fallback
- [x] Error `409` si se intenta crear form para un open mic que ya lo tiene
- [x] CORS habilitado en Flask para llamadas desde el navegador
- [ ] Tests unitarios de `GoogleFormBuilder` con mocks de Google APIs
