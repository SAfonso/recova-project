-- =========================================================
-- Migración: asegurar policy UPDATE de anon en silver.comicos
-- Fecha: 2026-02-17
-- Objetivo: reforzar RLS/policy idempotente para updates de anon.
-- =========================================================

ALTER TABLE silver.comicos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "p_anon_update_silver_comicos" ON silver.comicos;

CREATE POLICY "p_anon_update_silver_comicos"
ON silver.comicos FOR UPDATE TO anon
USING (true)
WITH CHECK (true);
