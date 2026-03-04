# Spec: OpenMicDetail — Vista de detalle y configuración de un Open Mic

**Afecta a:**
- `frontend/src/components/OpenMicDetail.jsx` (NUEVO)
- `frontend/src/main.jsx` — añade estado de navegación entre vistas

**Estado:** pendiente de implementación
**Versión:** v3.0

---

## 1. Contexto

Tras seleccionar o crear un open mic en `OpenMicSelector`, el host accede a
una vista de detalle antes de entrar al Lineup. Esta vista actúa como hub del
open mic: muestra su información, permite configurarlo y da acceso al Lineup.

Flujo completo:

```
Login → OpenMicSelector → OpenMicDetail → App (Lineup)
                ↑                |
                └────── Atrás ───┘
```

---

## 2. Responsabilidades

| Responsabilidad | Descripción |
|---|---|
| Info del open mic | Nombre, fecha de creación |
| Configuración | Embebe `ScoringConfigurator` — el host puede editar y guardar |
| Navegación atrás | Botón "← Atrás" → vuelve a `OpenMicSelector` |
| Acceso al Lineup | Botón "Ver Lineup →" → entra a `App` |

---

## 3. Props

```jsx
<OpenMicDetail
  session={session}           // sesión de Supabase
  openMicId={openMicId}       // UUID del open mic seleccionado
  onBack={fn}                 // vuelve a OpenMicSelector (resetea openMicId)
  onEnterLineup={fn}          // entra a App con el openMicId actual
/>
```

---

## 4. Fetch de datos

```js
const { data: openMic } = await supabase
  .schema('silver')
  .from('open_mics')
  .select('id, nombre, created_at')
  .eq('id', openMicId)
  .single();
```

---

## 5. UI

```
┌─────────────────────────────────────────┐
│  ← Atrás          AI LineUp Architect   │
├─────────────────────────────────────────┤
│                                         │
│  Recova Open Mic — Edición principal    │  ← nombre del open mic
│  Creado el 04/03/2026                   │  ← fecha de creación
│                                         │
│  ┌──── Configuración ────────────────┐  │
│  │  <ScoringConfigurator />          │  │
│  └───────────────────────────────────┘  │
│                                         │
│              [Ver Lineup →]             │
└─────────────────────────────────────────┘
```

- `ScoringConfigurator` embebido sin `onSaved` redirect — guardar queda en la misma vista
- "Ver Lineup →" siempre visible, independientemente de si se ha guardado config
- "← Atrás" llama `onBack()` → `main.jsx` resetea `openMicId` a `null`

---

## 6. Integración en main.jsx

```jsx
function Root() {
  const [session,   setSession]   = useState(null);
  const [checking,  setChecking]  = useState(true);
  const [openMicId, setOpenMicId] = useState(null);
  const [view,      setView]      = useState('selector'); // 'selector' | 'detail' | 'lineup'

  // ...auth listener sin cambios...

  if (checking) return <Spinner />;
  if (!session)               return <LoginScreen />;
  if (view === 'selector')    return <OpenMicSelector session={session} onSelect={handleSelect} />;
  if (view === 'detail')      return <OpenMicDetail
                                        session={session}
                                        openMicId={openMicId}
                                        onBack={handleBack}
                                        onEnterLineup={() => setView('lineup')}
                                      />;
  return <App session={session} openMicId={openMicId} />;
}

const handleSelect = (id) => { setOpenMicId(id); setView('detail'); };
const handleBack   = ()   => { setOpenMicId(null); setView('selector'); };
```

> **Nota:** se elimina `initialTab` — ya no es necesario porque Config vive en
> `OpenMicDetail`, no en `App`. `App` siempre arranca en `lineup`.

---

## 7. Cambios en App.jsx

- Eliminar prop `initialTab` (ya no se usa)
- `activeTab` vuelve a inicializarse siempre como `'lineup'`

---

## 8. Criterios de aceptación

- [ ] Tras seleccionar o crear un open mic, se muestra `OpenMicDetail`
- [ ] El nombre y fecha del open mic se muestran correctamente
- [ ] `ScoringConfigurator` carga y guarda la config desde esta vista
- [ ] "← Atrás" vuelve a `OpenMicSelector` y limpia el `openMicId`
- [ ] "Ver Lineup →" entra a `App` con el `openMicId` correcto
- [ ] `App` siempre arranca en la pestaña Lineup (sin `initialTab`)
- [ ] La pestaña Config en `NotebookSheet` sigue accesible dentro del Lineup
