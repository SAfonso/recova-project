# SDD — Ingesta Multi-tenant via Apps Script
**Sprint 6 — v0.11.0**

---

## Problema

El workflow `Ingesta-Solicitudes` no es multi-tenant:
- El trigger de n8n escucha **una sola Google Sheet** hardcodeada
- El `proveedor_id` está hardcodeado al proveedor de prueba
- El `open_mic_id` se intenta leer de `$json['open_mic_id']` pero ese campo no existe en las respuestas del form → llega `null` a la DB → el pipeline v3 de `bronze_to_silver_ingestion.py` no puede enlazar la solicitud con su open mic

## Solución

Invertir el origen del evento: en lugar de que n8n escuche el Sheet, **Google Forms envía directamente al backend** via Apps Script `onFormSubmit`. El Apps Script sabe a qué `open_mic_id` pertenece porque se configura en el momento de crear el form.

El workflow n8n `Ingesta-Solicitudes` se simplifica para hacer solo **clasificación de género** (job periódico global, sin cambios de lógica).

---

## Arquitectura nueva

```
Google Form (usuario rellena)
        ↓ onFormSubmit (Apps Script)
POST /api/form-submission  (backend Flask)
        ↓
INSERT bronze.solicitudes  (con open_mic_id + proveedor_id correctos)
        ↓
Llama internamente a bronze_to_silver_ingestion.py
        ↓
silver.solicitudes actualizado

n8n Ingesta-Solicitudes (schedule periódico)
        ↓
GET silver.comicos WHERE genero=unknown
        ↓
Gemini clasifica género
        ↓
PATCH silver.comicos
```

---

## Cambios

### 1. `backend/src/core/google_form_builder.py`

Después de crear el Form+Sheet, desplegar un **Apps Script** con:
- Trigger `onFormSubmit`
- Script Property `OPEN_MIC_ID` con el UUID del open mic
- Script Property `BACKEND_URL` con la URL del endpoint

**Apps Script template** (se genera como string en Python y se sube vía Google Apps Script API):

```javascript
function onFormSubmit(e) {
  var props = PropertiesService.getScriptProperties();
  var backendUrl = props.getProperty('BACKEND_URL');
  var openMicId  = props.getProperty('OPEN_MIC_ID');

  var itemResponses = e.response.getItemResponses();
  var payload = { open_mic_id: openMicId };

  itemResponses.forEach(function(r) {
    payload[r.getItem().getTitle()] = r.getResponse();
  });

  UrlFetchApp.fetch(backendUrl, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
}
```

**Método nuevo en `GoogleFormBuilder`:**

```python
def deploy_submit_webhook(self, form_id: str, open_mic_id: str) -> None:
    """Crea un Apps Script bound al form con trigger onFormSubmit."""
    # 1. Crear proyecto en Apps Script API (scope: https://www.googleapis.com/auth/script.projects)
    # 2. Subir el código del script
    # 3. Crear trigger onFormSubmit
    # 4. Setear Script Properties: BACKEND_URL, OPEN_MIC_ID
```

**Nota de scope OAuth2:** Añadir `https://www.googleapis.com/auth/script.projects` a la lista de scopes en `google_oauth_setup.py`.

---

### 2. Nuevo endpoint `POST /api/form-submission`

```
POST /api/form-submission
Sin API key (el secreto es la URL; opcionalmente añadir token por open_mic en futuro)
Content-Type: application/json
```

**Payload esperado** (campo names según los títulos del form en español):
```json
{
  "open_mic_id": "uuid-del-open-mic",
  "¿Nombre?": "Juan García",
  "¿Instagram?": "@juangarcia",
  "Whatsapp": "612345678",
  "¿Has actuado alguna vez?": "Sí, varias veces",
  "Fecha": "2026-03-15",
  "Si nos falla alguien en ultimo momento ¿Te podemos llamar?": "Sí",
  "¿Tienes algun Show cercano o algo?": "",
  "¿Por donde nos conociste?": "Instagram"
}
```

**Lógica del endpoint:**

```python
@app.route("/api/form-submission", methods=["POST"])
def form_submission():
    data = request.get_json(force=True)
    open_mic_id = data.get("open_mic_id")
    if not open_mic_id:
        return jsonify({"error": "open_mic_id required"}), 400

    # 1. Lookup proveedor_id desde silver.open_mics
    resp = supabase_get(f"/rest/v1/open_mics?id=eq.{open_mic_id}&select=proveedor_id",
                        schema="silver")
    if not resp or not resp[0].get("proveedor_id"):
        return jsonify({"error": "open_mic not found"}), 404
    proveedor_id = resp[0]["proveedor_id"]

    # 2. INSERT en bronze.solicitudes
    supabase_post("/rest/v1/solicitudes", schema="bronze", body={
        "proveedor_id":                    proveedor_id,
        "open_mic_id":                     open_mic_id,
        "nombre_raw":                      data.get("¿Nombre?"),
        "instagram_raw":                   data.get("¿Instagram?"),
        "telefono_raw":                    data.get("Whatsapp"),
        "experiencia_raw":                 data.get("¿Has actuado alguna vez?"),
        "fechas_seleccionadas_raw":        data.get("Fecha"),
        "disponibilidad_ultimo_minuto":    data.get("Si nos falla alguien en ultimo momento ¿Te podemos llamar?"),
        "info_show_cercano":               data.get("¿Tienes algun Show cercano o algo?"),
        "origen_conocimiento":             data.get("¿Por donde nos conociste?"),
    })

    # 3. Trigger bronze → silver (mismo script que /ingest)
    subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])

    return jsonify({"status": "ok"}), 200
```

**Helpers internos** (reusar o extraer de código existente):
- `supabase_get(path, schema)` — GET con headers apikey + Accept-Profile
- `supabase_post(path, schema, body)` — POST con headers apikey + Content-Profile

---

### 3. `workflows/n8n/Ingesta-Solicitudes.json`

**Eliminar:**
- Nodo `Google Sheets Trigger` (hardcodeado a una sheet)
- Nodo `Create a row` (insert bronze con proveedor_id hardcodeado)
- Nodo `HTTP Request` (llamada a `/ingest`)
- Conexiones entre ellos

**Mantener sin cambios:**
- `HTTP Request1` → GET `silver.comicos` WHERE `genero=eq.unknown`
- `Edit Fields` → extrae id, nombre, instagram
- `Aggregate` → agrupa para llamada batch a Gemini
- `Basic LLM Chain` + `Google Gemini Chat Model` → clasifica género
- `Code in JavaScript` → parsea respuesta
- `HTTP Request2` → PATCH `silver.comicos` con género

**Cambiar trigger a Schedule** (diario a las 11:00 o similar):
```json
{
  "type": "n8n-nodes-base.scheduleTrigger",
  "parameters": {
    "rule": { "interval": [{ "field": "hours", "hoursInterval": 24 }] }
  }
}
```

El workflow queda como un **clasificador de género autónomo** que corre diariamente y no tiene ningún acoplamiento con el flujo de ingesta.

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `backend/src/core/google_form_builder.py` | Añadir `deploy_submit_webhook()` |
| `backend/scripts/google_oauth_setup.py` | Añadir scope `script.projects` |
| `backend/src/triggers/webhook_listener.py` | Nuevo endpoint `POST /api/form-submission` |
| `workflows/n8n/Ingesta-Solicitudes.json` | Simplificar: solo clasificador de género con schedule trigger |

---

## Orden de implementación

1. **Endpoint backend** `POST /api/form-submission` + tests
2. **Workflow n8n** simplificado (clasificador de género con schedule)
3. **Apps Script** en `google_form_builder.py` + nuevo scope OAuth2
4. **Re-autorizar OAuth2** en servidor con nuevo scope
5. **Probar** creando un open mic nuevo y enviando un formulario

---

## Tests

**`backend/tests/test_form_submission.py`:**
- `POST /api/form-submission` sin `open_mic_id` → 400
- `POST /api/form-submission` con `open_mic_id` inexistente → 404
- `POST /api/form-submission` válido → bronze insertado + subprocess lanzado → 200

---

## Notas

- Los open mics creados **antes de este sprint** no tendrán el Apps Script instalado. Para migrarlos: script one-off `scripts/migrate_form_webhooks.py` que itera `silver.open_mics` y llama a `deploy_submit_webhook` para cada uno con `config.form.form_id`.
- El campo `open_mic_id` en `$json['open_mic_id']` del workflow antiguo probablemente llegaba `null` a la DB → los registros legacy en bronze con `open_mic_id=null` se procesan por el pipeline legacy (sin constraint multi-tenant), lo cual es correcto como fallback.
