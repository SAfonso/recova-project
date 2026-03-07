# SDD — Scoring Inteligente Custom (Sprint 10, v0.15.0)

---

## Objetivo

Cuando el host activa `scoring_type = 'custom'`, Gemini analiza los campos no
canónicos del formulario (los que tienen `null` en `field_mapping`) y propone
reglas de puntuación basadas en las respuestas almacenadas en
`silver.solicitudes.metadata`. El host ajusta cada regla (activar/desactivar,
puntos) y el scoring engine las aplica al calcular candidatos.

---

## Cambios

| Archivo | Cambio |
|---------|--------|
| `backend/src/core/custom_scoring_proposer.py` | Nueva clase `CustomScoringProposer` — Gemini propone reglas desde campos no canónicos |
| `backend/src/triggers/webhook_listener.py` | Nuevo endpoint `POST /api/open-mic/propose-custom-rules` |
| `backend/src/core/scoring_config.py` | Añadir `custom_scoring_rules` a `ScoringConfig` |
| `backend/src/scoring_engine.py` | Aplicar `custom_scoring_rules` desde `solicitudes.metadata` |
| `frontend/src/components/CustomScoringConfigurator.jsx` | Nuevo componente — lista de reglas con toggle + slider |
| `frontend/src/components/ScoringConfigurator.jsx` | Integrar `CustomScoringConfigurator` cuando `scoring_type = 'custom'` |
| `specs/sql/migrations/20260308_custom_scoring_rules.sql` | Documentar contrato JSONB de `custom_scoring_rules` |

---

## Modelo de datos — `config.custom_scoring_rules`

Clave nueva en el JSONB de `silver.open_mics.config`. No requiere ALTER TABLE.

```json
{
  "custom_scoring_rules": [
    {
      "field":       "¿Haces humor negro?",
      "condition":   "equals",
      "value":       "Sí",
      "points":      10,
      "enabled":     true,
      "description": "Bono por humor negro"
    },
    {
      "field":       "¿Tienes material nuevo?",
      "condition":   "equals",
      "value":       "Sí",
      "points":      5,
      "enabled":     false,
      "description": "Bono por material nuevo"
    }
  ]
}
```

### Contrato de cada regla

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `field` | `str` | Título exacto de la pregunta del form (clave en `solicitudes.metadata`) |
| `condition` | `"equals"` | En v0.15.0 solo se soporta `equals` (string exacto, case-insensitive) |
| `value` | `str` | Valor que activa la regla |
| `points` | `int` | Puntos a sumar (positivo = bono, negativo = penalización). Rango: -50..+50 |
| `enabled` | `bool` | Si `false`, la regla se ignora al scorar |
| `description` | `str` | Descripción legible generada por Gemini; editable por el host |

---

## `CustomScoringProposer` — `backend/src/core/custom_scoring_proposer.py`

### Responsabilidad

Recibe la lista de campos no canónicos (`unmapped_fields`) de `config.field_mapping`
y usa Gemini para proponer reglas de scoring para cada uno.

### Dependencias

- `google-genai>=1.0.0` (mismo SDK que `form_analyzer.py`)
- `GEMINI_API_KEY` en `.env`
- Modelo: `gemini-2.5-flash`

### `CustomScoringProposer.propose(unmapped_fields: list[str]) -> list[dict]`

**Prompt a Gemini:**

```
Tienes un formulario de inscripción para un open mic de comedia.
Los siguientes campos del formulario NO pertenecen al schema canónico
y sus respuestas se guardan como texto libre:

{lista_campos_numerada}

Para cada campo, propón una regla de scoring que tenga sentido para
seleccionar el lineup de un open mic de comedia. Una regla indica:
qué valor de respuesta da puntos extra (o resta puntos) al cómico.

Devuelve un JSON válido con este formato exacto:
{
  "rules": [
    {
      "field": "<nombre exacto del campo>",
      "condition": "equals",
      "value": "<valor que activa la regla>",
      "points": <entero entre -50 y 50>,
      "enabled": true,
      "description": "<descripción breve de la regla en español>"
    }
  ]
}

Reglas:
- Usa el nombre exacto del campo como "field".
- "condition" es siempre "equals".
- "value" debe ser un valor razonable que el cómico podría responder.
- "points" positivo = bono, negativo = penalización.
- Si un campo no tiene sentido para scoring, omítelo de la lista.
- Responde solo con el JSON, sin explicaciones ni markdown fences.
```

**Return:**

```python
[
  {
    "field": "¿Haces humor negro?",
    "condition": "equals",
    "value": "Sí",
    "points": 10,
    "enabled": True,
    "description": "Bono por humor negro"
  }
]
```

- Strip de markdown fences antes de parsear (mismo patrón que `form_analyzer.py`).
- Si Gemini devuelve JSON inválido → lanzar `ValueError` con el raw text.
- Si `unmapped_fields` está vacío → devolver `[]` sin llamar a Gemini.

---

## Endpoint `POST /api/open-mic/propose-custom-rules`

### Request

```json
{
  "open_mic_id": "uuid-del-open-mic"
}
```

Campo obligatorio. Requiere `X-API-KEY`.

### Lógica

1. Cargar `config` del open mic desde `silver.open_mics` via Supabase.
2. Extraer `unmapped_fields`: claves de `config.field_mapping` cuyo valor es `null`.
3. Si no hay `field_mapping` en config → `422` con mensaje claro.
4. Si `unmapped_fields` está vacío → devolver `200` con `rules: []`.
5. `CustomScoringProposer().propose(unmapped_fields)` → `rules`.
6. Guardar via RPC (merge JSONB):
   ```python
   sb.schema("silver").rpc("update_open_mic_config_keys", {
     "p_open_mic_id": open_mic_id,
     "p_keys": {"custom_scoring_rules": rules}
   })
   ```
7. Devolver respuesta.

### Response `200`

```json
{
  "rules": [
    {
      "field": "¿Haces humor negro?",
      "condition": "equals",
      "value": "Sí",
      "points": 10,
      "enabled": true,
      "description": "Bono por humor negro"
    }
  ],
  "unmapped_fields": ["¿Haces humor negro?"],
  "proposed_count": 1
}
```

### Response `400`

```json
{"status": "error", "message": "open_mic_id es obligatorio"}
```

### Response `422` — sin field_mapping

```json
{"status": "error", "message": "El open mic no tiene field_mapping. Primero analiza el formulario."}
```

### Response `422` — Gemini inválido

```json
{"status": "error", "message": "Gemini devolvió JSON inválido", "raw": "..."}
```

---

## `ScoringConfig` — cambios en `scoring_config.py`

### Nueva dataclass `CustomRule`

```python
@dataclass(frozen=True)
class CustomRule:
    field: str        # título del campo en solicitudes.metadata
    condition: str    # "equals" (único en v0.15.0)
    value: str        # valor que activa la regla (comparación case-insensitive)
    points: int       # bono o penalización
    enabled: bool = True
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict) -> "CustomRule":
        return cls(
            field=raw["field"],
            condition=raw.get("condition", "equals"),
            value=raw["value"],
            points=int(raw["points"]),
            enabled=bool(raw.get("enabled", True)),
            description=raw.get("description", ""),
        )

    def matches(self, metadata: dict) -> bool:
        """True si la respuesta en metadata cumple la condición."""
        if not self.enabled:
            return False
        answer = metadata.get(self.field, "")
        if self.condition == "equals":
            return str(answer).strip().lower() == self.value.strip().lower()
        return False
```

### Cambios en `ScoringConfig`

```python
@dataclass(frozen=True)
class ScoringConfig:
    # ... campos existentes ...

    # Scoring custom — solo aplicable cuando scoring_type == 'custom'
    scoring_type: str = "basic"           # 'none' | 'basic' | 'custom'
    custom_scoring_rules: list[CustomRule] = field(default_factory=list)
```

En `from_dict()`:

```python
scoring_type = raw.get("scoring_type", "basic")
raw_rules = raw.get("custom_scoring_rules", [])
custom_rules = [CustomRule.from_dict(r) for r in raw_rules if isinstance(r, dict)]

return cls(
    # ... args existentes ...,
    scoring_type=scoring_type,
    custom_scoring_rules=custom_rules,
)
```

### Nuevo método en `ScoringConfig`

```python
def apply_custom_rules(self, metadata: dict) -> int:
    """Suma los puntos de todas las reglas custom habilitadas que coinciden.

    Solo aplica si scoring_type == 'custom'. Si no, devuelve 0.
    """
    if self.scoring_type != "custom":
        return 0
    return sum(r.points for r in self.custom_scoring_rules if r.matches(metadata))
```

---

## `scoring_engine.py` — aplicar custom rules

### `fetch_silver_requests` — añadir metadata

La query existente debe incluir `s.metadata`:

```sql
SELECT
    s.id::text,
    s.comico_id::text,
    COALESCE(c.nombre, b.nombre_raw, '') AS nombre,
    c.telefono,
    COALESCE(c.instagram, '') AS instagram,
    COALESCE(c.genero, 'unknown') AS genero,
    c.categoria::text,
    to_char(s.fecha_evento, 'YYYY-MM-DD'),
    s.created_at,
    COALESCE(s.metadata, '{}') AS metadata   -- NUEVO
FROM silver.solicitudes s
...
```

### `SilverRequest` — añadir campo `metadata`

```python
@dataclass(frozen=True)
class SilverRequest:
    # ... campos existentes ...
    metadata: dict = field(default_factory=dict)   # NUEVO
```

### Integración en el loop de scoring

En `execute_scoring()`, al calcular `score_final`, después de `config.compute_score(...)`:

```python
base_score = config.compute_score(
    category=categoria_silver,
    has_recency_penalty=penalizado,
    is_single_date=is_single,
)
if base_score is None:
    continue  # restringido

custom_bonus = config.apply_custom_rules(request.metadata)
score_final = base_score + custom_bonus
```

---

## Frontend — `CustomScoringConfigurator.jsx`

### Props

```jsx
<CustomScoringConfigurator
  openMicId={openMicId}
  rules={config.custom_scoring_rules ?? []}   // lista desde config JSONB
  onRulesChanged={(newRules) => update(['custom_scoring_rules'], newRules)}
  onPropose={handlePropose}                   // llama al endpoint backend
  proposing={proposing}                       // boolean — spinner
/>
```

### UI

```
[ Proponer reglas automáticas ]   ← botón; spinner si proposing=true

┌─────────────────────────────────────────────┐
│ ¿Haces humor negro?                         │
│ Si respuesta = "Sí"  →  +10 pts             │
│ [toggle ON]  [ slider -50..+50: 10 ]        │
│ Bono por humor negro                        │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ¿Tienes material nuevo?                     │
│ Si respuesta = "Sí"  →  +5 pts              │
│ [toggle OFF] [ slider -50..+50: 5 ]         │
│ Bono por material nuevo                     │
└─────────────────────────────────────────────┘
```

- Botón "Proponer reglas" llama a `POST /api/open-mic/propose-custom-rules`.
- Si ya existen `custom_scoring_rules` en config, se muestran directamente sin llamar al endpoint.
- Botón "Re-proponer" visible si ya existen reglas (sobreescribe).
- Cada regla tiene:
  - **Toggle** enable/disable.
  - **Slider** para ajustar `points` (rango -50 a +50, paso 5).
  - Label descriptivo (editable inline no requerido en v0.15.0).
- Cambios en las reglas se guardan automáticamente via `onRulesChanged` → el padre
  llama a Supabase con el nuevo array (mismo flujo que el resto de `ScoringConfigurator`).
- El botón "Guardar configuración" de `ScoringConfigurator` persiste el array completo.

### Integración en `ScoringConfigurator.jsx`

Añadir sección justo después del `ScoringTypeSelector`:

```jsx
{config.scoring_type === 'custom' && (
  <SectionCard title="Reglas de scoring personalizadas">
    <CustomScoringConfigurator
      openMicId={openMicId}
      rules={config.custom_scoring_rules ?? []}
      onRulesChanged={(r) => update(['custom_scoring_rules'], r)}
      onPropose={handlePropose}
      proposing={proposing}
    />
  </SectionCard>
)}
```

---

## Migración SQL

`specs/sql/migrations/20260308_custom_scoring_rules.sql` — solo documentación,
no requiere DDL (JSONB es schema-less):

```sql
-- Documentación del contrato JSONB (no ejecutar, solo referencia):
-- config.custom_scoring_rules: array de objetos con estructura:
-- [
--   {
--     "field":       string,   -- título del campo en solicitudes.metadata
--     "condition":   "equals", -- tipo de comparación (solo "equals" en v0.15.0)
--     "value":       string,   -- valor que activa la regla
--     "points":      integer,  -- bono (+) o penalización (-), rango -50..50
--     "enabled":     boolean,
--     "description": string
--   }
-- ]
-- Solo se aplica cuando config.scoring_type = 'custom'.
-- Guardado via update_open_mic_config_keys RPC (ya existente desde Sprint 9).
```

---

## Tests a escribir (TDD)

### `backend/tests/core/test_custom_scoring_proposer.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_propose_returns_rules_list` | Lista de reglas con estructura correcta |
| 2 | `test_propose_empty_fields_returns_empty` | Sin unmapped_fields → `[]` sin llamar Gemini |
| 3 | `test_propose_strips_markdown_fences` | Gemini devuelve ```json...``` → parsea OK |
| 4 | `test_propose_raises_on_invalid_json` | JSON inválido → `ValueError` |
| 5 | `test_propose_skips_fields_gemini_omits` | Gemini puede omitir campos sin sentido → OK |

### `backend/tests/test_propose_custom_rules_endpoint.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_propose_returns_200_with_rules` | Happy path — unmapped_fields → reglas |
| 2 | `test_propose_missing_open_mic_id_400` | Sin open_mic_id → 400 |
| 3 | `test_propose_no_field_mapping_422` | Config sin field_mapping → 422 |
| 4 | `test_propose_no_unmapped_fields_200_empty` | Todos canónicos → `rules: []` |
| 5 | `test_propose_gemini_invalid_422` | Gemini falla → 422 |
| 6 | `test_propose_saves_rules_to_config` | RPC `update_open_mic_config_keys` llamada con rules |
| 7 | `test_propose_unauthorized_401` | Sin API key → 401 |

### `backend/tests/core/test_scoring_config_custom.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_custom_rule_matches_case_insensitive` | "sí" == "Sí" → True |
| 2 | `test_custom_rule_no_match` | Valor distinto → False |
| 3 | `test_custom_rule_disabled_no_match` | `enabled=False` → False siempre |
| 4 | `test_apply_custom_rules_sums_points` | Dos reglas activas → suma correcta |
| 5 | `test_apply_custom_rules_returns_zero_if_not_custom` | `scoring_type='basic'` → 0 |
| 6 | `test_scoring_config_loads_custom_rules_from_dict` | `from_dict` con rules → CustomRule list |

### `backend/tests/test_scoring_engine_custom.py`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `test_execute_scoring_applies_custom_bonus` | Metadata con match → score + bonus |
| 2 | `test_execute_scoring_no_bonus_if_basic` | `scoring_type='basic'` → no aplica rules |
| 3 | `test_execute_scoring_disabled_rule_no_bonus` | Regla disabled → no afecta score |
| 4 | `test_execute_scoring_negative_rule` | Puntos negativos → penalización |

### `frontend/src/test/CustomScoringConfigurator.test.jsx`

| # | Test | Descripción |
|---|------|-------------|
| 1 | `renders_rules_list` | Lista de reglas visible con toggle y slider |
| 2 | `renders_empty_state_with_propose_button` | Sin reglas → botón "Proponer reglas" |
| 3 | `toggle_calls_onRulesChanged` | Toggle una regla → callback con array actualizado |
| 4 | `slider_updates_points` | Mover slider → `points` actualizado en callback |
| 5 | `propose_button_calls_onPropose` | Click proponer → `onPropose` llamado |
| 6 | `shows_spinner_when_proposing` | `proposing=true` → botón deshabilitado con spinner |

---

## Criterios de aceptación

- [ ] `CustomScoringProposer.propose(unmapped_fields)` llama a Gemini y devuelve reglas válidas
- [ ] `POST /api/open-mic/propose-custom-rules` guarda `custom_scoring_rules` en config JSONB
- [ ] `ScoringConfig.apply_custom_rules(metadata)` suma puntos de reglas que coinciden
- [ ] `scoring_engine.py` aplica `custom_bonus` cuando `scoring_type == 'custom'`
- [ ] `CustomScoringConfigurator` muestra reglas con toggle y slider; persiste cambios
- [ ] El panel solo aparece en `ScoringConfigurator` cuando `scoring_type == 'custom'`
- [ ] 34 tests nuevos verdes (5 proposer + 7 endpoint + 6 config + 4 engine + 6 frontend = 28 nuevos; mantener los 34 de Sprint 9)
- [ ] Verificado end-to-end con el form real de producción ("¿Haces humor negro?" → regla propuesta)
