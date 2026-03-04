# Modelo simplificado: Bronze solo solicitudes + linaje a Silver

## Objetivo
Eliminar redundancia en Bronze y centralizar la identidad en Silver.

## Resultado de diseño

- `bronze`:
  - Solo existe `bronze.solicitudes`.
  - Almacena campos crudos (`*_raw`) y `raw_data_extra` (`jsonb`).

- `silver`:
  - `silver.comicos` (identidad única por `instagram_user` normalizado).
  - `silver.proveedores` (maestra de organizadores/open mics).
  - `silver.solicitudes` (transaccional con FKs a `silver.comicos`, `silver.proveedores` y linaje `bronze_id`).

## Reglas clave

- Linaje obligatorio:
  - `silver.solicitudes.bronze_id` -> `bronze.solicitudes(id)`.
- Enums en Silver:
  - `silver.tipo_categoria`
  - `silver.tipo_status`
- RLS habilitado en ambos esquemas para `service_role`.

## Flujo de ingesta preparado

1. Leer filas pendientes en `bronze.solicitudes`.
2. Normalizar `instagram_raw`.
3. Upsert de identidad en `silver.comicos`.
4. Insert en `silver.solicitudes` usando:
   - `bronze_id` (linaje)
   - `comico_id` y `proveedor_id` (FKs Silver)
