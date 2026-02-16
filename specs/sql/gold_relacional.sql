-- =========================================================
-- AI LineUp Architect - Capa Gold (PostgreSQL / Supabase)
-- =========================================================
-- Objetivo:
--   1) Mantener una maestra de perfiles enriquecidos (comicos).
--   2) Persistir historial de solicitudes + scoring (solicitudes).
--   3) Conservar linaje desde Silver reutilizando IDs de origen.

create extension if not exists pgcrypto;

create schema if not exists gold;

-- ---------------------------------------------------------
-- Compatibilidad: renombrar tablas legacy *_gold
-- ---------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('gold.comicos') IS NULL
     AND to_regclass('gold.comicos_gold') IS NOT NULL THEN
    ALTER TABLE gold.comicos_gold RENAME TO comicos;
  END IF;

  IF to_regclass('gold.solicitudes') IS NULL
     AND to_regclass('gold.solicitudes_gold') IS NOT NULL THEN
    ALTER TABLE gold.solicitudes_gold RENAME TO solicitudes;
  END IF;
END
$$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'gold'
      AND table_name = 'comicos'
      AND column_name = 'whatsapp'
  ) AND NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'gold'
      AND table_name = 'comicos'
      AND column_name = 'telefono'
  ) THEN
    ALTER TABLE gold.comicos RENAME COLUMN whatsapp TO telefono;
  END IF;
END
$$;

-- ---------------------------------------------------------
-- ENUMs Gold
-- ---------------------------------------------------------
-- Categoría de negocio para priorización (default: standard).
DO $$
BEGIN
  IF to_regtype('gold.categoria_comico') IS NULL THEN
    CREATE TYPE gold.categoria_comico AS ENUM (
      'standard',
      'priority',
      'gold',
      'restricted'
    );
  END IF;
END
$$;

-- Estado final/operativo de la solicitud para decisiones de lineup.
DO $$
BEGIN
  IF to_regtype('gold.estado_solicitud') IS NULL THEN
    CREATE TYPE gold.estado_solicitud AS ENUM (
      'pendiente',
      'aceptado',
      'rechazado',
      'cancelado',
      'expirado'
    );
  END IF;
END
$$;

-- ---------------------------------------------------------
-- Tabla maestra de perfiles (nutrida de silver.comicos)
-- ---------------------------------------------------------
create table if not exists gold.comicos (
  -- Linaje: este ID debe venir de silver.comicos.id para mantener trazabilidad.
  id uuid primary key,

  -- Identificadores normalizados de contacto.
  telefono text not null unique,
  instagram text not null unique,

  nombre text,
  genero text not null default 'unknown',
  categoria gold.categoria_comico not null default 'standard',
  fecha_ultima_actuacion date,

  created_at timestamptz not null default now(),
  modified_at timestamptz not null default now(),

  constraint chk_gold_comicos_instagram_normalizado
    check (
      instagram = lower(instagram)
      and left(instagram, 1) <> '@'
    ),

  constraint chk_gold_comicos_telefono_internacional
    check (telefono ~ '^\+[1-9][0-9]{7,14}$')
);

alter table gold.comicos
  add column if not exists genero text;

DO $$
DECLARE
  genero_data_type text;
BEGIN
  SELECT data_type
  INTO genero_data_type
  FROM information_schema.columns
  WHERE table_schema = 'gold'
    AND table_name = 'comicos'
    AND column_name = 'genero';

  IF genero_data_type = 'USER-DEFINED' THEN
    ALTER TABLE gold.comicos
      ALTER COLUMN genero TYPE text
      USING genero::text;
  END IF;
END
$$;

update gold.comicos
set genero = 'unknown'
where genero is null;

alter table gold.comicos
  alter column genero set default 'unknown',
  alter column genero set not null;

-- Índices de lookup para cruce rápido desde Silver por telefono/instagram.
create index if not exists idx_gold_comicos_telefono
  on gold.comicos (telefono);

create index if not exists idx_gold_comicos_instagram
  on gold.comicos (instagram);

create index if not exists idx_gold_comicos_fecha_ultima_actuacion
  on gold.comicos (fecha_ultima_actuacion);

-- ---------------------------------------------------------
-- Historial de solicitudes y scoring (nutrida de silver.solicitudes)
-- ---------------------------------------------------------
create table if not exists gold.solicitudes (
  -- Linaje: este ID debe venir de silver.solicitudes.id.
  id uuid primary key,

  comico_id uuid not null,
  fecha_evento date not null,
  estado gold.estado_solicitud not null default 'pendiente',

  -- Score calculado por el motor de selección.
  score_aplicado double precision,

  -- Orden de llegada original del formulario (Google Forms).
  marca_temporal timestamptz,
  created_at timestamptz not null default now(),

  constraint fk_gold_solicitudes_comico
    foreign key (comico_id)
    references gold.comicos(id)
    on delete cascade
);

create index if not exists idx_gold_solicitudes_comico_fecha
  on gold.solicitudes (comico_id, fecha_evento desc);

create index if not exists idx_gold_solicitudes_estado_fecha
  on gold.solicitudes (estado, fecha_evento desc);

create index if not exists idx_gold_solicitudes_marca_temporal
  on gold.solicitudes (marca_temporal);

-- Índice parcial clave para reglas de “ha actuado recientemente”.
create index if not exists idx_gold_solicitudes_aceptadas_por_comico
  on gold.solicitudes (comico_id, fecha_evento desc)
  where estado = 'aceptado';

-- ---------------------------------------------------------
-- Vista de ayuda de linaje Silver -> Gold
-- ---------------------------------------------------------
-- Esta vista permite cruzar silver.solicitudes con comicos usando
-- telefono o instagram como llave de negocio, para resolver comico_id Gold
-- aun cuando el proceso de carga llegue por distintas rutas.
create or replace view gold.vw_linaje_silver_a_gold as
select
  s.id as solicitud_silver_id,
  s.fecha_evento,
  s.created_at as silver_created_at,
  c.id as comico_gold_id,
  c.telefono,
  c.instagram
from silver.solicitudes s
join silver.comicos sc
  on sc.id = s.comico_id
join gold.comicos c
  on (
    (sc.telefono is not null and sc.telefono = c.telefono)
    or sc.instagram_user = c.instagram
  );

comment on table gold.comicos is
  'Maestra Gold de perfiles. ID heredado de silver.comicos para trazabilidad end-to-end.';

comment on table gold.solicitudes is
  'Histórico Gold de solicitudes + scoring. ID heredado de silver.solicitudes.';

comment on view gold.vw_linaje_silver_a_gold is
  'Cruce operacional entre Silver y Gold por telefono/instagram para resolver linaje de comico_id.';

-- ---------------------------------------------------------
-- Operación y Seguridad Gold (alineado con Bronze/Silver)
-- ---------------------------------------------------------
alter table gold.comicos enable row level security;
alter table gold.solicitudes enable row level security;

drop policy if exists p_service_role_all_gold_comicos on gold.comicos;
create policy p_service_role_all_gold_comicos
on gold.comicos
for all
to service_role
using (true)
with check (true);

drop policy if exists p_service_role_all_gold_solicitudes on gold.solicitudes;
create policy p_service_role_all_gold_solicitudes
on gold.solicitudes
for all
to service_role
using (true)
with check (true);

revoke all on schema gold from public;
revoke usage on schema gold from anon, authenticated;
grant usage on schema gold to service_role;
grant select, insert, update, delete on all tables in schema gold to service_role;
alter default privileges in schema gold
  grant select, insert, update, delete on tables to service_role;
