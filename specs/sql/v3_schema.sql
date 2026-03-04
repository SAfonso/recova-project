-- =============================================================================
-- AI LineUp Architect — Extensión v3 SaaS Multi-Tenant sobre Medallion
-- PostgreSQL / Supabase SQL Script
-- =============================================================================
-- Estrategia: NO reescribir el Medallion existente (Bronze/Silver/Gold).
-- Extender Silver con identidad multi-tenant y propagar open_mic_id a Gold.
--
-- Capas afectadas:
--   · silver.proveedores    → ya es "organización", añadimos slug + auth-ready
--   · silver.organization_members (NEW) → auth.users ↔ proveedores
--   · silver.open_mics      (NEW) → N open mics por proveedor, config JSONB
--   · silver.solicitudes    → +open_mic_id (nullable, backwards compatible)
--   · gold.solicitudes      → +open_mic_id (nullable, backwards compatible)
--   · RLS Silver            → Host lee/escribe solo sus open mics y solicitudes
--   · RLS Gold              → Host lee solo sus solicitudes y cómicos asociados
--   · confirm_lineup()      (NEW) → RPC atómica de confirmación de lineup
--
-- Convenciones:
--   · Todos los cambios son idempotentes (IF NOT EXISTS, DO $$ ... END $$)
--   · Los campos nuevos son nullable para no romper inserciones legacy
--   · lineup_slots.status = 'confirmed' es la única fuente de verdad de "actuó"
--   · La penalización de recencia se scopes por open_mic_id, no globalmente
-- =============================================================================


-- ---------------------------------------------------------------------------
-- 0. EXTENSIONES (idempotente)
-- ---------------------------------------------------------------------------
create extension if not exists pgcrypto;


-- ---------------------------------------------------------------------------
-- 1. EXTENDER silver.proveedores → organización multi-tenant
--    Ya existe. Añadimos slug único y form_contact para el futuro.
-- ---------------------------------------------------------------------------

-- slug: identificador URL-friendly de la organización
alter table silver.proveedores
  add column if not exists slug text;

-- Rellenar slug con el nombre en snake_case donde esté vacío
update silver.proveedores
set slug = lower(regexp_replace(trim(nombre_comercial), '[^a-z0-9]+', '-', 'g'))
where slug is null;

-- Índice único sobre slug (se aplica solo a rows con slug no nulo por ahora)
create unique index if not exists uq_silver_proveedores_slug
  on silver.proveedores (slug)
  where slug is not null;


-- ---------------------------------------------------------------------------
-- 2. silver.organization_members (NEW)
--    Tabla pivote: un auth.user puede gestionar 1..N proveedores (salas).
--    Un proveedor puede tener varios miembros (hosts + admins).
-- ---------------------------------------------------------------------------

do $$
begin
  if to_regtype('silver.org_role') is null then
    create type silver.org_role as enum ('host', 'admin');
  end if;
end
$$;

create table if not exists silver.organization_members (
  id              uuid primary key default gen_random_uuid(),
  proveedor_id    uuid not null
                    references silver.proveedores(id) on delete cascade,
  user_id         uuid not null,   -- auth.users(id) — FK no declarada para evitar
                                   -- dependencia cross-schema con Supabase auth
  role            silver.org_role not null default 'host',
  created_at      timestamptz not null default now(),

  constraint uq_org_member unique (proveedor_id, user_id)
);

create index if not exists idx_org_members_user_id
  on silver.organization_members (user_id);

create index if not exists idx_org_members_proveedor_id
  on silver.organization_members (proveedor_id);

alter table silver.organization_members enable row level security;

-- Host sólo ve su propia membresía
drop policy if exists p_org_members_select on silver.organization_members;
create policy p_org_members_select
  on silver.organization_members for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists p_org_members_service_role on silver.organization_members;
create policy p_org_members_service_role
  on silver.organization_members for all
  to service_role
  using (true) with check (true);

grant usage on schema silver to authenticated;
grant select on silver.organization_members to authenticated;


-- ---------------------------------------------------------------------------
-- 3. silver.open_mics (NEW)
--    Un proveedor tiene N open mics (distintos días, formatos, etc.).
--    config JSONB es la fuente de verdad de las reglas de scoring.
--    form_token es el slug público del formulario de inscripción.
--
--    Estructura de config JSONB (referencia — no enforced por DB):
--    {
--      "available_slots": 8,
--      "categories": {
--        "standard":   {"base_score": 50, "enabled": true},
--        "priority":   {"base_score": 70, "enabled": true},
--        "gold":       {"base_score": 90, "enabled": true},
--        "restricted": {"base_score": null, "enabled": true}
--      },
--      "recency_penalty": {
--        "enabled": true,
--        "last_n_editions": 2,
--        "penalty_points": 20
--      },
--      "single_date_boost": {
--        "enabled": true,
--        "boost_points": 10
--      },
--      "gender_parity": {
--        "enabled": false,
--        "target_female_nb_pct": 40
--      }
--    }
-- ---------------------------------------------------------------------------

create table if not exists silver.open_mics (
  id              uuid primary key default gen_random_uuid(),
  proveedor_id    uuid not null
                    references silver.proveedores(id) on delete restrict,
  name            text not null,
  form_token      text not null unique
                    default encode(gen_random_bytes(16), 'hex'),
  config          jsonb not null default '{
    "available_slots": 8,
    "categories": {
      "standard":   {"base_score": 50, "enabled": true},
      "priority":   {"base_score": 70, "enabled": true},
      "gold":       {"base_score": 90, "enabled": true},
      "restricted": {"base_score": null, "enabled": true}
    },
    "recency_penalty": {
      "enabled": true,
      "last_n_editions": 2,
      "penalty_points": 20
    },
    "single_date_boost": {
      "enabled": true,
      "boost_points": 10
    },
    "gender_parity": {
      "enabled": false,
      "target_female_nb_pct": 40
    }
  }'::jsonb,
  active          boolean not null default true,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists idx_open_mics_proveedor_id
  on silver.open_mics (proveedor_id);

create index if not exists idx_open_mics_form_token
  on silver.open_mics (form_token);

drop trigger if exists trg_open_mics_updated_at on silver.open_mics;
create trigger trg_open_mics_updated_at
  before update on silver.open_mics
  for each row execute function public.set_updated_at();

alter table silver.open_mics enable row level security;

-- Host lee los open_mics de su proveedor
drop policy if exists p_open_mics_select_own on silver.open_mics;
create policy p_open_mics_select_own
  on silver.open_mics for select
  to authenticated
  using (
    proveedor_id in (
      select proveedor_id from silver.organization_members
      where user_id = auth.uid()
    )
  );

-- Host puede actualizar config de sus open_mics (toggles, scoring rules)
drop policy if exists p_open_mics_update_own on silver.open_mics;
create policy p_open_mics_update_own
  on silver.open_mics for update
  to authenticated
  using (
    proveedor_id in (
      select proveedor_id from silver.organization_members
      where user_id = auth.uid()
    )
  )
  with check (
    proveedor_id in (
      select proveedor_id from silver.organization_members
      where user_id = auth.uid()
    )
  );

-- Acceso anónimo: solo lectura para open_mics activos (formulario público)
drop policy if exists p_open_mics_anon_active on silver.open_mics;
create policy p_open_mics_anon_active
  on silver.open_mics for select
  to anon
  using (active = true);

drop policy if exists p_open_mics_service_role on silver.open_mics;
create policy p_open_mics_service_role
  on silver.open_mics for all
  to service_role
  using (true) with check (true);

grant select, update on silver.open_mics to authenticated;
grant select on silver.open_mics to anon;


-- ---------------------------------------------------------------------------
-- 4. EXTENDER silver.solicitudes → añadir open_mic_id
--    Nullable para no romper el pipeline legacy (Bronze→Silver sin open_mic).
--    Las solicitudes nuevas (formulario web v3) siempre llevarán open_mic_id.
-- ---------------------------------------------------------------------------

alter table silver.solicitudes
  add column if not exists open_mic_id uuid
    references silver.open_mics(id) on delete restrict;

create index if not exists idx_silver_solicitudes_open_mic_id
  on silver.solicitudes (open_mic_id);

-- Índice compuesto clave para scoring engine: solicitudes de un open_mic en una fecha
create index if not exists idx_silver_solicitudes_open_mic_fecha
  on silver.solicitudes (open_mic_id, fecha_evento)
  where open_mic_id is not null;

-- RLS Silver: Host ve solicitudes de sus open_mics
drop policy if exists p_silver_solicitudes_auth_select on silver.solicitudes;
create policy p_silver_solicitudes_auth_select
  on silver.solicitudes for select
  to authenticated
  using (
    open_mic_id in (
      select om.id from silver.open_mics om
      join silver.organization_members mb
        on mb.proveedor_id = om.proveedor_id
      where mb.user_id = auth.uid()
    )
  );

-- Host puede actualizar score/status de solicitudes de sus open_mics
drop policy if exists p_silver_solicitudes_auth_update on silver.solicitudes;
create policy p_silver_solicitudes_auth_update
  on silver.solicitudes for update
  to authenticated
  using (
    open_mic_id in (
      select om.id from silver.open_mics om
      join silver.organization_members mb
        on mb.proveedor_id = om.proveedor_id
      where mb.user_id = auth.uid()
    )
  )
  with check (true);

grant select, update on silver.solicitudes to authenticated;


-- ---------------------------------------------------------------------------
-- 5. EXTENDER gold.solicitudes → añadir open_mic_id
--    Nullable para compatibilidad con datos históricos pre-v3.
--    Permite RLS directo sin joins costosos a Silver.
-- ---------------------------------------------------------------------------

alter table gold.solicitudes
  add column if not exists open_mic_id uuid;  -- no FK a silver para evitar
                                               -- dependencia cross-schema en DDL

-- Poblar open_mic_id en gold a partir del linaje silver cuando sea posible
-- (se ejecuta una sola vez; rows sin match en silver quedan null)
update gold.solicitudes gs
set open_mic_id = ss.open_mic_id
from silver.solicitudes ss
where ss.id = gs.id
  and ss.open_mic_id is not null
  and gs.open_mic_id is null;

create index if not exists idx_gold_solicitudes_open_mic_id
  on gold.solicitudes (open_mic_id)
  where open_mic_id is not null;

-- Índice especializado para la penalización de recencia (hot path del scoring)
-- Scoped por open_mic_id + estado aceptado + fecha desc
create index if not exists idx_gold_solicitudes_recency
  on gold.solicitudes (open_mic_id, comico_id, fecha_evento desc)
  where estado in ('aprobado', 'aceptado')
    and open_mic_id is not null;

-- RLS Gold: abrir acceso a authenticated (actualmente solo service_role)
grant usage on schema gold to authenticated;
grant select on gold.solicitudes to authenticated;
grant select on gold.comicos    to authenticated;

-- Host ve gold.solicitudes de sus open_mics
drop policy if exists p_gold_solicitudes_auth_select on gold.solicitudes;
create policy p_gold_solicitudes_auth_select
  on gold.solicitudes for select
  to authenticated
  using (
    open_mic_id in (
      select om.id from silver.open_mics om
      join silver.organization_members mb
        on mb.proveedor_id = om.proveedor_id
      where mb.user_id = auth.uid()
    )
  );

-- Host ve gold.comicos que tienen solicitudes en sus open_mics
drop policy if exists p_gold_comicos_auth_select on gold.comicos;
create policy p_gold_comicos_auth_select
  on gold.comicos for select
  to authenticated
  using (
    id in (
      select comico_id from gold.solicitudes
      where open_mic_id in (
        select om.id from silver.open_mics om
        join silver.organization_members mb
          on mb.proveedor_id = om.proveedor_id
        where mb.user_id = auth.uid()
      )
    )
  );

-- Mantener acceso total para service_role (no romper pipeline)
drop policy if exists p_service_role_all_gold_solicitudes on gold.solicitudes;
create policy p_service_role_all_gold_solicitudes
  on gold.solicitudes for all
  to service_role
  using (true) with check (true);

drop policy if exists p_service_role_all_gold_comicos on gold.comicos;
create policy p_service_role_all_gold_comicos
  on gold.comicos for all
  to service_role
  using (true) with check (true);


-- ---------------------------------------------------------------------------
-- 6. silver.lineup_slots (NEW)
--    Posiciones del lineup final para un open_mic en una fecha concreta.
--    status = 'confirmed' es la única fuente de verdad de "el cómico actuó".
--    Esto alimenta la penalización de recencia (scoped por open_mic_id).
-- ---------------------------------------------------------------------------

do $$
begin
  if to_regtype('silver.slot_status') is null then
    create type silver.slot_status as enum (
      'proposed',   -- propuesta del engine, pendiente confirmación del host
      'confirmed',  -- actuó (el único estado que cuenta para recencia)
      'removed'     -- quitado por el host en confirm_lineup()
    );
  end if;
end
$$;

create table if not exists silver.lineup_slots (
  id              uuid primary key default gen_random_uuid(),
  open_mic_id     uuid not null
                    references silver.open_mics(id) on delete restrict,
  solicitud_id    uuid not null
                    references silver.solicitudes(id) on delete restrict,
  fecha_evento    date not null,
  slot_order      int2 not null,   -- posición en el lineup (1..N)
  status          silver.slot_status not null default 'proposed',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),

  -- Una solicitud tiene un único slot por fecha
  constraint uq_lineup_slots_solicitud_fecha
    unique (solicitud_id, fecha_evento),

  -- Sin duplicados de posición dentro del mismo open_mic+fecha
  constraint uq_lineup_slots_order_per_mic_fecha
    unique (open_mic_id, fecha_evento, slot_order)
);

create index if not exists idx_lineup_slots_open_mic_id
  on silver.lineup_slots (open_mic_id);

create index if not exists idx_lineup_slots_solicitud_id
  on silver.lineup_slots (solicitud_id);

create index if not exists idx_lineup_slots_fecha
  on silver.lineup_slots (fecha_evento);

-- Índice especializado para la query de recencia (hot path)
create index if not exists idx_lineup_slots_recency
  on silver.lineup_slots (open_mic_id, status, fecha_evento desc)
  where status = 'confirmed';

drop trigger if exists trg_lineup_slots_updated_at on silver.lineup_slots;
create trigger trg_lineup_slots_updated_at
  before update on silver.lineup_slots
  for each row execute function public.set_updated_at();

alter table silver.lineup_slots enable row level security;

-- Host ve los slots de sus open_mics
drop policy if exists p_lineup_slots_auth_select on silver.lineup_slots;
create policy p_lineup_slots_auth_select
  on silver.lineup_slots for select
  to authenticated
  using (
    open_mic_id in (
      select om.id from silver.open_mics om
      join silver.organization_members mb
        on mb.proveedor_id = om.proveedor_id
      where mb.user_id = auth.uid()
    )
  );

drop policy if exists p_lineup_slots_service_role on silver.lineup_slots;
create policy p_lineup_slots_service_role
  on silver.lineup_slots for all
  to service_role
  using (true) with check (true);

grant select on silver.lineup_slots to authenticated;


-- ---------------------------------------------------------------------------
-- 7. RPC: confirm_lineup
--    Confirma atómicamente el lineup de un open_mic para una fecha.
--    - p_approved_ids: solicitud_ids que pasan a 'confirmed'
--    - p_removed_ids:  solicitud_ids que pasan a 'removed'
--    Solo el host autenticado de ese open_mic puede llamarla.
--    Retorna el número de slots marcados como confirmed.
--
--    Importante: solo lineup_slots controla el estado final.
--    gold.solicitudes.estado NO se modifica aquí (lo hace el pipeline Gold).
-- ---------------------------------------------------------------------------

create or replace function public.confirm_lineup(
  p_open_mic_id  uuid,
  p_fecha_evento date,
  p_approved_ids uuid[],
  p_removed_ids  uuid[]
)
returns int
language plpgsql
security definer
as $$
declare
  v_confirmed int := 0;
begin
  -- Verificar que el caller pertenece al proveedor del open_mic
  if not exists (
    select 1
    from silver.open_mics om
    join silver.organization_members mb
      on mb.proveedor_id = om.proveedor_id
    where om.id = p_open_mic_id
      and mb.user_id = auth.uid()
  ) then
    raise exception 'UNAUTHORIZED: user does not manage this open_mic';
  end if;

  -- Marcar aprobados como confirmed
  update silver.lineup_slots
  set    status = 'confirmed',
         updated_at = now()
  where  open_mic_id  = p_open_mic_id
    and  fecha_evento = p_fecha_evento
    and  solicitud_id = any(p_approved_ids);

  get diagnostics v_confirmed = row_count;

  -- Marcar removidos como removed
  update silver.lineup_slots
  set    status = 'removed',
         updated_at = now()
  where  open_mic_id  = p_open_mic_id
    and  fecha_evento = p_fecha_evento
    and  solicitud_id = any(p_removed_ids);

  return v_confirmed;
end;
$$;

-- Solo roles autenticados y service_role pueden llamar confirm_lineup
revoke execute on function public.confirm_lineup(uuid, date, uuid[], uuid[]) from public, anon;
grant  execute on function public.confirm_lineup(uuid, date, uuid[], uuid[])
  to authenticated, service_role;


-- ---------------------------------------------------------------------------
-- 8. VISTAS DE AYUDA
-- ---------------------------------------------------------------------------

-- v_lineup_candidatos: une silver.solicitudes con datos del cómico y su open_mic.
-- Usada por el scoring engine como punto de entrada principal.
create or replace view silver.v_lineup_candidatos as
select
  s.id                                              as solicitud_id,
  s.open_mic_id,
  s.proveedor_id,
  s.fecha_evento,
  s.status,
  s.comico_id,
  c.instagram,
  c.nombre,
  c.genero,
  c.categoria                                       as categoria_global,
  -- la categoria_override (por open_mic) vendrá en la siguiente iteración
  -- cuando silver.solicitudes tenga ese campo
  om.config                                         as open_mic_config,
  om.name                                           as open_mic_name,
  p.nombre_comercial                                as proveedor_nombre
from silver.solicitudes s
join silver.comicos      c  on c.id  = s.comico_id
join silver.open_mics    om on om.id = s.open_mic_id
join silver.proveedores  p  on p.id  = s.proveedor_id
where s.open_mic_id is not null;

-- v_ultimas_ediciones: últimas fechas con lineup confirmed por open_mic.
-- Hot path para calcular la ventana de recencia del scoring engine.
create or replace view silver.v_ultimas_ediciones as
select
  open_mic_id,
  fecha_evento,
  count(*) as total_confirmados
from silver.lineup_slots
where status = 'confirmed'
group by open_mic_id, fecha_evento
order by open_mic_id, fecha_evento desc;

grant select on silver.v_lineup_candidatos to authenticated, service_role;
grant select on silver.v_ultimas_ediciones  to authenticated, service_role;

-- v_gold_lineup_host: vista Gold para el panel del Host.
-- Une gold.solicitudes con gold.comicos, filtrado por open_mic (RLS activo).
create or replace view gold.v_lineup_host as
select
  gs.id                as solicitud_id,
  gs.open_mic_id,
  gs.fecha_evento,
  gs.estado,
  gs.score_aplicado,
  gs.marca_temporal,
  gc.instagram,
  gc.nombre,
  gc.genero,
  gc.categoria,
  gc.score_actual,
  gc.fecha_ultima_actuacion
from gold.solicitudes gs
join gold.comicos      gc on gc.id = gs.comico_id;

grant select on gold.v_lineup_host to authenticated, service_role;


-- ---------------------------------------------------------------------------
-- 9. GRANTS FINALES (resumen consolidado)
-- ---------------------------------------------------------------------------

-- Silver: authenticated puede leer proveedores de su organización
drop policy if exists p_proveedores_auth_select on silver.proveedores;
create policy p_proveedores_auth_select
  on silver.proveedores for select
  to authenticated
  using (
    id in (
      select proveedor_id from silver.organization_members
      where user_id = auth.uid()
    )
  );

grant select on silver.proveedores to authenticated;

-- Asegurar que anon mantiene lo que tenía (formulario legacy)
grant usage  on schema silver to anon;
grant select on silver.comicos      to anon;
grant select, update on silver.comicos to anon;
grant select, update on silver.solicitudes to anon;
