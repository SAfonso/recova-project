# Seed Data SQL con Casos de Borde

Se agrega el script `specs/sql/seed_data.sql` para poblar entorno de pruebas del MVP con escenarios realistas y de validación:

- 2 proveedores (`recova-open`, `comedy-lab`).
- 11 cómicos en `comicos_master_bronze` como fuente y sincronización en `comicos_master`:
  - 2 `gold`
  - 3 `priority`
  - 5 `general`
  - 1 `restricted` con `is_restricted=true` y metadata de veto.
- 18 solicitudes en `solicitudes_silver` con distribución de fechas entre `current_date + 1` y `current_date + 15`.
- Casos de borde incluidos:
  - **Spammer**: un cómico con 4 solicitudes en fechas distintas.
  - **Doblete controlado**: un cómico con solicitudes consecutivas en ambos proveedores (sin violar unicidad `comico_id + fecha_evento`).
  - **Restringido activo**: solicitud en estado `normalizado` para validar exclusión en scoring.
- Coherencia de UUIDs entre `proveedores`, `comicos_master_bronze`, `comicos_master`, `solicitudes_bronze` y `solicitudes_silver`.
- Inserciones idempotentes con `ON CONFLICT ... DO NOTHING`.

## Ejecución

```bash
psql "$DATABASE_URL" -f specs/sql/seed_data.sql
```

## Validación rápida sugerida

```sql
select count(*) from public.proveedores;
select categoria, count(*) from public.comicos_master_bronze group by categoria order by categoria;
select categoria, count(*) from public.comicos_master group by categoria order by categoria;
select status, count(*) from public.solicitudes_silver group by status order by status;
```
