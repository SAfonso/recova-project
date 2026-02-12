-- =========================================================
-- AI LineUp Architect - Capa Silver Relacional
-- PostgreSQL / Supabase SQL Script
-- Objetivo: separar identidad (comicos_master) de transacción (solicitudes_silver)
-- =========================================================

-- 1) Extensiones requeridas
create extension if not exists pgcrypto;

-- 2) Tipos requeridos
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
      'no_seleccionado',
      'expirado',
      'rechazado',
      'error_ingesta'
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

-- 4) Capa Silver - directorio centralizado de cómicos
create table if not exists public.comicos_master (
  id uuid primary key default gen_random_uuid(),
  instagram_user text not null unique,
  nombre_artistico text,
  telefono text,
  is_gold boolean not null default false,
  is_priority boolean not null default false,
  is_restricted boolean not null default false,
  categoria public.tipo_categoria_comico not null default 'general',
  metadata_comico jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),

  -- Instagram almacenado normalizado: minúsculas y sin prefijo @
  constraint chk_comicos_master_instagram_normalizado
    check (
      instagram_user = lower(instagram_user)
      and left(instagram_user, 1) <> '@'
    ),

  -- Formato E.164 (opcional, pero si existe debe validar)
  constraint chk_comicos_master_telefono_e164
    check (
      telefono is null
      or telefono ~ '^\+[1-9][0-9]{7,14}$'
    )
);

create index if not exists idx_comicos_master_instagram_user
  on public.comicos_master (instagram_user);

create index if not exists idx_comicos_master_categoria
  on public.comicos_master (categoria);

-- 5) Capa Silver - tabla transaccional refinada
create table if not exists public.solicitudes_silver (
  id uuid primary key default gen_random_uuid(),
  bronze_id uuid not null
    references public.solicitudes_bronze(id) on delete restrict,
  proveedor_id uuid not null
    references public.proveedores(id) on delete restrict,
  comico_id uuid not null
    references public.comicos_master(id) on delete restrict,

  fecha_evento date not null,
  nivel_experiencia int2 not null,
  disponibilidad_ultimo_minuto boolean not null default false,
  score_final numeric(5,2),
  status public.tipo_solicitud_status not null default 'crudo',
  metadata_ia jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),

  constraint chk_solicitudes_silver_nivel_experiencia
    check (nivel_experiencia between 0 and 3)
);

create index if not exists idx_solicitudes_silver_bronze_id
  on public.solicitudes_silver (bronze_id);

create unique index if not exists uq_solicitudes_silver_bronze_fecha
  on public.solicitudes_silver (bronze_id, fecha_evento);

create unique index if not exists uq_solicitudes_silver_comico_fecha
  on public.solicitudes_silver (comico_id, fecha_evento);

create index if not exists idx_solicitudes_silver_proveedor_fecha
  on public.solicitudes_silver (proveedor_id, fecha_evento);

create index if not exists idx_solicitudes_silver_comico_id
  on public.solicitudes_silver (comico_id);

create index if not exists idx_solicitudes_silver_status
  on public.solicitudes_silver (status);

create index if not exists idx_solicitudes_silver_metadata_ia_gin
  on public.solicitudes_silver
  using gin (metadata_ia);

-- 6) Regla de negocio: no repetir aprobados por semana/proveedor/cómico
-- Nota: date_trunc('week', fecha_evento) usa semana natural ISO iniciando en lunes.
create unique index if not exists uq_solicitudes_silver_aprobado_semana
  on public.solicitudes_silver (
    proveedor_id,
    comico_id,
    date_trunc('week', fecha_evento::timestamp)
  )
  where status = 'aprobado';

-- 7) Automatización de updated_at
DROP TRIGGER IF EXISTS trg_comicos_master_set_updated_at ON public.comicos_master;
create trigger trg_comicos_master_set_updated_at
before update on public.comicos_master
for each row
execute function public.set_updated_at();

DROP TRIGGER IF EXISTS trg_solicitudes_silver_set_updated_at ON public.solicitudes_silver;
create trigger trg_solicitudes_silver_set_updated_at
before update on public.solicitudes_silver
for each row
execute function public.set_updated_at();

-- 8) Seguridad: RLS habilitado
alter table public.comicos_master enable row level security;
alter table public.solicitudes_silver enable row level security;

-- 9) Políticas: solo service_role con acceso total
drop policy if exists p_service_role_all_comicos_master on public.comicos_master;
create policy p_service_role_all_comicos_master
on public.comicos_master
for all
to service_role
using (true)
with check (true);

drop policy if exists p_service_role_all_solicitudes_silver on public.solicitudes_silver;
create policy p_service_role_all_solicitudes_silver
on public.solicitudes_silver
for all
to service_role
using (true)
with check (true);
