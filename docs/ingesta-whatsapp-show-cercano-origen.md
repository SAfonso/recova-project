# Ingesta: mapeo WhatsApp + show cercano + origen de conocimiento

## Objetivo
Actualizar la ingesta atómica `bronze_to_silver_ingestion.py` para soportar:
- Mapeo de teléfono proveniente desde Google Sheets como `Whatsapp`.
- Limpieza determinística de `disponibilidad_ultimo_minuto`.
- Persistencia de `show_cercano` y `origen_conocimiento` tanto en Bronze como en Silver.

## Cambios implementados

### 1) Mapeo de teléfono
- Se agregan aliases CLI `--whatsapp` y `--Whatsapp` con destino común `telefono_raw`.
- El valor se guarda en `bronze.solicitudes.telefono_raw`.
- Durante normalización se valida a formato E.164 y se persiste en `silver.comicos.telefono`.

### 2) Disponibilidad último minuto
- Se normaliza el texto removiendo acentos y pasando a minúsculas.
- Regla de negocio aplicada:
  - Si contiene `si` en cualquier parte del string => `true`.
  - En cualquier otro caso => `false`.

### 3) Nuevos campos de contexto
- Nuevos argumentos:
  - `--show_cercano_raw`
  - `--conociste_raw`
- En Bronze se insertan como:
  - `info_show_cercano`
  - `origen_conocimiento`
- En Silver se insertan como:
  - `show_cercano`
  - `origen_conocimiento`

### 4) Consistencia SQL por esquema
- Se mantiene escritura explícita a `bronze.solicitudes` y `silver.solicitudes`.
- Se actualiza `specs/sql/silver_relacional.sql` para incluir de forma idempotente:
  - `show_cercano text`
  - `origen_conocimiento text`

## Impacto
- Mejora la trazabilidad del contexto comercial de cada solicitud.
- Evita pérdida del teléfono cuando la fuente n8n envía el campo como `Whatsapp`.
- Unifica la semántica de disponibilidad bajo una regla determinística simple.
