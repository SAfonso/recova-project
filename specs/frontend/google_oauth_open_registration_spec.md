# Spec: Google OAuth — Registro Abierto (Sprint 8 — v0.13.0)

**Archivos afectados:**
- `specs/sql/migrations/20260307_onboard_new_host.sql` (NEW)
- `frontend/src/components/LoginScreen.jsx` — reemplazar magic link por Google OAuth
- `frontend/src/components/OnboardingScreen.jsx` (NEW)
- `frontend/src/main.jsx` — nuevo estado `onboarding`
- `backend/tests/core/test_onboard_new_host.py` (NEW)

**Estado:** spec aprobada
**Versión:** v0.13.0
**Sprint:** 8

---

## 1. Contexto

Actualmente la autenticación es via magic link, lo que requiere que el host esté
pre-registrado y obliga a un flujo engorroso (email → click → volver a la web).

Con Google OAuth cualquier persona puede registrarse directamente, sin intervención
manual. Al ser el primer login, se crea automáticamente su proveedor y su membresía
(rol `host`) via un RPC `SECURITY DEFINER`.

---

## 2. Flujo completo

```
Usuario abre la app
    |
    +-- sesión activa? --NO--> <LoginScreen> (botón Google)
    |                               |
    |                    supabase.auth.signInWithOAuth({ provider: 'google' })
    |                               |
    |                    Google OAuth redirect → callback → sesión creada
    |                               |
    +<-------- onAuthStateChange (SIGNED_IN) --------+
    |
    v
¿tiene membership en silver.organization_members?
    |
    +-- SÍ --> renderiza <OpenMicSelector> (flujo normal)
    |
    +-- NO --> renderiza <OnboardingScreen>
                    |
                    usuario escribe nombre de su venue/sala
                    |
                    llama RPC silver.onboard_new_host(p_nombre_comercial)
                    (crea proveedor + membership rol='host')
                    |
                    --> renderiza <OpenMicSelector>
```

---

## 3. Base de datos — Migración

### RPC `silver.onboard_new_host`

```sql
CREATE OR REPLACE FUNCTION silver.onboard_new_host(
  p_nombre_comercial text
)
RETURNS uuid   -- devuelve el proveedor_id creado
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
  v_candidate := lower(regexp_replace(trim(p_nombre_comercial), '[^a-z0-9]+', '-', 'g'));
  v_candidate := trim(both '-' from v_candidate);

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
```

**Propiedades clave:**
- `SECURITY DEFINER`: ejecuta como el propietario de la función, bypaseando RLS en
  `silver.proveedores` e `silver.organization_members` para el INSERT inicial
- **Idempotente**: si el usuario ya tiene proveedor, devuelve el existente sin error
- Slug generado automáticamente; colisiones resueltas con sufijo numérico (`-2`, `-3`...)

---

## 4. Supabase Dashboard — configuración manual

Pasos que el operador ejecuta una sola vez:

1. **Authentication → Providers → Google** → habilitar
2. Crear credenciales en Google Cloud Console (OAuth 2.0 Client ID, tipo Web):
   - Authorized redirect URI: `https://<proyecto>.supabase.co/auth/v1/callback`
3. Pegar `Client ID` y `Client Secret` en Supabase
4. En Supabase → Authentication → URL Configuration:
   - Site URL: `https://recova-project-z5zp.vercel.app`
   - Redirect URLs: `https://recova-project-z5zp.vercel.app/**`

> Estas credenciales NO van al repositorio. Son configuración de infraestructura.

---

## 5. Frontend

### 5.1 LoginScreen.jsx — contrato de UI

**Eliminar:** campo email, botón "Enviar enlace", estados `email`/`sent`

**Añadir:** botón único "Continuar con Google"

```
+------------------------------------------+
|  AI LineUp Architect                     |
|  Gestiona tu open mic                    |
|                                          |
|  [ G  Continuar con Google ]             |
|                                          |
|  (mensaje de error si falla)             |
+------------------------------------------+
```

**Lógica:**
```js
const handleGoogleLogin = async () => {
  setLoading(true)
  const { error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin }
  })
  if (error) setError(error.message)
  // si OK: redirect externo → Supabase callback → onAuthStateChange
}
```

Estados internos: `loading: boolean`, `error: string | null`

---

### 5.2 OnboardingScreen.jsx (NEW) — contrato de UI

Se muestra tras el primer login cuando el usuario no tiene membership.

```
+------------------------------------------+
|  Bienvenido/a!                           |
|  Para empezar, cuéntanos de tu local.   |
|                                          |
|  Nombre de tu sala o evento              |
|  [ Comedy Club Madrid              ]     |
|                                          |
|  [ Crear mi espacio ]                    |
+------------------------------------------+
```

**Props:** `session`, `onComplete: () => void`

**Estados internos:** `nombre: string`, `loading: boolean`, `error: string | null`

**Lógica:**
```js
const handleCreate = async () => {
  setLoading(true)
  const { error } = await supabase.rpc('onboard_new_host', {
    p_nombre_comercial: nombre.trim()
  }, { schema: 'silver' })
  if (error) { setError(error.message); setLoading(false); return }
  onComplete()
}
```

**Validaciones:**
- Nombre no vacío — botón deshabilitado si `nombre.trim() === ''`
- Máximo 80 caracteres

---

### 5.3 main.jsx — estados del guard

```
checking → cargando sesión inicial
no-session → <LoginScreen />
onboarding → <OnboardingScreen session={session} onComplete={handleOnboardingDone} />
ready → <OpenMicSelector session={session} ... />
```

**Lógica de detección de onboarding:**
```js
const checkMembership = async (session) => {
  const { data } = await supabase
    .schema('silver')
    .from('organization_members')
    .select('id')
    .eq('user_id', session.user.id)
    .limit(1)
  return (data ?? []).length > 0
}

// En onAuthStateChange:
if (event === 'SIGNED_IN') {
  const hasMembership = await checkMembership(session)
  setAppState(hasMembership ? 'ready' : 'onboarding')
}
```

---

## 6. Tests (TDD)

### 6.1 `backend/tests/core/test_onboard_new_host.py`

Tests unitarios del comportamiento del RPC mockeando el cliente Supabase.

```
test_onboard_creates_proveedor_and_membership
  → RPC llamado con nombre_comercial válido
  → devuelve uuid (proveedor_id)
  → mock verifica que se insertó en proveedores Y organization_members

test_onboard_idempotent_returns_existing_proveedor
  → si ya existe membership, RPC devuelve proveedor_id existente
  → no intenta crear duplicado

test_onboard_rejects_empty_nombre
  → RPC con nombre_comercial='' lanza excepción PostgreSQL
  → frontend captura error y muestra mensaje

test_onboard_slug_collision_resolved
  → si slug 'comedy-club' ya existe, crea 'comedy-club-2'
  → mock de proveedores con slug existente

test_onboard_slug_generation
  → "Mi Sala Año!" → slug "mi-sala-ao" (sin tildes/especiales)
  → "  espacios  " → slug "espacios" (trim)
```

### 6.2 `specs/sql/migrations/test_onboard_new_host.sql`

Script SQL de verificación manual (no CI):

```sql
-- Ejecutar en Supabase SQL Editor como authenticated (con set_claim)
-- Limpia estado previo, llama RPC, verifica inserciones
```

---

## 7. Criterios de aceptación

- [ ] Login page muestra solo el botón Google, sin campo email
- [ ] Click en botón → redirect a Google OAuth → vuelve a la app con sesión
- [ ] Usuario nuevo (sin membership) → ve `<OnboardingScreen>`
- [ ] Nombre vacío → botón "Crear" deshabilitado
- [ ] Submit onboarding → crea proveedor + membership → entra a `<OpenMicSelector>`
- [ ] Usuario existente (con membership) → entra directamente a `<OpenMicSelector>`
- [ ] RPC idempotente: doble llamada no crea duplicados
- [ ] Cerrar sesión → vuelve a `<LoginScreen>`
- [ ] Slug generado sin caracteres especiales ni colisiones

---

## 8. Migracion SQL a aplicar

Archivo: `specs/sql/migrations/20260307_onboard_new_host.sql`

Aplicar en Supabase SQL Editor (dashboard) antes de desplegar el frontend.

---

## 9. Orden de implementación

1. Aplicar migración SQL (`onboard_new_host` RPC)
2. Configurar Google OAuth en Supabase Dashboard + Google Cloud Console
3. Escribir tests TDD (`test_onboard_new_host.py`) — deben fallar primero
4. Implementar `LoginScreen.jsx` (simplificar)
5. Implementar `OnboardingScreen.jsx` (nuevo)
6. Actualizar `main.jsx` (nuevo estado `onboarding`)
7. Verificar tests verdes
8. Push a `dev` → Vercel despliega automáticamente
