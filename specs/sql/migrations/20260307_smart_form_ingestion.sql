-- =========================================================
-- Migración: Smart Form Ingestion
-- Fecha: 2026-03-07
-- Sprint 9 — Smart Form Ingestion (v0.14.0)
-- =========================================================
-- Cambios:
--   1. silver.solicitudes.metadata — campos no canónicos del form
--   2. silver.update_open_mic_config_keys — merge seguro de claves JSONB en config
-- =========================================================


-- ---------------------------------------------------------
-- 1. Columna metadata en silver.solicitudes
-- ---------------------------------------------------------
-- Almacena los campos del form que no tienen mapeo al schema canónico.
-- Clave = título de la pregunta en el form, valor = respuesta del cómico.
-- Ejemplo: {"¿De dónde eres?": "Madrid", "¿Tienes redes sociales?": "TikTok: @juan"}

ALTER TABLE silver.solicitudes
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

COMMENT ON COLUMN silver.solicitudes.metadata IS
  'Campos del form sin mapeo al schema canónico. '
  'Clave = título pregunta, valor = respuesta. '
  'Poblado por FormIngestor (Sprint 9).';


-- ---------------------------------------------------------
-- 2. RPC silver.update_open_mic_config_keys
-- ---------------------------------------------------------
-- Hace merge de p_keys en el JSONB config del open mic indicado.
-- Usa el operador || para sobreescribir solo las claves enviadas
-- sin tocar el resto de la config (scoring, poster, form, etc.)
--
-- Claves que escribe Sprint 9:
--   config.field_mapping    — { "título pregunta" → "campo_canónico" | null }
--   config.external_form_id — form_id del Google Form externo del host
--   config.scoring_type     — 'none' | 'basic' | 'custom'  (escrito desde frontend)

CREATE OR REPLACE FUNCTION silver.update_open_mic_config_keys(
  p_open_mic_id uuid,
  p_keys        jsonb
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = silver, public
AS $$
  UPDATE silver.open_mics
  SET    config = COALESCE(config, '{}'::jsonb) || p_keys
  WHERE  id = p_open_mic_id;
$$;

GRANT EXECUTE ON FUNCTION silver.update_open_mic_config_keys(uuid, jsonb)
  TO authenticated, service_role;
