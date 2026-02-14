# Stack Tecnológico e Infraestructura del MVP

## Objetivo
Documentar el estado actual de la infraestructura del proyecto **AI LineUp Architect** en su fase MVP, diferenciando claramente lo **self-hosted** de los servicios en la nube.

## Infraestructura de ejecución (Self-Hosted)
- **VPS propio** asociado al dominio `machango.org`.
- **Coolify** como plataforma de gestión de aplicaciones y contenedores para despliegue y operación.
- **n8n** ejecutándose en el VPS (instalación nativa o contenedorizada según entorno) para orquestación event-driven en tiempo real.

## Persistencia de datos (Cloud)
- **Supabase (PostgreSQL)** como motor principal.
- Arquitectura por capas:
  - **Bronze (`bronze.solicitudes`)**: almacenamiento RAW con trazabilidad completa de ingesta.
  - **Silver (`silver.*`)**: capa normalizada para operación, scoring y reporting.

## Integraciones externas
- **Google Cloud Platform (OAuth2)** para conexión segura con Google Sheets y Google Drive.
- **Python 3.10+** para motores de ingesta, limpieza y scoring.
- **OpenAI API (preparado)** para curación y validación de lenguaje natural.
- **Canva API** para la automatización del cartel final.

## Flujo operativo resumido
1. Un cambio en Google Sheets dispara un trigger de n8n.
2. n8n invoca el script local de Python dentro de la infraestructura gestionada por Coolify.
3. El script persiste primero en Bronze y luego normaliza hacia Silver.
4. Con los datos curados, continúan los procesos de scoring, aprobación y generación visual.
