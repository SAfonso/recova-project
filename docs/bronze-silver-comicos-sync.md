# Separación de `comicos_master` entre Bronze y Silver

## Objetivo
Evitar conflictos de esquema entre capas y formalizar el flujo de identidad:

1. Bronze mantiene su tabla de identidad (`comicos_master_bronze`).
2. Silver mantiene su tabla enriquecida (`comicos_master`).
3. Silver se alimenta desde Bronze mediante sincronización idempotente.

## Cambios aplicados

### 1) Esquema Bronze
En `specs/sql/bronze_multi_proveedor_master.sql` la tabla de cómicos pasa a:

- `public.comicos_master_bronze`

Con sus propios:

- índice `idx_comicos_master_bronze_instagram_user`
- trigger `trg_comicos_master_bronze_set_updated_at`
- política RLS `p_service_role_all_comicos_master_bronze`

### 2) Esquema Silver
En `specs/sql/silver_relacional.sql`:

- `public.comicos_master` queda como tabla de identidad enriquecida de Silver.
- Se agrega sincronización inicial:
  - `INSERT ... SELECT ... FROM public.comicos_master_bronze`
  - `ON CONFLICT (instagram_user) DO UPDATE`

### 3) Ingesta Python Bronze -> Silver
En `backend/src/bronze_to_silver_ingestion.py`:

- El upsert de identidad se hace primero en `public.comicos_master_bronze`.
- Luego se sincroniza `public.comicos_master` desde el registro Bronze.
- `solicitudes_silver` sigue referenciando `comico_id` de `public.comicos_master`.

### 4) Seed y setup
- `specs/sql/seed_data.sql` ahora inserta cómicos en Bronze y luego sincroniza Silver.
- `setup_db.py` extiende backup/reset para incluir ambas tablas:
  - `comicos_master_bronze`
  - `comicos_master`

## Resultado
Se elimina el choque de nombre/estructura entre capas y la identidad fluye explícitamente de Bronze a Silver.
