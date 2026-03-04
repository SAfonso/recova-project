# Refactor de Manejo de Errores Bronze -> Silver

## Objetivo
Evitar que la capa Silver reciba registros de error de ingesta, manteniendo Silver exclusivamente con datos válidos para el motor de scoring y dejando la trazabilidad de fallos en Bronze.

## Cambios aplicados

### 1) Eliminación de errores en Silver
- Se eliminó la función `mark_bronze_as_error` del script de ingesta.
- Ya no existe ninguna ruta que inserte `status = error_ingesta` en `public.solicitudes_silver`.

### 2) Trazabilidad de errores en Bronze
- En `process_pending_bronze`, cuando una fila falla:
  - Se realiza `ROLLBACK TO SAVEPOINT`.
  - Se marca `procesado = true` en `public.solicitudes_bronze`.
  - Se actualiza `raw_data_extra` con la clave `error_log` y estructura:
    - `message`: mensaje de la excepción.
    - `timestamp`: timestamp UTC en formato ISO8601.
    - `phase`: fase funcional donde ocurrió el error.

### 3) Fases de error registradas
- `normalizacion`
- `parsing_fechas`
- `mapeo_experiencia`
- `upsert_comico`
- `insert_silver`

### 4) Robustez en normalización
- `map_experience_level` ahora usa fallback por defecto (`0`) mediante `.get(...)`.
- Si el valor no coincide con el catálogo esperado, se emite `warning` y continúa el procesamiento.

### 5) Robustez en parsing de fechas
- `parse_event_dates` ignora tokens con formato inválido (`DD-MM-YY`) y registra `warning`.
- El procesamiento de la fila continúa siempre que exista al menos una fecha válida futura.

### 6) Consistencia de estado Silver
- Las inserciones exitosas en `solicitudes_silver` mantienen `status = 'normalizado'`.
- Se añadió comentario en código indicando que este estado es previo al motor de scoring.

## Resultado esperado
- Silver queda limpia y lista para scoring.
- Bronze concentra toda la auditoría de errores de ingesta.
- El pipeline es más tolerante a ruido de entrada sin perder trazabilidad.
