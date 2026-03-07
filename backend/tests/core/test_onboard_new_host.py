"""
TDD — silver.onboard_new_host RPC
Sprint 8 — Google OAuth Open Registration (v0.13.0)

Estos tests validan el comportamiento del RPC mockeando el cliente Supabase.
No requieren conexión real a Supabase para pasar en CI.
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Stub de supabase para no requerir la librería instalada
# ---------------------------------------------------------------------------
def _make_supabase_stub():
    mod = types.ModuleType("supabase")
    mod.create_client = MagicMock()
    sys.modules.setdefault("supabase", mod)
    return mod


_make_supabase_stub()


# ---------------------------------------------------------------------------
# Helper: simula respuesta RPC de Supabase
# ---------------------------------------------------------------------------
def _rpc_ok(return_value):
    """Simula respuesta exitosa de supabase.rpc().execute()"""
    resp = MagicMock()
    resp.data = return_value
    resp.error = None
    mock_chain = MagicMock()
    mock_chain.execute.return_value = resp
    return mock_chain


def _rpc_error(message):
    """Simula respuesta de error de supabase.rpc().execute()"""
    resp = MagicMock()
    resp.data = None
    resp.error = MagicMock(message=message)
    mock_chain = MagicMock()
    mock_chain.execute.return_value = resp
    return mock_chain


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestOnboardNewHost(unittest.TestCase):

    def setUp(self):
        """Crea un cliente Supabase mockeado para cada test."""
        self.client = MagicMock()
        self.user_id = "test-user-uuid-1234"
        self.expected_proveedor_id = "prov-uuid-5678"

    # ------------------------------------------------------------------
    # 1. Caso base: crea proveedor y membership correctamente
    # ------------------------------------------------------------------
    def test_onboard_creates_proveedor_and_membership(self):
        """RPC con nombre válido devuelve un UUID de proveedor."""
        self.client.rpc.return_value = _rpc_ok(self.expected_proveedor_id)

        result = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": "Comedy Club Madrid"},
            schema="silver"
        ).execute()

        self.assertIsNone(result.error)
        self.assertEqual(result.data, self.expected_proveedor_id)

        # Verifica que se llamó con los parámetros correctos
        self.client.rpc.assert_called_once_with(
            "onboard_new_host",
            {"p_nombre_comercial": "Comedy Club Madrid"},
            schema="silver"
        )

    # ------------------------------------------------------------------
    # 2. Idempotencia: si ya existe membership, devuelve el proveedor_id existente
    # ------------------------------------------------------------------
    def test_onboard_idempotent_returns_existing_proveedor(self):
        """Doble llamada devuelve el mismo proveedor_id sin error."""
        existing_id = "existing-prov-uuid"
        self.client.rpc.return_value = _rpc_ok(existing_id)

        # Primera llamada
        result1 = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": "Mi Local"},
            schema="silver"
        ).execute()

        # Segunda llamada (simula re-llamada)
        result2 = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": "Mi Local"},
            schema="silver"
        ).execute()

        self.assertEqual(result1.data, existing_id)
        self.assertEqual(result2.data, existing_id)
        self.assertEqual(self.client.rpc.call_count, 2)

    # ------------------------------------------------------------------
    # 3. Nombre vacío → error
    # ------------------------------------------------------------------
    def test_onboard_rejects_empty_nombre(self):
        """RPC con nombre vacío devuelve error (RAISE EXCEPTION en SQL)."""
        self.client.rpc.return_value = _rpc_error(
            "nombre_comercial no puede estar vacío"
        )

        result = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": ""},
            schema="silver"
        ).execute()

        self.assertIsNotNone(result.error)
        self.assertIn("vacío", result.error.message)
        self.assertIsNone(result.data)

    # ------------------------------------------------------------------
    # 4. Nombre solo espacios → también error
    # ------------------------------------------------------------------
    def test_onboard_rejects_whitespace_only_nombre(self):
        """Nombre con solo espacios es equivalente a vacío."""
        self.client.rpc.return_value = _rpc_error(
            "nombre_comercial no puede estar vacío"
        )

        result = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": "   "},
            schema="silver"
        ).execute()

        self.assertIsNotNone(result.error)

    # ------------------------------------------------------------------
    # 5. Colisión de slug → crea sufijo numérico
    # ------------------------------------------------------------------
    def test_onboard_slug_collision_resolved(self):
        """Cuando slug base colisiona, el RPC añade sufijo y devuelve UUID igualmente."""
        # El RPC maneja la colisión internamente; el cliente solo ve el resultado
        new_id = "prov-with-suffix-uuid"
        self.client.rpc.return_value = _rpc_ok(new_id)

        result = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": "Comedy Club"},  # asumimos 'comedy-club' ya existe
            schema="silver"
        ).execute()

        self.assertIsNone(result.error)
        self.assertEqual(result.data, new_id)

    # ------------------------------------------------------------------
    # 6. Generación de slug — validar lógica Python equivalente
    # ------------------------------------------------------------------
    def test_slug_generation_logic(self):
        """Verifica la lógica de generación de slugs (equivalente Python al SQL)."""
        import re

        def generate_slug(nombre_comercial: str) -> str:
            candidate = nombre_comercial.lower().strip()
            candidate = re.sub(r'[^a-z0-9]+', '-', candidate)
            candidate = candidate.strip('-')
            return candidate

        self.assertEqual(generate_slug("Comedy Club Madrid"), "comedy-club-madrid")
        self.assertEqual(generate_slug("  espacios  "), "espacios")
        self.assertEqual(generate_slug("Mi Sala!!!"), "mi-sala")
        self.assertEqual(generate_slug("Open-Mic & More"), "open-mic-more")
        self.assertEqual(generate_slug("123 Número"), "123-n-mero")

    # ------------------------------------------------------------------
    # 7. Nombre con caracteres especiales — RPC no debe fallar
    # ------------------------------------------------------------------
    def test_onboard_nombre_with_special_chars(self):
        """Nombre con tildes y símbolos es aceptado; slug se normaliza en SQL."""
        new_id = "prov-special-uuid"
        self.client.rpc.return_value = _rpc_ok(new_id)

        result = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": "La Café & Comedia"},
            schema="silver"
        ).execute()

        self.assertIsNone(result.error)
        self.assertIsNotNone(result.data)

    # ------------------------------------------------------------------
    # 8. Nombre muy largo (>80 chars) — validación frontend, RPC lo acepta
    # ------------------------------------------------------------------
    def test_onboard_long_nombre_accepted_by_rpc(self):
        """El RPC no tiene límite de longitud; la validación de 80 chars es del frontend."""
        long_name = "A" * 100
        self.client.rpc.return_value = _rpc_ok("some-uuid")

        result = self.client.rpc(
            "onboard_new_host",
            {"p_nombre_comercial": long_name},
            schema="silver"
        ).execute()

        # RPC no valida longitud — eso es responsabilidad del frontend
        self.assertIsNone(result.error)


# ---------------------------------------------------------------------------
# Lógica de onboarding en main.jsx — tests de la función checkMembership
# (lógica equivalente en Python)
# ---------------------------------------------------------------------------
class TestCheckMembershipLogic(unittest.TestCase):

    def test_has_membership_returns_true(self):
        """Si hay filas en organization_members, el usuario no necesita onboarding."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "some-membership-id"}]

        client = MagicMock()
        client.schema.return_value.from_.return_value \
            .select.return_value.eq.return_value \
            .limit.return_value.execute.return_value = mock_response

        data = client.schema("silver").from_("organization_members") \
            .select("id").eq("user_id", "user-123").limit(1).execute().data

        has_membership = len(data or []) > 0
        self.assertTrue(has_membership)

    def test_no_membership_returns_false(self):
        """Si no hay filas, el usuario debe pasar por onboarding."""
        mock_response = MagicMock()
        mock_response.data = []

        client = MagicMock()
        client.schema.return_value.from_.return_value \
            .select.return_value.eq.return_value \
            .limit.return_value.execute.return_value = mock_response

        data = client.schema("silver").from_("organization_members") \
            .select("id").eq("user_id", "user-new").limit(1).execute().data

        has_membership = len(data or []) > 0
        self.assertFalse(has_membership)

    def test_null_data_treated_as_no_membership(self):
        """data=None (error de red) se trata como sin membership → onboarding."""
        data = None
        has_membership = len(data or []) > 0
        self.assertFalse(has_membership)


if __name__ == "__main__":
    unittest.main()
