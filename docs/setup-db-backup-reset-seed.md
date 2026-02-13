# setup_db.py: Backup + Reset + Seed robusto

## Objetivo
Consolidar `setup_db.py` como herramienta de despliegue local segura para Supabase/PostgreSQL, garantizando:

1. **Backup preventivo** antes de operaciones destructivas (`--reset`).
2. **Aplicación secuencial de esquema** y **siembra opcional** (`--seed`).
3. **Transaccionalidad y rollback** ante errores para evitar estados inconsistentes.

## Cambios implementados

### 1) Nuevo flag `--seed`
Se añadió el argumento opcional `--seed` para ejecutar `specs/sql/seed_data.sql` al final de la secuencia de esquema.

- Si el archivo no existe, se levanta `FileNotFoundError` y se activa rollback.
- El script no altera UUIDs del seed; ejecuta el SQL tal cual para respetar IDs deterministas.

### 2) Refuerzo de backup local previo a `--reset`
Antes de borrar tablas/enums:

- Se crea la carpeta `backups/` si no existe.
- Se evalúan tablas objetivo (`comicos_master`, `solicitudes_silver`, `proveedores`).
- Solo se exportan CSV de tablas existentes con datos.
- Se usa timestamp en formato `YYYYMMDD_HHMMSS`.

Si ocurre cualquier fallo (I/O, permisos, lectura), la ejecución se detiene y no se realiza reset.

### 3) Salida de consola mejorada
Mensajes explícitos para seguimiento:

- `📦 Backup generado: backups/<tabla>_<timestamp>.csv`
- `🗑️ Reset completado (Tablas y Enums eliminados)`
- `🏗️ Esquema aplicado: specs/sql/...`
- `🌱 Datos de prueba inyectados correctamente.`

### 4) Robustez transaccional
El flujo principal se ejecuta dentro de `try/except/finally`:

- `commit()` al finalizar correctamente.
- `rollback()` obligatorio ante cualquier excepción.
- Reempaquetado de error con mensaje de consistencia para troubleshooting.

## Uso

```bash
python setup_db.py --reset --seed
```

También soporta:

```bash
python setup_db.py --reset
python setup_db.py --seed
python setup_db.py
```
