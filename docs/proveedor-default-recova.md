# Proveedor fijo por defecto en ingesta Bronze -> Silver

## Contexto
Se simplifica `backend/src/bronze_to_silver_ingestion.py` para el escenario MVP con un único proveedor activo (`Recova`).

## Cambios realizados
- Se define la constante global `DEFAULT_PROVEEDOR_ID = "recova-om"`.
- Se elimina el argumento CLI `--proveedor_id` para que n8n no deba enviarlo.
- La inserción en `bronze.solicitudes` y la propagación a `silver.solicitudes` usan automáticamente el proveedor resuelto desde esa constante.
- Se añade `validate_default_proveedor_id()` para validar formato cuando la constante tenga forma UUID y fallar temprano si es inválida.

## Nota de compatibilidad
Si `silver.proveedores.id` es de tipo UUID y se desea resolver por id, reemplazar `DEFAULT_PROVEEDOR_ID` por un UUID válido existente en `silver.proveedores`.
