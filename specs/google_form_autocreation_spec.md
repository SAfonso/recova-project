# Spec: Auto-creación de Google Form al crear un Open Mic

**Afecta a:**
- `backend/src/triggers/webhook_listener.py` — nuevo endpoint `POST /api/open-mic/create-form`
- `backend/src/core/google_form_builder.py` — módulo nuevo, lógica de creación de Form + Sheet
- `frontend/src/components/OpenMicDetail.jsx` — botón "Crear Form" y display de link
- `silver.open_mics.config` — almacena `form_url` y `sheet_id`
- `workflows/n8n/Ingesta-Solicitudes.json` — Sheet ID viene del config del open mic

**Estado:** pendiente de implementación
**Versión:** v1.0

---

## 1. Contexto

Al crear un open mic, el host necesita un Google Form para recoger solicitudes de cómicos.
Actualmente el form se crea manualmente y el `open_mic_id` se añade a mano en la Sheet.

Este spec define la auto-creación del Form vía Google Forms API usando una **service account**
compartida del sistema. El host no necesita vincular su cuenta de Google.

---

## 2. Arquitectura

```
Frontend (OpenMicDetail)
    → POST /api/open-mic/create-form  { open_mic_id }
        → google_form_builder.py
            → Google Forms API  →  crea Form con campos estándar
            → Google Sheets API →  añade columna open_mic_id (ARRAYFORMULA)
            → Google Drive API  →  comparte Sheet con host (opcional)
        → PATCH silver.open_mics SET config.form = { form_url, sheet_id }
    ← { form_url, sheet_id }

Frontend: muestra link del Form en InfoCard
n8n Ingesta: lee sheet_id desde config del open mic (no hardcodeado)
```

---

## 3. Configuración Google Cloud

### 3.1 Service Account

1. Google Cloud Console → IAM → Service Accounts → Crear cuenta
2. Nombre: `recova-form-builder`
3. Descargar JSON de credenciales → guardar en servidor como `GOOGLE_SA_CREDENTIALS_PATH`
4. APIs a habilitar en el proyecto GCP:
   - Google Forms API
   - Google Sheets API
   - Google Drive API

### 3.2 Variables de entorno (backend `.env`)

```
GOOGLE_SA_CREDENTIALS_PATH=/path/to/service-account.json
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
class GoogleFormBuilder:
    def __init__(self, credentials_path: str): ...

    def create_form_for_open_mic(
        self,
        open_mic_id: str,
        nombre: str,
    ) -> dict:
        """
        Crea un Google Form con los campos estándar.
        Vincula la Sheet de respuestas.
        Añade ARRAYFORMULA de open_mic_id en columna I de la Sheet.
        Devuelve { form_url, sheet_id, form_id }.
        """
```

### 5.1 Flujo interno

1. `forms.create()` — crea form con título `f"Solicitudes — {nombre}"`
2. `forms.batchUpdate()` — añade los 8 campos del §4
3. Leer `linkedSheetId` de la respuesta (Google Forms auto-crea la Sheet)
4. `sheets.spreadsheets.values.update()` — escribe cabecera `open_mic_id` en celda `I1`
5. `sheets.spreadsheets.values.update()` — escribe ARRAYFORMULA en `I2`:
   ```
   =ARRAYFORMULA(IF(B2:B<>"","<open_mic_id>",""))
   ```
6. Devolver `{ form_url, sheet_id, form_id }`

---

## 6. Endpoint `POST /api/open-mic/create-form`

**Archivo:** `backend/src/triggers/webhook_listener.py`

```
POST /api/open-mic/create-form
Headers: X-API-KEY: <WEBHOOK_API_KEY>
Body: { "open_mic_id": "<uuid>", "nombre": "<nombre del open mic>" }
```

**Respuesta OK:**
```json
{
  "status": "success",
  "form_url": "https://docs.google.com/forms/d/...",
  "sheet_id": "...",
  "form_id": "..."
}
```

**Errores:**
- `401` — API key inválida
- `400` — `open_mic_id` o `nombre` ausentes
- `409` — el open mic ya tiene form creado (`config.form` no está vacío)
- `500` — error en Google API

**Tras éxito:** el endpoint hace PATCH en `silver.open_mics` vía Supabase service role:
```json
config.form = {
  "form_url": "...",
  "sheet_id": "...",
  "form_id": "..."
}
```

---

## 7. Frontend — OpenMicDetail

### 7.1 InfoCard

Añade sección condicional tras los InfoRows existentes:

```
Si config.form existe:
  → InfoRow "Google Form" → link clickable a form_url
  → InfoRow "Respuestas"  → link a Sheet (https://docs.google.com/spreadsheets/d/{sheet_id})

Si config.form NO existe:
  → Botón "Crear Google Form" → llama al endpoint
  → Estado: 'idle' | 'creating' | 'error'
```

### 7.2 Llamada al endpoint

El frontend llama directamente al backend (`VITE_BACKEND_URL`):

```js
POST ${VITE_BACKEND_URL}/api/open-mic/create-form
Headers: { 'X-API-KEY': VITE_WEBHOOK_API_KEY }
Body: { open_mic_id, nombre: openMic.nombre }
```

Tras respuesta OK: recarga el open mic (`fetchOpenMic()`) para mostrar el link.

---

## 8. n8n — Ingesta Sheet dinámica

El workflow `Ingesta-Solicitudes.json` necesita saber el `sheet_id` del open mic activo.

**Opción adoptada:** el trigger de Google Sheets usa el `sheet_id` almacenado en
`silver.open_mics.config.form.sheet_id`. El nodo trigger se configura con el Sheet ID
del open mic correspondiente.

> Por ahora el workflow sigue siendo uno por open mic en n8n (distintos triggers apuntando
> a distintas Sheets), pero el Sheet ID ya no es hardcodeado en el workflow — se obtiene
> de la BD al configurar el trigger.

---

## 9. Criterios de aceptación

- [ ] Service account configurada en Google Cloud con Forms + Sheets + Drive APIs
- [ ] `GOOGLE_SA_CREDENTIALS_PATH` en `.env` del backend
- [ ] `google_form_builder.py` crea Form con los 8 campos del contrato
- [ ] La Sheet tiene columna `open_mic_id` con ARRAYFORMULA auto-rellenada
- [ ] Endpoint `POST /api/open-mic/create-form` devuelve `form_url` y `sheet_id`
- [ ] `silver.open_mics.config.form` se actualiza tras la creación
- [ ] InfoCard muestra link al Form y a la Sheet si `config.form` existe
- [ ] Si el form ya existe, el botón no aparece (sin duplicados)
- [ ] Error `409` si se intenta crear form para un open mic que ya lo tiene
