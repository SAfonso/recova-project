# Setup DB: Backup local preventivo antes de `--reset`

## Objetivo
Agregar una capa de seguridad en `setup_db.py` para exportar datos actuales a CSV antes de ejecutar operaciones destructivas (`RESET_SQL`).

## Cambios implementados

1. **Carpeta de respaldos**
   - Se define `BACKUP_DIR = ROOT_DIR / "backups"`.
   - Se agrega `ensure_backup_dir()` para crear la carpeta automáticamente si no existe.

2. **Respaldo por tabla objetivo**
   - Se define `BACKUP_TABLES = ("comicos_master", "solicitudes_silver", "proveedores")`.
   - Se agrega `export_current_data(cursor, backup_dir)` con este flujo:
     - Verifica si la tabla existe (`table_exists`).
     - Verifica si la tabla tiene datos (`table_has_data`).
     - Si hay datos, exporta `SELECT *` a CSV con cabecera.

3. **Nomenclatura de archivos**
   - Formato: `tabla_YYYYMMDD_HHMMSS.csv`.
   - Ejemplo: `backups/comicos_master_20260213_153245.csv`.

4. **Orden de ejecución en `--reset`**
   - Al detectar `--reset`, primero ejecuta respaldo local.
   - Si no hay datos/tablas, informa por log y continúa.
   - Solo después ejecuta `RESET_SQL`.

5. **Recordatorio de seguridad**
   - Al final del script, se imprime:
   - `Recuerda añadir la carpeta backups/ a tu .gitignore para no subir datos sensibles al repositorio`

## Resultado esperado
Se reduce el riesgo de pérdida irreversible de datos durante procesos de reset del esquema, manteniendo un respaldo local rápido y simple para restauración manual.
