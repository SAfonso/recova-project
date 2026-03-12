# SDD — Smart Form Ingestion (Sprint 9, v0.14.0)

---

## Objetivo

Eliminar la dependencia de un formulario con campos fijos y de sheets vinculados.
Cualquier Google Form del host funciona: Gemini mapea sus campos al schema canónico,
la ingesta lee respuestas directamente via Forms API (sin sheets ni Apps Script).

---

## Cambios

| Archivo | Cambio |
|---------|--------|
| `backend/src/core/form_ingestor.py` | Nueva clase `FormIngestor` — lee respuestas via Forms API |
| `backend/src/core/form_analyzer.py` | Nueva clase `FormAnalyzer` — Gemini mapea campos al schema canónico |
| `backend/src/triggers/webhook_listener.py` | Nuevo endpoint `POST /api/open-mic/analyze-form` |
| `specs/sql/migrations/20260307_smart_form_ingestion.sql` | Migración: `solicitudes.metadata`, `config.field_mapping/scoring_type` |
| `frontend/src/components/OpenMicDetail.jsx` | Campo "Google Form ID/URL" en tab Info |
| `frontend/src/components/ScoringTypeSelector.jsx` | Nuevo componente — selector `none / basic / custom` |
| `backend/scripts/google_oauth_setup.py` | Añadir scope `forms.responses.readonly` |

---

## Schema canónico

Los 8 campos que el pipeline silver entiende nativamente:

| Campo canónico | Mapea a (Bronze) | Descripción |
|----------------|------------------|-------------|
| `nombre_artistico` | `nombre_raw` | Nombre artístico del cómico |
| `instagram` | `instagram_raw` | Usuario Instagram sin @ |
| `whatsapp` | `telefono_raw` | Número de teléfono |
| `experiencia` | `experiencia_raw` | Nivel de experiencia (opción múltiple) |
| `fechas_disponibles` | `fechas_seleccionadas_raw` | Fechas disponibles |
| `backup` | `disponibilidad_ultimo_minuto` | Disponible de sustituto (sí/no) |
| `show_proximo` | `info_show_cercano` | Show próximo a mencionar |
| `como_nos_conociste` | `origen_conocimiento` | Canal de captación |

Cualquier campo del form que no encaje en ninguno de estos va a `solicitudes.metadata` JSONB.

---

## DB — Migración

### `silver.solicitudes` — columna `metadata`

```sql
-- specs/sql/migrations/20260307_smart_form_ingestion.sql

ALTER TABLE silver.solicitudes
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

COMMENT ON COLUMN silver.solicitudes.metadata IS
  'Campos del form que no tienen mapeo al schema canónico. Clave = título pregunta del form, valor = respuesta.';
```

### `silver.open_mics.config` — nuevas claves JSONB

No requiere ALTER TABLE (JSONB es schema-less). La migración documenta el contrato:

```sql
-- Documentación del contrato JSONB (no ejecutar, solo referencia):
-- config.scoring_type: 'none' | 'basic' | 'custom'   (default: 'basic')
-- config.field_mapping: { "Título pregunta form": "campo_canónico" | null }
--   null = campo no canónico → va a metadata
--   La clave 'field_mapping' solo existe tras llamar a /api/open-mic/analyze-form
-- config.external_form_id: string | null
--   Form externo del host (distinto del form auto-creado por GoogleFormBuilder)
```

---

## `FormIngestor` — `backend/src/core/form_ingestor.py`

### Scopes OAuth requeridos

```python
_SCOPES = [
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
]
```

> Nota: tras este sprint hay que regenerar el refresh token añadiendo estos scopes.
> `backend/scripts/google_oauth_setup.py` debe actualizarse con los nuevos scopes.

### Constructor

```python
FormIngestor()
```

Lee `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`.
Construye cliente Forms API v1.

### `get_form_questions(form_id: str) -> list[dict]`

Llama a `forms().get(formId=form_id)`.
Devuelve lista de preguntas con su `question_id` y `title`:

```python
[
  {"question_id": "1a2b3c", "title": "Nombre artístico", "kind": "textQuestion"},
  {"question_id": "4d5e6f", "title": "¿De dónde eres?", "kind": "textQuestion"},
  ...
]
```

- Solo items de tipo `questionItem` (ignora secciones, imágenes, etc.)
- `kind`: `"textQuestion"` o `"choiceQuestion"`

### `get_responses(form_id: str, field_mapping: dict[str, str | None]) -> list[dict]`

1. Llama a `forms().responses().list(formId=form_id)`.
2. Para cada `FormResponse`:
   - Construye índice `question_id → title` desde la misma llamada al form (o desde `get_form_questions`).
   - Para cada `answer` en `response.answers`:
     - Resuelve `question_id → title`.
     - Aplica `field_mapping[title]` para obtener `canonical_field`.
     - Si `canonical_field` no es `None` → añade al dict raíz: `{canonical_field: value}`.
     - Si `canonical_field` es `None` o no existe en el mapping → añade a `metadata_extra`: `{title: value}`.
   - Incluye `_response_id` y `_submitted_at` (ISO 8601 desde `createTime`).
3. Devuelve lista de dicts normalizados.

**Return type:**

```python
[
  {
    "_response_id": "ACYDBNj...",
    "_submitted_at": "2026-03-06T10:30:00Z",
    "nombre_artistico": "Juan García",
    "instagram": "juangarcia",
    "whatsapp": "612345678",
    "experiencia": "Llevo tiempo haciendo stand-up",
    "fechas_disponibles": "14-03-26, 21-03-26",
    "backup": "Sí",
    "show_proximo": "",
    "como_nos_conociste": "Instagram",
    "metadata_extra": {
      "¿De dónde eres?": "Madrid"
    }
  },
  ...
]
```

### Extracción de valor de respuesta

La Forms API devuelve respuestas en formato:

```json
{
  "textAnswers": { "answers": [{"value": "Juan García"}] }
}
```

Regla: tomar `answers[0].value`. Si `answers` está vacío → string vacío.
Para `choiceQuestion` con selección múltiple → unir con coma.

---

## `FormAnalyzer` — `backend/src/core/form_analyzer.py`

### Responsabilidad

Recibe la lista de títulos de preguntas de un form y usa Gemini para mapear
cada una a un campo canónico (o `null` si no tiene equivalente).

### Dependencias

- `google-genai>=1.0.0` (ya instalado, mismo SDK que `poster_detector_gemini.py`)
- `GEMINI_API_KEY` en `.env`

### `FormAnalyzer.analyze(form_questions: list[str]) -> dict[str, str | None]`

**Prompt a Gemini** (modelo: `gemini-2.5-flash`):

```
Tienes un formulario de solicitud para actuar en un open mic de comedia.
Las preguntas del formulario son:

{lista_preguntas_numerada}

El schema canónico tiene estos campos:
- nombre_artistico: nombre artístico o de escena
- instagram: usuario de Instagram (sin @)
- whatsapp: número de teléfono o WhatsApp
- experiencia: nivel de experiencia en stand-up o comedy
- fechas_disponibles: fechas o días disponibles para actuar
- backup: disponibilidad para cubrir a última hora / sustituto
- show_proximo: show próximo, espectáculo, actuación destacada
- como_nos_conociste: cómo conoció el open mic / canal de captación

Devuelve un JSON válido con este formato exacto:
{
  "field_mapping": {
    "<título exacto de la pregunta>": "<campo_canónico>" | null,
    ...
  }
}

Reglas:
- Usa el título exacto de la pregunta como clave.
- Si una pregunta encaja claramente en un campo canónico, usa ese campo.
- Si no encaja en ningún campo canónico, usa null.
- No inventes campos canónicos nuevos.
- Responde solo con el JSON, sin explicaciones.
```

**Return:**

```python
{
  "Nombre artístico": "nombre_artistico",
  "¿Cuál es tu Instagram?": "instagram",
  "WhatsApp o teléfono": "whatsapp",
  "¿Tienes experiencia en open mics?": "experiencia",
  "Fechas disponibles": "fechas_disponibles",
  "¿Puedes ser sustituto?": "backup",
  "¿Tienes show próximo?": "show_proximo",
  "¿Cómo nos conociste?": "como_nos_conociste",
  "¿De dónde eres?": null
}
```

- Strip de markdown fences antes de parsear (mismo patrón que `poster_detector_gemini.py`).
- Si Gemini devuelve JSON inválido → lanzar `ValueError` con el raw text.

---

## Endpoint `POST /api/open-mic/analyze-form`

### Request

```json
{
  "open_mic_id": "uuid-del-open-mic",
  "form_id": "1BxEfoo..."
}
```

Ambos campos obligatorios. Requiere `X-API-KEY`.

### Lógica

1. `FormIngestor().get_form_questions(form_id)` → lista de preguntas.
2. `FormAnalyzer().analyze([q["title"] for q in questions])` → `field_mapping`.
3. Actualizar `silver.open_mics.config` via Supabase:
   ```python
   # Merge en el JSONB existente (no sobreescribir otras claves de config)
   supabase.rpc("update_open_mic_config_keys", {
     "p_open_mic_id": open_mic_id,
     "p_keys": {"field_mapping": field_mapping, "external_form_id": form_id}
   })
   ```
   > Ver RPC `update_open_mic_config_keys` en migración SQL.
4. Calcular métricas de cobertura.
5. Devolver respuesta.

### Response `200`

```json
{
  "field_mapping": {
    "Nombre artístico": "nombre_artistico",
    "¿Cuál es tu Instagram?": "instagram",
    "¿De dónde eres?": null
  },
  "canonical_coverage": 7,
  "total_questions": 9,
  "unmapped_fields": ["¿De dónde eres?"]
}
```

### Response `400`

```json
{"status": "error", "message": "open_mic_id y form_id son obligatorios"}
```

### Response `422`

```json
{"status": "error", "message": "Gemini devolvió JSON inválido", "raw": "..."}
```

---

## RPC `update_open_mic_config_keys`

Necesaria para hacer merge de claves en el JSONB sin sobreescribir el resto de la config.

```sql
-- En la migración SQL

CREATE OR REPLACE FUNCTION silver.update_open_mic_config_keys(
    p_open_mic_id uuid,
    p_keys        jsonb
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
    UPDATE silver.open_mics
    SET config = config || p_keys
    WHERE id = p_open_mic_id;
$$;

GRANT EXECUTE ON FUNCTION silver.update_open_mic_config_keys TO authenticated, service_role;
```

---

## Frontend — `OpenMicDetail.jsx`

### Tab Info — campo "Google Form externo"

Añadir al formulario de info un campo nuevo debajo del campo de instagram:

```
Google Form URL (opcional)
[ https://docs.google.com/forms/d/1BxE... ]
[ Analizar campos ]
```

- Input tipo URL; acepta URL completa o solo el form_id.
- Extracción del `form_id` desde URL: regex `/forms\/d\/([a-zA-Z0-9_-]+)/`.
- Si el open mic ya tiene `config.form.form_id` (form auto-creado), pre-rellenar con esa URL.
- Si el host pega una URL de form externo, se sobreescribe `config.external_form_id`.
- Botón "Analizar campos":
  - Llama `POST /api/open-mic/analyze-form` con `{open_mic_id, form_id}`.
  - Muestra spinner mientras carga.
  - Tras respuesta OK: muestra resumen "7/9 campos mapeados" con lista de `unmapped_fields`.
  - Botón "Re-analizar formulario" visible si `config.field_mapping` ya existe.

### Estado de carga en Info tab

El análisis de form puede tardar 2-5s (Gemini). Usar estado local `analyzing: boolean`.

---

## Frontend — `ScoringTypeSelector.jsx`

Nuevo componente usado en el tab Config de `OpenMicDetail`.

```jsx
// Tres opciones con descripción breve
<ScoringTypeSelector
  value={scoringType}           // 'none' | 'basic' | 'custom'
  onChange={setScoringType}
/>
```

| Opción | Label | Descripción |
|--------|-------|-------------|
| `none` | Sin scoring | El host selecciona el lineup manualmente |
| `basic` | Scoring básico | Algoritmo estándar (experiencia + recencia + género) |
| `custom` | Scoring personalizado | Reglas basadas en los campos de tu formulario (Sprint 10) |

- `custom` se muestra como disabled si `config.field_mapping` no existe aún, con tooltip "Primero analiza tu formulario".
- Al cambiar el valor: hace PATCH a `silver.open_mics.config.scoring_type` via Supabase.
- Integrado en `ScoringConfigurator.jsx` como nueva sección encima de los parámetros existentes.

---

## Flujo de ingesta diaria actualizado

```
n8n Schedule 09:00
  → POST /api/ingest-from-sheets   (sigue funcionando para open mics con sheet)
  → POST /api/ingest-from-forms    (nuevo — para open mics con field_mapping)
      ↓
  FormIngestor.get_responses(form_id, field_mapping)
      ↓
  Inserta en bronze.solicitudes (con campos canónicos mapeados)
      ↓
  bronze_to_silver_ingestion (sin cambios)
      ↓
  Clasificador género Gemini (ya existente en n8n)
```

> Nota: `POST /api/ingest-from-forms` es el endpoint de ingesta diaria (similar a
> `POST /api/ingest-from-sheets`). Se especifica en detalle al implementar el endpoint
> en `webhook_listener.py`.

---

## Tests a escribir (TDD)

### `backend/tests/core/test_form_ingestor.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_get_form_questions_returns_list` | Devuelve lista de `{question_id, title, kind}` |
| 2 | `test_get_form_questions_ignores_non_question_items` | Secciones e imágenes ignoradas |
| 3 | `test_get_responses_maps_canonical_fields` | Campos canónicos en dict raíz |
| 4 | `test_get_responses_unmapped_to_metadata_extra` | Campos sin mapeo van a `metadata_extra` |
| 5 | `test_get_responses_empty_answer_is_empty_string` | Respuesta vacía → `""` |
| 6 | `test_get_responses_choice_question_single` | Opción única → string plano |
| 7 | `test_get_responses_includes_response_id_and_timestamp` | `_response_id` y `_submitted_at` presentes |
| 8 | `test_get_responses_empty_form` | Form sin respuestas → lista vacía |
| 9 | `test_constructor_raises_without_env_vars` | ValueError si faltan vars de entorno |

### `backend/tests/core/test_form_analyzer.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_analyze_maps_standard_fields` | Form estándar → mapping correcto |
| 2 | `test_analyze_returns_null_for_unrecognized_fields` | Campos desconocidos → `null` |
| 3 | `test_analyze_strips_markdown_fences` | Gemini devuelve ```json ... ``` → parsea OK |
| 4 | `test_analyze_raises_on_invalid_json` | JSON inválido → `ValueError` |
| 5 | `test_analyze_partial_mapping` | Form con 3 campos canónicos + 1 extra → mapeo parcial |

### `backend/tests/test_analyze_form_endpoint.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_analyze_form_returns_200_with_mapping` | Happy path |
| 2 | `test_analyze_form_saves_to_config` | `config.field_mapping` actualizado en DB |
| 3 | `test_analyze_form_missing_params_400` | Sin `form_id` → 400 |
| 4 | `test_analyze_form_unauthorized_401` | Sin API key → 401 |
| 5 | `test_analyze_form_gemini_invalid_422` | Gemini falla → 422 |
| 6 | `test_analyze_form_includes_coverage_metrics` | `canonical_coverage` y `unmapped_fields` en response |

Todos los tests usan mocks de `google.oauth2.credentials.Credentials`,
`googleapiclient.discovery.build` y `google.genai.Client` via `sys.modules`
(mismo patrón que `test_poster_detector_gemini.py`).

---

## Criterios de aceptación

- [ ] `FormIngestor.get_form_questions(form_id)` devuelve lista de preguntas con `question_id` y `title`
- [ ] `FormIngestor.get_responses(form_id, field_mapping)` mapea campos canónicos y mete el resto en `metadata_extra`
- [ ] `FormAnalyzer.analyze(questions)` llama a Gemini y devuelve mapping válido
- [ ] `POST /api/open-mic/analyze-form` guarda `field_mapping` en `config` del open mic
- [ ] `silver.solicitudes.metadata` existe y acepta JSONB
- [ ] `ScoringTypeSelector` permite elegir `none | basic | custom` y persiste en config
- [ ] Campo "Google Form URL" en tab Info; botón "Analizar campos" funciona end-to-end
- [ ] 19 tests verdes (9 FormIngestor + 5 FormAnalyzer + 6 endpoint) — todos mockeados
- [ ] Refresh token regenerado con scopes `forms.body.readonly` + `forms.responses.readonly`
