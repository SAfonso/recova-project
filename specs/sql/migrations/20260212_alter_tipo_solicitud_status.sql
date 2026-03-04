-- =========================================================
-- Migración: ampliación controlada de silver.tipo_status
-- Fecha: 2026-02-12
-- Objetivo: asegurar que el enum exista en silver con todos los estados requeridos.
-- =========================================================

create schema if not exists silver;

DO $$
BEGIN
  IF to_regtype('silver.tipo_status') IS NULL THEN
    IF to_regtype('silver.tipo_solicitud_status') IS NOT NULL THEN
      ALTER TYPE silver.tipo_solicitud_status RENAME TO tipo_status;
    ELSIF to_regtype('public.tipo_solicitud_status') IS NOT NULL THEN
      ALTER TYPE public.tipo_solicitud_status SET SCHEMA silver;
      ALTER TYPE silver.tipo_solicitud_status RENAME TO tipo_status;
    ELSE
      CREATE TYPE silver.tipo_status AS ENUM (
        'crudo',
        'normalizado',
        'scorado',
        'aprobado',
        'rechazado',
        'error_ingesta'
      );
    END IF;
  END IF;
END
$$;

ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'crudo';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'normalizado';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'scorado';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'aprobado';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'no_seleccionado';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'expirado';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'rechazado';
ALTER TYPE silver.tipo_status ADD VALUE IF NOT EXISTS 'error_ingesta';
