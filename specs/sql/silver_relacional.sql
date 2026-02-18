-- =========================================================
-- AI LineUp Architect - Capa Silver Relacional (schema dedicado)
-- PostgreSQL / Supabase SQL Script
-- =========================================================

-- 1) Extensión requerida.
create extension if not exists pgcrypto;

-- 2) Esquema físico Silver.
create schema if not exists silver;

-- 3) Compatibilidad: mover tablas legacy desde public.
DO $$
BEGIN
  IF to_regclass('silver.proveedores') IS NULL
     AND to_regclass('public.proveedores') IS NOT NULL THEN
    ALTER TABLE public.proveedores SET SCHEMA silver;
  END IF;

  IF to_regclass('silver.comicos') IS NULL
     AND to_regclass('public.comicos_master') IS NOT NULL THEN
    ALTER TABLE public.comicos_master SET SCHEMA silver;
    ALTER TABLE silver.comicos_master RENAME TO comicos;
  END IF;

  IF to_regclass('silver.solicitudes') IS NULL
     AND to_regclass('public.solicitudes_silver') IS NOT NULL THEN
    ALTER TABLE public.solicitudes_silver SET SCHEMA silver;
    ALTER TABLE silver.solicitudes_silver RENAME TO solicitudes;
  END IF;
END
$$;

-- 4) Tipos ENUM en esquema silver.
DO $$
BEGIN
  IF to_regtype('silver.tipo_categoria') IS NULL THEN
    IF to_regtype('public.tipo_categoria_comico') IS NOT NULL THEN
      ALTER TYPE public.tipo_categoria_comico SET SCHEMA silver;
      ALTER TYPE silver.tipo_categoria_comico RENAME TO tipo_categoria;
    ELSIF to_regtype('silver.tipo_categoria_comico') IS NOT NULL THEN
      ALTER TYPE silver.tipo_categoria_comico RENAME TO tipo_categoria;
    ELSE
      CREATE TYPE silver.tipo_categoria AS ENUM (
        'general',
        'priority',
        'gold',
        'restricted'
      );
    END IF;
  END IF;
END
$$;

DO $$
BEGIN
  IF to_regtype('silver.tipo_status') IS NULL THEN
    IF to_regtype('public.tipo_solicitud_status') IS NOT NULL THEN
      ALTER TYPE public.tipo_solicitud_status SET SCHEMA silver;
      ALTER TYPE silver.tipo_solicitud_status RENAME TO tipo_status;
    ELSIF to_regtype('silver.tipo_solicitud_status') IS NOT NULL THEN
      ALTER TYPE silver.tipo_solicitud_status RENAME TO tipo_status;
    ELSE
      CREATE TYPE silver.tipo_status AS ENUM (
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

-- 5) Maestra de proveedores.
create table if not exists silver.proveedores (
  id uuid primary key default gen_random_uuid(),
  nombre_comercial text not null,
  slug text not null unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table silver.proveedores
  add column if not exists nombre_comercial text,
  add column if not exists slug text,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

create unique index if not exists uq_silver_proveedores_slug
  on silver.proveedores (slug);

-- 6) Maestra de cómicos (identidad única normalizada).
create table if not exists silver.comicos (
  id uuid primary key default gen_random_uuid(),
  instagram text not null unique,
  nombre text,
  telefono text,
  genero text not null default 'unknown',
  categoria silver.tipo_categoria not null default 'general',
  metadata_comico jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint chk_silver_comicos_instagram_normalizado
    check (
      instagram = lower(instagram)
      and left(instagram, 1) <> '@'
    ),

  constraint chk_silver_comicos_telefono_e164
    check (
      telefono is null
      or telefono ~ '^\+[1-9][0-9]{7,14}$'
    )
);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'silver'
      AND table_name = 'comicos'
      AND column_name = 'instagram_user'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'silver'
      AND table_name = 'comicos'
      AND column_name = 'instagram'
  ) THEN
    ALTER TABLE silver.comicos RENAME COLUMN instagram_user TO instagram;
  ELSIF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'silver'
      AND table_name = 'comicos'
      AND column_name = 'instagram_user'
  ) THEN
    UPDATE silver.comicos
    SET instagram = COALESCE(instagram, instagram_user)
    WHERE instagram_user IS NOT NULL;
    ALTER TABLE silver.comicos DROP COLUMN instagram_user;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'silver'
      AND table_name = 'comicos'
      AND column_name = 'nombre_artistico'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'silver'
      AND table_name = 'comicos'
      AND column_name = 'nombre'
  ) THEN
    ALTER TABLE silver.comicos RENAME COLUMN nombre_artistico TO nombre;
  ELSIF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'silver'
      AND table_name = 'comicos'
      AND column_name = 'nombre_artistico'
  ) THEN
    UPDATE silver.comicos
    SET nombre = COALESCE(nombre, nombre_artistico)
    WHERE nombre_artistico IS NOT NULL;
    ALTER TABLE silver.comicos DROP COLUMN nombre_artistico;
  END IF;
END
$$;

alter table silver.comicos
  add column if not exists nombre text,
  add column if not exists instagram text,
  add column if not exists telefono text,
  add column if not exists genero text not null default 'unknown',
  add column if not exists categoria silver.tipo_categoria not null default 'general',
  add column if not exists metadata_comico jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

alter table silver.comicos
  drop column if exists is_gold,
  drop column if exists is_priority,
  drop column if exists is_restricted;

update silver.comicos
set instagram = lower(trim(instagram))
where instagram is not null;

alter table silver.comicos
  alter column instagram set not null;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_silver_comicos_instagram_normalizado'
      AND conrelid = 'silver.comicos'::regclass
  ) THEN
    ALTER TABLE silver.comicos
      ADD CONSTRAINT chk_silver_comicos_instagram_normalizado
      CHECK (
        instagram = lower(instagram)
        and left(instagram, 1) <> '@'
      );
  END IF;
END
$$;

update silver.comicos
set genero = 'unknown'
where genero is null;

alter table silver.comicos
  alter column genero set default 'unknown',
  alter column genero set not null;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_silver_comicos_telefono_e164'
      AND conrelid = 'silver.comicos'::regclass
  ) THEN
    ALTER TABLE silver.comicos
      ADD CONSTRAINT chk_silver_comicos_telefono_e164
      CHECK (
        telefono is null
        or telefono ~ '^\+[1-9][0-9]{7,14}$'
      );
  END IF;
END
$$;

DO $$
BEGIN
  IF to_regclass('silver.idx_silver_comicos_instagram_user') IS NOT NULL
     AND to_regclass('silver.idx_silver_comicos_instagram') IS NULL THEN
    ALTER INDEX silver.idx_silver_comicos_instagram_user
      RENAME TO idx_silver_comicos_instagram;
  END IF;
END
$$;

create index if not exists idx_silver_comicos_instagram
  on silver.comicos (instagram);

create index if not exists idx_silver_comicos_categoria
  on silver.comicos (categoria);

-- 7) Transaccional Silver con linaje obligatorio a Bronze.
create table if not exists silver.solicitudes (
  id uuid primary key default gen_random_uuid(),
  bronze_id uuid not null,
  proveedor_id uuid not null,
  comico_id uuid not null,

  fecha_evento date not null,
  nivel_experiencia int2 not null,
  disponibilidad_ultimo_minuto boolean not null default false,
  show_cercano text,
  origen_conocimiento text,
  status silver.tipo_status not null default 'crudo',
  metadata_ia jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint chk_silver_solicitudes_nivel_experiencia
    check (nivel_experiencia between 0 and 3),

  constraint uq_silver_solicitudes_comico_fecha
    unique (comico_id, fecha_evento)
);

alter table silver.solicitudes
  add column if not exists bronze_id uuid,
  add column if not exists proveedor_id uuid,
  add column if not exists comico_id uuid,
  add column if not exists fecha_evento date,
  add column if not exists nivel_experiencia int2,
  add column if not exists disponibilidad_ultimo_minuto boolean not null default false,
  add column if not exists show_cercano text,
  add column if not exists origen_conocimiento text,
  add column if not exists status silver.tipo_status not null default 'crudo',
  add column if not exists metadata_ia jsonb not null default '{}'::jsonb,
  add column if not exists created_at timestamptz not null default now(),
  add column if not exists updated_at timestamptz not null default now();

alter table silver.solicitudes
  drop column if exists score_final;

-- Reemplazo controlado de FKs por relaciones schema-qualified correctas.
DO $$
DECLARE
  fk_record record;
BEGIN
  FOR fk_record IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'silver.solicitudes'::regclass
      AND contype = 'f'
  LOOP
    EXECUTE format(
      'ALTER TABLE silver.solicitudes DROP CONSTRAINT %I',
      fk_record.conname
    );
  END LOOP;

  ALTER TABLE silver.solicitudes
    ADD CONSTRAINT fk_silver_solicitudes_bronze
    FOREIGN KEY (bronze_id)
    REFERENCES bronze.solicitudes(id)
    ON DELETE RESTRICT;

  ALTER TABLE silver.solicitudes
    ADD CONSTRAINT fk_silver_solicitudes_proveedor
    FOREIGN KEY (proveedor_id)
    REFERENCES silver.proveedores(id)
    ON DELETE RESTRICT;

  ALTER TABLE silver.solicitudes
    ADD CONSTRAINT fk_silver_solicitudes_comico
    FOREIGN KEY (comico_id)
    REFERENCES silver.comicos(id)
    ON DELETE RESTRICT;
END
$$;

create index if not exists idx_silver_solicitudes_bronze_id
  on silver.solicitudes (bronze_id);

create unique index if not exists uq_silver_solicitudes_bronze_fecha
  on silver.solicitudes (bronze_id, fecha_evento);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_silver_solicitudes_comico_fecha'
      AND conrelid = 'silver.solicitudes'::regclass
  ) THEN
    IF EXISTS (
      SELECT 1
      FROM pg_class
      WHERE relname = 'uq_silver_solicitudes_comico_fecha'
        AND relkind = 'i'
    ) THEN
      ALTER TABLE silver.solicitudes
        ADD CONSTRAINT uq_silver_solicitudes_comico_fecha
        UNIQUE USING INDEX uq_silver_solicitudes_comico_fecha;
    ELSE
      ALTER TABLE silver.solicitudes
        ADD CONSTRAINT uq_silver_solicitudes_comico_fecha
        UNIQUE (comico_id, fecha_evento);
    END IF;
  END IF;
END
$$;

create index if not exists idx_silver_solicitudes_proveedor_fecha
  on silver.solicitudes (proveedor_id, fecha_evento);

create index if not exists idx_silver_solicitudes_comico_id
  on silver.solicitudes (comico_id);

create index if not exists idx_silver_solicitudes_status
  on silver.solicitudes (status);

create index if not exists idx_silver_solicitudes_metadata_ia_gin
  on silver.solicitudes
  using gin (metadata_ia);

create unique index if not exists uq_silver_solicitudes_aprobado_semana
  on silver.solicitudes (
    proveedor_id,
    comico_id,
    date_trunc('week', fecha_evento::timestamp)
  )
  where status = 'aprobado';

-- 8) Triggers updated_at.
drop trigger if exists trg_silver_proveedores_set_updated_at on silver.proveedores;
create trigger trg_silver_proveedores_set_updated_at
before update on silver.proveedores
for each row
execute function public.set_updated_at();

drop trigger if exists trg_silver_comicos_set_updated_at on silver.comicos;
create trigger trg_silver_comicos_set_updated_at
before update on silver.comicos
for each row
execute function public.set_updated_at();

drop trigger if exists trg_silver_solicitudes_set_updated_at on silver.solicitudes;
create trigger trg_silver_solicitudes_set_updated_at
before update on silver.solicitudes
for each row
execute function public.set_updated_at();

-- 9) Seguridad RLS Silver.
alter table silver.proveedores enable row level security;
alter table silver.comicos enable row level security;
alter table silver.solicitudes enable row level security;

drop policy if exists p_service_role_all_silver_proveedores on silver.proveedores;
create policy p_service_role_all_silver_proveedores
on silver.proveedores
for all
to service_role
using (true)
with check (true);

drop policy if exists p_service_role_all_silver_comicos on silver.comicos;
create policy p_service_role_all_silver_comicos
on silver.comicos
for all
to service_role
using (true)
with check (true);

drop policy if exists p_service_role_all_silver_solicitudes on silver.solicitudes;
create policy p_service_role_all_silver_solicitudes
on silver.solicitudes
for all
to service_role
using (true)
with check (true);

drop policy if exists p_anon_select_silver_solicitudes on silver.solicitudes;
create policy p_anon_select_silver_solicitudes
on silver.solicitudes
for select
to anon
using (true);

drop policy if exists p_anon_update_silver_solicitudes on silver.solicitudes;
create policy p_anon_update_silver_solicitudes
on silver.solicitudes
for update
to anon
using (true)
with check (true);

alter table silver.comicos enable row level security;

drop policy if exists "Permitir lectura comicos anon" on silver.comicos;
drop policy if exists "Permitir update comicos anon" on silver.comicos;
drop policy if exists "p_anon_select_silver_comicos" on silver.comicos;
drop policy if exists "p_anon_update_silver_comicos" on silver.comicos;

create policy "p_anon_select_silver_comicos"
on silver.comicos
for select
to anon
using (true);

create policy "p_anon_update_silver_comicos"
on silver.comicos
for update
to anon
using (true)
with check (true);

revoke all on schema silver from public;
revoke usage on schema silver from anon, authenticated;
grant usage on schema silver to anon;
grant usage on schema silver to service_role;
grant select, update on silver.comicos to anon;
grant select, update on all tables in schema silver to anon;
grant select, insert, update, delete on all tables in schema silver to service_role;
alter default privileges in schema silver
  grant select, update on tables to anon;
alter default privileges in schema silver
  grant select, insert, update, delete on tables to service_role;
