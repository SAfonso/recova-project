-- =========================================================
-- Migración: sincronizar estados de validación LineUp (Gold/Silver)
-- Fecha: 2026-02-17
-- =========================================================

ALTER TABLE gold.comicos
  ADD COLUMN IF NOT EXISTS score_actual double precision;

ALTER TYPE gold.estado_solicitud ADD VALUE IF NOT EXISTS 'scorado';
ALTER TYPE gold.estado_solicitud ADD VALUE IF NOT EXISTS 'aprobado';
ALTER TYPE gold.estado_solicitud ADD VALUE IF NOT EXISTS 'no_seleccionado';

UPDATE gold.solicitudes
SET estado = 'scorado'
WHERE estado = 'pendiente';

UPDATE gold.solicitudes
SET estado = 'aprobado'
WHERE estado = 'aceptado';

DROP VIEW IF EXISTS gold.lineup_candidates;

CREATE OR REPLACE VIEW gold.lineup_candidates AS
SELECT
  s.id AS solicitud_id,
  s.fecha_evento,
  s.estado,
  c.nombre,
  c.genero,
  c.categoria,
  c.score_actual,
  s.score_aplicado AS score_final,
  c.id AS comico_id,
  COALESCE(c.telefono, c.instagram) AS contacto,
  c.telefono,
  c.instagram
FROM gold.solicitudes s
JOIN gold.comicos c ON c.id = s.comico_id;

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

  DROP TABLE IF EXISTS tmp_payload_entries;
  DROP TABLE IF EXISTS tmp_accepted_gold;

  CREATE TEMP TABLE tmp_payload_entries ON COMMIT DROP AS
  SELECT
    NULLIF(entry->>'solicitud_id', '')::uuid AS solicitud_id,
    NULLIF(entry->>'comico_id', '')::uuid AS comico_id,
    NULLIF(entry->>'categoria', '') AS categoria,
    NULLIF(entry->>'genero', '') AS genero,
    NULLIF(entry->>'fecha_evento', '')::date AS fecha_evento
  FROM jsonb_array_elements(p_selection) AS entry;

  CREATE TEMP TABLE tmp_accepted_gold (
    id uuid,
    comico_id uuid,
    fecha_evento date
  ) ON COMMIT DROP;

  WITH accepted_gold AS (
    UPDATE gold.solicitudes AS s
    SET estado = 'aprobado'
    WHERE s.estado IN ('scorado', 'pendiente')
      AND EXISTS (
        SELECT 1
        FROM tmp_payload_entries pe
        WHERE (
          pe.solicitud_id IS NOT NULL
          AND pe.solicitud_id = s.id
        ) OR (
          pe.solicitud_id IS NULL
          AND pe.comico_id IS NOT NULL
          AND pe.comico_id = s.comico_id
          AND (
            (pe.fecha_evento IS NOT NULL AND s.fecha_evento = pe.fecha_evento)
            OR (pe.fecha_evento IS NULL AND p_event_date IS NOT NULL AND s.fecha_evento = p_event_date)
            OR (pe.fecha_evento IS NULL AND p_event_date IS NULL)
          )
        )
      )
    RETURNING s.id, s.comico_id, s.fecha_evento
  )
  INSERT INTO tmp_accepted_gold (id, comico_id, fecha_evento)
  SELECT id, comico_id, fecha_evento
  FROM accepted_gold;

  UPDATE gold.solicitudes AS s
  SET estado = 'no_seleccionado'
  WHERE s.estado IN ('scorado', 'pendiente')
    AND s.fecha_evento IN (
      SELECT DISTINCT fecha_evento
      FROM tmp_accepted_gold
      UNION
      SELECT DISTINCT COALESCE(pe.fecha_evento, p_event_date)
      FROM tmp_payload_entries pe
      WHERE COALESCE(pe.fecha_evento, p_event_date) IS NOT NULL
    )
    AND NOT EXISTS (
      SELECT 1
      FROM tmp_accepted_gold ag
      WHERE ag.id = s.id
    );

  UPDATE silver.solicitudes AS ss
  SET status = 'aprobado',
      updated_at = now()
  WHERE ss.id IN (SELECT id FROM tmp_accepted_gold)
     OR (
       ss.fecha_evento = p_event_date
       AND ss.comico_id IN (
         SELECT comico_id
         FROM tmp_payload_entries
         WHERE solicitud_id IS NULL
           AND comico_id IS NOT NULL
       )
     );

  UPDATE silver.solicitudes AS ss
  SET status = 'no_seleccionado',
      updated_at = now()
  WHERE ss.status IN ('scorado', 'normalizado')
    AND ss.fecha_evento IN (
      SELECT DISTINCT fecha_evento
      FROM tmp_accepted_gold
      UNION
      SELECT DISTINCT COALESCE(pe.fecha_evento, p_event_date)
      FROM tmp_payload_entries pe
      WHERE COALESCE(pe.fecha_evento, p_event_date) IS NOT NULL
    )
    AND NOT EXISTS (
      SELECT 1
      FROM tmp_accepted_gold ag
      WHERE ag.id = ss.id
    );

  UPDATE gold.comicos AS gc
  SET
    categoria = COALESCE((entry.categoria)::gold.categoria_comico, gc.categoria),
    genero = COALESCE(entry.genero, gc.genero),
    fecha_ultima_actuacion = COALESCE(entry.fecha_evento, p_event_date, gc.fecha_ultima_actuacion),
    modified_at = now()
  FROM (
    SELECT DISTINCT comico_id, categoria, genero, fecha_evento
    FROM tmp_payload_entries
    WHERE comico_id IS NOT NULL
  ) AS entry
  WHERE gc.id = entry.comico_id;

  UPDATE silver.comicos AS sc
  SET
    categoria = CASE entry.categoria
      WHEN 'priority' THEN 'priority'::silver.tipo_categoria
      WHEN 'gold' THEN 'gold'::silver.tipo_categoria
      WHEN 'restricted' THEN 'restricted'::silver.tipo_categoria
      WHEN 'standard' THEN 'general'::silver.tipo_categoria
      ELSE sc.categoria
    END,
    genero = COALESCE(entry.genero, sc.genero),
    updated_at = now()
  FROM (
    SELECT DISTINCT comico_id, categoria, genero
    FROM tmp_payload_entries
    WHERE comico_id IS NOT NULL
  ) AS entry
  WHERE sc.id = entry.comico_id;

  UPDATE gold.comicos AS gc
  SET score_actual = latest.score_aplicado
  FROM (
    SELECT DISTINCT ON (s.comico_id)
      s.comico_id,
      s.score_aplicado
    FROM gold.solicitudes s
    WHERE s.score_aplicado IS NOT NULL
    ORDER BY s.comico_id, s.fecha_evento DESC, s.created_at DESC
  ) AS latest
  WHERE gc.id = latest.comico_id;

  -- Corrección de consistencia histórica:
  -- si la solicitud ya existe en Gold pero quedó como normalizado, se normaliza a scorado.
  UPDATE silver.solicitudes AS ss
  SET status = 'scorado',
      updated_at = now()
  WHERE ss.status = 'normalizado'
    AND EXISTS (
      SELECT 1
      FROM gold.solicitudes gs
      WHERE gs.id = ss.id
    );
END;
$$;

GRANT SELECT ON gold.lineup_candidates TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION gold.validate_lineup(jsonb, date) TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA gold TO anon, authenticated;
