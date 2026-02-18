-- =========================================================
-- Migración: eliminar score_final de silver.solicitudes
-- Fecha: 2026-02-17
-- =========================================================

ALTER TABLE silver.solicitudes
  DROP COLUMN IF EXISTS score_final;
