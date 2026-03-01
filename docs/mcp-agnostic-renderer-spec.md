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
