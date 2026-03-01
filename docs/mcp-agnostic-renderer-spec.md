# MCP Agnostic Renderer: guía técnica de adopción

## Objetivo

Este documento aterriza la adopción operativa de la nueva Capa de Abstracción MCP (Agnostic Renderer) para desacoplar n8n del mecanismo físico de renderizado.

La especificación normativa (Source of Truth) está en:

- `specs/mcp_agnostic_renderer_spec.md`

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

## Estado

- **Implementación:** pendiente (spec-first).
- **Cobertura documental:** completa para iniciar desarrollo backend con SDD.
