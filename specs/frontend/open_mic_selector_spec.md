# Spec: OpenMicSelector — Selección y creación de Open Mic

**Afecta a:**
- `frontend/src/components/OpenMicSelector.jsx` (NUEVO)
- `frontend/src/main.jsx` — añade paso selector entre Login y App
- `frontend/src/App.jsx` — recibe `openMicId` como prop, elimina fetch propio

**Estado:** pendiente de implementación
**Versión:** v3.0

---

## 1. Contexto

Tras el login, el host debe elegir con qué open mic quiere trabajar antes de
acceder al Lineup y la Config. Un proveedor puede tener N open mics.

Flujo completo:

```
Login → OpenMicSelector → App (Lineup + Config del open mic seleccionado)
```

---

## 2. Responsabilidades del componente

| Responsabilidad | Descripción |
|---|---|
| Fetch de open mics | Consulta `silver.open_mics` del host vía `organization_members → proveedor_id` |
| Lista de selección | Muestra los open mics disponibles; clic selecciona y entra a la App |
| Crear nuevo | Formulario inline con campo `nombre`; INSERT en `silver.open_mics`; auto-selecciona |
| Estado vacío | Si no hay open mics, muestra solo el formulario de creación |
| Logout | Botón para cerrar sesión (igual que en Header) |

---

## 3. Props

```jsx
<OpenMicSelector
  session={session}         // objeto de sesión de Supabase
  onSelect={fn(openMicId)} // callback cuando el host selecciona un open mic
/>
```

---

## 4. Queries a Supabase

### 4.1 Fetch de open mics del host

Un usuario ve **únicamente** los open mics de los proveedores a los que pertenece
(como `host` o `collaborator`). Nunca ve open mics de otros proveedores.

```js
// Paso 1: obtener TODOS los proveedor_id del usuario (puede tener rol en N proveedores)
const { data: memberships } = await supabase
  .schema('silver')
  .from('organization_members')
  .select('proveedor_id, role')
  .eq('user_id', session.user.id);

const proveedorIds = memberships.map((m) => m.proveedor_id);

// Paso 2: obtener open mics de TODOS esos proveedores
const { data: openMics } = await supabase
  .schema('silver')
  .from('open_mics')
  .select('id, nombre, proveedor_id, created_at')
  .in('proveedor_id', proveedorIds)
  .order('created_at', { ascending: true });
```

> **Nota de seguridad:** la RLS de `silver.open_mics` actúa como segunda capa —
> aunque el frontend enviara un `proveedor_id` ajeno, la política rechazaría la fila.
> El filtro del frontend es UX, la RLS es la garantía real.

### 4.1.1 Rol y permisos

| Rol en `organization_members` | Ver open mics | Crear nuevo open mic |
|---|---|---|
| `host` | Sí | Sí |
| `collaborator` | Sí | No |

El botón **"+ Nuevo Open Mic"** solo se muestra si el usuario tiene al menos
un membership con `role = 'host'`.

### 4.2 Crear nuevo open mic

Solo disponible para usuarios con `role = 'host'`. El INSERT usa el `proveedor_id`
del membership con rol `host` (si tiene varios, el primero en orden de creación).

```js
const hostMembership = memberships.find((m) => m.role === 'host');

const { data: newMic } = await supabase
  .schema('silver')
  .from('open_mics')
  .insert({
    proveedor_id: hostMembership.proveedor_id,
    nombre: nombre.trim(),
    config: {},          // config vacío → ScoringConfig.default() aplica en backend
  })
  .select('id, nombre')
  .single();
```

---

## 5. Estados del componente

| Estado | Descripción |
|---|---|
| `loading` | Cargando open mics desde la BD |
| `openMics: []` | Lista de open mics accesibles por el usuario |
| `memberships: []` | Todos los memberships del usuario (para calcular permisos) |
| `canCreate` | `true` si algún membership tiene `role = 'host'` |
| `creating` | El formulario de creación está visible |
| `newName` | Valor del input de nombre del nuevo open mic |
| `saving` | INSERT en curso |
| `error` | Mensaje de error global |

---

## 6. UI / Comportamiento

### Vista con open mics existentes

```
┌─────────────────────────────────────┐
│  Tus Open Mics                      │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ Recova Open Mic — Edición 1 │    │  ← botón, clic → onSelect(id)
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ Comedy Lab Sesión Mensual   │    │
│  └─────────────────────────────┘    │
│                                     │
│  [+ Nuevo Open Mic]                 │  ← toggle formulario
│                                     │
│                          [Logout]   │
└─────────────────────────────────────┘
```

### Formulario de creación (inline, aparece al pulsar "+ Nuevo")

```
┌─────────────────────────────────────┐
│  Nombre del nuevo Open Mic          │
│  [________________________]         │
│  [Cancelar]  [Crear]                │
└─────────────────────────────────────┘
```

- `Crear` deshabilitado si `newName.trim() === ''`
- Tras INSERT exitoso: el nuevo open mic se auto-selecciona (`onSelect(newMic.id)`)
- Si el INSERT falla: muestra error inline

### Vista sin open mics (estado vacío)

- Muestra directamente el formulario de creación sin opción de cancelar

---

## 7. Integración en main.jsx

```jsx
function Root() {
  const [session, setSession] = useState(null);
  const [checking, setChecking] = useState(true);
  const [openMicId, setOpenMicId] = useState(null);

  // ... auth listener (igual que antes)

  if (checking) return <Spinner />;
  if (!session) return <LoginScreen />;
  if (!openMicId) return <OpenMicSelector session={session} onSelect={setOpenMicId} />;
  return <App session={session} openMicId={openMicId} />;
}
```

---

## 8. Cambios en App.jsx

- Recibe `openMicId` como prop (ya no lo fetcha internamente)
- Elimina el `useEffect` de `organization_members → open_mics`
- Elimina el estado `openMicId`
- Pasa `openMicId` directamente a `NotebookSheet`

---

## 9. Criterios de aceptación

- [ ] El usuario solo ve open mics de los proveedores donde tiene membership
- [ ] Un collaborator ve los open mics pero NO ve el botón "Nuevo Open Mic"
- [ ] Un host ve la lista y puede crear nuevos open mics
- [ ] Host sin open mics ve directamente el formulario de creación
- [ ] Crear nuevo open mic lo auto-selecciona y entra al App
- [ ] El formulario valida que el nombre no esté vacío
- [ ] Errores de BD se muestran inline
- [ ] Botón Logout disponible en la pantalla de selección
- [ ] `App` recibe `openMicId` como prop y no lo fetcha por su cuenta
- [ ] RLS en `silver.open_mics` garantiza el aislamiento a nivel de BD
