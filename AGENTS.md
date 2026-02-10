# 🤖 Definición de Agentes y Roles (MVP)

Este documento establece las responsabilidades, estándares de nomenclatura y el flujo de decisión del sistema.

## 1. El Orquestador (n8n)
**Rol:** Sistema Nervioso Central (Event-Driven).
- **Responsabilidades:** Gestión de Webhooks, control de estados de la base de datos y orquestación de servicios externos.
- **Nomenclatura:** camelCase para nodos y variables internas (ej: `solicitudId`, `isAprobado`).

## 2. El Analista de Datos (Python: Ingestion Engine)
**Rol:** Limpieza y Normalización.
- **Estándar:** PEP 8 (snake_case).
- **Toma de Decisiones:**
    - **Determinística:** Uso de Regex para normalizar Instagram (ej: `@usuario` -> `usuario`) y validar teléfonos con prefijo internacional.
    - **Control de Errores:** Datos inválidos se marcan con `estado: error_ingesta` en Supabase.

## 3. El Estratega (Python + Gemini: Scoring Engine)
**Rol:** Inteligencia de Negocio y Curación.
- **Lógica de Decisión (Híbrida):**
    - **Capa 1 (Python):** Cálculo de `base_score` numérico (paridad, días desde última actuación, prioridad).
    - **Capa 2 (Gemini):** Análisis de lenguaje natural en comentarios. Gemini sugiere un `ai_modifier` (±10 puntos) con una razón obligatoria.
- **Decisión Final:** `final_score = base_score + ai_modifier`.

## 4. El Diseñador (Python: Canva Builder)
**Rol:** Automatización Visual.
- **Responsabilidad:** Mapear el LineUp aprobado en la API de Canva.
- **Restricción:** Solo se ejecuta con `estado: aprobado`.

## 5. La Interfaz (WhatsApp Bot)
**Rol:** Canal de Comunicación y Validación Humana.
- **Responsabilidades:** Notificación de sugerencias al Host y distribución del cartel final a los cómicos.

---

## 🛠️ Estándares de Trabajo
- **Documentación:** Cada cambio significativo genera un `.md` en `/docs`.
- **Versiones:** Incremento obligatorio en `package.json` y `pyproject.toml` según SemVer.
- **Changelog:** Registro estricto en `CHANGELOG.md` siguiendo *Keep a Changelog*.
