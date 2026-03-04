# Especificación SDD: Motor de Renderizado Local con Playwright

## 1) Análisis del Payload Actual

Fuente analizada: nodo **"Code in JavaScript"** del workflow `workflows/n8n/LineUp.json`.

### 1.1 Comportamiento actual
El nodo transforma los items de entrada en un único objeto plano con esta forma:

```json
{
  "fecha": "...",
  "nombre_1": "...",
  "nombre_2": "...",
  "nombre_3": "...",
  "nombre_4": "...",
  "nombre_5": "..."
}
```

### 1.2 Riesgo de TypeError (items vacío)
Actualmente se usa:

```js
fecha: items[0].json.fecha_evento
```

Si `items.length === 0`, `items[0]` es `undefined` y se produce un error de acceso a propiedad (`Cannot read properties of undefined`), interrumpiendo la ejecución del flujo.

### 1.3 Pérdida de información de Instagram
Aunque el `HTTP Request3` consulta `select=nombre,instagram`, el nodo Code solo conserva `nombre_N` y descarta `instagram`. Esto rompe la trazabilidad hacia la fase de diseño/publicación y obliga a recomputar o volver a consultar datos en fases posteriores.

### 1.4 Debilidad estructural del payload
El formato `nombre_1..nombre_5`:
- No escala para lineups de tamaño variable.
- Acopla lógica de negocio al índice.
- Dificulta validación automática (schema) y versionado del contrato.

---

## 2) Contrato de Input (Propuesta)

> Objetivo: definir el **payload exacto** que recibirá el script Python de renderizado Playwright.

## 2.1 Recomendación de corrección previa en n8n
El workflow debe:
1. Tomar `fecha_evento` del **webhook inicial** como fuente canónica.
2. Estructurar cómicos en un **array** de objetos preservando `nombre` e `instagram`.
3. Enviar un objeto único tipado (no campos posicionales `nombre_1...`).

## 2.2 Esquema de Input (v1)

```json
{
  "request_id": "string-uuid",
  "schema_version": "1.0",
  "event": {
    "date": "YYYY-MM-DD",
    "venue": "string|null",
    "city": "string|null",
    "title": "string|null",
    "timezone": "Europe/Madrid"
  },
  "lineup": [
    {
      "order": 1,
      "name": "string",
      "instagram": "string|null"
    }
  ],
  "template": {
    "template_id": "lineup_default_v1",
    "width": 1080,
    "height": 1350,
    "theme": "default"
  },
  "render": {
    "format": "png",
    "quality": 100,
    "scale": 2,
    "timeout_ms": 15000
  },
  "metadata": {
    "source": "n8n.LineUp",
    "initiated_at": "ISO-8601",
    "trace_id": "string"
  }
}
```

## 2.3 Reglas de validación del Input
- `request_id`: obligatorio, UUID válido.
- `schema_version`: obligatorio, valor permitido `1.0`.
- `event.date`: obligatorio, formato `YYYY-MM-DD`.
- `lineup`: obligatorio, array de 1 a 8 elementos.
- `lineup[].order`: obligatorio, entero positivo, sin duplicados.
- `lineup[].name`: obligatorio, string no vacío tras trim.
- `lineup[].instagram`: opcional/null permitido; si viene informado, debe ir limpio (sin `@`, sin URL completa).
- `template.width` y `template.height`: obligatorios, enteros > 0.
- `render.timeout_ms`: obligatorio, entero entre 3000 y 60000.

---

## 3) Contrato de Output (Preparado para MCP)

> Objetivo: devolver respuesta estructurada y extensible, no un string plano.

## 3.1 Output de éxito

```json
{
  "status": "success",
  "request_id": "string-uuid",
  "render_id": "string-uuid",
  "storage": {
    "provider": "supabase",
    "bucket": "posters",
    "path": "YYYY-MM-DD/lineup_{request_id}.png",
    "storage_url": "https://.../storage/v1/object/public/posters/YYYY-MM-DD/lineup_{request_id}.png",
    "public_url": "https://.../storage/v1/object/public/posters/YYYY-MM-DD/lineup_{request_id}.png",
    "public": true
  },
  "artifact": {
    "format": "png",
    "dimensions": {
      "width": 1080,
      "height": 1350
    },
    "size_bytes": 245123,
    "checksum_sha256": "hex-string"
  },
  "timing": {
    "execution_time_ms": 1320,
    "browser_launch_ms": 210,
    "html_injection_ms": 120,
    "screenshot_ms": 760,
    "upload_ms": 180
  },
  "warnings": [],
  "meta": {
    "schema_version": "1.0",
    "generated_at": "ISO-8601",
    "engine": "playwright-chromium",
    "engine_version": "string"
  }
}
```

### 3.1.1 Proceso de Upload (Supabase Storage)
- El artefacto PNG se sube al bucket **`posters`** en Supabase Storage.
- Convención de nombre obligatoria: `YYYY-MM-DD/lineup_{request_id}.png`.
- Las credenciales de subida se obtienen exclusivamente de variables de entorno:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
- `public_url` es obligatorio en respuestas de éxito y debe apuntar al objeto público generado en el bucket.

## 3.2 Output de error

```json
{
  "status": "error",
  "request_id": "string-uuid|null",
  "error": {
    "code": "RENDER_TIMEOUT",
    "message": "Human-readable message",
    "details": {
      "stage": "browser_launch|template_load|data_bind|screenshot|upload",
      "retryable": true,
      "timeout_ms": 15000
    }
  },
  "timing": {
    "execution_time_ms": 15034
  },
  "meta": {
    "schema_version": "1.0",
    "generated_at": "ISO-8601"
  }
}
```

---

## 4) Invariantes

## 4.1 Plantilla HTML base
- Debe existir una plantilla base versionada (`template_id`).
- Debe exponer placeholders/dataslots deterministas para:
  - Fecha del evento.
  - Hasta 8 posiciones de lineup.
  - Handle de Instagram por cada cómico (si existe).
- Debe renderizar de forma estable en viewport fijo (`width` x `height`) sin depender de red externa para estilos/fuentes críticas.
- Debe soportar fallback visual para campos faltantes (ej. instagram nulo).

## 4.2 Restricciones de texto
- `name`: máximo **32 caracteres** visibles por línea.
- Si excede límite:
  1. Intentar ajuste tipográfico predefinido.
  2. Si no cabe, truncar con ellipsis (`…`) conservando legibilidad.
- `instagram`: máximo **30 caracteres**; truncado con ellipsis si excede.

## 4.3 Regla de cardinalidad del lineup
- Caso nominal: 5 a 8 cómicos.
- Si hay **menos de 5 cómicos**:
  - El render **no falla** por defecto.
  - Se completa con placeholders visuales (`"Próximamente"`) hasta 5 slots mínimos.
  - Se añade warning estructurado en output:
    - `code: "LINEUP_UNDER_MINIMUM"`
    - `details.current_count`
    - `details.minimum_required = 5`
- Si hay 0 cómicos, se trata como error de validación de input (ver sección 5).

---

## 5) Manejo de Errores

## 5.1 Mapeo de códigos HTTP
- `200 OK`: render completado (incluye warnings no bloqueantes).
- `400 Bad Request`: payload inválido (schema/validación).
- `404 Not Found`: `template_id` inexistente.
- `409 Conflict`: `request_id` duplicado en modo idempotente.
- `422 Unprocessable Entity`: payload válido pero no procesable por reglas de negocio (ej. lineup vacío).
- `500 Internal Server Error`: fallo interno no clasificado.
- `502 Bad Gateway`: fallo de dependencia de almacenamiento externo.
- `504 Gateway Timeout`: timeout total de render.

## 5.2 Catálogo mínimo de errores de dominio
- `INVALID_INPUT_SCHEMA`
- `INVALID_LINEUP_DATA`
- `TEMPLATE_NOT_FOUND`
- `PLAYWRIGHT_BROWSER_LAUNCH_FAILED`
- `PLAYWRIGHT_TEMPLATE_INJECTION_FAILED`
- `PLAYWRIGHT_RENDER_TIMEOUT`
- `PLAYWRIGHT_SCREENSHOT_FAILED`
- `STORAGE_UPLOAD_FAILED`
- `UNEXPECTED_INTERNAL_ERROR`

## 5.3 Formato obligatorio de error
Toda respuesta de error debe seguir:

```json
{
  "status": "error",
  "request_id": "string-uuid|null",
  "error": {
    "code": "UPPER_SNAKE_CASE",
    "message": "Descripción accionable",
    "details": {
      "stage": "string",
      "retryable": true,
      "hint": "Sugerencia operativa"
    }
  },
  "meta": {
    "generated_at": "ISO-8601",
    "schema_version": "1.0"
  }
}
```

## 5.4 Criterio de retry
- `retryable = true` para errores transitorios (timeout, storage temporal, arranque de browser).
- `retryable = false` para errores de contrato/input/template inexistente.
