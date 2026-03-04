# Capa Silver Relacional (AI LineUp Architect)

Este diseño introduce una separación estricta entre:

1. **Identidad normalizada en Bronze** (`comicos_master_bronze`).
2. **Identidad enriquecida en Silver** (`comicos_master`).
3. **Intención transaccional por evento** (`solicitudes_silver`).

El script fuente está en `specs/sql/silver_relacional.sql`.

## Objetivo de normalización

- Evitar duplicidad de datos personales por cada solicitud.
- Hacer que los atributos permanentes del artista (instagram, teléfono, flags de segmentación) vivan en una sola fila maestra.
- Mantener en Silver solo datos dinámicos por solicitud: fecha, experiencia declarada, disponibilidad de último minuto, estado y score.

## Diseño de tablas

### `comicos_master_bronze`

Fuente canónica de identidad en la capa Bronze.

Incluye:

- `instagram_user` normalizado.
- `nombre_artistico` y `telefono` como datos provenientes de ingesta.
- `categoria` base para segmentación inicial.

### `comicos_master`

Directorio enriquecido de Silver y único por `instagram_user` normalizado.

Incluye:

- Identidad (`instagram_user`, `nombre_artistico`, `telefono`).
- Flags de scoring (`is_gold`, `is_priority`, `is_restricted`).
- Segmentación (`categoria`).
- `metadata_comico` para extensibilidad sin romper esquema.
- Restricciones de calidad:
  - Instagram en minúsculas y sin `@`.
  - Teléfono E.164 cuando esté presente.
- Sincronización inicial desde `comicos_master_bronze` mediante upsert idempotente.

### `solicitudes_silver`

Registro de cada solicitud ya refinada desde Bronze.

Incluye:

- Trazabilidad 1:1 (`bronze_id` único).
- Integración multi-proveedor (`proveedor_id`).
- Referencia de identidad (`comico_id`) sin duplicar PII.
- Datos dinámicos para scoring:
  - `fecha_evento`
  - `nivel_experiencia` (0-3)
  - `disponibilidad_ultimo_minuto`
  - `status`
  - `metadata_ia`

## Regla crítica de negocio

Se implementa un índice único parcial para evitar doble aprobación semanal del mismo cómico por proveedor:

- Clave: (`proveedor_id`, `comico_id`, `date_trunc('week', fecha_evento)`)
- Condición: `status = 'aprobado'`

Esto garantiza la política operativa directamente en base de datos, evitando inconsistencias por condiciones de carrera.

## Seguridad (Supabase)

- RLS habilitado en ambas tablas.
- Política explícita `FOR ALL` únicamente para `service_role`.

Con esto, solo backend/orquestador autenticado por service key puede leer y escribir la Silver.

## ¿Por qué optimiza al motor de Python?

La arquitectura reduce trabajo y complejidad del motor de ingesta/scoring porque:

1. **Persistencia por capas:** el motor normaliza `instagram_user` y hace upsert primero en `comicos_master_bronze`.
2. **Sincronización Bronze -> Silver:** el perfil enriquecido en `comicos_master` se actualiza desde Bronze por upsert idempotente.
3. **Reutilización de perfil:** cada solicitud nueva solo crea/actualiza `solicitudes_silver` con FK a `comico_id`.
4. **Scoring más barato y consistente:** reglas de prioridad/restricción viven en `comicos_master`; el cálculo no depende de texto crudo repetido en cada transacción.
5. **Menos riesgo de drift de datos:** cambiar teléfono, categoría o flags impacta inmediatamente a todas las futuras decisiones sin migraciones masivas.

En síntesis: **identidad centralizada + transacción desacoplada** mejora gobernanza de datos, acelera scoring y evita duplicidades.
