-- =========================================================
-- Migración: ampliación controlada de tipo_solicitud_status
-- Fecha: 2026-02-12
-- Objetivo: asegurar que el enum exista y contenga todos los estados requeridos.
-- =========================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typname = 'tipo_solicitud_status'
      AND n.nspname = 'public'
  ) THEN
    CREATE TYPE public.tipo_solicitud_status AS ENUM (
      'crudo',
      'normalizado',
      'scorado',
      'aprobado',
      'rechazado',
      'error_ingesta'
    );
  END IF;
END
$$;

ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'crudo';
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'normalizado';
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'scorado';
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'aprobado';
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'rechazado';
ALTER TYPE public.tipo_solicitud_status ADD VALUE IF NOT EXISTS 'error_ingesta';
