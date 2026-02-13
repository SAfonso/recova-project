# Setup de Base de Datos con Migraciones y Limpieza de Enums

## Objetivo
Este cambio introduce `setup_db.py` para automatizar el despliegue del esquema de PostgreSQL/Supabase respetando dependencias entre capas SQL y permitiendo limpieza controlada de objetos críticos.

## Flujo implementado
1. Carga `DATABASE_URL` desde `.env` con `python-dotenv`.
2. Verifica existencia de enums:
   - `tipo_categoria_comico`
   - `tipo_solicitud_status`
3. Si se ejecuta con `--reset`, realiza:
   - `DROP TABLE IF EXISTS solicitudes_silver, solicitudes_bronze, comicos_master, proveedores CASCADE;`
   - `DROP TYPE IF EXISTS tipo_categoria_comico, tipo_solicitud_status CASCADE;`
4. Ejecuta SQL en orden estricto:
   - `specs/sql/bronze_multi_proveedor_master.sql`
   - `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql`
   - `specs/sql/silver_relacional.sql`

## Archivo de migración agregado
Se agrega `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` para asegurar que `tipo_solicitud_status` exista y contenga todos los valores requeridos mediante `ADD VALUE IF NOT EXISTS`.

## Uso
```bash
python setup_db.py
python setup_db.py --reset
```
