# 🤖 Agents.md: AI LineUp Architect (v2.1 · Arquitectura MCP)

Este documento define responsabilidades, contratos de caja negra y protocolos de comunicación para los agentes del sistema, alineados con el SDD (secciones §1-§13).

## 1. Agente Ingestor (Estado: OPERATIVO 🟢)
**Responsabilidad:** Procesar solicitudes desde `solicitudes_bronze` (datos crudos de Google Forms) hacia `solicitudes_silver` (datos normalizados y validados).

### Reglas de Normalización Aplicadas
**Whatsapp:**
- **Entrada:** Acepta formatos con espacios, guiones, prefijos `+` o `00`.
- **Procesamiento:** Regex `^(\\+?|00)?[\\d\\s-]{9,}$`.
- **Salida:** Formato internacional limpio (ej: `+34666555888`). Si tiene 9 dígitos sin prefijo, se añade `+34` por defecto.

**Instagram:**
- **Limpieza:** Eliminación de espacios, símbolo `@` y extracción del usuario cuando se recibe URL completa.

**Campos Críticos:**
- `¿Nombre?`, `¿Instagram?` y `Whatsapp` son obligatorios. Si fallan, el registro se marca como inválido.

### Infraestructura Técnica
- **Script:** `data_ingestion.py`.
- **Trazabilidad:** Logs diarios en `/root/RECOVA/backend/logs/ingestion.log`.
- **Validación:** Batería de tests unitarios operativa en `test_ingestion.py` (`pytest`).

## 2. Agente Scorer (Estado: EN DESARROLLO 🟡)
**Responsabilidad:** Actuar como puente entre `solicitudes_silver` y el Designer/MCP Renderer, produciendo el contrato de entrada canónico para renderizado.

### Contrato Funcional (Caja Negra)
- **Input:** Datos normalizados de `solicitudes_silver`, histórico de actuaciones, señales de prioridad y contexto operativo.
- **Output:** **Input Schema Canónico** del evento (SDD §2.2), incluyendo:
  - Normalización final de nombres de artistas.
  - Asignación obligatoria de `event_id`.
  - Lista final de slots lista para inyección por plantilla.

### Reglas de Negocio Obligatorias
- **Validación de Capacidad por Plantilla:** Antes de confirmar cualquier LineUp, el Scorer debe validar cardinalidad y compatibilidad contra el `manifest.json` de la plantilla seleccionada en el Designer.
- **Política de Selección:** Mantener criterios de antigüedad, balance de género y prioridad interna como señales de scoring del candidato.
- **Bloqueo de Publicación:** Si el esquema no cumple contrato o excede capacidad declarada por plantilla, el LineUp no se confirma.

## 3. Agente Designer / MCP Renderer (Estado: EN DESARROLLO 🟡)
**Responsabilidad (Caja Negra Pura):** Transformar un JSON canónico de entrada en un único artefacto visual `.png`.

### Motor y Ejecución
- **Herramienta:** `MCP Renderer (Playwright + Vision-to-Code)`.
- **Contrato de Entrada:** JSON canónico emitido por Scorer (sin lógica de negocio adicional en render).
- **Contrato de Salida:**
  - URL persistida en Supabase Storage.
  - Objeto `trace` con metadatos de ejecución para auditoría.

### Invariantes Críticos de Render
- **Auto-ajuste de Texto (FitText):** El renderer debe ajustar tipografía para preservar legibilidad y no desbordar contenedores.
- **Inyección por Selectores `.slot-n`:** El binding de contenido se realiza exclusivamente por selectores estructurados de plantilla.

### Gestión de Fallbacks (Resiliencia)
- **Jerarquía obligatoria:** `Intento Primario -> Plantilla Fallback`.
- Si el render primario falla validación o ejecución, se activa la plantilla fallback con el mismo contrato de entrada.

## 🛠️ Notas de Infraestructura General
- **Entorno:** Python 3.12 bajo `venv` en `/root/RECOVA`.
- **Modelo Stateless:** El VPS no almacena imágenes finales; la persistencia se delega a Supabase Storage bucket `design-archive`.
- **Seguridad de Artefactos:** Todas las referencias externas pasan por Gatekeeper de Magic Bytes antes de procesar o persistir.
- **Orquestación MCP:** n8n orquesta mediante llamadas a herramientas MCP y contratos entre agentes, no por scripts lineales acoplados.
- **Persistencia Operativa:** PM2 mantiene procesos de servicio (`webhook-ingesta`) y tareas de integración.
- **Base de Datos:** Supabase PostgreSQL (conexión vía URI).
