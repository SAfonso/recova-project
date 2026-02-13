# Separación física por esquemas: Bronze y Silver

## Objetivo
Separar la base de datos por capas reales en Supabase/PostgreSQL:

- `bronze`: datos crudos de ingesta.
- `silver`: datos normalizados, maestros y transaccionales para negocio.

## Archivos SQL por capa

- `specs/sql/bronze_multi_proveedor_master.sql`
  - Crea esquema `bronze`.
  - Define `bronze.comicos` y `bronze.solicitudes`.
  - Aplica RLS y políticas `service_role` para Bronze.

- `specs/sql/silver_relacional.sql`
  - Crea esquema `silver`.
  - Define tipos `silver.tipo_categoria` y `silver.tipo_status`.
  - Define `silver.proveedores`, `silver.comicos`, `silver.solicitudes`.
  - Aplica FKs schema-qualified (incluyendo `silver.solicitudes -> bronze.solicitudes`).
  - Aplica RLS y políticas `service_role` para Silver.

- `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql`
  - Asegura la existencia de `silver.tipo_status` y todos sus valores.

## Compatibilidad con instalaciones legacy
Los scripts incluyen bloques `DO $$ ... $$` para migrar objetos existentes en `public` hacia `bronze`/`silver` cuando aplica.

## Notas de seguridad
- Extensión `pgcrypto` se mantiene en `public`.
- Se revoca acceso general a los esquemas y se habilita explícitamente para `service_role`.
- Queda preparado el terreno para habilitar acceso futuro solo a `silver` en roles de lectura.
