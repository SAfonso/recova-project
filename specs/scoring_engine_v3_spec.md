# Spec: Scoring Engine v3 — Multi-tenant con ScoringConfig

**Módulo:** `backend/src/scoring_engine.py`
**Estado:** implementado ✅
**Versión:** v3.0
**Dependencias:** `ScoringConfig`, `psycopg2`, `dotenv`

---

## 1. Contexto y motivación

El engine v2 tenía dos problemas críticos para el SaaS multi-tenant:

1. **Constantes globales:** `CATEGORY_BONUS`, `CATEGORY_ALIASES`, penalización y bono
   hardcodeados. Un solo open_mic no podía tener reglas distintas a otro.
2. **Recencia global:** `has_recent_acceptance_penalty` buscaba en toda `gold.solicitudes`
   sin filtrar por open_mic. Un cómico penalizado en "Sala A" también era penalizado
   en "Sala B", aunque nunca hubiera actuado allí.

v3 resuelve ambos problemas: toda la configuración viene de `ScoringConfig` (que lee
el JSONB de `silver.open_mics`), y la recencia se scopes por `open_mic_id`.

---

## 2. Flujo principal

```
execute_scoring(open_mic_id)
  │
  ├─ fetch_scoring_config(conn, open_mic_id)
  │    └─ SELECT config FROM silver.open_mics WHERE id = open_mic_id
  │         → ScoringConfig.from_dict(open_mic_id, raw_jsonb)
  │
  ├─ fetch_silver_requests(conn, open_mic_id)
  │    └─ SELECT ... FROM silver.solicitudes WHERE open_mic_id = %s
  │         AND status IN ('normalizado', 'scorado')
  │
  ├─ build_ranking(conn, requests, config)
  │    └─ por cada request:
  │         upsert_comico(conn, request)       → (comico_id, categoria_gold)
  │         config.is_restricted(categoria)    → skip si True
  │         has_recent_acceptance_penalty(...)  → bool
  │         config.compute_score(...)          → int | None
  │         → CandidateScore con open_mic_id
  │    └─ balancear por género (f/nb ↔ m alternados, unknowns al final)
  │
  └─ persist_pending_score(conn, candidate)  × len(ranking)
       └─ INSERT/UPDATE gold.solicitudes con open_mic_id
          UPDATE silver.solicitudes status = 'scorado'
          UPDATE gold.comicos score_actual
```

---

## 3. Funciones públicas

### `execute_scoring(open_mic_id: str) → dict`

Punto de entrada principal. Ejecuta el ciclo completo en una sola transacción de BD.

**Parámetros:**
- `open_mic_id`: UUID del open_mic a procesar (obligatorio)

**Respuesta:**
```json
{
  "status": "ok",
  "open_mic_id": "...",
  "filas_procesadas": 12,
  "filas_insertadas_gold": 10,
  "filas_descartadas_restriccion": 2,
  "top_sugeridos": [
    {
      "nombre": "Ada Torres",
      "instagram": "adatorres",
      "genero": "f",
      "categoria": "priority",
      "score_final": 80,
      "penalizado": false,
      "bono_bala_unica": true,
      "marca_temporal": "2026-02-01T10:00:00+00:00"
    }
  ]
}
```

`top_sugeridos` devuelve hasta `config.available_slots` candidatos.

---

### `fetch_scoring_config(conn, open_mic_id: str) → ScoringConfig`

- Si el open_mic no existe → `ScoringConfig.default(open_mic_id)` (no lanza)
- Si el JSONB está vacío → `ScoringConfig.default(open_mic_id)`

---

### `fetch_silver_requests(conn, open_mic_id: str) → list[SilverRequest]`

Query a `silver.solicitudes` filtrada por `open_mic_id`.
Solo devuelve solicitudes con `status IN ('normalizado', 'scorado')`.
Incluye join a `silver.comicos` y LEFT JOIN a `bronze.solicitudes`.
**No** incluye columna `score_final` (eliminada de Silver en migración anterior).

---

### `has_recent_acceptance_penalty(conn, comico_id, open_mic_id, config) → bool`

Fuente de verdad: `silver.lineup_slots WHERE status = 'confirmed'`.

```sql
WITH ultimas_ediciones AS (
    SELECT DISTINCT fecha_evento
    FROM silver.lineup_slots
    WHERE open_mic_id = %s          -- ← scoped a ESTE open_mic
      AND status = 'confirmed'
    ORDER BY fecha_evento DESC
    LIMIT %s                        -- ← config.recency_last_n_editions
)
SELECT EXISTS (
    SELECT 1
    FROM silver.lineup_slots ls
    JOIN silver.solicitudes s ON s.id = ls.solicitud_id
    WHERE s.comico_id    = %s
      AND ls.open_mic_id = %s       -- ← scoped a ESTE open_mic
      AND ls.status      = 'confirmed'
      AND ls.fecha_evento IN (SELECT fecha_evento FROM ultimas_ediciones)
)
```

**Si `config.recency_penalty_enabled = False`:** devuelve `False` directamente,
sin ejecutar la query.

---

### `build_ranking(conn, requests, config: ScoringConfig) → tuple[list[CandidateScore], int]`

**Lógica de descarte:**
1. `config.is_restricted(categoria_gold)` → incrementa contador, skip
2. `config.compute_score(...) is None` → incrementa contador, skip

**Orden del ranking (balanceo de género):**
- Bucket f/nb ordenado por `(-score, marca_temporal ASC)`
- Bucket m ordenado por `(-score, marca_temporal ASC)`
- Alternancia: f/nb → m → f/nb → m → ...
- Unknowns appended al final
- Deduplicación por `comico_id` (primera aparición gana)

---

### `persist_pending_score(conn, candidate: CandidateScore) → None`

Escribe en Gold. Condición de guarda: solo modifica filas en estado `pendiente` o `scorado`
(no sobreescribe `aprobado`, `confirmado`, etc.).

Operaciones (en orden, misma transacción):
1. `INSERT INTO gold.solicitudes` con `open_mic_id` — `ON CONFLICT DO UPDATE`
2. `UPDATE gold.solicitudes SET estado = 'scorado'`
3. `UPDATE silver.solicitudes SET status = 'scorado'`
4. `UPDATE gold.comicos SET score_actual = ...`

---

## 4. Dataclasses

### `SilverRequest`
```
comico_id, nombre, telefono, instagram, genero,
categoria_silver, fechas_disponibles, marca_temporal, solicitud_id
```

### `CandidateScore`
```
nombre, telefono, instagram, genero, comico_id, categoria,
open_mic_id,        ← NUEVO en v3
score_final, marca_temporal, fecha_evento,
penalizado_por_recencia, bono_bala_unica, solicitud_id
```

---

## 5. Mapeo de categorías Silver → Gold

| Silver        | Gold       |
|---------------|------------|
| `general`     | `standard` |
| `priority`    | `priority` |
| `gold`        | `gold`     |
| `restricted`  | `restricted` |
| (desconocida) | `standard` |

La función `_map_to_gold_category()` es privada del módulo.

---

## 6. Invocación desde CLI

```bash
python -m backend.src.scoring_engine <open_mic_id>
```

Requiere `DATABASE_URL` en el entorno (`.env` o variable de entorno).

---

## 7. Tests requeridos

Archivo: `backend/tests/unit/test_scoring_engine.py`

| Test | Cubre |
|------|-------|
| `_map_to_gold_category` cubre todos los valores Silver | Mapeo correcto |
| `has_single_date` detecta una vs varias fechas | Parser de fechas |
| Ordenación por `marca_temporal` en empate de score | Desempate FIFO |
| `build_ranking` deduplica por `comico_id` | Sin duplicados en lineup |
| `build_ranking` agota bucket f sin romper m | Resiliencia de alternancia |
| `build_ranking` alterna f/nb ↔ m correctamente | Paridad de género |
| `build_ranking` descarta categoría restringida | Restricción efectiva |
| `build_ranking` aplica penalización de recencia | Scoring correcto |
| `fetch_silver_requests` no menciona `score_final` | Compatibilidad esquema Silver |
| `persist_pending_score` escribe `open_mic_id` | Multi-tenant en Gold |
| `persist_pending_score` marca Silver como `scorado` | Trazabilidad Silver |

---

## 8. Restricciones

- `execute_scoring` requiere `open_mic_id` explícito; no existe modo "global"
- La recencia nunca es cross-open_mic
- `gold.solicitudes` solo se modifica si `estado IN ('pendiente', 'scorado')`
- La función no hace commit directamente; el contexto `db_connection()` es responsable
- No usa `telefono` como identificador primario (migrado a `instagram`)
