# Spec: Scripts de Utilidad de Seed y Reset

## Contexto

Tres scripts de utilidad para desarrollo local que complementan `setup_db.py`.
Todos residen en `backend/scripts/` y usan `psycopg2` + `DATABASE_URL` del `.env` raíz.

---

## Script 1: `seed_conditional.py`

### Propósito
Para cada open mic existente en `silver.open_mics` que no tenga solicitudes,
inserta 10 cómicos aleatorios con sus bronze y silver solicitudes.

### Comportamiento

1. Lee todos los open mics con un LEFT JOIN a `silver.solicitudes` para contar registros.
2. Por cada open mic con 0 solicitudes:
   a. Genera 10 cómicos con nombres, instagram único (nombre_slug + prefijo_open_mic_id),
      teléfono, categoría aleatoria (mayoría `general`, algunos `priority`/`gold`).
   b. INSERT en `silver.comicos` con `ON CONFLICT (instagram) DO UPDATE SET id = silver.comicos.id RETURNING id`.
   c. INSERT en `bronze.solicitudes` con datos ficticios y `procesado = true`.
   d. INSERT en `silver.solicitudes` con `status = 'normalizado'`.
3. Si un open mic ya tiene solicitudes, se omite (log de skip).
4. Transacción única: commit al final o rollback completo.

### Contratos de datos

- `instagram`: `{slug_nombre}_{primeros_8_chars_open_mic_id}` — único por ejecución
- `fecha_evento`: próximo viernes desde hoy
- `nivel_experiencia`: 1-4 mapeado desde `experiencia_raw`
- `sheet_row_id`: entero aleatorio en rango 2000-9999 + índice

### Salida esperada (stdout)
```
  [skip] Recova Open Mic — ya tiene 5 solicitudes
  [seed] Comedy Lab Sesión — insertando 10 comicos...
Seed condicional completado: 1 open mic(s) rellenados.
```

---

## Script 2: `seed_full.py`

### Propósito
Crear desde cero un escenario de prueba completo: 1 proveedor + 3 open mics +
30 cómicos distintos (10 por open mic) con sus solicitudes.

### Comportamiento

1. Genera e inserta 1 `silver.proveedores` (nombre y slug únicos con timestamp).
2. Genera e inserta 3 `silver.open_mics` asociados a ese proveedor, con config scoring estándar.
3. Por cada open mic, genera 10 cómicos con nombres distintos entre sí y al resto de open mics:
   - 5 `general`, 3 `priority`, 1 `gold`, 1 `restricted`
   - Instagram único: `{slug_nombre}_{8chars_om_id}`
4. INSERT en `silver.comicos`, `bronze.solicitudes`, `silver.solicitudes`.
5. Imprime un resumen con IDs generados.
6. Transacción única.

### Salida esperada (stdout)
```
Proveedor creado: Test Venue 20260307 (id: ...)
Open mic 1: Test Open Mic A — 10 comicos insertados
Open mic 2: Test Open Mic B — 10 comicos insertados
Open mic 3: Test Open Mic C — 10 comicos insertados
Seed completo: 3 open mics, 30 comicos, 30 bronze, 30 silver.
```

---

## Script 3: `reset_data.py`

### Propósito
Eliminar todos los **datos** (no el esquema) de las tablas bronze/silver/gold,
con backup CSV previo opcional.

### Comportamiento

1. Genera backup CSV de todas las tablas con datos (igual que `setup_db.py`).
2. TRUNCATE con CASCADE en orden:
   - `gold.solicitudes`, `gold.comicos`, `gold.lineup_validated` (si existe)
   - `silver.lineup_slots`, `silver.solicitudes`, `silver.comicos`,
     `silver.open_mics`, `silver.organization_members`, `silver.proveedores`
   - `bronze.solicitudes`
3. NO elimina esquemas ni tablas de auth (`silver.telegram_users`, `silver.validation_tokens`
   se mantienen opcionales — flag `--include-auth`).
4. Pide confirmación interactiva antes de ejecutar (a menos que se pase `--yes`).

### Flags
- `--yes` / `-y`: omite confirmación interactiva
- `--include-auth`: también trunca `silver.telegram_users`, `silver.telegram_registration_codes`,
  `silver.validation_tokens`
- `--no-backup`: omite generación de CSV

### Salida esperada (stdout)
```
Backup generado: backups/silver_comicos_20260307_120000.csv
...
ADVERTENCIA: se borrarán TODOS los datos de bronze/silver/gold.
¿Continuar? [s/N]: s
Truncando tablas...
Reset de datos completado.
```

---

## Tests

Los tests van en `backend/tests/scripts/` y usan `unittest.mock` para parchear
`psycopg2.connect` y capturar las queries ejecutadas. No requieren BD real.

### Tests `test_seed_conditional.py`
- `test_skips_open_mic_with_solicitudes`: si total > 0, no ejecuta INSERTs
- `test_seeds_open_mic_without_solicitudes`: si total == 0, ejecuta INSERTs (comicos + bronze + silver)
- `test_instagram_unique_per_open_mic`: instagram incluye prefijo del open_mic_id
- `test_commits_on_success`: `conn.commit()` llamado
- `test_rollback_on_error`: si falla un INSERT, llama `conn.rollback()`

### Tests `test_seed_full.py`
- `test_inserts_one_proveedor`: INSERT en silver.proveedores exactamente una vez
- `test_inserts_three_open_mics`: INSERT en silver.open_mics exactamente 3 veces
- `test_inserts_thirty_comics_total`: INSERT en silver.comicos 30 veces
- `test_commits_on_success`
- `test_rollback_on_error`

### Tests `test_reset_data.py`
- `test_requires_confirmation_interactive`: sin `--yes`, pregunta antes de truncar
- `test_yes_flag_skips_confirmation`: con `--yes`, no pregunta
- `test_truncates_core_tables`: TRUNCATE ejecutado para tablas principales
- `test_no_truncate_auth_tables_by_default`: sin `--include-auth`, no toca telegram_users
- `test_include_auth_truncates_auth_tables`: con `--include-auth`, sí toca auth tables
- `test_no_backup_flag_skips_csv`: con `--no-backup`, no genera CSV
