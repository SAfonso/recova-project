# Especificación SDD: Capa de Abstracción MCP (Agnostic Renderer)

## 1) Objetivo y alcance

Esta especificación define la **Fuente de Verdad técnica** para la nueva Capa de Abstracción MCP (Agnostic Renderer) del sistema AI LineUp Architect.

El objetivo es desacoplar n8n del renderizado físico, transformando el proceso de generación de cartel en una **Caja Negra Cognitiva** con dos modos compatibles:

1. **Template Catalog Mode:** render basado en plantillas locales versionadas.
2. **Vision Generated Mode:** render generado dinámicamente desde imagen de referencia (Vision-to-Code).

Esta especificación cubre exclusivamente contratos, invariantes y estructura de catálogo. **No incluye implementación en Python**.

---

## 2) Contrato de entrada (Input Schema)

### 2.1 Principio de contrato único

Todo consumidor (n8n, CLI, test harness) DEBE enviar un único JSON canónico con cuatro bloques obligatorios:

- `event_id`
- `metadata`
- `lineup`
- `intent`

### 2.2 Schema canónico (v1)

```json
{
  "event_id": "c7f4d80f-8b66-4ff9-95d3-2b042dbb1c79",
  "metadata": {
    "date_text": "Jueves 12 de Marzo · 21:30h",
    "venue": "RECOVA Comedy Club"
  },
  "lineup": [
    {
      "name": "Ada Torres",
      "instagram": "adatorres"
    },
    {
      "name": "Bruno Gil",
      "instagram": "brunogil"
    }
  ],
  "intent": {
    "template_id": "lineup_bold_v1",
    "reference_image_url": null
  }
}
```

### 2.3 Reglas de validación de input

- `event_id`
  - Obligatorio.
  - Debe ser UUID válido (RFC 4122).
- `metadata.date_text`
  - Obligatorio.
  - String no vacío tras `trim`.
- `metadata.venue`
  - Obligatorio.
  - String no vacío tras `trim`.
- `lineup`
  - Obligatorio.
  - Array con mínimo 1 y máximo 8 elementos.
- `lineup[].name`
  - Obligatorio.
  - String no vacío tras `trim`.
- `lineup[].instagram`
  - Obligatorio en contrato (puede ser `""` si no aplica, pero no `null`).
  - Debe llegar normalizado (sin `@`, sin URL completa).
- `intent`
  - Obligatorio.
  - Debe incluir ambos campos (`template_id`, `reference_image_url`) para evitar ambigüedad de contrato.
- `intent.template_id`
  - Nullable (`string|null`).
  - Requerido funcionalmente cuando `reference_image_url` sea `null`.
- `intent.reference_image_url`
  - Nullable (`string|null`).
  - Si informado, debe ser URL absoluta `http` o `https`.

### 2.4 Errores de contrato (400)

Se responderá `400 Bad Request` cuando:

- Falte cualquiera de los bloques obligatorios.
- `event_id` no sea UUID.
- `lineup` esté vacío o exceda 8 elementos.
- Se reciba `intent.reference_image_url = null` y `intent.template_id = null` simultáneamente.

---

## 3) Lógica de comportamiento (Invariantes de diseño)

### 3.1 Invariante de prioridad de generación

Orden de resolución obligatorio del modo de generación:

1. Si `intent.reference_image_url` existe y es válido → `generation_mode = "vision_generated"`.
2. Si no existe `reference_image_url` → `generation_mode = "template_catalog"` y se resuelve `intent.template_id`.

**Nota:** En caso de coexistencia de ambos (`template_id` + `reference_image_url`), prevalece `reference_image_url` por diseño y se emite warning de precedencia.

### 3.2 Invariante CRÍTICO de fuentes seguras (solo `vision_generated`)

Cuando `generation_mode = "vision_generated"`, el renderer DEBE forzar la inyección de fuentes seguras mediante `@import` de Google Fonts en el CSS generado.

Set mínimo obligatorio:

- `Bebas Neue`
- `Montserrat`
- `Open Sans`

Reglas obligatorias:

- Queda prohibido el uso de fuentes locales no verificadas (`local()`, nombres arbitrarios del sistema, rutas de fuentes fuera del catálogo).
- Si el HTML/CSS generado por Vision-to-Code declara fuentes no permitidas, la capa MCP debe sobrescribir el stack tipográfico al set seguro.
- El trace debe registrar explícitamente la normalización tipográfica aplicada.

Objetivo operativo: eliminar fallos de render por diferencias de fuentes en Linux (entorno VPS/CI).

### 3.3 Inyección estándar por selectores `.slot-n`

Todo HTML (de catálogo o generado por visión) DEBE exponer slots de contenido con selectores deterministas:

- `.slot-1`
- `.slot-2`
- ...
- `.slot-n`

Reglas:

- Los slots representan posición visual de cada persona del lineup.
- La inyección por Playwright se realizará exclusivamente contra estos selectores.
- Si falta un selector requerido para el tamaño de lineup recibido, el render debe fallar con error estructurado (`SLOT_BINDING_ERROR`).

---

## 4) Contrato de salida y trazabilidad (Output Schema)

### 4.1 Schema de respuesta

```json
{
  "status": "success",
  "output": {
    "public_url": "https://<storage>/posters/2026-03-01/lineup_c7f4d80f.png"
  },
  "trace": {
    "engine": "playwright-chromium",
    "generation_mode": "vision_generated",
    "template_id": "lineup_bold_v1",
    "logs": [
      "input.validated",
      "mode.vision_generated.selected",
      "fonts.safe_pack.injected",
      "slots.binding.completed",
      "artifact.uploaded"
    ],
    "warnings": [
      "intent.template_id_ignored_due_to_reference_image"
    ]
  }
}
```

### 4.2 Definición de campos

- `status`
  - Enum: `success | error`.
- `output.public_url`
  - URL pública del artefacto final (obligatorio en `success`).
- `trace.engine`
  - Motor efectivo de render.
- `trace.generation_mode`
  - Enum: `template_catalog | vision_generated`.
- `trace.template_id`
  - `string|null` (puede ir `null` si el flujo de visión es puro sin plantilla base).
- `trace.logs`
  - Array ordenado de eventos de ejecución.
- `trace.warnings`
  - Array de warnings no bloqueantes.

### 4.3 Contrato de error

En `status = error`, se mantiene la estructura de `trace` (para observabilidad) y `output.public_url` debe ser `null`.

---

## 5) Estructura de carpetas del catálogo

### 5.1 Ruta raíz obligatoria

```text
backend/src/templates/catalog/
```

### 5.2 Jerarquía propuesta (autocontenida por estilo)

```text
backend/src/templates/catalog/
  lineup_bold_v1/
    template.html
    style.css
    manifest.json
    assets/
      bg.png
      logo.svg
      textures/
        grain.png
  lineup_minimal_v1/
    template.html
    style.css
    manifest.json
    assets/
      bg.jpg
```

### 5.3 Reglas de catálogo

- Cada `template_id` corresponde a una carpeta autocontenida.
- `template.html` y `style.css` son obligatorios por plantilla.
- `manifest.json` es obligatorio para metadatos mínimos:
  - `template_id`
  - `version`
  - `supported_slots` (ej. 8)
  - `canvas` (`width`, `height`)
- Los assets de estilo deben permanecer dentro de su carpeta de plantilla.
- No se permiten dependencias cruzadas entre carpetas de estilos para preservar portabilidad y versionado.

---

## 6) Matriz de decisión operativa

| Condición de entrada | Modo seleccionado | Resultado esperado |
|---|---|---|
| `reference_image_url` válido | `vision_generated` | Generación Vision-to-Code + inyección de fuentes seguras + binding `.slot-n`. |
| `reference_image_url = null` y `template_id` válido | `template_catalog` | Carga de plantilla local del catálogo + binding `.slot-n`. |
| Ambos nulos | N/A | Error de validación (`400`). |
| Ambos informados | `vision_generated` | Se ignora `template_id`, se emite warning en trace. |

---

## 7) Compatibilidad con n8n (Caja Negra Cognitiva)

Para n8n, la Capa MCP se comporta como un endpoint abstracto con contrato estable:

- n8n no conoce detalles de Playwright, HTML o estrategia de tipografías.
- n8n solo gestiona input canónico + consume `status/output/trace`.
- Cambios de implementación interna no requieren cambiar nodos n8n mientras se preserve este contrato.

---

## 8) Criterios de aceptación de la especificación

La implementación futura se considerará conforme si:

1. Acepta el Input Schema definido (sección 2).
2. Cumple la prioridad de generación (sección 3.1).
3. En `vision_generated`, inyecta siempre Google Fonts seguras y bloquea fuentes locales no verificadas (sección 3.2).
4. Garantiza inyección por `.slot-1..n` para cualquier origen HTML (sección 3.3).
5. Devuelve Output Schema con trazabilidad completa (`status`, `output.public_url`, `trace`) según sección 4.
6. Respeta la estructura de catálogo autocontenida en `backend/src/templates/catalog/` (sección 5).

