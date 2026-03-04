# Spec: OpenMicDetail — Hub de detalle de un Open Mic

**Afecta a:**
- `frontend/src/components/OpenMicDetail.jsx` (REFACTOR)
- `frontend/src/main.jsx` — sin cambios en navegación externa

**Estado:** pendiente de implementación
**Versión:** v3.1

---

## 1. Contexto

`OpenMicDetail` es el hub de un open mic concreto. Tiene dos vistas internas:

- **`info`** (por defecto): tarjeta de solo lectura con los datos del open mic
- **`config`**: formulario de edición de configuración de scoring

El host navega entre ellas sin salir del componente. Para entrar al Lineup
existe un botón "Ver Lineup →" siempre visible en la vista `info`.

Flujo completo:

```
OpenMicSelector
      ↓ onSelect
  OpenMicDetail [info]  ←──────── ← Volver (desde config)
      │                                  ↑
      ├── [Configurar] ──────────► [config] → guardar → vuelve a info
      │
      └── [Ver Lineup →] ──────► App (Lineup)
```

---

## 2. Vista `info` — Tarjeta de solo lectura

```
┌─────────────────────────────────────────┐
│  ← Atrás                   host@...     │
├─────────────────────────────────────────┤
│                                         │
│  ┌─── Tarjeta del Open Mic ───────────┐ │
│  │                                    │ │
│  │  Recova Open Mic — Edición 1       │ │  ← nombre
│  │  Creado el 04/03/2026              │ │  ← fecha
│  │                                    │ │
│  │  Slots:      8                     │ │
│  │  Gold:       90 pts                │ │
│  │  Priority:   70 pts                │ │
│  │  Standard:   50 pts                │ │
│  │  Restricted: bloqueado             │ │
│  │                                    │ │
│  │  Recencia:   -20 pts (últimas 2)   │ │
│  │  Bono fecha única: +10 pts         │ │
│  │  Paridad:    desactivada           │ │
│  │                                    │ │
│  └────────────────────────────────────┘ │
│                                         │
│  [Configurar]          [Ver Lineup →]   │
└─────────────────────────────────────────┘
```

- Todos los valores son de solo lectura, extraídos del campo `config` JSONB
- Si `config` está vacío o es `{}`, muestra los valores por defecto de `ScoringConfig`

---

## 3. Vista `config` — Edición de configuración

```
┌─────────────────────────────────────────┐
│  ← Volver                  host@...     │
├─────────────────────────────────────────┤
│                                         │
│  Configuración de scoring               │
│                                         │
│  <ScoringConfigurator                   │
│     openMicId={openMicId}               │
│     onSaved={() => setView('info')}     │
│  />                                     │
│                                         │
└─────────────────────────────────────────┘
```

- "← Volver" vuelve a `info` sin guardar
- Guardar en `ScoringConfigurator` llama `onSaved` → vuelve a `info` y recarga los datos

---

## 4. Props

```jsx
<OpenMicDetail
  session={session}
  openMicId={openMicId}
  onBack={fn}           // ← Atrás → OpenMicSelector
  onEnterLineup={fn}    // Ver Lineup → App
/>
```

---

## 5. Estado interno

| Estado | Tipo | Descripción |
|---|---|---|
| `view` | `'info' \| 'config'` | Vista activa dentro del componente |
| `openMic` | objeto | `{ id, nombre, created_at, config }` |
| `loading` | boolean | Cargando datos del open mic |
| `error` | string \| null | Error de fetch |

---

## 6. Fetch de datos

```js
const { data } = await supabase
  .schema('silver')
  .from('open_mics')
  .select('id, nombre, created_at, config')
  .eq('id', openMicId)
  .single();
```

Se recarga tras `onSaved` para reflejar la config actualizada en la tarjeta.

---

## 7. Criterios de aceptación

- [ ] La vista `info` muestra nombre, fecha y resumen de config en modo lectura
- [ ] Si `config` es `{}`, se muestran los valores por defecto
- [ ] [Configurar] abre la vista `config`
- [ ] Guardar en config vuelve a `info` y refleja los nuevos valores
- [ ] "← Volver" desde config vuelve a `info` sin guardar
- [ ] "← Atrás" vuelve a `OpenMicSelector`
- [ ] "Ver Lineup →" entra a `App`
