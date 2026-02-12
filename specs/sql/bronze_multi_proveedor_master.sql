-- =========================================================
-- AI LineUp Architect - Capa Bronze + Multi-Proveedor + Master Data
-- PostgreSQL / Supabase SQL Script
-- =========================================================

-- 1) Extensiones requeridas
create extension if not exists pgcrypto;

-- 2) Enum para la categorización central de cómicos
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typname = 'tipo_categoria_comico'
      AND n.nspname = 'public'
  ) THEN
    CREATE TYPE public.tipo_categoria_comico AS ENUM (
      'general',
      'priority',
      'gold',
      'restricted'
    );
  END IF;
END
$$;

-- 3) Función común para auto-actualizar updated_at
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- 4) Infraestructura de escalado: proveedores
create table if not exists public.proveedores (
  id uuid primary key default gen_random_uuid(),
  nombre_comercial text not null,
  slug text not null unique,
  created_at timestamptz not null default now()
);

create index if not exists idx_proveedores_slug on public.proveedores (slug);

-- 5) Directorio central de cómicos
create table if not exists public.comicos_master (
  id uuid primary key default gen_random_uuid(),
  instagram_user text not null unique,
  categoria public.tipo_categoria_comico not null default 'general',
  updated_at timestamptz not null default now(),
  -- Garantiza formato normalizado sin @ y en minúsculas
  constraint chk_comicos_master_instagram_normalizado
    check (
      instagram_user = lower(instagram_user)
      and left(instagram_user, 1) <> '@'
    )
);

create index if not exists idx_comicos_master_instagram_user on public.comicos_master (instagram_user);

create trigger trg_comicos_master_set_updated_at
before update on public.comicos_master
for each row
execute function public.set_updated_at();

-- 6) Capa de ingesta híbrida (Bronze)
create table if not exists public.solicitudes_bronze (
  id uuid primary key default gen_random_uuid(),
  proveedor_id uuid not null references public.proveedores(id) on delete restrict,
  sheet_row_id int4 not null,
  created_at timestamptz not null default now(),

  -- Campos espejo del formulario
  nombre_raw text,
  instagram_raw text,
  whatsapp_raw text,
  experiencia_raw text,
  fechas_seleccionadas_raw text,
  disponibilidad_ultimo_minuto text,
  info_show_cercano text,
  origen_conocimiento text,

  -- Payload completo proveniente de n8n
  raw_data_extra jsonb,

  procesado boolean not null default false,

  -- Unicidad por proveedor + fila de hoja
  constraint uq_solicitudes_bronze_proveedor_sheet
    unique (proveedor_id, sheet_row_id)
);

create index if not exists idx_solicitudes_bronze_proveedor_id
  on public.solicitudes_bronze (proveedor_id);

create index if not exists idx_solicitudes_bronze_sheet_row_id
  on public.solicitudes_bronze (sheet_row_id);

create index if not exists idx_solicitudes_bronze_raw_data_extra_gin
  on public.solicitudes_bronze
  using gin (raw_data_extra);

-- 7) Seguridad: RLS habilitado en todas las tablas
alter table public.proveedores enable row level security;
alter table public.comicos_master enable row level security;
alter table public.solicitudes_bronze enable row level security;

-- 8) Políticas: solo service_role puede leer y escribir
-- (n8n y scripts backend autenticados con service key)
drop policy if exists p_service_role_all_proveedores on public.proveedores;
create policy p_service_role_all_proveedores
on public.proveedores
for all
to service_role
using (true)
with check (true);

drop policy if exists p_service_role_all_comicos_master on public.comicos_master;
create policy p_service_role_all_comicos_master
on public.comicos_master
for all
to service_role
using (true)
with check (true);

drop policy if exists p_service_role_all_solicitudes_bronze on public.solicitudes_bronze;
create policy p_service_role_all_solicitudes_bronze
on public.solicitudes_bronze
for all
to service_role
using (true)
with check (true);
