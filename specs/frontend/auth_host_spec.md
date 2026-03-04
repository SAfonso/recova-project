# Spec: Auth de Host — Magic Link (Supabase)

**Archivos afectados:**
- `frontend/src/supabaseClient.js` — activar `persistSession: true`
- `frontend/src/components/LoginScreen.jsx` (NEW)
- `frontend/src/main.jsx` — envolver con `AuthProvider`
- `frontend/src/App.jsx` — proteger con guard de sesión

**Estado:** pendiente de implementación
**Versión:** v3.0

---

## 1. Contexto

El Host necesita autenticarse para acceder al panel y para que las RLS de Supabase
filtren correctamente los datos de su open_mic. Sin sesión activa, todas las queries
a `silver.*` y `gold.*` devuelven 0 filas (RLS bloquea).

---

## 2. Flujo de autenticación

```
Usuario abre la app
    │
    ├─ supabase.auth.getSession() → sesión activa?
    │       ├─ SÍ → renderiza <App /> (panel principal)
    │       └─ NO → renderiza <LoginScreen />
    │
<LoginScreen>
    usuario escribe email → pulsa "Enviar enlace"
    supabase.auth.signInWithOtp({ email })
    → muestra mensaje "Revisa tu email"
    │
usuario hace click en el enlace del email
    → Supabase redirige a la app con token en URL
    → onAuthStateChange dispara evento SIGNED_IN
    → sesión guardada → renderiza <App />
```

---

## 3. Cambios en supabaseClient.js

```js
// ANTES
auth: { persistSession: false }

// DESPUÉS
auth: { persistSession: true }
```

`persistSession: false` era un workaround de desarrollo. Con Auth real necesita
`true` para que la sesión sobreviva recargas de página.

---

## 4. LoginScreen — contrato de UI

### Props
Ninguna. Lee y escribe estado interno.

### Estados internos
- `email: string` — campo controlado
- `loading: boolean` — mientras se envía el OTP
- `sent: boolean` — true tras envío exitoso
- `error: string | null`

### Pantalla: formulario
```
┌─────────────────────────────────────────┐
│  AI LineUp Architect                    │
│  Acceso para hosts                      │
│                                         │
│  [ tu@email.com              ]          │
│                                         │
│  [ Enviar enlace de acceso ]            │
└─────────────────────────────────────────┘
```

### Pantalla: tras envío exitoso
```
┌─────────────────────────────────────────┐
│  ✓ Enlace enviado                       │
│  Revisa tu bandeja de entrada en        │
│  tu@email.com                           │
│                                         │
│  [ Cambiar email ]                      │
└─────────────────────────────────────────┘
```

### Validaciones
- Email no vacío antes de enviar
- Formato de email básico (HTML `type="email"`)

---

## 5. Guard de sesión en main.jsx

El componente raíz gestiona la sesión globalmente con `onAuthStateChange`.
No se usa React Router: el guard es un renderizado condicional.

```jsx
// Pseudocódigo del componente raíz
function Root() {
  const [session, setSession] = useState(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    supabase.auth.getSession()
      .then(({ data }) => { setSession(data.session); setChecking(false) })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_, session) => setSession(session)
    )
    return () => subscription.unsubscribe()
  }, [])

  if (checking) return <Spinner />
  return session ? <App session={session} /> : <LoginScreen />
}
```

---

## 6. Logout

Un botón "Cerrar sesión" en el Header existente llama a
`supabase.auth.signOut()`. El `onAuthStateChange` lo captura y vuelve a
`<LoginScreen />` automáticamente.

---

## 7. Prop `session` en App.jsx

`App` recibe `session` como prop. En este sprint solo se usa para mostrar
el email del host en el Header. La asociación Host ↔ open_mic (via
`silver.organization_members`) se usa en el próximo componente (formulario público).

---

## 8. Criterios de aceptación

- [ ] Sin sesión → se muestra `<LoginScreen />`, no el panel
- [ ] Email vacío → botón deshabilitado
- [ ] Envío exitoso → pantalla de confirmación con el email usado
- [ ] Click en enlace del email → sesión activa, panel visible
- [ ] Recarga de página → sesión persiste (no vuelve a login)
- [ ] "Cerrar sesión" → vuelve a `<LoginScreen />`
- [ ] El email del host se muestra en el Header
- [ ] Sin React Router (renderizado condicional puro)
