# SDD — Poster Placeholder Detector (Sprint 7)

**Versión:** 1.0
**Fecha:** 2026-03-07
**Estado:** Aprobado

---

## 1. Objetivo

Dado un PNG "sucio" con placeholders `COMICO_1..N` horneados, detectar la
posición exacta (center_x, center_y, font_size) de cada placeholder para
luego renderizar los nombres reales sobre un PNG limpio con Pillow.

Estrategia elegida: **Gemini Flash** (visión IA).

EasyOCR fue evaluado y descartado — detectó solo 2/5 placeholders sobre el
diseño con fondo rojo complejo. Gemini detectó los 5 correctamente.

| Módulo                      | Dep. externa    |
|-----------------------------|-----------------|
| `poster_detector_gemini.py` | `google-genai`  |

---

## 2. Contrato de assets

```
backend/assets/templates/
  limpio.png   ← PNG 1080×1350 sin texto de cómicos
  suxio.png    ← PNG 1080×1350 con COMICO_1..5 visibles (referencia)
```

Variables de entorno opcionales (sobreescriben defaults):

| Variable                   | Descripción                      |
|----------------------------|----------------------------------|
| `RECOVA_CLEAN_POSTER_PATH` | Ruta absoluta a `limpio.png`     |
| `RECOVA_DIRTY_POSTER_PATH` | Ruta absoluta a `suxio.png`      |
| `GEMINI_API_KEY`           | Clave API para Variante B        |

---

## 3. Tipos compartidos (`poster_detector_base.py`)

### 3.1 `PlaceholderAnchor`

```python
@dataclass(slots=True)
class PlaceholderAnchor:
    placeholder: str   # "COMICO_1"
    slot:        int   # 1-based
    center_x:    int   # píxeles desde izquierda
    center_y:    int   # píxeles desde arriba
    font_size:   int   # altura estimada en px
    color:       str   # hex, default "#ffffff"
```

### 3.2 `AbstractDetector`

```python
class AbstractDetector(ABC):
    @abstractmethod
    def detect(self, dirty_path: Path) -> list[PlaceholderAnchor]: ...
```

### 3.3 `render_on_anchors`

Función pura que recibe `clean_path`, lista `(name, anchor)`, `date`,
`output_path` y delega el dibujado en `PosterComposer._draw_outlined_text`.

---

## 4. Variante A — EasyOCR

### 4.1 Algoritmo

1. `easyocr.Reader(['en'], gpu=False).readtext(dirty_path)`
   → lista de `(bbox_4pts, text, confidence)`
2. Filtrar textos que coincidan con `COMICO[_\-\s]?\d+` (case-insensitive)
3. Calcular centro: `center_x = (min_x + max_x) / 2`, `center_y = (min_y + max_y) / 2`
4. Estimar `font_size = max_y - min_y`
5. Devolver lista ordenada por `slot`

### 4.2 Comportamiento ante fallos

- Si no detecta ningún placeholder → devuelve `[]` (no lanza excepción)
- Confianza mínima: 0.3 (configurable vía `min_confidence`)

---

## 5. Variante B — Gemini Flash

### 5.1 Algoritmo

1. Leer `dirty_path` → base64
2. `genai.GenerativeModel("gemini-2.0-flash").generate_content([img, prompt])`
3. Prompt pide JSON array con `{placeholder, slot, center_x, center_y, font_size, color}`
4. Parsear respuesta (strip markdown fences si los hay)
5. Devolver lista ordenada por `slot`

### 5.2 Comportamiento ante fallos

- `GEMINI_API_KEY` ausente → `RuntimeError("ERR_MISSING_KEY: ...")`
- JSON malformado → `RuntimeError("ERR_GEMINI_PARSE: ...")`
- Red caída → propagar excepción original

---

## 6. Script de comparación

`backend/scripts/compare_poster_renderers.py`

```
uso: python compare_poster_renderers.py \
       --names "Ada Torres,Bruno Gil,Clara Moreno,Diego Ruiz,Eva Sanz" \
       --date "04 MAR" \
       --dirty  /ruta/suxio.png \
       --clean  /ruta/limpio.png \
       --output /tmp/comparacion/
```

Genera:
- `output_ocr.png`    ← render Variante A
- `output_gemini.png` ← render Variante B
- `anchors.json`      ← anchors detectados por ambas variantes

---

## 7. Tests

### Variante A (`test_poster_detector_ocr.py`)
- `test_detect_returns_sorted_anchors` — mock `easyocr.Reader`
- `test_detect_calculates_center_from_bbox`
- `test_detect_ignores_low_confidence`
- `test_detect_normalizes_pattern_variations` — "COMICO 1", "COMICO-1"
- `test_detect_returns_empty_when_no_match`

### Variante B (`test_poster_detector_gemini.py`)
- `test_detect_parses_valid_json_response`
- `test_detect_strips_markdown_fences`
- `test_detect_raises_on_malformed_json`
- `test_raises_on_missing_api_key`
- `test_detect_sorts_by_slot`
