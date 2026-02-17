# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.7] - 2026-02-17

### Added
- Nueva migración `specs/sql/migrations/20260217_fix_anon_update_policy_silver_comicos.sql` para aplicar de forma idempotente el bloque solicitado sobre `silver.comicos`: `ENABLE ROW LEVEL SECURITY`, `DROP POLICY IF EXISTS "p_anon_update_silver_comicos"` y recreación de la policy `FOR UPDATE TO anon`.

### Changed
- `setup_db.py` incorpora la nueva migración en `SQL_SEQUENCE` para que se ejecute automáticamente en despliegues estándar.
- `backend/tests/sql/test_sql_contracts.py` valida la existencia y el contenido de la migración de RLS/policy para `silver.comicos`.
- Incremento de versión a `0.5.7` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.6] - 2026-02-16

### Changed
- `specs/sql/silver_relacional.sql` estandariza las policies RLS de `anon` en `silver.comicos` con nombres técnicos idempotentes: `p_anon_select_silver_comicos` y `p_anon_update_silver_comicos`.
- `specs/sql/silver_relacional.sql` añade limpieza explícita de políticas previas antes de crear las nuevas para evitar conflictos en redeploys.
- `backend/tests/sql/test_sql_contracts.py` incorpora validación de contrato para asegurar RLS + grants de `anon` sobre `silver.comicos`.
- Incremento de versión a `0.5.6` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.5] - 2026-02-16

### Changed
- `specs/sql/silver_relacional.sql` amplía permisos de `anon` en Silver con `GRANT SELECT, UPDATE ON ALL TABLES IN SCHEMA silver` y `ALTER DEFAULT PRIVILEGES ... GRANT SELECT, UPDATE ON TABLES TO anon`.
- `specs/sql/silver_relacional.sql` incorpora políticas RLS explícitas para `anon` sobre `silver.comicos` (lectura y actualización) y grant específico `GRANT SELECT, UPDATE ON silver.comicos TO anon`.
- Incremento de versión a `0.5.5` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.4] - 2026-02-16

### Changed
- `silver.comicos` alinea nomenclatura con Gold: `nombre_artistico` pasa a `nombre` e `instagram_user` pasa a `instagram`, incluyendo migración compatible para instalaciones existentes.
- `backend/src/bronze_to_silver_ingestion.py` actualiza el upsert/lookup de cómicos Silver para operar con `instagram` y `nombre`.
- `backend/src/scoring_engine.py` y `specs/sql/gold_relacional.sql` actualizan cruces Silver -> Gold para leer `silver.comicos.instagram` y `silver.comicos.nombre`.
- `specs/sql/seed_data.sql` y `backend/tests/sql/test_sql_contracts.py` se ajustan al nuevo contrato de columnas en `silver.comicos`.
- `specs/sql/silver_relacional.sql` renombra índice legacy `idx_silver_comicos_instagram_user` a `idx_silver_comicos_instagram` cuando aplica.
- Incremento de versión a `0.5.4` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.3] - 2026-02-16

### Changed
- `setup_db.py` ahora gestiona la capa Gold como parte del ciclo estándar (`SQL_SEQUENCE`, backup de `gold.comicos`/`gold.solicitudes`, reset de esquema `gold` y verificación de enums Gold).
- `specs/sql/gold_relacional.sql` incorpora bloque de seguridad y operación equivalente a Bronze/Silver (RLS, policies `service_role` y grants del esquema).
- Tests actualizados para validar la nueva gestión de Gold en setup y contratos SQL.
- `specs/sql/gold_relacional.sql` renombra el identificador de contacto de Gold a `telefono` (antes `whatsapp`) y mantiene compatibilidad para migrar instalaciones existentes.
- `backend/src/scoring_engine.py` migra de `whatsapp` a `telefono` en lectura/escritura de Gold, logs y salida JSON.
- `specs/sql/silver_relacional.sql` elimina los flags booleanos legacy de Silver (`is_gold`, `is_priority`, `is_restricted`) y su lógica de mantenimiento en esquema.
- `specs/sql/seed_data.sql` se ajusta al nuevo contrato de `silver.comicos` sin flags booleanos.
- `backend/src/scoring_engine.py` ahora respeta la categoría proveniente de `silver.comicos.categoria` al poblar/actualizar `gold.comicos.categoria` (mapeo `general -> standard`).
- `silver.comicos` y `gold.comicos` incorporan/estandarizan el campo `genero` como `text` con default `unknown`.
- `gold.comicos.genero` migra de enum a `text` para alinear el modelo entre capas Silver y Gold.
- `setup_db.py` deja de verificar el enum `gold.genero_comico` (el enum de género ya no forma parte del contrato de Gold).
- Incremento de versión a `0.5.3` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.1] - 2026-02-16

### Changed
- Nomenclatura de tablas Gold alineada al esquema: `gold.comicos` y `gold.solicitudes` (sin sufijos `_gold`), manteniendo compatibilidad de migración desde `gold.comicos_gold` / `gold.solicitudes_gold`.
- `backend/src/scoring_engine.py` actualizado para usar tablas schema-qualified (`silver.*`, `bronze.solicitudes`, `gold.comicos`, `gold.solicitudes`) y evitar referencias legacy (`*_silver`, `*_gold`).
- `backend/tests/sql/test_sql_contracts.py` actualizado para validar los nuevos nombres de tablas en la capa Gold.
- Incremento de versión a `0.5.1` en `package.json`, `pyproject.toml` y `README.md`.

## [0.5.0] - 2026-02-16

### Added
- Script SQL `specs/sql/gold_relacional.sql` para la nueva capa `gold`, con enums `gold.genero_comico` / `gold.categoria_comico` / `gold.estado_solicitud`, tablas `gold.comicos_gold` y `gold.solicitudes_gold`, e índices para consultas de recencia/estado.
- Vista de linaje `gold.vw_linaje_silver_a_gold` para enlazar solicitudes de Silver con perfiles Gold por `whatsapp` o `instagram`.
- Motor `backend/src/scoring_engine.py` para ranking Silver -> Gold con persistencia en historial de solicitudes, descarte de blacklist y salida JSON (`top_10_sugeridos` + métricas de proceso).
- Suite `backend/tests/unit/test_scoring_engine.py` con cobertura de alias de categoría, cálculo de score, detección de disponibilidad única y desempate por `marca_temporal`.

### Changed
- `backend/tests/sql/test_sql_contracts.py` amplía contratos para validar existencia/estructura de la capa Gold y su vista de linaje con Silver.
- `.github/workflows/deploy.yml` añade gate de pruebas previo al restart/start de PM2 en deploy (`push` a `dev`), ejecutando `pytest -q backend/tests` para evitar publicar cambios con regresiones.
- Incremento de versión a `0.5.0` en `package.json`, `pyproject.toml` y `README.md`.

## [0.4.9] - 2026-02-15

### Added
- Documento técnico `docs/refactor-validacion-bronze-silver.md` con el detalle de la nueva normalización de campos obligatorios y reglas de limpieza para WhatsApp/Instagram en la ingesta Bronze -> Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` incorpora `clean_phone(phone_str)` con validación por regex `^(\+?|00)?[\d\s-]{9,}$`, limpieza de separadores, conversión de prefijo `00` a `+` y prefijo por defecto `+34` para números locales de 9 dígitos.
- `backend/src/bronze_to_silver_ingestion.py` refuerza la limpieza de Instagram para soportar `@usuario` y URLs (`instagram.com/usuario`), extrayendo únicamente el username final.
- `backend/src/bronze_to_silver_ingestion.py` añade `normalize_row(row)` para procesar las claves exactas del formulario, validar campos obligatorios y acumular errores por fila en la fase de normalización.
- `backend/src/bronze_to_silver_ingestion.py` agrega un bloque de tests unitarios locales `_unit_tests_clean_phone()` para verificar los formatos de teléfono definidos para el formulario.
- Incremento de versión a `0.4.9` en `package.json` y `pyproject.toml`.

## [0.4.8] - 2026-02-15

### Added
- Documento técnico `docs/ingesta-logs-auditoria.md` con el detalle de la nueva trazabilidad de descartes y la configuración de logs rotativos para la ingesta Bronze -> Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` incorpora logging a archivo absoluto `/root/RECOVA/backend/logs/ingestion.log` con `TimedRotatingFileHandler` diario y retención de 7 días, usando formato `%(asctime)s - %(levelname)s - %(message)s`.
- `backend/src/bronze_to_silver_ingestion.py` añade auditoría de descartes por fila con `detalles_descarte` y la expone en la salida JSON bajo la clave `errores` (incluyendo duplicados, faltas de datos y errores por validación/fase).
- `backend/src/bronze_to_silver_ingestion.py` endurece robustez del pipeline con captura de fallo fatal y `LOGGER.exception(...)` para traza completa en logs.
- Incremento de versión a `0.4.8` en `package.json` y `pyproject.toml`.

## [0.4.7] - 2026-02-15

### Added
- Workflow de GitHub Actions `.github/workflows/deploy.yml` para despliegue automático por `push` a `dev` vía `appleboy/ssh-action@master`, con actualización del código, instalación de dependencias y gestión de PM2 para `webhook-ingesta`.
- Documento `docs/github-actions-deploy-dev.md` con el comando local de creación de estructura y la plantilla YAML lista para copiar.

### Changed
- Incremento de versión a `0.4.7` en `package.json` y `pyproject.toml`.

## [0.4.6] - 2026-02-15

### Added
- Listener HTTP `backend/src/triggers/webhook_listener.py` con Flask para recibir `POST /ingest`, validar `X-API-KEY` (env `WEBHOOK_API_KEY`) y disparar la ingesta Bronze -> Silver mediante `subprocess`.
- Documento técnico `docs/webhook-listener-n8n-ingesta.md` con el flujo, seguridad básica y forma de ejecución del listener.

### Changed
- Dependencias de backend actualizadas para incluir `flask>=3.0.0` en `pyproject.toml` y `requirements.txt`.
- Incremento de versión a `0.4.6` en `package.json` y `pyproject.toml`.

## [0.4.5] - 2026-02-15

### Added
- Documento técnico `docs/ingesta-batch-bronze-queue.md` con la migración del proceso de ingesta desde modo CLI a worker batch sobre cola Bronze.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` elimina `argparse` y ahora procesa en lote las filas pendientes de `bronze.solicitudes` (`procesado = false`) leyendo directamente desde PostgreSQL/Supabase.
- `backend/src/bronze_to_silver_ingestion.py` mantiene la limpieza de `instagram`, `telefono` y fechas, añade normalización explícita de `disponibilidad_ultimo_minuto` (`sí/no` -> `true/false`) y conserva el mapeo de `info_show_cercano`/`origen_conocimiento` hacia Silver.
- `backend/src/bronze_to_silver_ingestion.py` marca `procesado = true` solo en casos exitosos; ante error por fila registra `error_ingesta` en `metadata` (o `raw_data_extra` fallback) y continúa con el resto de la cola.
- `backend/src/old/ingestion_cli_backup.py` conserva la versión anterior basada en argumentos CLI como respaldo operativo.
- Incremento de versión a `0.4.5` en `package.json` y `pyproject.toml`.

## [0.4.4] - 2026-02-14

### Added
- Documento técnico `docs/ingesta-whatsapp-show-cercano-origen.md` con el detalle del nuevo mapeo de WhatsApp y los campos de contexto de solicitud en Bronze/Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` agrega aliases CLI `--whatsapp`/`--Whatsapp` para mapear el campo de Google Sheets a `telefono_raw` en Bronze y normalizarlo a `telefono` en `silver.comicos`.
- `backend/src/bronze_to_silver_ingestion.py` incorpora `--show_cercano_raw` y `--conociste_raw`, persistiendo en `bronze.solicitudes.info_show_cercano`/`bronze.solicitudes.origen_conocimiento` y en `silver.solicitudes.show_cercano`/`silver.solicitudes.origen_conocimiento`.
- `backend/src/bronze_to_silver_ingestion.py` endurece la limpieza de `disponibilidad_ultimo_minuto`: cualquier texto que contenga `si` (insensible a mayúsculas y acentos) se normaliza a `true`, en otro caso `false`.
- `specs/sql/silver_relacional.sql` añade de forma idempotente las columnas `show_cercano` y `origen_conocimiento` en `silver.solicitudes` para mantener consistencia con la ingesta.
- Incremento de versión a `0.4.4` en `package.json` y `pyproject.toml`.

## [0.4.3] - 2026-02-14

### Added
- Documento técnico `docs/ingesta-constraint-unicidad-proveedor-slug.md` con la corrección persistente para `ON CONFLICT (comico_id, fecha_evento)` y la unificación del slug de proveedor por defecto.

### Changed
- `specs/sql/silver_relacional.sql` añade y garantiza de forma idempotente la restricción única `uq_silver_solicitudes_comico_fecha` sobre `(comico_id, fecha_evento)` para compatibilidad con la ingesta Bronze -> Silver.
- `specs/sql/seed_data.sql` unifica el slug del proveedor semilla de `recova-open` a `recova-om`.
- Incremento de versión a `0.4.3` en `package.json` y `pyproject.toml`.

## [0.4.2] - 2026-02-14

### Added
- Documento técnico `docs/stack-tecnologico-infraestructura-mvp.md` con el estado actual de despliegue self-hosted, capas de datos y flujo operativo del MVP.

### Changed
- `README.md` incorpora la nueva sección visual **Stack Tecnológico e Infraestructura (MVP Actual)** con detalle de VPS, Coolify, n8n, Supabase por capas Bronze/Silver, integraciones y flujo de datos Google Sheets -> n8n -> Python.
- Incremento de versión a `0.4.2` en `package.json` y `pyproject.toml`.

## [0.4.1] - 2026-02-14

### Added
- Documento técnico `docs/proveedor-default-recova.md` con la simplificación de proveedor único en la ingesta Bronze -> Silver.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` define `DEFAULT_PROVEEDOR_ID` como constante global fija para el proveedor Recova y elimina el argumento CLI `--proveedor_id`.
- `backend/src/bronze_to_silver_ingestion.py` aplica automáticamente el proveedor por defecto en inserciones a `bronze.solicitudes` y `silver.solicitudes` vía linaje Bronze.
- `backend/src/bronze_to_silver_ingestion.py` añade validación temprana de formato para `DEFAULT_PROVEEDOR_ID` cuando tenga forma de UUID, para compatibilidad con esquemas PostgreSQL UUID.
- Incremento de versión a `0.4.1` en `package.json` y `pyproject.toml`.

## [0.4.0] - 2026-02-14

### Added
- Documento técnico `docs/ingesta-atomica-n8n.md` con el flujo event-driven de ingesta atómica para n8n.

### Changed
- `backend/src/bronze_to_silver_ingestion.py` migra de procesamiento batch (`fetch_pending_bronze_rows`) a ejecución atómica por argumentos CLI (`argparse`) y salida JSON de integración para n8n.
- `backend/src/bronze_to_silver_ingestion.py` ahora inserta primero en `bronze.solicitudes`, recupera `bronze_id` y luego procesa Silver con `SAVEPOINT` para rollback parcial y trazabilidad de `error_ingesta`.
- `backend/src/bronze_to_silver_ingestion.py` incorpora resolución de `proveedor_id` por UUID o `slug`, con valor por defecto `recova-om`.
- Incremento de versión a `0.4.0` en `package.json` y `pyproject.toml`.

## [0.3.0] - 2026-02-13

### Added
- Documento técnico `docs/bronze-solo-solicitudes-linaje-silver.md` con el modelo simplificado de linaje Bronze -> Silver.

### Changed
- `specs/sql/bronze_multi_proveedor_master.sql` elimina la tabla redundante de cómicos en Bronze y deja únicamente `bronze.solicitudes` como tabla cruda.
- `specs/sql/bronze_multi_proveedor_master.sql` incorpora normalización de columna legacy `whatsapp_raw` hacia `telefono_raw`.
- `specs/sql/silver_relacional.sql` consolida maestras y transaccional en Silver (`silver.comicos`, `silver.proveedores`, `silver.solicitudes`) con FK obligatoria de linaje `bronze_id -> bronze.solicitudes(id)`.
- `specs/sql/seed_data.sql` se adapta al nuevo flujo sin `bronze.comicos`.
- `backend/src/bronze_to_silver_ingestion.py` se adapta al flujo directo Bronze -> `silver.comicos` -> `silver.solicitudes` (sin tabla intermedia de cómicos en Bronze).
- `setup_db.py` actualiza tablas de backup al modelo simplificado por esquemas.
- Incremento de versión a `0.3.0` en `package.json` y `pyproject.toml`.

## [0.2.0] - 2026-02-13

### Added
- Documento técnico `docs/esquemas-bronze-silver.md` con la separación física de capas por esquemas reales.
- Estructura SQL schema-qualified en capas:
  - `bronze.comicos`, `bronze.solicitudes`
  - `silver.proveedores`, `silver.comicos`, `silver.solicitudes`

### Changed
- `specs/sql/bronze_multi_proveedor_master.sql` crea y gestiona el esquema `bronze` con RLS/políticas propias para `service_role`.
- `specs/sql/silver_relacional.sql` crea y gestiona el esquema `silver`, mueve objetos legacy desde `public`, y aplica FKs explícitas entre esquemas.
- Se corrigen defaults UUID en SQL para usar `gen_random_uuid()` (sin prefijo `public.`), evitando el error `UndefinedFunction` en Supabase/PostgreSQL.
- Enums migrados al esquema `silver` con nombres `silver.tipo_categoria` y `silver.tipo_status`.
- `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` adaptada para operar sobre `silver.tipo_status`.
- `specs/sql/seed_data.sql` actualizada para poblar tablas `bronze.*` y `silver.*`.
- `setup_db.py` actualizada para backup/reset por esquema y verificación de enums en `silver`.
- `backend/src/bronze_to_silver_ingestion.py` actualizada para leer/escribir en `bronze.*` y `silver.*`.
- Incremento de versión a `0.2.0` en `package.json` y `pyproject.toml`.

## [0.1.9] - 2026-02-13

### Added
- Documento técnico `docs/seed-unique-comico-fecha-fix.md` con el ajuste del seed para respetar la unicidad de `solicitudes_silver`.

### Changed
- `specs/sql/seed_data.sql` corrige el caso de Nora Priority para evitar duplicidad en `(comico_id, fecha_evento)` y mantener compatibilidad con `uq_solicitudes_silver_comico_fecha`.
- `docs/seed-data-casos-borde.md` actualiza la descripción del caso de doblete para reflejar el comportamiento compatible con la restricción de unicidad.
- Incremento de versión a `0.1.9` en `package.json` y `pyproject.toml`.

## [0.1.8] - 2026-02-13

### Added
- Documento técnico `docs/bronze-silver-comicos-sync.md` con el diseño de separación de `comicos_master` por capa y sincronización Bronze -> Silver.

### Changed
- `specs/sql/bronze_multi_proveedor_master.sql` migra la identidad Bronze a `public.comicos_master_bronze` con índice, trigger y política RLS propios.
- `specs/sql/silver_relacional.sql` mantiene `public.comicos_master` como directorio Silver enriquecido y agrega sincronización idempotente desde `public.comicos_master_bronze`.
- `specs/sql/silver_relacional.sql` conserva compatibilidad de migración in-place con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para instalaciones legacy.
- `specs/sql/seed_data.sql` ahora puebla primero `comicos_master_bronze` y luego sincroniza `comicos_master`.
- `backend/src/bronze_to_silver_ingestion.py` actualiza el flujo para hacer upsert en Bronze y sincronización posterior en Silver.
- `setup_db.py` amplía backup y reset para incluir ambas tablas de identidad (`comicos_master_bronze` y `comicos_master`).
- Incremento de versión a `0.1.8` en `package.json` y `pyproject.toml`.

### Removed
- Documento `docs/silver-comicos-master-schema-compat.md`, reemplazado por la nueva guía de separación Bronze/Silver.

## [0.1.7] - 2026-02-13

### Added
- Documento técnico `docs/silver-comicos-master-schema-compat.md` con la causa raíz del fallo de seed y la estrategia de compatibilidad entre Bronze y Silver.

### Changed
- `specs/sql/silver_relacional.sql` ahora completa `public.comicos_master` con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para `nombre_artistico`, `telefono`, `is_gold`, `is_priority`, `is_restricted` y `metadata_comico` cuando la tabla ya existe por ejecución previa de Bronze.
- `specs/sql/silver_relacional.sql` agrega de forma idempotente la constraint `chk_comicos_master_telefono_e164` para instalaciones previas sin esa validación.
- Incremento de versión a `0.1.7` en `package.json` y `pyproject.toml`.

## [0.1.6] - 2026-02-13

### Added
- Documento técnico `docs/setup-db-backup-reset-seed.md` con el flujo final de despliegue local seguro (`backup + reset + seed`) para `setup_db.py`.

### Changed
- Refactor de `setup_db.py` con nuevo flag `--seed` para ejecutar `specs/sql/seed_data.sql` tras el esquema.
- Endurecimiento transaccional de `setup_db.py` con bloque `try/except/finally`, `rollback()` ante fallo y cierre explícito de conexión.
- Mejora de trazas de consola en `setup_db.py` para reportar backup, reset, aplicación de esquema y seed con mensajes claros.
- Incremento de versión a `0.1.6` en `package.json` y `pyproject.toml`.

## [0.1.5] - 2026-02-13

### Added
- Script de seed data `specs/sql/seed_data.sql` con 2 proveedores, 11 cómicos y 18 solicitudes Silver con casos de borde (spammer, doblete y restringido activo).
- Documento técnico `docs/seed-data-casos-borde.md` con instrucciones de ejecución y validación rápida.

### Changed
- Incremento de versión a `0.1.5` en `package.json` y `pyproject.toml`.

## [0.1.4] - 2026-02-12

### Added
- Documento técnico `docs/ingesta-bronze-silver-error-handling.md` con el detalle de la refactorización de manejo de errores Bronze -> Silver.

### Changed
- Refactor de `backend/src/bronze_to_silver_ingestion.py` para mantener errores de ingesta exclusivamente en Bronze (`raw_data_extra.error_log`) y evitar cualquier inserción de errores en `solicitudes_silver`.
- Robustez en `map_experience_level` con fallback por defecto a `0` y warning cuando el texto no coincide exactamente.
- Robustez en `parse_event_dates` para ignorar tokens inválidos de fecha con warning sin romper el procesamiento completo de la fila.
- Trazabilidad de fallos por fase (`normalizacion`, `parsing_fechas`, `mapeo_experiencia`, `upsert_comico`, `insert_silver`) y timestamp UTC en el registro de error.

## [0.1.3] - 2026-02-12

### Added
- Migración SQL en `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` para extender `tipo_solicitud_status` con `no_seleccionado` y `expirado`.
- Script de ingesta transaccional en `backend/src/bronze_to_silver_ingestion.py` con normalización de identidad, explosión de fechas, anti-duplicados por `(comico_id, fecha_evento)` y expiración automática de reservas a 60 días.
- Documento técnico `docs/ingesta-bronze-silver-reserva.md` con flujo, ejecución y garantías de idempotencia.

### Changed
- Especificación `specs/sql/silver_relacional.sql` para soportar explosión de fechas (eliminación de `unique` en `bronze_id`) y nuevos índices únicos `(bronze_id, fecha_evento)` y `(comico_id, fecha_evento)`.
- Dependencias de backend con `psycopg2-binary` en `pyproject.toml` y `requirements.txt`.
## [0.1.4] - 2026-02-13

### Added
- Respaldo preventivo en `setup_db.py` previo a `--reset`: creación automática de carpeta `backups/`, exportación de datos a CSV con timestamp por tabla objetivo (`comicos_master`, `solicitudes_silver`, `proveedores`) y logs de continuidad cuando no hay datos o tablas aún no existen.
- Recordatorio al finalizar la ejecución para añadir `backups/` al `.gitignore` y evitar subir datos sensibles.
- Documentación técnica en `docs/setup-db-backup-local.md`.

## [0.1.3] - 2026-02-13

### Added
- Script `setup_db.py` para despliegue secuencial del esquema SQL en Supabase, con carga de `DATABASE_URL` desde `.env`, verificación de enums y opción `--reset` para limpieza de tablas y tipos.
- Migración `specs/sql/migrations/20260212_alter_tipo_solicitud_status.sql` para asegurar la existencia y completitud de `tipo_solicitud_status`.
- Documentación técnica en `docs/setup-db-migraciones.md`.

## [0.1.2] - 2026-02-12

### Added
- Script SQL de Capa Silver relacional en `specs/sql/silver_relacional.sql`, con tablas `comicos_master` y `solicitudes_silver`, restricciones de calidad, unicidad semanal de aprobados, triggers de `updated_at` y políticas RLS para `service_role`.
- Documento técnico de soporte en `docs/silver-relacional.md` explicando la normalización y el impacto en el motor de scoring.

## [0.1.1] - 2026-02-12

### Added
- Script SQL base para Capa Bronze, infraestructura multi-proveedor y master data de cómicos en `specs/sql/bronze_multi_proveedor_master.sql`.
- Documento técnico de soporte en `docs/bronze-multi-proveedor-master-data.md`.

## [0.1.0] - 2026-02-10

### Added
- Definición de roles y responsabilidades en `AGENTS.md`.
- Estructura de versionado híbrida (`package.json` + `pyproject.toml`).
- Configuración de dependencias base para Python.
- Definición de flujo de decisión híbrido (Lógica determinística + IA).
- Roadmap inicial del MVP en el README.
