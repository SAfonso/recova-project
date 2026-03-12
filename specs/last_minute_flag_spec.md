# Spec: Flag "Puede Hoy" — Last-Minute Availability
**Sprint 14 — v0.19.0**

---

## Problema

La pregunta "¿Estarías disponible si nos falla alguien de última hora?" se usaba como campo con peso en el scoring. Esto hace que pierda sentido: en cuanto los cómicos sepan que responder "Sí" da puntos, todos lo harán y el campo queda devaluado.

---

## Solución

El campo `backup` (canónico) deja de influir en el scoring. En su lugar activa un **flag booleano** (`puede_hoy`) en el registro de la solicitud, y ese flag solo se usa visualmente el día del show o el día anterior, durante la edición del lineup.

---

## Reglas de negocio

### 1. Scoring — `backup` excluido
- `apply_custom_rules` ignora cualquier regla cuyo `field == "backup"`, aunque exista en la config JSONB.
- `CustomScoringProposer` no propone reglas para el campo `backup`.

### 2. Flag `puede_hoy`
- **True** si la respuesta al campo canónico `backup` es una afirmación: `sí`, `si`, `yes`, `true`, `1` (case-insensitive, trim).
- Persiste en `gold.solicitudes.puede_hoy` al ejecutar el scoring.
- La vista `gold.lineup_candidates` expone `puede_hoy`.

### 3. Modo "Puede Hoy" en el frontend
Activo cuando se cumplan **todas** las condiciones:

| Condición | Descripción |
|-----------|-------------|
| `has_backup_field` | `scoring_type === 'basic'` ∨ (`scoring_type === 'custom'` ∧ `field_mapping` incluye `'backup'`) |
| `isSameDayOrDayBefore` | `0 ≤ (fecha_evento − today) ≤ 1` día |

- Si `scoring_type === 'none'` → modo **nunca** activo (ese form no tiene la pregunta).

### 4. Visual — `ComicCard`
Condición completa: `isLastMinuteMode && isLastMinute && !isSelected`

- **Glow** ámbar pulsante (`last-minute-glow`) en el wrapper de la card.
- **Badge** "Puede hoy" (Bangers, fondo `#EAB308`, borde negro) junto al nombre.
- Si el cómico es seleccionado para el lineup → glow y badge **desaparecen**.
- Solo visible en `ExpandedView` (modal de edición), no en la vista principal.

---

## Cambios de datos

### `gold.solicitudes`
```sql
ALTER TABLE gold.solicitudes
  ADD COLUMN IF NOT EXISTS puede_hoy boolean NOT NULL DEFAULT false;
```

### `gold.lineup_candidates` (vista)
Incluye la columna `puede_hoy` de `gold.solicitudes`.

### Backfill
```sql
UPDATE gold.solicitudes gs
SET    puede_hoy = true
FROM   silver.solicitudes ss
WHERE  ss.id = gs.id
  AND  LOWER(TRIM(ss.metadata->>'backup')) IN ('sí', 'si', 'yes', 'true', '1');
```

---

## Flujo de datos

```
Form response (backup = "Sí")
  → silver.solicitudes.metadata = { "backup": "Sí" }
  → scoring_engine: puede_hoy = True
  → gold.solicitudes.puede_hoy = true
  → gold.lineup_candidates.puede_hoy = true
  → App.jsx: isLastMinuteMode (si scoring_type adecuado + día correcto)
  → ExpandedView → ComicCard: glow + badge "Puede hoy"
```

---

## Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `specs/sql/migrations/20260312_add_puede_hoy_to_gold.sql` | DDL + backfill + vista |
| `backend/src/scoring_engine.py` | `CandidateScore.puede_hoy` + INSERT/UPDATE |
| `backend/src/core/scoring_config.py` | `apply_custom_rules` ignora `backup` |
| `backend/src/core/custom_scoring_proposer.py` | Filtra `backup` de unmapped_fields |
| `frontend/src/App.jsx` | Fetch config + `isLastMinuteMode` + select `puede_hoy` |
| `frontend/src/components/open-mic/ExpandedView.jsx` | Prop `isLastMinuteMode` → ComicCard |
| `frontend/src/components/open-mic/ComicCard.jsx` | Badge + glow |
| `frontend/src/index.css` | `@keyframes last-minute-pulse` + `.last-minute-glow` |

---

---

## Addendum v0.19.1 — `single_date_priority`

### Decisión
El bono por "disponibilidad única" deja de ser un valor configurable (puntos) y se convierte en un toggle con efecto interno fijo. Un cómico que marcó UNA sola fecha disponible (la del show en curso) recibe un bono interno de **+40 pts** al hacer el scoring — suficiente para competir con categorías superiores. El host no ve ni controla los puntos, solo activa/desactiva la prioridad.

### Reglas
- `single_date_priority_enabled`: boolean en `open_mics.config`. Default `true`.
- `has_single_date(fechas_disponibles)`: el cómico tiene exactamente 1 fecha disponible.
- Si ambos → `score += 40` al calcular el ranking (interno, no expuesto en UI).
- `gold.solicitudes.is_single_date boolean` — persiste el flag en gold.
- `gold.lineup_candidates` expone `is_single_date`.
- **Badge "Solo puede hoy"** en `ComicCard` dentro de `ExpandedView` cuando `candidate.is_single_date && config.single_date_priority_enabled`.

### Archivos afectados
- `specs/sql/migrations/20260312_add_is_single_date_to_gold.sql` — DDL + backfill
- `backend/src/core/scoring_config.py` — toggle + `compute_score(is_single_date)`
- `backend/src/scoring_engine.py` — `has_single_date` + `CandidateScore.is_single_date` + persist
- `frontend/src/components/ScoringConfigurator.jsx` — toggle UI (sin campo de puntos)
- `frontend/src/App.jsx` — select `is_single_date`
- `frontend/src/components/open-mic/ExpandedView.jsx` — prop `singleDateMode`
- `frontend/src/components/open-mic/ComicCard.jsx` — badge "Solo puede hoy"

---

## Tests

### Backend
- `scoring_config`: `apply_custom_rules` ignora campo `backup` (con y sin otras reglas).
- `custom_scoring_proposer`: filtra `backup` antes de llamar a Gemini; si solo hay `backup`, no llama a Gemini.
- `scoring_engine`: `puede_hoy` derivado correctamente de metadata (variantes truthy/falsy); persiste en SQL.

### Frontend
- `ComicCard`: badge visible cuando `lastMinuteMode=true && isLastMinute=true`.
- `ComicCard`: sin badge cuando `lastMinuteMode=false` o `isLastMinute=false`.
- `ComicCard`: clase `last-minute-glow` presente/ausente según condiciones.
