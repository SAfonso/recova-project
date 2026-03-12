-- =========================================================
-- Migración: RPC silver.onboard_new_host
-- Fecha: 2026-03-07
-- Sprint 8 — Google OAuth Open Registration (v0.13.0)
-- =========================================================
-- Crea proveedor + membership para un nuevo usuario autenticado.
-- SECURITY DEFINER para bypasear RLS en el primer login.
-- Idempotente: si ya existe membership, devuelve el proveedor_id existente.
-- =========================================================

CREATE OR REPLACE FUNCTION silver.onboard_new_host(
  p_nombre_comercial text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = silver, public
AS $$
DECLARE
  v_proveedor_id uuid;
  v_slug         text;
  v_suffix       int := 0;
  v_candidate    text;
BEGIN
  -- Validación
  IF p_nombre_comercial IS NULL OR trim(p_nombre_comercial) = '' THEN
    RAISE EXCEPTION 'nombre_comercial no puede estar vacío';
  END IF;

  -- Idempotencia: si ya tiene proveedor, devolver el existente
  SELECT proveedor_id INTO v_proveedor_id
  FROM silver.organization_members
  WHERE user_id = auth.uid()
  LIMIT 1;

  IF v_proveedor_id IS NOT NULL THEN
    RETURN v_proveedor_id;
  END IF;

  -- Generar slug único desde nombre_comercial
  -- Lowercase, reemplaza caracteres no alfanuméricos por guión, elimina guiones extremos
  v_candidate := lower(regexp_replace(trim(p_nombre_comercial), '[^a-z0-9]+', '-', 'g'));
  v_candidate := trim(both '-' from v_candidate);

  -- Resolver colisiones con sufijo numérico
  LOOP
    IF v_suffix = 0 THEN
      v_slug := v_candidate;
    ELSE
      v_slug := v_candidate || '-' || v_suffix;
    END IF;

    EXIT WHEN NOT EXISTS (
      SELECT 1 FROM silver.proveedores WHERE slug = v_slug
    );
    v_suffix := v_suffix + 1;
  END LOOP;

  -- Crear proveedor
  INSERT INTO silver.proveedores (nombre_comercial, slug)
  VALUES (trim(p_nombre_comercial), v_slug)
  RETURNING id INTO v_proveedor_id;

  -- Crear membresía host
  INSERT INTO silver.organization_members (user_id, proveedor_id, role)
  VALUES (auth.uid(), v_proveedor_id, 'host');

  RETURN v_proveedor_id;
END;
$$;

GRANT EXECUTE ON FUNCTION silver.onboard_new_host(text)
  TO authenticated;
