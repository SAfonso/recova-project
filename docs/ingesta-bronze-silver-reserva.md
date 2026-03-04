# Ingesta Bronze -> Silver con Explosión de Fechas y Reserva (60 días)

## Objetivo
Implementar el flujo de normalización para mover solicitudes de `solicitudes_bronze` a `solicitudes_silver`, con enfoque idempotente y seguro para reintentos.

## Componentes entregados

### 1) Migración SQL de estado
Se agrega una migración dedicada para extender el enum `tipo_solicitud_status`:

- `no_seleccionado`
- `expirado`

Archivo: `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql`

### 2) Ajustes en modelo Silver
Se actualizó la especificación relacional para soportar explosión de fechas:

- `bronze_id` deja de ser `unique` por fila (una fila Bronze puede generar varias fechas en Silver).
- Se agrega unicidad por `(bronze_id, fecha_evento)` para idempotencia por origen y fecha.
- Se agrega unicidad por `(comico_id, fecha_evento)` para anti-spam y evitar duplicados de mismo cómico/día.
- Se añaden estados `no_seleccionado` y `expirado` al enum base.

### 3) Script de ingesta Python
Archivo: `backend/src/bronze_to_silver_ingestion.py`

Flujo implementado:

1. **Expiración de reservas**
   - Antes de procesar Bronze, actualiza `solicitudes_silver` con:
     - `status = 'expirado'`
     - `fecha_evento <= today() - 60 días`
   - Nuevo estado: `expirado`.

2. **Lectura de pendientes Bronze**
   - Solo filas con `procesado = false`.

3. **Normalización de identidad**
   - Instagram: trim + lowercase + remover `@`.
   - Teléfono: validación E.164 (`+` y prefijo internacional).

4. **Upsert de identidad en Bronze**
   - Inserta/actualiza en `comicos_master_bronze`.
   - Si existe, actualiza teléfono cuando llega uno válido.

5. **Sincronización Bronze -> Silver**
   - Upsert de `comicos_master` (Silver) desde `comicos_master_bronze`.
   - Mantiene `categoria` e identidad alineadas por `instagram_user`.

6. **Explosión de fechas**
   - Split por coma en `fechas_seleccionadas_raw`.
   - Parse `DD-MM-YY`.
   - Filtra fechas pasadas.

7. **Inserción en Silver (idempotente)**
   - Inserta una fila por fecha válida.
   - `ON CONFLICT (comico_id, fecha_evento) DO NOTHING`.
   - Marca Bronze como `procesado = true`.

8. **Transaccionalidad y reintentos**
   - Transacción global (`autocommit = false`).
   - `SAVEPOINT` por fila Bronze.
   - Ante error de una fila: rollback a savepoint, marcar Bronze procesado y registrar error en `raw_data_extra.error_log` con `message`, `timestamp` y `phase`.

## Ejecución
```bash
export DATABASE_URL='postgresql://...'
python backend/src/bronze_to_silver_ingestion.py
```

## Notas operativas
- El proceso es seguro para reintentos gracias a constraints + `ON CONFLICT`.
- El control de duplicados se hace por `comico_id + fecha_evento`.
- La lógica de reserva no altera solicitudes aprobadas/rechazadas, solo `no_seleccionado`.
