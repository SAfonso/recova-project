# Sistema de logs y auditoría en ingesta Bronze -> Silver

## Objetivo
Fortalecer la trazabilidad del proceso `backend/src/bronze_to_silver_ingestion.py` para que cada descarte de fila quede auditado en:
- Archivo físico rotativo: `/root/RECOVA/backend/logs/ingestion.log`.
- Respuesta JSON final del pipeline mediante la clave `errores`.

## Cambios implementados

### 1) Configuración de logging con rotación diaria
- Se crea automáticamente el directorio absoluto `/root/RECOVA/backend/logs` con `os.makedirs(..., exist_ok=True)`.
- Se utiliza `TimedRotatingFileHandler` con:
  - `when="midnight"`
  - `interval=1`
  - `backupCount=7`
- Formato aplicado: `%(asctime)s - %(levelname)s - %(message)s`.
- Archivo de salida: `/root/RECOVA/backend/logs/ingestion.log`.

### 2) Auditoría de descartes por fila
- Se añadió la lista `detalles_descarte` al inicio de `run_pipeline`.
- En cada descarte se agrega un objeto con estructura:
  - `{"id": "<uuid>", "motivo": "<causa>"}`
- Casos cubiertos:
  - Sin fechas futuras válidas.
  - Duplicado en Silver (sin nuevas filas insertadas).
  - Error de validación/procesamiento por fase.
- Cada descarte se registra también en log con `INFO` o `WARNING`.

### 3) Respuesta JSON con errores
- `run_pipeline` ahora retorna un diccionario y también lo imprime como JSON.
- Se incorpora la clave `errores` con formato legible:
  - `ID <uuid>: <motivo>`
- En error fatal del pipeline se responde con:
  - `status: error`
  - `errores: ["Error fatal: ..."]`
- Los errores fatales se registran con `LOGGER.exception(...)` para incluir stack trace completo.

## Impacto operativo
- PM2/n8n ahora pueden inspeccionar en la salida JSON los motivos de descarte sin abrir la base de datos.
- Se conserva histórico local de 7 días para diagnóstico rápido de incidencias.
