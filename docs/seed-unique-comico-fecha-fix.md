# Fix de seed para unicidad `comico_id + fecha_evento`

## Problema
`python setup_db.py --seed` fallaba con:

- `duplicate key value violates unique constraint "uq_solicitudes_silver_comico_fecha"`

El conflicto ocurría en `specs/sql/seed_data.sql` porque dos filas de `solicitudes_silver` usaban el mismo `comico_id` y la misma `fecha_evento`.

## Ajuste aplicado
Se movió una de las fechas del caso de Nora Priority:

- Bronze `id=30000000-...-0006`: `current_date + 5` -> `current_date + 6`
- Silver `id=40000000-...-0006`: `current_date + 5` -> `current_date + 6`

Con eso se conservan 18 filas seed y se respeta la restricción de unicidad.

## Resultado esperado
`setup_db.py --seed` deja de fallar por `uq_solicitudes_silver_comico_fecha`.
