-- =========================================================
-- Migración: silver.telegram_users + silver.telegram_registration_codes
-- Fecha: 2026-03-05
-- Sprint: 3 — Telegram Lineup Agent
-- =========================================================

-- =========================================================
-- 1) Tabla silver.telegram_users
--    Mapea telegram_user_id (bigint) → host_id (uuid)
-- =========================================================

CREATE TABLE IF NOT EXISTS silver.telegram_users (
  telegram_user_id  bigint      PRIMARY KEY,
  host_id           uuid        NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE silver.telegram_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_service_role_all_telegram_users ON silver.telegram_users;
CREATE POLICY p_service_role_all_telegram_users
  ON silver.telegram_users FOR ALL TO service_role
  USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS p_authenticated_select_telegram_users ON silver.telegram_users;
CREATE POLICY p_authenticated_select_telegram_users
  ON silver.telegram_users FOR SELECT TO authenticated
  USING (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON silver.telegram_users TO service_role;
GRANT SELECT ON silver.telegram_users TO authenticated;

-- =========================================================
-- 2) Tabla silver.telegram_registration_codes
--    Códigos temporales para self-registration con QR
--    (futuro — no se usa en el MVP)
-- =========================================================

CREATE TABLE IF NOT EXISTS silver.telegram_registration_codes (
  code        text        PRIMARY KEY,
  host_id     uuid        NOT NULL,
  expires_at  timestamptz NOT NULL DEFAULT now() + interval '15 minutes',
  used        boolean     NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE silver.telegram_registration_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_service_role_all_tg_reg_codes ON silver.telegram_registration_codes;
CREATE POLICY p_service_role_all_tg_reg_codes
  ON silver.telegram_registration_codes FOR ALL TO service_role
  USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON silver.telegram_registration_codes TO service_role;

-- =========================================================
-- 3) Registro manual MVP
--    Instrucciones para registrar un host a mano:
--
--    INSERT INTO silver.telegram_users (telegram_user_id, host_id)
--    VALUES (<telegram_id_del_host>, '<uuid_del_host>');
--
--    Para obtener el telegram_id: enviar cualquier mensaje a @userinfobot
-- =========================================================
