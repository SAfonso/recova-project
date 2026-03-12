-- =========================================================
-- Migración: flag puede_hoy en gold.solicitudes
-- Fecha: 2026-03-12
-- Sprint 14 — Last-Minute Flag (v0.19.0)
-- =========================================================
-- Cambios:
--   1. gold.solicitudes.puede_hoy — boolean; true si el cómico
--      respondió que está disponible a última hora en el formulario.
--   2. gold.lineup_candidates — incluye puede_hoy.
--   3. Backfill de registros existentes desde silver.solicitudes.metadata.
-- =========================================================


-- ---------------------------------------------------------
-- 1. Columna puede_hoy en gold.solicitudes
-- ---------------------------------------------------------
ALTER TABLE gold.solicitudes
  ADD COLUMN IF NOT EXISTS puede_hoy boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN gold.solicitudes.puede_hoy IS
  'True si el cómico indicó disponibilidad de última hora en el formulario '
  '(campo canónico backup). Usado para destacarlos en edición de lineup el '
  'día del show o el día anterior. No influye en el scoring.';


-- ---------------------------------------------------------
-- 2. Backfill desde silver.solicitudes.metadata
-- ---------------------------------------------------------
-- Detecta respuestas afirmativas en el campo 'backup' de metadata.
-- Acepta: 'sí', 'si', 'yes', 'true', '1' (case-insensitive).

UPDATE gold.solicitudes gs
SET    puede_hoy = true
FROM   silver.solicitudes ss
WHERE  ss.id = gs.id
  AND  LOWER(TRIM(ss.metadata->>'backup')) IN ('sí', 'si', 'yes', 'true', '1');


-- ---------------------------------------------------------
-- 3. Vista gold.lineup_candidates — añade puede_hoy
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
