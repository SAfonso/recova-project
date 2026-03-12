# Spec: ScoringConfig — Configuración dinámica de scoring por open_mic

**Módulo:** `backend/src/core/scoring_config.py`
**Estado:** implementado ✅
**Versión:** v3.0
**Dependencias:** ninguna (módulo puro, sin I/O)

---

## 1. Contexto y motivación

El scoring engine anterior usaba constantes hardcodeadas (`CATEGORY_BONUS`, penalización de
recencia fija en −100, bono bala única fijo en +20). Esto impedía que cada Host pudiera
configurar las reglas de su propio open_mic desde la UI web.

Este módulo introduce un contrato limpio entre el JSONB almacenado en
`silver.open_mics.config` y el scoring engine de Python, sin acoplamiento a la BD.

---

## 2. Fuente de verdad del JSONB

El JSONB de `silver.open_mics.config` tiene la siguiente estructura canónica.
Cualquier clave ausente debe ser cubierta por valores por defecto (`_DEFAULTS`).

```json
{
  "available_slots": 8,
  "categories": {
    "standard":   { "base_score": 50,   "enabled": true  },
    "priority":   { "base_score": 70,   "enabled": true  },
    "gold":       { "base_score": 90,   "enabled": true  },
    "restricted": { "base_score": null, "enabled": true  }
  },
  "recency_penalty": {
    "enabled":        true,
    "last_n_editions": 2,
    "penalty_points":  20
  },
  "single_date_boost": {
    "enabled":      true,
    "boost_points": 10
  },
  "gender_parity": {
    "enabled":             false,
    "target_female_nb_pct": 40
  }
}
```

> **Invariante:** `_DEFAULTS` en Python y el valor DEFAULT de la columna en SQL
> deben mantenerse siempre sincronizados.

---

## 3. Clases

### 3.1 `CategoryRule`

```
CategoryRule(base_score: int | None, enabled: bool = True)
```

| Campo        | Tipo        | Descripción                                          |
|--------------|-------------|------------------------------------------------------|
| `base_score` | `int\|None` | Puntuación base. `None` = categoría restringida      |
| `enabled`    | `bool`      | False bloquea la categoría aunque tenga base_score   |

**Propiedad derivada:**
- `is_restricted → bool`: True si `base_score is None` o `enabled is False`

**Constructor:** `CategoryRule.from_dict(raw: dict) → CategoryRule`

---

### 3.2 `ScoringConfig`

Dataclass frozen (inmutable). Representa la configuración completa de un open_mic.

| Campo                       | Tipo                        | Default |
|-----------------------------|-----------------------------|---------|
| `open_mic_id`               | `str`                       | —       |
| `available_slots`           | `int`                       | 8       |
| `categories`                | `dict[str, CategoryRule]`   | ver JSONB |
| `recency_penalty_enabled`   | `bool`                      | True    |
| `recency_last_n_editions`   | `int`                       | 2       |
| `recency_penalty_points`    | `int`                       | 20      |
| `single_date_boost_enabled` | `bool`                      | True    |
| `single_date_boost_points`  | `int`                       | 10      |
| `gender_parity_enabled`     | `bool`                      | False   |
| `gender_parity_target_pct`  | `int`                       | 40      |

---

## 4. Constructores

### `ScoringConfig.from_dict(open_mic_id: str, raw: dict) → ScoringConfig`

- Acepta `raw` parcial o vacío; rellena con `_DEFAULTS` lo que falte
- Acepta `raw = None`; trata como dict vacío (no lanza excepción)
- Acepta categorías extra en el JSONB (no presentes en defaults)
- Merge a un nivel: las categorías del JSONB sobreescriben las de defaults por nombre

### `ScoringConfig.default(open_mic_id: str) → ScoringConfig`

- Equivalente a `from_dict(open_mic_id, {})`
- Uso: tests, fallbacks de pipeline, entornos sin BD

---

## 5. Métodos de scoring

### `category_rule(category: str) → CategoryRule`
- Busca en `self.categories[category.lower()]`
- Fallback a `categories["standard"]` si no existe

### `is_restricted(category: str) → bool`
- Delega en `category_rule(category).is_restricted`

### `compute_score(category, has_recency_penalty, is_single_date) → int | None`

```
score = categories[category].base_score
if recency_penalty_enabled and has_recency_penalty:
    score -= recency_penalty_points
if single_date_boost_enabled and is_single_date:
    score += single_date_boost_points
return score  # None si la categoría es restringida
```

Devuelve `None` (no `0`) cuando la categoría es restringida, para que el engine
pueda distinguir "cero puntos" de "descartado".

---

## 6. Comportamiento de categorías

| Categoría    | base_score | Resultado en ranking      |
|--------------|------------|---------------------------|
| `gold`       | 90         | Prioridad máxima          |
| `priority`   | 70         | Alta prioridad            |
| `standard`   | 50         | Prioridad normal          |
| `restricted` | None       | Descartado (`None`)       |
| desconocida  | fallback a `standard` | 50               |

La categoría `general` de Silver se mapea a `standard` antes de llegar a ScoringConfig.

---

## 7. Tests requeridos

Archivo: `backend/tests/core/test_scoring_config.py`

| Test | Cubre |
|------|-------|
| `CategoryRule(None)` → `is_restricted = True` | Restricción por score nulo |
| `CategoryRule(enabled=False)` → `is_restricted = True` | Restricción por flag |
| `from_dict({})` → usa todos los defaults | Resiliencia a config vacía |
| `from_dict(None)` → no lanza | Resiliencia a config inválida |
| `from_dict` parcial → merge con defaults | Compatibilidad hacia atrás |
| `compute_score("restricted", ...)` → `None` | Descarte de restringidos |
| penalty disabled → sin efecto en score | Toggle de recencia |
| boost disabled → sin efecto en score | Toggle de bono |
| Categoría extra en JSONB → registrada | Extensibilidad |
| `default()` == `from_dict({})` | Consistencia de constructores |

---

## 8. Restricciones

- Sin dependencias externas (no importa psycopg2, supabase, etc.)
- El objeto es frozen: no mutar después de construir
- No hace queries a BD: es un value object puro
- `_DEFAULTS` es privado del módulo; no exportar como API pública
