-- =========================================================
-- Migración: fix security advisor warnings
-- Fecha: 2026-03-12
-- Cambios:
--   1. Vistas silver/gold — añadir security_invoker = on
--   2. public.set_updated_at — fijar search_path
--   3. public.confirm_lineup — fijar search_path
-- =========================================================


-- ---------------------------------------------------------
-- 1a. silver.v_lineup_candidatos — security_invoker
-- ---------------------------------------------------------
DROP VIEW IF EXISTS silver.v_lineup_candidatos;

CREATE VIEW silver.v_lineup_candidatos
  WITH (security_invoker = on)
AS
SELECT
  s.id                    AS solicitud_id,
  s.open_mic_id,
  s.proveedor_id,
  s.fecha_evento,
  s.status,
  s.comico_id,
  c.instagram,
  c.nombre,
  c.genero,
  c.categoria             AS categoria_global,
  om.config               AS open_mic_config,
  om.name                 AS open_mic_name,
  p.nombre_comercial      AS proveedor_nombre
FROM silver.solicitudes s
JOIN silver.comicos      c  ON c.id  = s.comico_id
JOIN silver.open_mics    om ON om.id = s.open_mic_id
JOIN silver.proveedores  p  ON p.id  = s.proveedor_id
WHERE s.open_mic_id IS NOT NULL;

GRANT SELECT ON silver.v_lineup_candidatos TO authenticated, service_role;


-- ---------------------------------------------------------
-- 1b. silver.v_ultimas_ediciones — security_invoker
-- ---------------------------------------------------------
DROP VIEW IF EXISTS silver.v_ultimas_ediciones;

CREATE VIEW silver.v_ultimas_ediciones
  WITH (security_invoker = on)
AS
SELECT
  open_mic_id,
  fecha_evento,
  count(*) AS total_confirmados
FROM silver.lineup_slots
WHERE status = 'confirmed'
GROUP BY open_mic_id, fecha_evento
ORDER BY open_mic_id, fecha_evento DESC;

GRANT SELECT ON silver.v_ultimas_ediciones TO authenticated, service_role;


-- ---------------------------------------------------------
-- 1c. gold.v_lineup_host — security_invoker
-- ---------------------------------------------------------
DROP VIEW IF EXISTS gold.v_lineup_host;

CREATE VIEW gold.v_lineup_host
  WITH (security_invoker = on)
AS
SELECT
  gs.id                   AS solicitud_id,
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
FROM gold.solicitudes gs
JOIN gold.comicos gc ON gc.id = gs.comico_id;

GRANT SELECT ON gold.v_lineup_host TO authenticated, service_role;


-- ---------------------------------------------------------
-- 2. public.set_updated_at — fijar search_path vacío
--    Es un trigger puro (solo usa NEW), no necesita esquema.
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;


-- ---------------------------------------------------------
-- 3. public.confirm_lineup — fijar search_path
--    SECURITY DEFINER es intencional (verifica auth.uid()).
--    Solo añadimos SET search_path para evitar search_path injection.
-- ---------------------------------------------------------
CREATE OR REPLACE FUNCTION public.confirm_lineup(
  p_open_mic_id  uuid,
  p_fecha_evento date,
  p_approved_ids uuid[],
  p_removed_ids  uuid[]
)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = silver, public
AS $$
DECLARE
  v_confirmed int := 0;
BEGIN
  -- Verificar que el caller pertenece al proveedor del open_mic
  IF NOT EXISTS (
    SELECT 1
    FROM silver.open_mics om
    JOIN silver.organization_members mb
      ON mb.proveedor_id = om.proveedor_id
    WHERE om.id = p_open_mic_id
      AND mb.user_id = auth.uid()
  ) THEN
    RAISE EXCEPTION 'UNAUTHORIZED: user does not manage this open_mic';
  END IF;

  -- Marcar aprobados como confirmed
  UPDATE silver.lineup_slots
  SET    status = 'confirmed',
         updated_at = now()
  WHERE  open_mic_id  = p_open_mic_id
    AND  fecha_evento = p_fecha_evento
    AND  solicitud_id = ANY(p_approved_ids);

  GET DIAGNOSTICS v_confirmed = ROW_COUNT;

  -- Marcar removidos como removed
  UPDATE silver.lineup_slots
  SET    status = 'removed',
         updated_at = now()
  WHERE  open_mic_id  = p_open_mic_id
    AND  fecha_evento = p_fecha_evento
    AND  solicitud_id = ANY(p_removed_ids);

  RETURN v_confirmed;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.confirm_lineup(uuid, date, uuid[], uuid[]) FROM public, anon;
GRANT  EXECUTE ON FUNCTION public.confirm_lineup(uuid, date, uuid[], uuid[])
  TO authenticated, service_role;
