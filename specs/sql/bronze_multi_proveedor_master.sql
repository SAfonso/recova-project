-- =========================================================
-- AI LineUp Architect - Capa Bronze (schema dedicado)
-- PostgreSQL / Supabase SQL Script
-- =========================================================

-- 1) Extensión requerida.
create extension if not exists pgcrypto;

-- 2) Esquemas físicos.
create schema if not exists bronze;
create schema if not exists silver;

-- 3) Función común para auto-actualizar updated_at.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- 4) Compatibilidad con estructura legacy.
DO $$
BEGIN
  IF to_regclass('bronze.solicitudes') IS NULL
     AND to_regclass('public.solicitudes_bronze') IS NOT NULL THEN
    ALTER TABLE public.solicitudes_bronze SET SCHEMA bronze;
    ALTER TABLE bronze.solicitudes_bronze RENAME TO solicitudes;
  END IF;

  -- Eliminar tabla redundante de identidad en Bronze.
  IF to_regclass('bronze.comicos') IS NOT NULL THEN
    DROP TABLE bronze.comicos CASCADE;
  END IF;

  IF to_regclass('public.comicos_master_bronze') IS NOT NULL THEN
    DROP TABLE public.comicos_master_bronze CASCADE;
  END IF;
END
$$;

-- 5) Solicitudes crudas Bronze (única tabla del esquema).
create table if not exists bronze.solicitudes (
  id uuid primary key default gen_random_uuid(),
  proveedor_id uuid,
  sheet_row_id int4,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  nombre_raw text,
  instagram_raw text,
  telefono_raw text,
  experiencia_raw text,
  fechas_seleccionadas_raw text,
  disponibilidad_ultimo_minuto text,
  info_show_cercano text,
  origen_conocimiento text,

  raw_data_extra jsonb,
  procesado boolean not null default false
);

-- Endurecer tabla existente sin romper instalaciones previas.
alter table bronze.solicitudes
  add column if not exists proveedor_id uuid,
  add column if not exists sheet_row_id int4,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now(),
  add column if not exists nombre_raw text,
  add column if not exists instagram_raw text,
  add column if not exists telefono_raw text,
  add column if not exists experiencia_raw text,
  add column if not exists fechas_seleccionadas_raw text,
  add column if not exists disponibilidad_ultimo_minuto text,
  add column if not exists info_show_cercano text,
  add column if not exists origen_conocimiento text,
  add column if not exists raw_data_extra jsonb,
  add column if not exists procesado boolean not null default false;

-- Compatibilidad: whatsapp_raw legacy -> telefono_raw.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'bronze'
      AND table_name = 'solicitudes'
      AND column_name = 'whatsapp_raw'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'bronze'
      AND table_name = 'solicitudes'
      AND column_name = 'telefono_raw'
  ) THEN
    ALTER TABLE bronze.solicitudes RENAME COLUMN whatsapp_raw TO telefono_raw;
  ELSIF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'bronze'
      AND table_name = 'solicitudes'
      AND column_name = 'whatsapp_raw'
  ) THEN
    UPDATE bronze.solicitudes
    SET telefono_raw = COALESCE(telefono_raw, whatsapp_raw)
    WHERE whatsapp_raw IS NOT NULL;
    ALTER TABLE bronze.solicitudes DROP COLUMN whatsapp_raw;
  END IF;
END
$$;

-- Unicidad por proveedor + fila (solo cuando ambos existen).
create unique index if not exists uq_bronze_solicitudes_proveedor_sheet
  on bronze.solicitudes (proveedor_id, sheet_row_id)
  where proveedor_id is not null and sheet_row_id is not null;

-- Bronze no debe depender por FK de otras capas: elimina FKs previas.
DO $$
DECLARE
  fk_record record;
BEGIN
  FOR fk_record IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'bronze.solicitudes'::regclass
      AND contype = 'f'
  LOOP
    EXECUTE format(
      'ALTER TABLE bronze.solicitudes DROP CONSTRAINT %I',
      fk_record.conname
    );
  END LOOP;
END
$$;

create index if not exists idx_bronze_solicitudes_proveedor_id
  on bronze.solicitudes (proveedor_id);

create index if not exists idx_bronze_solicitudes_sheet_row_id
  on bronze.solicitudes (sheet_row_id);

create index if not exists idx_bronze_solicitudes_procesado
  on bronze.solicitudes (procesado);

create index if not exists idx_bronze_solicitudes_raw_data_extra_gin
  on bronze.solicitudes
  using gin (raw_data_extra);

drop trigger if exists trg_bronze_solicitudes_set_updated_at on bronze.solicitudes;
create trigger trg_bronze_solicitudes_set_updated_at
before update on bronze.solicitudes
for each row
execute function public.set_updated_at();

-- 6) Seguridad Bronze.
alter table bronze.solicitudes enable row level security;

drop policy if exists p_service_role_all_bronze_solicitudes on bronze.solicitudes;
create policy p_service_role_all_bronze_solicitudes
on bronze.solicitudes
for all
to service_role
using (true)
with check (true);

revoke all on schema bronze from public;
revoke usage on schema bronze from anon, authenticated;
grant usage on schema bronze to service_role;
grant select, insert, update, delete on all tables in schema bronze to service_role;
alter default privileges in schema bronze
  grant select, insert, update, delete on tables to service_role;
