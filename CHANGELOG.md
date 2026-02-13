# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-02-13

### Added
- Script `setup_db.py` para despliegue secuencial del esquema SQL en Supabase, con carga de `DATABASE_URL` desde `.env`, verificación de enums y opción `--reset` para limpieza de tablas y tipos.
- Migración `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` para asegurar la existencia y completitud de `tipo_solicitud_status`.
- Documentación técnica en `docs/setup-db-migraciones.md`.

## [0.1.2] - 2026-02-12

### Added
- Script SQL de Capa Silver relacional en `specs/sql/silver_relacional.sql`, con tablas `comicos_master` y `solicitudes_silver`, restricciones de calidad, unicidad semanal de aprobados, triggers de `updated_at` y políticas RLS para `service_role`.
- Documento técnico de soporte en `docs/silver-relacional.md` explicando la normalización y el impacto en el motor de scoring.

## [0.1.1] - 2026-02-12

### Added
- Script SQL base para Capa Bronze, infraestructura multi-proveedor y master data de cómicos en `specs/sql/bronze_multi_proveedor_master.sql`.
- Documento técnico de soporte en `docs/bronze-multi-proveedor-master-data.md`.

## [0.1.0] - 2026-02-10

### Added
- Definición de roles y responsabilidades en `AGENTS.md`.
- Estructura de versionado híbrida (`package.json` + `pyproject.toml`).
- Configuración de dependencias base para Python.
- Definición de flujo de decisión híbrido (Lógica determinística + IA).
- Roadmap inicial del MVP en el README.