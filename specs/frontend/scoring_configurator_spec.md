# Spec: ScoringConfigurator — Componente React de configuración de scoring

**Componente:** `frontend/src/components/ScoringConfigurator.jsx`
**Estado:** pendiente de implementación
**Versión:** v3.0
**Dependencias:** React 18, Supabase JS, Tailwind CSS

---

## 1. Contexto y motivación

El Host de un open_mic necesita poder ajustar las reglas de scoring desde la UI web
sin tocar código ni la BD directamente. Toda la configuración vive en
`silver.open_mics.config` (JSONB). Este componente lee ese JSONB, permite editarlo
mediante controles visuales y lo guarda de vuelta en Supabase con un solo UPDATE.

---

## 2. Props

```ts
interface ScoringConfiguratorProps {
  openMicId: string        // UUID del open_mic que se está configurando
  onSaved?: () => void     // callback opcional tras guardar con éxito
}
```

---

## 3. Estado interno

El componente mantiene una copia local del config JSONB (`config`) que solo se
persiste al pulsar "Guardar". Nunca muta el estado con spread directo sobre objetos
anidados: usa el helper `setIn(obj, path, value)`.

```js
// Helper puro: actualización inmutable de rutas anidadas
function setIn(obj, [key, ...rest], value) {
  return rest.length === 0
    ? { ...obj, [key]: value }
    : { ...obj, [key]: setIn(obj[key] ?? {}, rest, value) }
}
```

Estados locales:
- `config` — copia de trabajo del JSONB (inicializada desde Supabase)
- `loading` — true mientras se carga la config inicial
- `saving` — true durante el UPDATE a Supabase
- `error` — string | null con el mensaje de error más reciente

---

## 4. Ciclo de vida

```
mount
  └─ useEffect → supabase
       .from('open_mics')
       .select('config')
       .eq('id', openMicId)
       .single()
     → setConfig(data.config ?? DEFAULTS)

"Guardar" click
  └─ setSaving(true)
     supabase
       .from('open_mics')
       .update({ config })
       .eq('id', openMicId)
     → onSaved?.()
     → setSaving(false)
```

---

## 5. Estructura del JSONB gestionado

El componente gestiona exactamente el mismo JSONB que define `ScoringConfig.from_dict`
en Python. Los valores por defecto del componente (`DEFAULTS`) deben ser idénticos a
`_DEFAULTS` en `backend/src/core/scoring_config.py`.

```js
const DEFAULTS = {
  available_slots: 8,
  categories: {
    standard:   { base_score: 50,   enabled: true },
    priority:   { base_score: 70,   enabled: true },
    gold:       { base_score: 90,   enabled: true },
    restricted: { base_score: null, enabled: true },
  },
  recency_penalty: {
    enabled:         true,
    last_n_editions: 2,
    penalty_points:  20,
  },
  single_date_boost: {
    enabled:      true,
    boost_points: 10,
  },
  gender_parity: {
    enabled:              false,
    target_female_nb_pct: 40,
  },
}
```

> **Regla de sincronización:** cualquier cambio en `_DEFAULTS` de Python debe
> reflejarse en `DEFAULTS` de este componente, y viceversa.

---

## 6. Secciones de la UI

### 6.1 Slots disponibles

```
Slots disponibles: [  8  ] ← input type="number" min=1 max=20
```

Ruta JSONB: `available_slots`

---

### 6.2 Categorías

Tabla con una fila por categoría (`standard`, `priority`, `gold`, `restricted`).

| Categoría  | Puntuación base        | Activa          |
|------------|------------------------|-----------------|
| Standard   | `[ 50 ]` number input  | `[✓]` checkbox  |
| Priority   | `[ 70 ]` number input  | `[✓]` checkbox  |
| Gold       | `[ 90 ]` number input  | `[✓]` checkbox  |
| Restricted | `[ — ]` deshabilitado  | `[✓]` checkbox  |

- `restricted.base_score` siempre es `null` y el input está deshabilitado
- Si `enabled = false`, la fila se muestra atenuada
- Ruta JSONB: `categories.<nombre>.base_score` / `categories.<nombre>.enabled`

---

### 6.3 Penalización de recencia

```
[✓] Activar penalización por recencia

    Últimas N ediciones:   [ 2 ]   ← input number, min=1 max=10
    Puntos de penalización: [ 20 ]  ← input number, min=1 max=100
```

- Cuando el toggle está desactivado, los inputs numéricos se muestran pero deshabilitados
- Ruta JSONB: `recency_penalty.{enabled, last_n_editions, penalty_points}`

---

### 6.4 Bono bala única

```
[✓] Activar bono por disponibilidad única

    Puntos de bono: [ 10 ]  ← input number, min=1 max=50
```

- Ruta JSONB: `single_date_boost.{enabled, boost_points}`

---

### 6.5 Paridad de género

```
[ ] Activar objetivo de paridad de género

    % objetivo femenino/nb: [ 40 ]  ← input number, min=0 max=100
```

- Ruta JSONB: `gender_parity.{enabled, target_female_nb_pct}`

---

### 6.6 Acciones

```
[ Guardar configuración ]   ← disabled durante saving o loading
```

- Muestra spinner mientras `saving = true`
- Muestra mensaje de éxito temporal (2 s) tras guardar
- Muestra `error` en rojo si el UPDATE falla

---

## 7. Validaciones en cliente

| Campo | Regla |
|-------|-------|
| `available_slots` | Entero, 1–20 |
| `categories.*.base_score` | Entero, 0–200 (si no es restricted) |
| `recency_penalty.last_n_editions` | Entero, 1–10 |
| `recency_penalty.penalty_points` | Entero, 1–100 |
| `single_date_boost.boost_points` | Entero, 1–50 |
| `gender_parity.target_female_nb_pct` | Entero, 0–100 |

Validación en `handleSave` antes de llamar a Supabase. No bloquea la UI mientras
el usuario escribe; solo al intentar guardar.

---

## 8. Permisos y RLS

El componente solo funciona si el usuario autenticado pertenece al proveedor del
`open_mic_id` (garantizado por la policy `p_open_mics_update_own` definida en
`specs/sql/v3_schema.sql §3`). No hay lógica de autorización en el componente:
Supabase devolverá error si el usuario no tiene permisos.

---

## 9. Estructura de archivos

```
frontend/src/
  components/
    ScoringConfigurator.jsx     ← componente principal
  hooks/
    useOpenMicConfig.js         ← (opcional) hook de carga/guardado
```

---

## 10. Criterios de aceptación

- [ ] Carga la config actual del open_mic al montar
- [ ] Todos los campos se pueden modificar sin recargar la página
- [ ] El guardado lanza un único `UPDATE` a `silver.open_mics`
- [ ] Los campos deshabilitados (`restricted.base_score`) no son editables
- [ ] Los inputs numéricos de secciones desactivadas (recency, boost, parity) se bloquean
- [ ] Validación pre-guardado con mensajes de error claros
- [ ] Estado `loading` y `saving` reflejados visualmente
- [ ] Si el usuario no tiene permisos, se muestra el error de Supabase
- [ ] `DEFAULTS` del componente coincide exactamente con `_DEFAULTS` de Python

---

## 11. Lo que este componente NO hace

- No gestiona `form_token` ni la URL del formulario público
- No crea ni elimina open_mics (solo edita config del existente)
- No muestra el historial de scoring ni el ranking
- No llama al scoring engine directamente (solo persiste config)
