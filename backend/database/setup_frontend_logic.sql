-- =============================================================
-- AI LineUp Architect - Frontend DB Logic Setup
-- Este script crea la vista y la función RPC necesarias para App.jsx.
-- Es idempotente para que pueda ejecutarse múltiples veces sin colisiones.
-- =============================================================

-- =============================================================
-- 1) Limpieza de seguridad
-- Elimina objetos previos para evitar errores por "already exists".
-- =============================================================
DROP VIEW IF EXISTS gold.lineup_candidates;
DROP FUNCTION IF EXISTS gold.validate_lineup(JSONB[], DATE);

-- =============================================================
-- 2) Vista de candidatos para el frontend
-- Fuente: unión entre solicitudes (gold.solicitudes) y cómicos (gold.comicos)
-- Filtro: solo solicitudes pendientes
-- Campos esperados por App.jsx:
--   nombre, genero, categoria, score_final, comico_id, telefono, instagram, fecha_evento
-- =============================================================
CREATE VIEW gold.lineup_candidates AS
SELECT
  c.nombre,
  c.genero,
  c.categoria,
  s.score_aplicado AS score_final,
  c.comico_id,
  c.telefono,
  c.instagram,
  s.fecha_evento
FROM gold.solicitudes AS s
INNER JOIN gold.comicos AS c
  ON c.comico_id = s.comico_id
WHERE s.estado = 'pendiente';

-- =============================================================
-- 3) Función RPC de validación del lineup
-- Firma esperada por el frontend:
--   gold.validate_lineup(p_selection JSONB[], p_event_date DATE)
--
-- Para cada elemento de p_selection (JSON con comico_id, categoria, genero):
--   a) Marca solicitudes del cómico como "aceptado"
--   b) Actualiza su categoría/género y ultima_fecha_actuada en gold.comicos
--   c) Sincroniza categoria + genero en silver.comicos
--      (categoria con cast explícito a silver.tipo_categoria)
-- =============================================================
CREATE FUNCTION gold.validate_lineup(p_selection JSONB[], p_event_date DATE)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_item JSONB;
  v_comico_id BIGINT;
  v_categoria TEXT;
  v_genero TEXT;
BEGIN
  FOREACH v_item IN ARRAY p_selection
  LOOP
    v_comico_id := (v_item ->> 'comico_id')::BIGINT;
    v_categoria := v_item ->> 'categoria';
    v_genero := v_item ->> 'genero';

    -- a) Aceptar solicitudes pendientes del cómico seleccionado.
    UPDATE gold.solicitudes
    SET estado = 'aceptado'
    WHERE comico_id = v_comico_id
      AND estado = 'pendiente';

    -- b) Persistir datos curatoriales en gold.comicos.
    UPDATE gold.comicos
    SET
      categoria = v_categoria,
      genero = v_genero,
      ultima_fecha_actuada = p_event_date
    WHERE comico_id = v_comico_id;

    -- c) Sincronizar datos necesarios en silver.comicos.
    UPDATE silver.comicos
    SET
      categoria = v_categoria::silver.tipo_categoria,
      genero = v_genero
    WHERE comico_id = v_comico_id;
  END LOOP;
END;
$$;
