-- =========================================================
-- Migración: sincronizar estados de validación LineUp (Gold/Silver)
-- Fecha: 2026-02-17
-- =========================================================

CREATE OR REPLACE VIEW gold.lineup_candidates AS
SELECT
  s.id AS solicitud_id,
  s.fecha_evento,
  s.estado,
  c.nombre,
  c.genero,
  c.categoria,
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

  WITH payload_entries AS (
    SELECT
      NULLIF(entry->>'solicitud_id', '')::uuid AS solicitud_id,
      NULLIF(entry->>'comico_id', '')::uuid AS comico_id,
      NULLIF(entry->>'categoria', '') AS categoria,
      NULLIF(entry->>'genero', '') AS genero
    FROM jsonb_array_elements(p_selection) AS entry
  ),
  accepted_gold AS (
    UPDATE gold.solicitudes AS s
    SET estado = 'aceptado'
    WHERE s.estado = 'pendiente'
      AND (
        s.id IN (
          SELECT solicitud_id
          FROM payload_entries
          WHERE solicitud_id IS NOT NULL
        )
        OR (
          s.fecha_evento = p_event_date
          AND s.comico_id IN (
            SELECT comico_id
            FROM payload_entries
            WHERE solicitud_id IS NULL
              AND comico_id IS NOT NULL
          )
        )
      )
    RETURNING s.id, s.comico_id, s.fecha_evento
  )
  UPDATE silver.solicitudes AS ss
  SET status = 'aprobado',
      updated_at = now()
  WHERE ss.id IN (SELECT id FROM accepted_gold)
     OR (
       ss.fecha_evento = p_event_date
       AND ss.comico_id IN (
         SELECT comico_id
         FROM payload_entries
         WHERE solicitud_id IS NULL
           AND comico_id IS NOT NULL
       )
     );

  UPDATE gold.comicos AS gc
  SET
    categoria = COALESCE((entry.categoria)::gold.categoria_comico, gc.categoria),
    genero = COALESCE(entry.genero, gc.genero),
    fecha_ultima_actuacion = p_event_date,
    modified_at = now()
  FROM (
    SELECT DISTINCT comico_id, categoria, genero
    FROM (
      SELECT
        NULLIF(entry->>'comico_id', '')::uuid AS comico_id,
        NULLIF(entry->>'categoria', '') AS categoria,
        NULLIF(entry->>'genero', '') AS genero
      FROM jsonb_array_elements(p_selection) AS entry
    ) dedup
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
    FROM (
      SELECT
        NULLIF(entry->>'comico_id', '')::uuid AS comico_id,
        NULLIF(entry->>'categoria', '') AS categoria,
        NULLIF(entry->>'genero', '') AS genero
      FROM jsonb_array_elements(p_selection) AS entry
    ) dedup
    WHERE comico_id IS NOT NULL
  ) AS entry
  WHERE sc.id = entry.comico_id;
END;
$$;

GRANT SELECT ON gold.lineup_candidates TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION gold.validate_lineup(jsonb, date) TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA gold TO anon, authenticated;
