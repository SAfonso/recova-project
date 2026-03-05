-- =========================================================
-- Migración: tabla silver.lineup_slots + RPCs de confirmación
-- Fecha: 2026-03-05
-- =========================================================

-- 1) Tabla silver.lineup_slots
CREATE TABLE IF NOT EXISTS silver.lineup_slots (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  open_mic_id   uuid        NOT NULL,
  fecha_evento  date        NOT NULL,
  solicitud_id  uuid        NOT NULL,
  slot_order    int2        NOT NULL,
  status        text        NOT NULL DEFAULT 'confirmed',
  created_at    timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_lineup_slots_open_mic_fecha_solicitud
    UNIQUE (open_mic_id, fecha_evento, solicitud_id)
);

CREATE INDEX IF NOT EXISTS idx_lineup_slots_open_mic_fecha
  ON silver.lineup_slots (open_mic_id, fecha_evento);

-- RLS
ALTER TABLE silver.lineup_slots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_service_role_all_lineup_slots ON silver.lineup_slots;
CREATE POLICY p_service_role_all_lineup_slots
  ON silver.lineup_slots FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_authenticated_select_lineup_slots ON silver.lineup_slots;
CREATE POLICY p_authenticated_select_lineup_slots
  ON silver.lineup_slots FOR SELECT TO authenticated
  USING (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON silver.lineup_slots TO service_role;
GRANT SELECT ON silver.lineup_slots TO authenticated;
GRANT USAGE ON SCHEMA silver TO authenticated;

-- =========================================================
-- 2) RPC upsert_confirmed_lineup
-- =========================================================
CREATE OR REPLACE FUNCTION silver.upsert_confirmed_lineup(
  p_open_mic_id             uuid,
  p_fecha_evento            date,
  p_approved_solicitud_ids  uuid[]
)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = silver, public
AS $$
DECLARE
  v_count int;
BEGIN
  -- Borra slots existentes para este open_mic + fecha
  DELETE FROM silver.lineup_slots
  WHERE open_mic_id = p_open_mic_id
    AND fecha_evento = p_fecha_evento;

  -- Inserta un slot por cada solicitud aprobada
  INSERT INTO silver.lineup_slots (open_mic_id, fecha_evento, solicitud_id, slot_order, status)
  SELECT
    p_open_mic_id,
    p_fecha_evento,
    unnested.solicitud_id,
    ordinality::int2,
    'confirmed'
  FROM unnest(p_approved_solicitud_ids) WITH ORDINALITY AS unnested(solicitud_id, ordinality);

  v_count := array_length(p_approved_solicitud_ids, 1);
  RETURN COALESCE(v_count, 0);
END;
$$;

GRANT EXECUTE ON FUNCTION silver.upsert_confirmed_lineup(uuid, date, uuid[])
  TO authenticated, service_role;

-- =========================================================
-- 3) RPC reset_lineup_slots
-- =========================================================
CREATE OR REPLACE FUNCTION silver.reset_lineup_slots(
  p_open_mic_id   uuid,
  p_fecha_evento  date
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = silver, public
AS $$
BEGIN
  DELETE FROM silver.lineup_slots
  WHERE open_mic_id = p_open_mic_id
    AND fecha_evento = p_fecha_evento;
END;
$$;

GRANT EXECUTE ON FUNCTION silver.reset_lineup_slots(uuid, date)
  TO authenticated, service_role;
