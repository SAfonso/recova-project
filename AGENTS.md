# 🤖 Agents.md: AI LineUp Architect (v2.0)

Este documento define las responsabilidades, reglas de negocio y estado de implementación de los agentes que componen el sistema.

## 1. Agente Ingestor (Estado: OPERATIVO 🟢)
**Responsabilidad:** Procesar las solicitudes desde `solicitudes_bronze` (datos crudos de Google Forms) hacia `solicitudes_silver` (datos normalizados).

### Reglas de Normalización Aplicadas
**Whatsapp:**
- **Entrada:** Acepta formatos con espacios, guiones, prefijos `+` o `00`.
- **Procesamiento:** Regex `^(\\+?|00)?[\\d\\s-]{9,}$`.
- **Salida:** Formato internacional limpio (ej: `+34666555888`). Si tiene 9 dígitos sin prefijo, se añade `+34` por defecto.

**Instagram:**
- **Limpieza:** Eliminación de espacios, símbolo `@` y extracción del usuario si se recibe una URL completa.

**Campos Críticos:**
- `¿Nombre?`, `¿Instagram?` y `Whatsapp` son obligatorios. Si fallan, el registro se marca como inválido.

### Infraestructura Técnica
- **Script:** `data_ingestion.py`.
- **Trazabilidad:** Logs diarios en `/root/RECOVA/backend/logs/ingestion.log`.
- **Validación:** Batería de tests unitarios operativa en `test_ingestion.py` (`pytest`).

## 2. Agente Scorer (Estado: EN DEFINICIÓN 🟡)
**Responsabilidad:** Analizar la tabla `solicitudes_silver` y el historial de actuaciones para proponer el LineUp semanal (6-8 cómicos).

### Lógica de Scoring (Próximos Pasos)
- **Antigüedad:** Prioridad para quienes llevan más tiempo sin actuar.
- **Balance de Género:** Algoritmo de equilibrio para garantizar diversidad en el cartel.
- **Prioridad:** Gestión de solicitudes con flag de "emergencia" o prioridad interna.
- **Evolutivo 1:** Integración de contexto histórico mediante MCP (Model Context Protocol).

## 3. Agente Designer (Estado: PENDIENTE 🔴)
**Responsabilidad:** Transformar el LineUp seleccionado en una pieza gráfica profesional.

### Especificaciones
- **Entrada:** Lista final de cómicos validada por el host.
- **Herramienta:** Canva API.
- **Mapeo:** Vinculación de los nombres y usuarios de Instagram (limpios) con los campos de texto de la plantilla predefinida.
- **Salida:** Generación automática del póster y envío de confirmación.

## 🛠️ Notas de Infraestructura General
- **Entorno:** Python 3.12 bajo `venv` en `/root/RECOVA`.
- **Orquestación:** n8n (`main_pipeline.json`).
- **Persistencia:** Gestionada por PM2 (`webhook-ingesta`).
- **Base de Datos:** Supabase PostgreSQL (conexión vía URI).
