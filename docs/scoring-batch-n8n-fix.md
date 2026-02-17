# Corrección de scoring batch en n8n + SQL

## Problema corregido
- La vista `gold.lineup_candidates` no exponía `estado`, impidiendo filtrar en frontend por estado real.
- El flujo de scoring podía cortar tras el primer item cuando el nodo HTTP/Python recibía solo el primer registro en vez de un array/lote.

## Vista Gold corregida
Se actualizó la vista para devolver:
- `nombre`
- `genero`
- `categoria`
- `estado` (desde `gold.solicitudes`)
- `score_final`
- `contacto` (`COALESCE(telefono, instagram)`)
- `comico_id`, `telefono`, `instagram`

Además se quitó el filtro duro `WHERE s.estado = 'pendiente'` para que la pestaña **Curation** pueda ver el estado real de todos los candidatos.

## Configuración n8n recomendada (batch robusto)
Archivo plantilla: `workflows/main_pipeline.json`.

Flujo:
1. `Postgres` obtiene todos los pendientes de scoring con query **sin `LIMIT 1`**.
2. `Split in Batches` divide en lotes (ej. 25).
3. `HTTP Request` envía cada lote en JSON (`records: [...]`) al endpoint de scoring.
4. El nodo vuelve a `Split in Batches` por la salida de loop hasta vaciar entrada.
5. `continueOnFail: true` evita que el pipeline se detenga por un éxito/fallo individual.

### Query segura (sin cortes)
```sql
SELECT s.id, s.comico_id, s.fecha_evento, s.status
FROM silver.solicitudes s
WHERE s.status IN ('normalizado', 'pendiente_scoring')
ORDER BY s.created_at ASC, s.id ASC;
```

## Nota para nodos Python/HTTP
Si usas un nodo `Code`/Python en n8n, procesa `items` completos, no solo `items[0]`:

```javascript
// Node Code (JavaScript)
return items.map((item) => ({
  json: {
    ...item.json,
    ready_for_scoring: true
  }
}));
```

Y en `HTTP Request`, para enviar todo el batch:

```json
{
  "records": {{$input.all().map(i => i.json)}}
}
```
