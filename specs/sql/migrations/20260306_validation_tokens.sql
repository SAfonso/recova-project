-- =========================================================
-- Migracion: silver.validation_tokens
-- Fecha: 2026-03-06
-- Sprint: 5 — Lineup Validation via Telegram
-- =========================================================
-- Tokens temporales para autenticar la vista standalone de validacion.
-- Expiran cuando empieza el show (expires_at = show datetime).
-- =========================================================

CREATE TABLE IF NOT EXISTS silver.validation_tokens (
  token        uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  host_id      uuid        NOT NULL,
  open_mic_id  uuid        NOT NULL,
  fecha_evento date        NOT NULL,
  expires_at   timestamptz NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE silver.validation_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_service_role_all_validation_tokens ON silver.validation_tokens;
CREATE POLICY p_service_role_all_validation_tokens
  ON silver.validation_tokens FOR ALL TO service_role
  USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, DELETE ON silver.validation_tokens TO service_role;

-- Limpieza periodica de tokens expirados (ejecutar manualmente o via cron):
-- DELETE FROM silver.validation_tokens WHERE expires_at < now();
