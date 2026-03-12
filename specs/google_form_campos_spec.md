# Spec: Google Form por Open Mic — campos y pipeline de ingesta

**Afecta a:**
- Google Forms (configuración manual por el Host)
- `bronze.solicitudes` — nueva columna `open_mic_id`
- `backend/src/bronze_to_silver_ingestion.py` — propaga `open_mic_id`
- n8n workflow de lectura de Google Sheets

**Estado:** pendiente de implementación
**Versión:** v3.0

---

## 1. Modelo: un Google Form por open_mic

Cada open_mic tiene su propio Google Form → su propia Google Sheet.
El n8n workflow que lee esa Sheet conoce el `open_mic_id` correspondiente
(configurado en el nodo de n8n como variable) y lo incluye al insertar
en `bronze.solicitudes`.

```
Google Form (open_mic A)  →  Google Sheet A  →  n8n (open_mic_id = A)
Google Form (open_mic B)  →  Google Sheet B  →  n8n (open_mic_id = B)
                                                      ↓
                                              bronze.solicitudes
                                              (con open_mic_id)
                                                      ↓
                                           bronze_to_silver_ingestion
                                                      ↓
                                              silver.solicitudes
                                              (con open_mic_id)
```

---

## 2. Campos del Google Form

Nombres de pregunta exactos que debe tener cada Google Form.
Son los que la ingesta mapea desde la Google Sheet.

| # | Nombre de pregunta en Google Form                                   | Tipo GF          | Obligatorio | Mapea a (Bronze)                    |
|---|---------------------------------------------------------------------|------------------|-------------|-------------------------------------|
| 1 | `Nombre artístico`                                                  | Respuesta corta  | Sí          | `nombre_raw`                        |
| 2 | `Instagram (sin @)`                                                 | Respuesta corta  | Sí          | `instagram_raw`                     |
| 3 | `WhatsApp`                                                          | Respuesta corta  | Sí          | `telefono_raw`                      |
| 4 | `¿Cuántas veces has actuado en un open mic?`                        | Opción múltiple  | Sí          | `experiencia_raw`                   |
| 5 | `¿Qué fechas te vienen bien?`                                       | Casillas / corta | Sí          | `fechas_seleccionadas_raw`          |
| 6 | `¿Estarías disponible si nos falla alguien de última hora?`         | Opción múltiple  | Sí          | `disponibilidad_ultimo_minuto`      |
| 7 | `¿Tienes algún show próximo que quieras mencionar?`                 | Respuesta larga  | No          | `info_show_cercano`                 |
| 8 | `¿Cómo nos conociste?`                                              | Respuesta corta  | No          | `origen_conocimiento`               |

### Opciones del campo 4 — Experiencia

Estas opciones son las que la ingesta mapea a nivel numérico (0–3):

| Opción en el Form                          | Nivel |
|--------------------------------------------|-------|
| `Es mi primera vez`                        | 0     |
| `He probado alguna vez`                    | 1     |
| `Llevo tiempo haciendo stand-up`           | 2     |
| `Soy un profesional / tengo cachés`        | 3     |

### Opciones del campo 6 — Disponibilidad última hora

| Opción en el Form | Resultado |
|-------------------|-----------|
| `Sí`              | `true`    |
| `No`              | `false`   |

### Campo 5 — Fechas

Formato esperado en la Sheet: `DD-MM-YY`, separadas por comas si son varias.
Ejemplo: `14-03-26, 21-03-26`

---

## 3. Migración: añadir open_mic_id a bronze.solicitudes

```sql
-- specs/sql/migrations/YYYYMMDD_add_open_mic_id_to_bronze.sql
ALTER TABLE bronze.solicitudes
  ADD COLUMN IF NOT EXISTS open_mic_id uuid;

CREATE INDEX IF NOT EXISTS idx_bronze_solicitudes_open_mic_id
  ON bronze.solicitudes (open_mic_id)
  WHERE open_mic_id IS NOT NULL;
```

- Nullable: las filas legacy (pre-v3) quedan con `open_mic_id = NULL`
- La ingesta ignora filas sin `open_mic_id` para el nuevo pipeline

---

## 4. Cambios en el n8n workflow

El nodo que inserta en `bronze.solicitudes` debe incluir `open_mic_id`
como campo fijo (hardcodeado en el nodo, distinto para cada workflow).

```json
{
  "open_mic_id": "{{ $vars.OPEN_MIC_ID }}",
  "nombre_raw":  "{{ $json['Nombre artístico'] }}",
  "instagram_raw": "{{ $json['Instagram (sin @)'] }}",
  "telefono_raw":  "{{ $json['WhatsApp'] }}",
  "experiencia_raw": "{{ $json['¿Cuántas veces has actuado en un open mic?'] }}",
  "fechas_seleccionadas_raw": "{{ $json['¿Qué fechas te vienen bien?'] }}",
  "disponibilidad_ultimo_minuto": "{{ $json['¿Estarías disponible si nos falla alguien de última hora?'] }}",
  "info_show_cercano":  "{{ $json['¿Tienes algún show próximo que quieras mencionar?'] }}",
  "origen_conocimiento": "{{ $json['¿Cómo nos conociste?'] }}"
}
```

---

## 5. Cambios en bronze_to_silver_ingestion.py

### 5.1 BronzeRecord — añadir open_mic_id

```python
@dataclass(frozen=True)
class BronzeRecord:
    id: UUID
    proveedor_id: UUID
    open_mic_id: UUID | None   # ← NUEVO, nullable para compatibilidad legacy
    nombre_raw: str | None
    ...
```

### 5.2 fetch_pending_bronze_rows — leer open_mic_id

```sql
SELECT id, proveedor_id, open_mic_id, nombre_raw, ...
FROM bronze.solicitudes
WHERE procesado = false
  AND open_mic_id IS NOT NULL   -- solo procesar registros v3
```

> **Nota:** el filtro `open_mic_id IS NOT NULL` asegura que el nuevo pipeline
> solo procesa registros v3. Los legacy (open_mic_id = NULL) los sigue procesando
> el pipeline anterior sin modificar.

### 5.3 normalize_row — actualizar nombres de campos

```python
form_row = {
    "Nombre artístico":                                           bronze.nombre_raw,
    "Instagram (sin @)":                                          bronze.instagram_raw,
    "WhatsApp":                                                   bronze.telefono_raw,
    "¿Cuántas veces has actuado en un open mic?":                bronze.experiencia_raw,
    "¿Qué fechas te vienen bien?":                               bronze.fechas_seleccionadas_raw,
    "¿Estarías disponible si nos falla alguien de última hora?": bronze.disponibilidad_ultimo_minuto,
    "¿Tienes algún show próximo que quieras mencionar?":         bronze.info_show_cercano,
    "¿Cómo nos conociste?":                                      bronze.origen_conocimiento,
}
```

### 5.4 insert_silver_rows — incluir open_mic_id

```sql
INSERT INTO silver.solicitudes (
    bronze_id, proveedor_id, open_mic_id,   -- ← open_mic_id añadido
    comico_id, fecha_evento, nivel_experiencia,
    disponibilidad_ultimo_minuto, show_cercano, origen_conocimiento, status
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'normalizado')
ON CONFLICT (comico_id, open_mic_id, fecha_evento) DO NOTHING  -- ← constraint v3
```

---

## 6. Compatibilidad con pipeline legacy

Las filas Bronze con `open_mic_id = NULL` se procesan con el pipeline anterior
(sin cambios en el código legacy). Conviven en la misma tabla.

El nuevo pipeline (`open_mic_id IS NOT NULL`) corre en paralelo desde el mismo
script, diferenciado por el filtro de la query.

---

## 7. Criterios de aceptación

- [ ] `bronze.solicitudes.open_mic_id` existe (migración aplicada)
- [ ] n8n inserta `open_mic_id` al leer cada Google Sheet
- [ ] La ingesta lee `open_mic_id` de Bronze y lo escribe en Silver
- [ ] `ON CONFLICT (comico_id, open_mic_id, fecha_evento)` respetado
- [ ] Filas legacy (open_mic_id NULL) no se rompen
- [ ] Los nombres de campos del Form coinciden exactamente con los de la ingesta
