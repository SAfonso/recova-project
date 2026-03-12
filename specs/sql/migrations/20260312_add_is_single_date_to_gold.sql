-- =========================================================
-- Migración: flag is_single_date en gold.solicitudes
-- Fecha: 2026-03-12
-- Sprint 14 — Single Date Priority (v0.19.1)
-- =========================================================
-- Cambios:
--   1. gold.solicitudes.is_single_date — boolean; true si el
--      cómico marcó exactamente una fecha disponible.
--   2. gold.lineup_candidates — incluye is_single_date.
--   3. Backfill de registros existentes.
-- =========================================================


-- ---------------------------------------------------------
-- 1. Columna is_single_date en gold.solicitudes
-- ---------------------------------------------------------
ALTER TABLE gold.solicitudes
  ADD COLUMN IF NOT EXISTS is_single_date boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN gold.solicitudes.is_single_date IS
  'True si el cómico indicó exactamente una fecha disponible. '
  'Cuando single_date_priority_enabled=true en la config, recibe '
  'un bono interno de +40 pts al hacer el scoring. Usado también '
  'para mostrar el badge "Solo puede hoy" en la edición del lineup.';


-- ---------------------------------------------------------
-- 2. Backfill — marcar registros con una sola fecha
-- ---------------------------------------------------------
-- silver.solicitudes almacena fechas como texto en fecha_evento
-- (una sola fecha ISO, no lista). Todos los existentes tienen is_single_date=false
-- por defecto; el motor de scoring lo actualizará correctamente
-- en el próximo ciclo. No hay backfill automático porque las
-- fechas_disponibles no se guardan en gold (solo fecha_evento).


-- ---------------------------------------------------------
-- 3. Vista gold.lineup_candidates — añade is_single_date
-- ---------------------------------------------------------
DROP VIEW IF EXISTS gold.lineup_candidates;

CREATE VIEW gold.lineup_candidates AS
SELECT
  s.id              AS solicitud_id,
  s.open_mic_id,
  s.fecha_evento,
  s.estado,
  s.score_aplicado  AS score_final,
  s.puede_hoy,
  s.is_single_date,
  c.id              AS comico_id,
  c.nombre,
  c.genero,
  c.categoria,
  COALESCE(c.telefono, c.instagram) AS contacto,
  c.telefono,
  c.instagram
FROM gold.solicitudes s
JOIN gold.comicos c ON c.id = s.comico_id;

GRANT SELECT ON gold.lineup_candidates TO anon, authenticated, service_role;
