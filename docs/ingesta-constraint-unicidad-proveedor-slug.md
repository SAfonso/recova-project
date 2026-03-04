# Fix de ingesta Bronze -> Silver: unicidad en solicitudes y slug de proveedor

## Contexto
La ingesta `bronze_to_silver_ingestion.py` inserta en `silver.solicitudes` con:

- `ON CONFLICT (comico_id, fecha_evento) DO NOTHING`

Además, el motor utiliza el proveedor por defecto con slug:

- `recova-om`

## Cambios aplicados

### 1) Restricción única persistente para `silver.solicitudes`
Se aseguró una restricción explícita sobre `(comico_id, fecha_evento)` para que el `ON CONFLICT` del script Python sea válido y evite duplicados de forma consistente.

- Se declara `CONSTRAINT uq_silver_solicitudes_comico_fecha UNIQUE (comico_id, fecha_evento)` en la creación de tabla.
- Se agrega un bloque idempotente `DO $$ ... $$` para crear/adoptar la constraint en instalaciones existentes.

### 2) Consistencia de slug de proveedor semilla
Se unificó el dato semilla para que el proveedor principal use el slug esperado por el código de ingesta.

- Cambio realizado: `recova-open` -> `recova-om` en `specs/sql/seed_data.sql`.

## Resultado esperado
- La inserción con `ON CONFLICT (comico_id, fecha_evento)` deja de fallar por ausencia de clave única/constraint compatible.
- El proveedor por defecto se resuelve correctamente por slug en los flujos que usan `recova-om`.
