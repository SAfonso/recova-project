# SDD — Forms Batch Ingest (Sprint 11, v0.16.0)

---

## Objetivo

Conectar `FormIngestor` al pipeline n8n. Actualmente las respuestas de Google Forms
solo se ingestad vía webhook en tiempo real (`/api/form-submission`).
Este endpoint permite que n8n lance una ingesta batch diaria de todas las respuestas
nuevas de todos los open mics que usan Google Forms.

---

## Cambios

| Archivo | Cambio |
|---------|--------|
| `backend/src/triggers/webhook_listener.py` | Nuevo endpoint `POST /api/ingest-from-forms` |
| `backend/tests/test_ingest_from_forms.py` | Tests TDD (7 tests) |

---

## Endpoint: `POST /api/ingest-from-forms`

### Auth
`X-API-KEY` header requerido (mismo patrón que el resto de endpoints internos).

### Lógica

1. Lee todos los `silver.open_mics` con `config.external_form_id` y `config.field_mapping` no vacíos.
2. Si no hay ninguno, devuelve `{"status": "ok", "open_mics_processed": 0, "rows_ingested": 0}`.
3. Instancia `FormIngestor()` una sola vez (OAuth refresh es costoso).
4. Por cada open mic:
   a. Lee `config.last_form_ingestion_at` (default `"1970-01-01T00:00:00Z"`).
   b. Llama `ingestor.get_responses(form_id, field_mapping)`.
   c. Filtra respuestas con `_submitted_at > last_form_ingestion_at`.
   d. Inserta cada respuesta nueva en `bronze.solicitudes` mapeando campos canónicos.
   e. Actualiza `config.last_form_ingestion_at` al mayor `_submitted_at` del batch
      via RPC `update_open_mic_config_keys`.
   f. Si `get_responses` lanza excepción: continúa con el siguiente open mic.
5. Lanza `bronze_to_silver_ingestion.py` en background (igual que los otros endpoints).
6. Devuelve `{"status": "ok", "open_mics_processed": N, "rows_ingested": M}`.

### Deduplicación

Se usa `config.last_form_ingestion_at` (ISO 8601 UTC) como cursor.
Solo se insertan respuestas con `_submitted_at` estrictamente mayor.
Tras cada batch exitoso se actualiza el cursor al máximo `_submitted_at` procesado.
La comparación es léxica sobre strings ISO 8601 (válida para UTC sin offset variable).

### Mapeo canónico → bronze.solicitudes

| Campo canónico (`field_mapping` valor) | Columna bronze |
|----------------------------------------|----------------|
| `nombre_artistico` | `nombre_raw` |
| `instagram` | `instagram_raw` |
| `whatsapp` | `telefono_raw` |
| `experiencia` | `experiencia_raw` |
| `fechas_disponibles` | `fechas_seleccionadas_raw` |
| `backup` | `disponibilidad_ultimo_minuto` |
| `show_proximo` | `info_show_cercano` |
| `como_nos_conociste` | `origen_conocimiento` |

Los campos `metadata_extra` del `FormIngestor` no se persisten en bronze
(la tabla no tiene columna JSONB libre). El scoring custom ya accede a `metadata`
en silver vía el webhook en tiempo real (`/api/form-submission`).

### Respuesta 200 (happy path)

```json
{
  "status": "ok",
  "open_mics_processed": 2,
  "rows_ingested": 5
}
```

### Respuesta 500 (FormIngestor sin credenciales)

```json
{ "error": "Faltan variables de entorno: ..." }
```

---

## Tests TDD

| Test | Descripción |
|------|-------------|
| `test_ingest_from_forms_requires_api_key` | 401 sin X-API-KEY |
| `test_ingest_from_forms_skips_open_mics_without_form` | 200, 0 si ningún open mic tiene `external_form_id` |
| `test_ingest_from_forms_happy_path` | 200, N filas insertadas, Popen lanzado |
| `test_ingest_from_forms_maps_canonical_fields_to_bronze` | Cada campo canónico llega al campo `_raw` correcto |
| `test_ingest_from_forms_deduplication_skips_old_responses` | Filtra respuestas con `_submitted_at <= last_form_ingestion_at` |
| `test_ingest_from_forms_updates_last_ingestion_timestamp` | Llama RPC con el mayor `_submitted_at` del batch |
| `test_ingest_from_forms_continues_on_form_error` | Si `get_responses` falla en un open mic, sigue con los demás |
