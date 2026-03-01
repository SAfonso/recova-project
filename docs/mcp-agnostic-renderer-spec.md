# MCP Agnostic Renderer: guía técnica de adopción

## Objetivo

Este documento aterriza la adopción operativa de la nueva Capa de Abstracción MCP (Agnostic Renderer) para desacoplar n8n del mecanismo físico de renderizado.

La especificación normativa (Source of Truth) está en:

- `specs/mcp_agnostic_renderer_spec.md`

## Exposición HTTP para n8n

La operación en VPS expone `backend/src/mcp_server.py` en modo HTTP en `127.0.0.1:5050` con:

- `POST /tools/render_lineup` para consumo REST directo desde n8n.
- `GET /healthz` para sonda de disponibilidad.
- `POST /mcp` cuando está disponible `mcp[http]` (transporte streamable MCP).
- Logging por request en `backend/logs/mcp_render.log` incluyendo `event_id` para trazabilidad.

## Qué cambia para integraciones

1. **Contrato de entrada único**
   - Todo request debe incluir `event_id`, `metadata`, `lineup` e `intent`.
2. **Resolución de modo determinista**
   - Si existe `reference_image_url`, se ejecuta `vision_generated`.
   - Si no existe, se usa `template_catalog` con `template_id`.
3. **Trazabilidad obligatoria de salida**
   - El response siempre devuelve `status`, `output.public_url` y `trace`.

## Invariantes críticos de operación

- En `vision_generated` se inyecta de forma forzada un pack seguro de Google Fonts (`Bebas Neue`, `Montserrat`, `Open Sans`).
- Todo HTML que llegue al renderer debe exponer selectores `.slot-1 ... .slot-n` para binding confiable con Playwright.
- Se aplica **Security Gate** obligatorio sobre `reference_image_url`: pre-fetch de 32 bytes, validación por Magic Bytes y rechazo inmediato con `ERR_INVALID_FILE_TYPE` cuando no sea PNG/JPEG/WebP real.
- Solo se permiten **direct links** (o bucket de Supabase). URLs wrapper/preview (Google Drive estándar, Dropbox Preview, etc.) están prohibidas y deben fallar con `ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK`.
- El `trace.logs` debe registrar `ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK` en fallos de acceso/enlace no directo, junto con el MIME detectado vs esperado (`image/*`) para facilitar debugging.


## Manual operativo: URLs de referencia válidas

Para evitar fallos no deterministas en Vision-to-Code, operación debe respetar:

1. **Permitido**
   - URL directa a archivo de imagen (respuesta binaria de imagen).
   - Objeto publicado desde Supabase Storage.
2. **No permitido**
   - Páginas de visualización/compartición que devuelven HTML (wrappers).
3. **Diagnóstico estándar**
   - Si el Magic Bytes inspector detecta HTML/script o MIME no imagen, el renderer aborta por contrato (`ERR_INVALID_FILE_TYPE` o `ERR_ACCESS_DENIED_OR_NOT_DIRECT_LINK`).

## Catálogo de plantillas

Ruta base del catálogo:

```text
backend/src/templates/catalog/
```

Cada estilo debe ser autocontenido con:

- `template.html`
- `style.css`
- `manifest.json`
- `assets/` locales del estilo


## Unidad Atómica de Diseño (Plantilla Local)

La Sección 12 de la spec formaliza la plantilla local como unidad autocontenida y define que `manifest.json` es la única fuente de configuración para el render.

### Estructura obligatoria por `template_id`

```text
backend/src/templates/catalog/{template_id}/
  template.html
  style.css
  manifest.json
  assets/
```

- `template.html`: DOM con `.slot-1 ... .slot-n`.
- `style.css`: estilos encapsulados con soporte de variables CSS.
- `manifest.json`: contrato técnico consumido por MCP.
- `assets/`: imágenes, logos y texturas específicas del diseño.

### Contrato mínimo de `manifest.json`

Campos obligatorios:

- `template_id`, `version`, `display_name`.
- `canvas.width` y `canvas.height` (px; viewport Playwright).
- `capabilities.min_slots` y `capabilities.max_slots`.
- `font_strategy` (Google Fonts inyectables vía `@import`).

### Pre-vuelo de capacidad y override controlado

Pre-check obligatorio antes de render:

- Comparar `len(lineup)` con `manifest.capabilities.max_slots`.
- Si se excede capacidad, abortar con `TEMPLATE_CAPACITY_EXCEEDED`.

Override permitido por contrato:

- `intent.force_capacity_override = true` ignora `max_slots` y permite continuar.
- Con override activo, `trace.logs` debe registrar `CAPACITY_OVERRIDE_ACTIVE`.
- Advertencia normativa: no se garantiza integridad estética al forzar override; la responsabilidad recae en el Host.


## Motor de inyección visual e integridad de layout (Sección 13)

La Sección 13 de la SDD formaliza el comportamiento del renderer como motor visual agnóstico con tres invariantes operativos:

1. **Data-to-DOM estricto**
   - `lineup[n].name` se inyecta exclusivamente en `.slot-(n+1) .name`.
   - `lineup[n].instagram` queda explícitamente fuera del DOM del cartel (dato no visual).
   - `metadata.date_text` y `metadata.venue` solo se inyectan en sus selectores únicos de plantilla.
2. **FitText Engine post-inyección**
   - Tras bind de datos, Playwright evalúa cada `.name` comparando `scrollWidth` vs `clientWidth`.
   - Si hay overflow, reduce `font-size` en iteraciones de `1px` hasta encajar o alcanzar `12px` como mínimo de seguridad de layout.
   - Todo ajuste tipográfico se registra en `trace.logs` para auditoría estética.
  - Señal de fin de ajuste: al terminar, el script debe fijar `window.renderReady = true` para que Playwright sincronice el snapshot/render final.
3. **Single Responsibility de salida**
   - El renderer devuelve únicamente `output.public_url` del artefacto visual y `trace`.
   - No genera captions ni textos para redes.

## Estado

- **Implementación:** pendiente (spec-first).
- **Cobertura documental:** completa para iniciar desarrollo backend con SDD.


## Jerarquía de resiliencia (fallback strategy)

La ejecución del MCP se define en dos niveles obligatorios:

1. **Nivel 1 — Active Mode**
   - Ejecuta render según `intent` resuelto (`vision_generated` o `template_catalog`).
2. **Nivel 2 — Local Fallback**
   - Si Nivel 1 falla por `timeout`, error de Playwright o assets corruptos, el MCP debe usar `backend/src/templates/catalog/fallback/`.

Trazabilidad mínima obligatoria al activar fallback:

- `trace.warnings[]` debe contener `SYSTEM_FALLBACK_TRIGGERED`.

## Persistencia eficiente: ciclo de vida y archivo condicional

El VPS se trata como entorno efímero. La persistencia permanente se controla por modo:

- **`vision_generated`**
  - Debe crear `archive/{event_id}/{timestamp}/` en bucket `design-archive` con:
    - `final.png`
    - `generated.html`
    - `generated.css`
    - `reference.png`
    - `metadata.json`
- **`template_catalog`**
  - No debe crear entrada en `archive/`, porque el diseño ya vive en catálogo persistente (`backend/src/templates/catalog/` o `archive/catalog_templates`).

Tras render exitoso (y upload cuando aplique), el MCP debe purgar temporales del VPS para evitar acumulación.

## Capacidad de hidratación (recovery)

El contrato acepta `intent.recovery_event_id` para reconstruir carteles únicos históricos:

1. Buscar carpeta del evento en bucket `design-archive`.
2. Descargar assets archivados a entorno local efímero.
3. Re-renderizar usando esos assets.

Distinción operativa:

- `template_catalog` se recupera por `template_id` (catálogo).
- `vision_generated` se recupera por `recovery_event_id` (archivo histórico).

Esta separación evita redundancia de datos y mantiene reproducibilidad de diseños generados por IA.


## Sección 14: Fallo No Bloqueante (operación n8n-safe)

La SDD incorpora una filosofía de continuidad operativa: si el renderer logra entregar un cartel (incluso vía contingencia), la API responde `HTTP 200 OK` para no romper automatizaciones de n8n.

### Reglas operativas

1. **HTTP 200 con recuperación:** los incidentes recuperables se reportan en JSON (`status`, `trace`) y no en códigos HTTP de transporte.
2. **Matriz de auto-recuperación obligatoria:**
   - `ERR_CONTRACT_INVALID` → ignorar input dañado y renderizar `/active/` con datos genéricos.
   - `ERR_INVALID_FILE_TYPE` → omitir Vision y renderizar `/active/`.
   - `ERR_NOT_DIRECT_LINK` → omitir Vision y renderizar `/active/`.
   - `ERR_CAPACITY_EXCEEDED` → recorte automático del lineup a capacidad máxima (`n`).
3. **Trazabilidad explícita para notificación al Host:**
   - `trace.status = recovered_with_warnings`
   - `trace.recovery_notes` con mensaje humano (ej. `Imagen de referencia inválida, se usó plantilla activa`).
4. **Abortos reales restringidos a dos casos:**
   - `ERR_RENDER_ENGINE_CRASH`
   - `ERR_STORAGE_UNREACHABLE`

Con esto, la capa MCP prioriza siempre la entrega de un cartel funcional frente a la parada por error técnico recuperable.
