# Refactorización de Reglas de Validación de Datos (Bronze -> Silver)

## Resumen
Se actualizó `backend/src/bronze_to_silver_ingestion.py` para robustecer la normalización de campos provenientes del formulario, especialmente en los campos obligatorios `¿Nombre?`, `¿Instagram?` y `Whatsapp`.

## Cambios implementados

### 1. Normalización crítica de WhatsApp
- Se añadió `clean_phone(phone_str)` como función independiente.
- Se aplica la regex de entrada `^(\+?|00)?[\d\s-]{9,}$`.
- Se eliminan espacios y guiones.
- Si el número inicia con `00`, se transforma a `+`.
- Si llega un número local de 9 dígitos sin prefijo, se agrega `+34` por defecto.
- Se valida salida en formato E.164.

### 2. Limpieza de Instagram
- Se añadió extracción de usuario cuando el valor viene como URL (`instagram.com/usuario`).
- Se eliminan espacios extremos y el prefijo `@`.
- Se limpian sufijos de querystring y fragmentos (`?`, `#`).

### 3. Normalización de fila completa
- Se creó `normalize_row(row)` con las claves exactas del formulario:
  - `¿Nombre?`
  - `¿Instagram?`
  - `Whatsapp`
  - `¿Has actuado alguna vez?`
  - `Fecha`
  - `Si nos falla alguien en ultimo momento ¿Te podemos llamar?`
  - `¿Tienes algun Show cercano o algo?`
  - `¿Por donde nos conociste?`
- `¿Nombre?` se estandariza con `.strip().title()`.
- `Fecha` se conserva como string (`fechas_raw`) y también como lista (`fechas_lista`).
- Si falla un campo obligatorio, la fila se marca como inválida y se retorna una lista de errores.

### 4. Integración con el pipeline
- `process_single_solicitud(...)` ahora utiliza `normalize_row(...)` en la fase `normalizacion`.
- Si la fila no es válida, se lanza un error de validación por fase y se aprovecha la misma ruta de auditoría ya existente:
  - logging con `LOGGER.exception(...)`
  - persistencia de `error_ingesta` en metadata/raw_data_extra
  - inclusión en `detalles_descarte`

### 5. Bloque de tests unitarios en el script
- Se agregó `_unit_tests_clean_phone()` al final del script para validar formatos:
  - `666555888`
  - `666-555-888`
  - `66-65-55-88-8`
  - `666 555 888`
  - `+34666555888`
  - `0034666555888`
