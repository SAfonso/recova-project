# Webhook Listener para disparar ingesta Bronze -> Silver

## Resumen
Se añadió un listener HTTP en Flask para que n8n pueda disparar el proceso de ingesta existente mediante una llamada `POST` a `/ingest`.

## Implementación
- Archivo nuevo: `backend/src/triggers/webhook_listener.py`.
- Endpoint: `POST /ingest`.
- Seguridad básica: validación de API Key en header `X-API-KEY` contra la variable de entorno `WEBHOOK_API_KEY`.
- Acción: ejecución de `python3 /root/AI_LineUp_Architect/backend/src/bronze_to_silver_ingestion.py` vía `subprocess.run`.
- Respuesta exitosa (`returncode == 0`): JSON con `status: success` y `output`.
- Respuesta de error (`returncode != 0`): HTTP 500 con `status: error` y detalle de `stderr`/`stdout`.

## Ejecución
```bash
python3 backend/src/triggers/webhook_listener.py
```

El servidor escucha en `0.0.0.0:5000`.
