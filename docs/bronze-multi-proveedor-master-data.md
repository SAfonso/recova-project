# Capa Bronze + Multi-Proveedor + Master Data

Este documento describe la base de datos inicial para el MVP de **AI LineUp Architect** en Supabase.

## Alcance

Se implementan tres componentes:

1. Infraestructura de escalado por proveedor (`proveedores`).
2. Directorio central de cómicos (`comicos_master`).
3. Capa de ingesta híbrida (`solicitudes_bronze`).

## Script SQL

El script ejecutable se encuentra en:

- `specs/sql/bronze_multi_proveedor_master.sql`

## Decisiones clave

- Se usa `pgcrypto` para `gen_random_uuid()`.
- `instagram_user` en `comicos_master` está protegido por una restricción de formato para garantizar minúsculas y ausencia de `@`.
- Se define una función genérica `set_updated_at()` y trigger sobre `comicos_master` para mantener `updated_at` automáticamente.
- Se habilita RLS en todas las tablas y se restringe acceso de lectura/escritura al rol `service_role`.
