-- Migración: corregir security model de gold.lineup_candidates
-- Problema: la vista corría con permisos del owner (SECURITY DEFINER implícito),
--           bypasseando RLS de gold.solicitudes y gold.comicos.
-- Fix: recrear con security_invoker = on para que respete RLS del usuario llamante.
-- Fecha: 2026-03-12

DROP VIEW IF EXISTS gold.lineup_candidates;

CREATE VIEW gold.lineup_candidates
  WITH (security_invoker = on)
AS
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
