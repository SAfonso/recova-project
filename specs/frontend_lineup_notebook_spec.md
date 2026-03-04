# Frontend Curación Notebook Spec (React/Vite)

## 1. Objetivo
Definir el contrato SDD para la interfaz de curación del MVP "AI LineUp Architect" con diseño visual notebook/cartoon, manteniendo intacta la lógica operativa existente en `frontend/src/App.jsx`.

## 2. Restricciones de arquitectura
- El frontend permanece en React + Vite.
- Prohibido migrar a Next.js (`app/page.tsx`) o TypeScript.
- Punto de entrada único: `frontend/src/App.jsx`.
- Los componentes visuales deben ser `jsx` y recibir estado/acciones vía `props`.

## 3. Invariantes funcionales
- `fetchCandidates` mantiene la carga de Supabase sobre `lineup_candidates`, incluyendo fallback legacy por drift de esquema.
- `toggleSelected` mantiene límite máximo de 5 seleccionados.
- `updateDraft` mantiene edición de `categoria`/`genero` por candidato activo (`activeId`).
- `validateLineup` mantiene secuencia: validación local -> RPC `validate_lineup` -> webhook n8n.

## 4. Contrato visual
- Fondo principal rojo con manchas (`paint-bg`).
- Contenedor de libreta con líneas y perforaciones (`notebook-lines`).
- Pestañas de vista:
  - `lineup`
  - `gold`
  - `priority`
  - `restricted`
- Botón `...` abre modal/vista expandida con todos los candidatos.
- Tarjeta expandida muestra:
  - `@instagram`
  - selector de categoría por 3 botones (`gold`, `priority`, `restricted`)
  - checkbox de inclusión en lineup

## 5. Contrato de recuperación SDD
- La UI debe exponer `textarea` de notas de recuperación (`recoveryNotes`).
- `validateLineup` debe inyectar este dato en webhook n8n:

```json
{
  "trace": {
    "recovery_notes": "<texto_host>"
  }
}
```

## 6. Criterios de aceptación
- Selección/des-selección sigue funcionando con máximo 5.
- RPC `validate_lineup` recibe exactamente el mismo payload operativo previo.
- Webhook n8n sigue enviándose y ahora incluye `trace.recovery_notes`.
- Sin dependencias de Next.js ni archivos `.ts/.tsx` en la integración nueva.
