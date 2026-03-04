# Ingesta atómica Bronze -> Silver para n8n

## Resumen
Se refactorizó `backend/src/bronze_to_silver_ingestion.py` para operar en modo **un registro por ejecución** (evento `On row added` de n8n), reemplazando la lectura batch de pendientes.

## Cambios clave
- Se incorpora `argparse` para recibir payload raw por CLI:
  - `--nombre_raw`
  - `--instagram_raw`
  - `--telefono_raw`
  - `--experiencia_raw`
  - `--fechas_raw`
  - `--disponibilidad_uv`
  - `--proveedor_id` (default: `recova-om`)
- El flujo ahora inserta primero en `bronze.solicitudes` y recupera el `id` generado.
- Luego ejecuta normalización/upsert en `silver.comicos` e inserción en `silver.solicitudes`.
- Se mantiene `SAVEPOINT` para rollback parcial: si falla Silver, Bronze se marca como procesado con `raw_data_extra.estado = error_ingesta` y `error_log`.
- Salida JSON para integración con n8n:
  - éxito: `{"status": "success", "bronze_id": "...", "fechas_creadas": X}`
  - error: `{"status": "error", "message": "..."}` + `exit(1)`

## Notas operativas
- `--proveedor_id` acepta UUID o slug (`silver.proveedores.slug`).
- Si el proveedor no existe, el script falla con salida JSON de error.
- Se preserva la expiración de reservas antiguas (`no_seleccionado` > 60 días) en cada ejecución.
