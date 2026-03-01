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

### 2.5 Security Gate de `reference_image_url` (validación de entrada estricta)

Cuando `intent.reference_image_url` esté informado, la capa MCP DEBE ejecutar el siguiente protocolo antes de cualquier procesamiento Vision-to-Code:

1. **Pre-fetch acotado:** descargar exclusivamente los primeros **32 bytes** del recurso remoto.
2. **Inspección de Magic Bytes:** validar firma binaria real contra formatos permitidos.
3. **Fail-fast:** abortar de inmediato si el contenido no es imagen válida.

Formatos permitidos por firma:

- PNG (`89 50 4E 47 0D 0A 1A 0A`)
- JPEG (`FF D8 FF`)
- WebP (`52 49 46 46 .... 57 45 42 50`)

Reglas de rechazo:

- Si el payload corresponde a HTML, script u otro binario fuera de whitelist → `ERR_INVALID_FILE_TYPE`.
- Si la URL no es accesible o no devuelve binario de imagen directo → `ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK`.

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

### 3.4 Invariantes de seguridad operativa (origen de imágenes)

Para `generation_mode = "vision_generated"`, la especificación impone estas invariantes no negociables:

- **Direct Link Only:** `reference_image_url` DEBE apuntar a un recurso de descarga directa (Content-Type de imagen) o a un objeto del bucket de Supabase.
- **Wrappers prohibidos:** URLs de visualización previa (ej. Google Drive preview/uc wrapper, Dropbox preview/share page) quedan explícitamente prohibidas.
- **Razonamiento operativo:** cualquier wrapper HTML rompe el inspector de Magic Bytes y debe considerarse entrada inválida por diseño.

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

En errores de acceso/origen no directo, `trace.logs` DEBE incluir `ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK`.

El trace DEBE registrar también el MIME detectado versus el MIME esperado para debugging forense (por ejemplo: `mime.detected=text/html`, `mime.expected=image/*`).

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
| `reference_image_url` con firma no válida | N/A | Abortar por `ERR_INVALID_FILE_TYPE`. |
| `reference_image_url` no accesible o wrapper HTML | N/A | Abortar por `ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK` + log de MIME detectado/esperado. |
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
5. Aplica Security Gate para `reference_image_url` (32 bytes + Magic Bytes + fail-fast) según sección 2.5.
6. En `vision_generated`, solo acepta direct links/Supabase y rechaza wrappers HTML (sección 3.4).
7. Devuelve Output Schema con trazabilidad completa (`status`, `output.public_url`, `trace`) según sección 4.
8. Respeta la estructura de catálogo autocontenida en `backend/src/templates/catalog/` (sección 5).

---

## 9) Jerarquía de resiliencia (Fallback Strategy)

La Capa MCP DEBE implementar una jerarquía de recuperación determinística para mantener continuidad operativa sin romper contrato.

### 9.1 Nivel 1 — Active Mode

Primera ruta de ejecución (modo objetivo según `intent`):

- Si `generation_mode = "vision_generated"`: ejecutar pipeline Vision-to-Code con assets validados.
- Si `generation_mode = "template_catalog"`: resolver `template_id` y renderizar desde su carpeta de catálogo.

### 9.2 Nivel 2 — Local Fallback

Si el Nivel 1 falla por causas no contractuales de ejecución (ej. `timeout`, error de Playwright, assets corruptos/inaccesibles), el MCP DEBE activar fallback local obligatorio:

- Ruta de contingencia fija: `backend/src/templates/catalog/fallback/`.
- El renderer DEBE intentar completar el artefacto final usando el template de contingencia y mantener el output schema estándar.

### 9.3 Trazabilidad obligatoria de fallback

Al activarse el Nivel 2, `trace.warnings` DEBE incluir explícitamente:

- `SYSTEM_FALLBACK_TRIGGERED`

Además, se recomienda registrar en `trace.logs` el motivo técnico (`timeout`, `playwright_error`, `assets_corrupted`) para auditoría operativa.

---

## 10) Ciclo de vida de persistencia y archivo condicional

La Capa MCP se ejecuta sobre un VPS con rol de **procesador efímero**. La persistencia de artefactos debe ser explícita, condicional y orientada a eficiencia de almacenamiento.

### 10.1 Invariante de archivo (sincronización por modo)

#### Caso A — `generation_mode = "vision_generated"`

El MCP DEBE crear una entrada en bucket `design-archive` con estructura:

```text
archive/{event_id}/{timestamp}/
```

Contenido obligatorio por ejecución:

- `final.png` (artefacto renderizado final)
- `generated.html` (HTML generado por IA)
- `generated.css` (CSS generado por IA)
- `reference.png` (imagen de referencia original usada en Vision)
- `metadata.json` (metadatos de trazabilidad y versión de contrato)

Objetivo: garantizar reproducibilidad de carteles únicos sin depender del filesystem local.

#### Caso B — `generation_mode = "template_catalog"`

NO se crea entrada en `archive/`.

Razonamiento normativo:

- Los diseños de catálogo ya son persistentes por definición en `backend/src/templates/catalog/` (activo) o en `archive/catalog_templates` (histórico de plantillas).
- Duplicar artefactos de catálogo en `design-archive` genera redundancia de bajo valor y coste innecesario.

### 10.2 Invariante de purga del VPS

Tras confirmar éxito de renderizado (y subida a Supabase cuando aplique `vision_generated`), el MCP DEBE eliminar todos los archivos temporales locales del VPS:

- HTML/CSS intermedios
- imágenes descargadas
- PNG temporal
- cualquier artefacto auxiliar de sesión

Esta purga es obligatoria para evitar acumulación local y preservar el modelo efímero de ejecución.

---

## 11) Capacidad de hidratación (Recovery)

La Capa MCP DEBE soportar re-render de carteles históricos únicos mediante recuperación desde archivo.

### 11.1 Extensión de contrato de entrada

`intent` debe aceptar el campo opcional:

- `recovery_event_id` (`string|null`)

### 11.2 Lógica de hidratación

Si se recibe `intent.recovery_event_id`, el MCP DEBE:

1. Buscar en bucket `design-archive` la carpeta correspondiente al evento.
2. Descargar a entorno local efímero los assets archivados necesarios (`generated.html`, `generated.css`, `reference.png`, `metadata.json`, etc.).
3. Ejecutar renderizado usando esos assets hidratados.

Este flujo habilita recuperación de carteles `vision_generated` históricos que no existen como plantilla reusable en catálogo.

### 11.3 Distinción normativa (no redundancia)

- **Diseños de catálogo (`template_catalog`)**: se recuperan por `template_id` desde catálogo persistente; no requieren hidratación desde `design-archive`.
- **Diseños generados (`vision_generated`)**: se recuperan por `recovery_event_id` desde `design-archive` para reproducibilidad fiel.

La separación anterior es obligatoria para optimizar almacenamiento, reducir duplicados y preservar trazabilidad de diseños únicos.

---

## 12) Unidad Atómica de Diseño (Plantilla Local)

La Capa MCP DEBE tratar cada plantilla local como una **Unidad Atómica de Diseño** autocontenida y versionable.
El `manifest.json` es la **única fuente de configuración** consumida por el motor de renderizado para capacidad, canvas y estrategia tipográfica.

### 12.1 Estructura de directorio de plantilla

Cada `template_id` corresponde a una carpeta dentro de:

```text
backend/src/templates/catalog/
```

Estructura obligatoria por plantilla:

```text
backend/src/templates/catalog/{template_id}/
  template.html
  style.css
  manifest.json
  assets/
```

Contrato mínimo de contenido:

- `template.html`
  - Define la estructura DOM del diseño.
  - Debe exponer selectores `.slot-1` a `.slot-n` para binding determinista del lineup.
- `style.css`
  - Define estilos encapsulados por plantilla.
  - Debe soportar variables CSS (`--token`) para parametrización visual sin alterar contrato estructural.
- `manifest.json`
  - Define configuración técnica obligatoria que interpreta el MCP.
- `assets/`
  - Contiene recursos locales del diseño (imágenes, logos, texturas y variantes gráficas propias de la plantilla).

No se permiten dependencias externas implícitas entre plantillas del catálogo.

### 12.2 Contrato del `manifest.json`

Para que el MCP “entienda” la plantilla, el `manifest.json` DEBE incluir estos campos obligatorios:

- `template_id` (`string`)
- `version` (`string`)
- `display_name` (`string`)
- `canvas` (`object`)
  - `width` (`number`, px)
  - `height` (`number`, px)
- `capabilities` (`object`)
  - `min_slots` (`number`)
  - `max_slots` (`number`)
- `font_strategy` (`array[string]`)
  - Lista de Google Fonts requeridas para inyección vía `@import`.

Ejemplo canónico:

```json
{
  "template_id": "lineup_bold_v1",
  "version": "1.2.0",
  "display_name": "LineUp Bold",
  "canvas": {
    "width": 1080,
    "height": 1350
  },
  "capabilities": {
    "min_slots": 6,
    "max_slots": 8
  },
  "font_strategy": [
    "Bebas Neue",
    "Montserrat",
    "Open Sans"
  ]
}
```

Regla normativa: cualquier configuración de render (viewport, capacidad o tipografía) fuera de `manifest.json` se considera inválida por contrato.

### 12.3 Invariante de pre-vuelo y override de capacidad

Antes de renderizar, el MCP DEBE ejecutar un pre-check de capacidad usando exclusivamente el `manifest.json` de la plantilla resuelta.

#### Protocolo de validación

- El MCP compara `len(lineup)` contra `manifest.capabilities.max_slots`.
- Si `len(lineup) > manifest.capabilities.max_slots`, el render DEBE abortar con error estructurado:
  - `TEMPLATE_CAPACITY_EXCEEDED`

#### Mecanismo de override

El contrato de entrada acepta:

- `intent.force_capacity_override` (`boolean`, opcional, default `false`).

Comportamiento:

- Si `intent.force_capacity_override = true`, el MCP ignora el límite `manifest.capabilities.max_slots` y procede con el render.

#### Trazabilidad obligatoria

Cuando el override esté activo, el trace DEBE registrar:

- `CAPACITY_OVERRIDE_ACTIVE`

Este registro es obligatorio para auditoría operativa.

#### Advertencia operativa

Si se activa `force_capacity_override`, el sistema **no garantiza la integridad estética** del resultado final (overflow, solapamientos, pérdida de legibilidad, clipping).
La responsabilidad editorial y operativa recae en el Host que fuerza el override.

---

## 13) Motor de Inyección Visual e Integridad de Layout (Agnostic Renderer)

La Capa MCP DEBE comportarse como un renderer agnóstico, reactivo y especializado en producción de artefactos visuales.
Esta sección define de forma exclusiva la inyección de datos visuales, el auto-ajuste tipográfico y el principio de responsabilidad única de salida.

### 13.1 Mapeo de Capa Visual (Data-to-DOM)

La inyección de contenido DEBE ejecutarse con binding estricto, determinista y sin transformación semántica adicional.

#### Mapeo de LineUp (estricto por índice)

Para cada elemento `lineup[n]`, el renderer DEBE inyectar exclusivamente:

- `lineup[n].name` → selector `.slot-(n+1) .name`

No se permite:

- inyectar `name` en otros nodos no declarados por contrato,
- reasignar índices,
- aplicar enriquecimiento textual fuera del valor recibido.

Si el selector objetivo no existe para un índice requerido, aplica error estructurado de binding (`SLOT_BINDING_ERROR`) conforme a sección 3.3.

#### Exclusión normativa de metadatos no visuales

El campo `lineup[n].instagram` NO tiene representación en el DOM del cartel.

Invariante obligatorio:

- `lineup[n].instagram` se considera dato de transporte de payload (si hiciera falta para capas externas),
- el Agnostic Renderer NO lo procesa visualmente,
- NO se renderiza en texto, subtítulo, badge ni atributo DOM.

#### Mapeo de metadata del evento

El renderer DEBE inyectar:

- `metadata.date_text` en su selector único de fecha definido por el manual técnico de la plantilla.
- `metadata.venue` en su selector único de venue definido por el manual técnico de la plantilla.

Queda prohibido duplicar estos valores en slots de lineup o en selectores no declarados por la plantilla.

### 13.2 Invariante de Auto-ajuste de Texto (FitText Engine)

Tras finalizar la inyección Data-to-DOM, el renderer DEBE ejecutar un motor de ajuste tipográfico en contexto navegador (Playwright) para proteger la integridad del layout ante nombres extensos.

#### Algoritmo de evaluación post-inyección

Para cada nodo `.name`, el motor DEBE medir:

- `scrollWidth` del contenido,
- `clientWidth` del contenedor.

Regla de overflow:

- Si `scrollWidth > clientWidth`, existe desbordamiento horizontal y se activa ajuste.

#### Reducción dinámica obligatoria

El ajuste DEBE aplicarse de forma iterativa:

1. Tomar `font-size` computado actual del nodo.
2. Reducir en pasos de `2px`.
3. Re-evaluar `scrollWidth` vs `clientWidth` tras cada iteración.
4. Detener cuando:
   - el texto encaje (`scrollWidth <= clientWidth`), o
   - se alcance `min-font-size` definido en `manifest.json` de la plantilla.

Reglas normativas:

- Nunca bajar de `manifest.min-font-size`.
- No escalar al alza durante este ciclo (el motor solo corrige overflow por reducción).
- El ajuste se ejecuta por slot y no debe alterar el orden ni el contenido textual del lineup.

#### Trazabilidad estética obligatoria

Cualquier ajuste de fuente aplicado por FitText DEBE registrarse en `trace.logs` como evento informativo auditable.

Mínimo recomendado de payload de log:

- identificador de slot (`slot-1`, `slot-2`, ...),
- `font-size` inicial,
- `font-size` final,
- resultado (`fit_applied` o `min_font_size_reached`).

### 13.3 Output Simplificado (Single Responsibility)

La Capa MCP mantiene una salida mínima alineada con responsabilidad única del renderer visual.

Invariante de output:

- El Output Schema (§4) solo expone:
  - `output.public_url` del artefacto visual persistido,
  - `trace` con observabilidad operativa.

Queda fuera de alcance del renderer:

- generación de copies,
- captions,
- textos para redes sociales,
- transformaciones editoriales no visuales.

El renderer termina su responsabilidad al publicar el recurso gráfico y devolver su URL pública con trazabilidad.


---

## 14) Filosofía de Fallo No Bloqueante

La Capa MCP DEBE priorizar la entrega de un cartel funcional por encima de la interrupción del flujo por errores técnicos recuperables.
El principio normativo es: **si existe una ruta de render exitoso (incluyendo emergencia/fallback), el flujo no se bloquea**.

### 14.1 Filosofía de respuesta y HTTP Status

Regla obligatoria de transporte para integración con n8n:

- El MCP DEBE responder `HTTP 200 OK` siempre que el proceso de render culmine con artefacto válido, incluso si fue necesario activar recuperación automática.
- La semántica de éxito/error funcional se gestiona exclusivamente dentro del JSON de respuesta (`status`, `trace`, `warnings`, `recovery_notes`).
- Este diseño evita detener ejecuciones de n8n por códigos HTTP de error cuando el cartel ya fue entregado mediante ruta de contingencia.

### 14.2 Matriz de errores y acciones de auto-recuperación

Los errores recuperables NO deben abortar el flujo. Deben activar alternativa obligatoria según la siguiente matriz:

| Código de error | Causa | Acción de auto-recuperación (obligatoria) |
|---|---|---|
| `ERR_CONTRACT_INVALID` | JSON mal formado o incompleto | Ignorar el input dañado y renderizar plantilla en `/active/` con datos genéricos operativos. |
| `ERR_INVALID_FILE_TYPE` | La referencia no es imagen válida por Magic Bytes | Omitir modo Vision y renderizar plantilla en `/active/`. |
| `ERR_NOT_DIRECT_LINK` | La URL de referencia es wrapper HTML/no binario directo | Omitir modo Vision y renderizar plantilla en `/active/`. |
| `ERR_CAPACITY_EXCEEDED` | `lineup` supera slots máximos de la plantilla | **Recorte Automático**: renderizar solo los primeros `n` perfiles que entren; descartar el resto. |

Invariante operativo:

- En cualquiera de los casos anteriores, si la recuperación produce artefacto final, el MCP DEBE responder `HTTP 200 OK` y `status = "success"`.

### 14.3 Protocolo de notificación en el trace

Cuando ocurra auto-recuperación, el objeto `trace` DEBE notificar explícitamente la degradación controlada para que n8n informe al Host (ej. Telegram):

- `trace.status`: DEBE tomar el valor `recovered_with_warnings`.
- `trace.recovery_notes`: DEBE incluir un mensaje legible por humanos explicando la modificación aplicada.

Ejemplos válidos de `trace.recovery_notes`:

- `"Imagen de referencia inválida, se usó plantilla activa"`
- `"Lineup recortado de 8 a 5 personas"`

Adicionalmente, se recomienda mantener códigos estructurados en `trace.warnings[]` para consumo automático de nodos n8n.

### 14.4 Errores fatales (aborto real)

Solo existen dos categorías donde el sistema SÍ debe detenerse al no disponer de ruta de recuperación funcional:

1. `ERR_RENDER_ENGINE_CRASH`
   - Fallo crítico de Playwright/Chromium que impide tanto el render principal como el fallback.
2. `ERR_STORAGE_UNREACHABLE`
   - Imposibilidad total de subir el artefacto a Supabase Storage tras múltiples reintentos.

Regla final:

- Fuera de estos errores fatales, el comportamiento normativo de la Capa MCP es **fallo no bloqueante** con entrega de cartel funcional y trazabilidad explícita de recuperación.
