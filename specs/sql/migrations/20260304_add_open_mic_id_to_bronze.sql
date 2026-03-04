-- Migración: añadir open_mic_id a bronze.solicitudes
-- Nullable para compatibilidad con registros legacy (pre-v3).

ALTER TABLE bronze.solicitudes
  ADD COLUMN IF NOT EXISTS open_mic_id uuid;

CREATE INDEX IF NOT EXISTS idx_bronze_solicitudes_open_mic_id
  ON bronze.solicitudes (open_mic_id)
  WHERE open_mic_id IS NOT NULL;
