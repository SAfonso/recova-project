-- =========================================================
-- Migración: vista de candidatos + validación atómica de lineup
-- Fecha: 2026-02-18
-- =========================================================

CREATE OR REPLACE VIEW gold.lineup_candidates AS
SELECT
  c.nombre,
  c.genero,
  c.categoria,
  s.estado,
  s.score_aplicado AS score_final,
  c.id AS comico_id,
  COALESCE(c.telefono, c.instagram) AS contacto,
  c.telefono,
  c.instagram
FROM gold.solicitudes s
JOIN gold.comicos c ON c.id = s.comico_id;

ALTER TYPE gold.estado_solicitud ADD VALUE IF NOT EXISTS 'scorado';
ALTER TYPE gold.estado_solicitud ADD VALUE IF NOT EXISTS 'aprobado';
ALTER TYPE gold.estado_solicitud ADD VALUE IF NOT EXISTS 'no_seleccionado';

CREATE OR REPLACE FUNCTION gold.validate_lineup(
  p_selection jsonb,
  p_event_date date
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = gold, silver, public
AS $$
DECLARE
  selected_count integer;
BEGIN
  selected_count := COALESCE(jsonb_array_length(p_selection), 0);

  IF selected_count <> 5 THEN
    RAISE EXCEPTION 'Se requieren exactamente 5 cómicos para validar (actual: %).', selected_count;
  END IF;

  UPDATE gold.solicitudes AS s
  SET estado = 'aprobado'
  WHERE s.comico_id IN (
    SELECT (entry->>'comico_id')::uuid
    FROM jsonb_array_elements(p_selection) AS entry
  )
    AND s.fecha_evento = p_event_date
    AND s.estado IN ('scorado', 'pendiente');

  UPDATE gold.solicitudes AS s
  SET estado = 'no_seleccionado'
  WHERE s.fecha_evento = p_event_date
    AND s.estado IN ('scorado', 'pendiente')
    AND s.comico_id NOT IN (
      SELECT (entry->>'comico_id')::uuid
      FROM jsonb_array_elements(p_selection) AS entry
    );

  UPDATE gold.comicos AS gc
  SET
    categoria = COALESCE((entry->>'categoria')::gold.categoria_comico, gc.categoria),
    genero = COALESCE(entry->>'genero', gc.genero),
    fecha_ultima_actuacion = p_event_date,
    modified_at = now()
  FROM jsonb_array_elements(p_selection) AS entry
  WHERE gc.id = (entry->>'comico_id')::uuid;

  UPDATE silver.comicos AS sc
  SET
    categoria = CASE entry->>'categoria'
      WHEN 'priority' THEN 'priority'::silver.tipo_categoria
      WHEN 'gold' THEN 'gold'::silver.tipo_categoria
      WHEN 'restricted' THEN 'restricted'::silver.tipo_categoria
      ELSE sc.categoria
    END,
    genero = COALESCE(entry->>'genero', sc.genero),
    updated_at = now()
  FROM jsonb_array_elements(p_selection) AS entry
  WHERE sc.id = (entry->>'comico_id')::uuid;

  UPDATE silver.solicitudes AS ss
  SET status = 'aprobado',
      updated_at = now()
  WHERE ss.fecha_evento = p_event_date
    AND ss.comico_id IN (
      SELECT (entry->>'comico_id')::uuid
      FROM jsonb_array_elements(p_selection) AS entry
    );

  UPDATE silver.solicitudes AS ss
  SET status = 'no_seleccionado',
      updated_at = now()
  WHERE ss.fecha_evento = p_event_date
    AND ss.status IN ('scorado', 'normalizado')
    AND ss.comico_id NOT IN (
      SELECT (entry->>'comico_id')::uuid
      FROM jsonb_array_elements(p_selection) AS entry
    );
END;
$$;

GRANT SELECT ON gold.lineup_candidates TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION gold.validate_lineup(jsonb, date) TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA gold TO anon, authenticated;
