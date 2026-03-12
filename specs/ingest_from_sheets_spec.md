# SDD — POST /api/ingest-from-sheets
**Sprint 6 — v0.11.0**

---

## Objetivo

Endpoint protegido que lee todas las Google Sheets de los open mics activos,
ingesta las filas nuevas en bronze y lanza el pipeline bronze→silver.
Reemplaza la lectura de Sheets que hacía el workflow n8n hardcodeado.

---

## Cambios

| Archivo | Cambio |
|---------|--------|
| `backend/src/core/google_form_builder.py` | `_inject_open_mic_id_column` añade cabecera `n8n_procesado` en K1 |
| `backend/src/core/sheet_ingestor.py` | Nueva clase `SheetIngestor` |
| `backend/src/triggers/webhook_listener.py` | Nuevo endpoint `POST /api/ingest-from-sheets` |
| `workflows/n8n/Ingesta-Solicitudes.json` | Simplificado: Schedule → POST endpoint → clasificador género |

---

## Estructura de la Sheet

| Col | Header | Origen |
|-----|--------|--------|
| A | Marca temporal | Google Forms (automático) |
| B | Nombre artístico | Respuesta form |
| C | Instagram (sin @) | Respuesta form |
| D | WhatsApp | Respuesta form |
| E | ¿Cuántas veces has actuado en un open mic? | Respuesta form |
| F | ¿Qué fechas te vienen bien? | Respuesta form |
| G | ¿Estarías disponible si nos falla alguien de última hora? | Respuesta form |
| H | ¿Tienes algún show próximo que quieras mencionar? | Respuesta form |
| I | ¿Cómo nos conociste? | Respuesta form |
| J | open_mic_id | ARRAYFORMULA (inyectado por `_inject_open_mic_id_column`) |
| K | n8n_procesado | Vacío = pendiente; `"si"` = procesado por backend |

---

## `SheetIngestor` — `backend/src/core/sheet_ingestor.py`

### Constructor

```python
SheetIngestor()
```

Lee las mismas variables de entorno que `GoogleFormBuilder`:
`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REFRESH_TOKEN`.

Construye cliente Sheets API v4 con los mismos scopes OAuth.

### `get_pending_rows(sheet_id: str) -> list[dict]`

1. Lee el rango completo de la Sheet (`A:K`) via Sheets API v4.
2. La primera fila se interpreta como headers.
3. Devuelve solo las filas donde la columna `n8n_procesado` (K) está **vacía**
   y la columna `Marca temporal` (A) **no está vacía** (es una respuesta real).
4. Cada dict incluye `_row_number` (entero, 1-based, para poder hacer el PATCH posterior).

**Return type:**
```python
[
  {
    "_row_number": 2,
    "Marca temporal": "2026-03-06 10:30:00",
    "Nombre artístico": "Juan García",
    "Instagram (sin @)": "@juangarcia",
    "WhatsApp": "612345678",
    "¿Cuántas veces has actuado en un open mic?": "Sí, varias veces",
    "¿Qué fechas te vienen bien?": "2026-03-15",
    "¿Estarías disponible si nos falla alguien de última hora?": "Sí",
    "¿Tienes algún show próximo que quieras mencionar?": "",
    "¿Cómo nos conociste?": "Instagram",
    "open_mic_id": "uuid-del-open-mic",
    "n8n_procesado": ""
  },
  ...
]
```

### `mark_rows_processed(sheet_id: str, row_numbers: list[int]) -> None`

Escribe `"si"` en la columna K de cada fila indicada, usando
`spreadsheets.values.batchUpdate` con `valueInputOption: RAW`.

---

## Endpoint `POST /api/ingest-from-sheets`

```
POST /api/ingest-from-sheets
X-API-KEY: <WEBHOOK_API_KEY>
Content-Type: application/json  (body vacío permitido)
```

### Lógica

```
1. Auth check → 401 si falla
2. GET silver.open_mics WHERE config->'form'->>'sheet_id' IS NOT NULL
3. Para cada open mic:
   a. sheet_id   = open_mic.config["form"]["sheet_id"]
   b. proveedor_id = open_mic.proveedor_id
   c. open_mic_id  = open_mic.id
   d. pending = SheetIngestor().get_pending_rows(sheet_id)
   e. Para cada row en pending:
      INSERT bronze.solicitudes {
        proveedor_id, open_mic_id,
        nombre_raw:                   row["Nombre artístico"],
        instagram_raw:                row["Instagram (sin @)"],
        telefono_raw:                 row["WhatsApp"],
        experiencia_raw:              row["¿Cuántas veces has actuado en un open mic?"],
        fechas_seleccionadas_raw:     row["¿Qué fechas te vienen bien?"],
        disponibilidad_ultimo_minuto: row["¿Estarías disponible si nos falla alguien de última hora?"],
        info_show_cercano:            row["¿Tienes algún show próximo que quieras mencionar?"],
        origen_conocimiento:          row["¿Cómo nos conociste?"],
      }
   f. SheetIngestor().mark_rows_processed(sheet_id, [r["_row_number"] for r in pending])
4. subprocess.Popen([sys.executable, INGEST_SCRIPT_PATH])
5. Return 200 { "open_mics_processed": N, "rows_ingested": M }
```

### Respuesta 200

```json
{
  "status": "ok",
  "open_mics_processed": 3,
  "rows_ingested": 7
}
```

### Errores

| Código | Motivo |
|--------|--------|
| 401 | API key inválida o ausente |
| 500 | Error de Google API o Supabase (incluye mensaje) |

### Comportamiento si no hay open mics con Sheet

Devuelve 200 con `open_mics_processed: 0, rows_ingested: 0`. No es un error.

### Comportamiento si una Sheet falla

Continúa con las demás. El open mic fallido se registra en el log pero no interrumpe el proceso.
Devuelve 200 igualmente (ingesta parcial es mejor que fallo total).

---

## Cambio en `google_form_builder.py`

`_inject_open_mic_id_column` pasa a escribir también la cabecera `n8n_procesado` en K1:

```python
values = [
    ["open_mic_id", "n8n_procesado"],   # ← K1, L1... espera, J1 y K1
    [f'=ARRAYFORMULA(IF(B2:B<>"","{open_mic_id}",""))'],  # J2
    # K queda vacía (la rellena el backend)
]
```

Concretamente: el rango de escritura pasa de `J1` a `J1:K1` para las cabeceras.

---

## Workflow n8n actualizado

```
Schedule Trigger (09:00 diario)
  → POST /api/ingest-from-sheets  (X-API-KEY)
  → GET silver.comicos WHERE genero=unknown  (Supabase HTTP)
  → Edit Fields (id, nombre, instagram)
  → Aggregate
  → Basic LLM Chain + Google Gemini
  → Code (parse JSON)
  → PATCH silver.comicos (genero)
```

5 nodos activos + 2 sticky notes. Sin loops ni lógica compleja en n8n.

---

## Tests — `backend/tests/test_ingest_from_sheets.py`

### SheetIngestor

- `get_pending_rows` con sheet vacía → lista vacía
- `get_pending_rows` con filas procesadas (K="si") → excluidas
- `get_pending_rows` con filas pendientes (K vacía) → incluidas con `_row_number` correcto
- `get_pending_rows` ignora fila de cabecera
- `mark_rows_processed` llama a `batchUpdate` con los valores correctos

### Endpoint

- Sin API key → 401
- Sin open mics con Sheet → 200, `rows_ingested: 0`
- Happy path: 2 open mics, 3 filas → `rows_ingested: 3`, Popen llamado, mark_rows_processed llamado
- Si una Sheet falla → 200 con ingesta parcial (no 500)

---

## Variables de entorno necesarias (sin cambios)

```
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GOOGLE_OAUTH_REFRESH_TOKEN
SUPABASE_URL
SUPABASE_SERVICE_KEY
WEBHOOK_API_KEY
```
