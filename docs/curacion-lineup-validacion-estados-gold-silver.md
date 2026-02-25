# Curación y Validación de Lineup: sincronización de estados Gold/Silver

## Alcance
Este documento consolida cambios de proceso introducidos entre `0.5.12` y `0.5.15`:
- robustez de validación/n8n desde frontend (`VITE_N8N_WEBHOOK_URL`)
- exposición de estado real en `gold.lineup_candidates`
- sincronización de estados al validar lineup (`gold.validate_lineup`)
- persistencia de scoring en estado `scorado` y `gold.comicos.score_actual`

Complementa `docs/scoring-batch-n8n-fix.md`, que cubre el batch de scoring en n8n.

## Objetivo del proceso
Garantizar un flujo consistente desde scoring hasta validación final del lineup:
1. Scoring persiste candidatos en Gold/Silver con estado `scorado`.
2. Frontend consume `gold.lineup_candidates` con estado real y score.
3. Host selecciona exactamente 5 cómicos.
4. RPC `gold.validate_lineup(...)` sincroniza estados en Gold y Silver.
5. Frontend notifica a n8n para continuar con generación de póster.

## Estados operativos (actuales)

### En Gold (`gold.solicitudes.estado`)
- `scorado`: candidato ya puntuado y disponible para curación
- `aprobado`: seleccionado en lineup validado
- `no_seleccionado`: descartado para ese evento

Compatibilidad histórica:
- El código y migraciones mantienen compatibilidad con estados legacy como `pendiente` y `aceptado` en transiciones/consultas de recencia.

### En Silver (`silver.solicitudes.status`)
- `normalizado`
- `scorado`
- `aprobado`
- `no_seleccionado`

## Flujo de scoring (Silver -> Gold)
Archivo: `backend/src/scoring_engine.py`

### Entrada
- Lee `silver.solicitudes` con `status IN ('normalizado', 'scorado')`
- Enlaza con `silver.comicos` y `bronze.solicitudes` para nombre/identidad/metadata

### Persistencia de scoring
Por cada candidato:
- inserta/actualiza `gold.solicitudes` con:
  - `estado = 'scorado'`
  - `score_aplicado`
  - `marca_temporal`
- actualiza `silver.solicitudes.status = 'scorado'` (si no está `aprobado`)
- actualiza `gold.comicos.score_actual`

### Ranking (curación)
`build_ranking(...)`:
- intercalado por género en orden `f/nb -> m`
- `unknown` solo al final cuando se agotan buckets anteriores
- deduplicación por `comico_id` (`seen_ids`)

## Vista de curación `gold.lineup_candidates`
La vista se reconstruye en migración y expone el estado real para frontend:
- `solicitud_id`
- `fecha_evento`
- `estado`
- `nombre`, `genero`, `categoria`
- `score_actual`, `score_final`
- `comico_id`
- `contacto` (`COALESCE(telefono, instagram)`)
- `telefono`, `instagram`

Notas operativas:
- Se eliminó el filtro fijo por `pendiente`.
- Se añade `DROP VIEW IF EXISTS gold.lineup_candidates` previo al `CREATE OR REPLACE VIEW` para evitar errores de despliegue por drift de columnas.

## Validación de lineup (RPC)
Archivo/migración: `specs/sql/migrations/20260217_sync_lineup_validation_states.sql`

Función:
- `gold.validate_lineup(p_selection jsonb, p_event_date date)`

### Reglas de entrada
- Exige exactamente `5` cómicos (`jsonb_array_length = 5`)
- Acepta entradas con:
  - `solicitud_id` (modo preferente)
  - o fallback por `comico_id` + `fecha_evento` / `p_event_date`

### Qué hace la RPC
1. Crea tablas temporales (`tmp_payload_entries`, `tmp_accepted_gold`) para procesar el payload.
2. Marca en `gold.solicitudes` como `aprobado` las selecciones.
3. Marca como `no_seleccionado` el resto del mismo evento.
4. Sincroniza `silver.solicitudes`:
   - seleccionados -> `aprobado`
   - no seleccionados -> `no_seleccionado`
5. Propaga cambios de perfil a `gold.comicos` y `silver.comicos`:
   - `categoria`
   - `genero`
   - `fecha_ultima_actuacion` (Gold)
6. Recalcula `gold.comicos.score_actual` con el último `score_aplicado` disponible.
7. Corrige consistencia histórica en Silver:
   - si existe la solicitud en Gold y Silver sigue en `normalizado`, la normaliza a `scorado`.

### Grants y acceso frontend
La migración asegura:
- `GRANT SELECT ON gold.lineup_candidates TO anon, authenticated, service_role`
- `GRANT EXECUTE ON FUNCTION gold.validate_lineup(jsonb, date) TO anon, authenticated, service_role`
- `GRANT USAGE ON SCHEMA gold TO anon, authenticated`

## Flujo frontend de curación/validación
Archivo: `frontend/src/App.jsx`

### Carga de candidatos
- Consulta `lineup_candidates` con columnas nuevas (`solicitud_id`, `fecha_evento`, `estado`, `contacto`)
- Incluye modo compatibilidad para entornos legacy si faltan columnas
- Selección inicial:
  - prioriza estado `scorado`
  - fallback a `pendiente`
  - si no hay, usa el orden general

### Validación
- Requiere exactamente 5 seleccionados
- Invoca RPC `validate_lineup` vía Supabase con:
  - `p_selection` (payload de selección + edición de `categoria/genero`)
  - `p_event_date`
- Si RPC OK:
  - actualiza UI local
  - notifica a n8n vía webhook

### Robustez del webhook n8n (0.5.12)
- `VITE_N8N_WEBHOOK_URL` debe existir y ser URL absoluta (`http/https`)
- Se añade diagnóstico en consola para distinguir:
  - error de configuración frontend
  - error HTTP del webhook n8n
- `setSaving(false)` se ejecuta en `finally` para evitar botón bloqueado

## Payload del frontend hacia `validate_lineup`
Cada elemento de `p_selection` incluye:
- `row_key`
- `solicitud_id` (si existe)
- `comico_id`
- `fecha_evento`
- `categoria` (editada o actual)
- `genero` (editado o actual)

La RPC usa `solicitud_id` como referencia principal y cae a matching por `comico_id` + fecha cuando hace falta.

## Checklist operativo (validación de lineup)
1. Ejecutar scoring para poblar `gold.solicitudes.estado = 'scorado'`.
2. Verificar que `gold.lineup_candidates` expone `estado` y `contacto`.
3. Confirmar que frontend selecciona 5 y llama a `validate_lineup`.
4. Verificar transiciones:
   - Gold: `scorado -> aprobado/no_seleccionado`
   - Silver: `scorado/normalizado -> aprobado/no_seleccionado`
5. Revisar webhook n8n con `VITE_N8N_WEBHOOK_URL` absoluta.

## Archivos de referencia
- `backend/src/scoring_engine.py`
- `frontend/src/App.jsx`
- `specs/sql/migrations/20260217_sync_lineup_validation_states.sql`
- `docs/scoring-batch-n8n-fix.md`
