-- Migración: añade open_mic_id y solicitud_id a lineup_candidates
-- Necesario para aislamiento multi-tenant: el frontend filtra por open_mic_id
-- y solo ve candidatos del open mic seleccionado.

DROP VIEW IF EXISTS gold.lineup_candidates;

CREATE VIEW gold.lineup_candidates AS
SELECT
  s.id              AS solicitud_id,
  s.open_mic_id,
  s.fecha_evento,
  s.estado,
  s.score_aplicado  AS score_final,
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
