# Ingesta Batch Bronze -> Silver desde cola en DB

## Contexto
Se refactoriza la ingesta para alinearla con la arquitectura event-driven actual: n8n inserta datos crudos directamente en `bronze.solicitudes` y el script Python deja de recibir payload por CLI.

## Cambios principales
- Se respalda el flujo anterior CLI en `backend/src/old/ingestion_cli_backup.py`.
- `backend/src/bronze_to_silver_ingestion.py` ahora ejecuta procesamiento batch:
  - Lee filas con `procesado = false`.
  - Normaliza `instagram`, `telefono`, fechas y `disponibilidad_ultimo_minuto` (`sí/no` -> `True/False`).
  - Inserta/relaciona datos en `silver.comicos` y `silver.solicitudes`.
  - Mapea `bronze.info_show_cercano` -> `silver.show_cercano` y `bronze.origen_conocimiento` -> `silver.origen_conocimiento`.
  - Marca en Bronze `procesado = true` cuando la fila termina correctamente.
- Si ocurre error por fila:
  - Hace rollback a savepoint de esa fila.
  - Registra `estado=error_ingesta` y `error_log` en `metadata` (o `raw_data_extra` como fallback).
  - Continúa con el resto de solicitudes pendientes.

## Resultado operativo
El script queda listo para ejecución periódica (cron/job runner) como worker de cola Bronze sin dependencia de argumentos de entrada.
