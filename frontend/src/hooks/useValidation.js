import { useCallback, useState } from 'react';
import { supabase } from '../supabaseClient';

export function useValidation({
  openMicId, eventDate, selectedIds, selectedCandidates,
  getDraft, recoveryNotes,
  setError, setCandidates, setIsValidated, clearEdits,
}) {
  const [saving, setSaving] = useState(false);
  const [showCambiarConfirm, setShowCambiarConfirm] = useState(false);

  const validateLineup = useCallback(async () => {
    const n8nWebhookUrl = import.meta.env.VITE_N8N_WEBHOOK_URL;

    if (selectedIds.length !== 5) {
      setError('Debes seleccionar exactamente 5 cómicos para validar el lineup.');
      return;
    }

    setSaving(true);
    try {
      setError('');
      console.log('🔗 URL de n8n detectada:', n8nWebhookUrl);

      const normalizedN8nWebhookUrl =
        typeof n8nWebhookUrl === 'string' ? n8nWebhookUrl.trim() : '';

      if (!normalizedN8nWebhookUrl) {
        console.error(
          'Error de configuración: VITE_N8N_WEBHOOK_URL está vacía o no definida. Revisa las variables de entorno en Vercel y en frontend/.env.',
          { n8nWebhookUrl },
        );
        alert('⚠️ Error de configuración: La URL de n8n no está definida en las variables de entorno.');
        return;
      }

      if (!normalizedN8nWebhookUrl.startsWith('http')) {
        console.warn(
          'VITE_N8N_WEBHOOK_URL parece mal formada (debe empezar por http/https). Se aborta el fetch para evitar rutas relativas.',
          { normalizedN8nWebhookUrl },
        );
        return;
      }

      const payload = selectedCandidates.map((candidate) => {
        const draft = getDraft(candidate);
        return {
          row_key: candidate.row_key,
          solicitud_id: candidate.solicitud_id,
          comico_id: candidate.comico_id,
          fecha_evento: candidate.fecha_evento,
          categoria: draft.categoria,
          genero: draft.genero,
        };
      });
      const selectedEventDate =
        selectedCandidates.find((c) => c.fecha_evento)?.fecha_evento ?? null;
      const rpcEventDate = selectedEventDate ?? (eventDate || null);

      const { error: rpcError } = await supabase.rpc('validate_lineup', {
        p_selection: payload,
        p_event_date: rpcEventDate,
      });

      if (rpcError) {
        setError(rpcError.message);
        return;
      }

      setCandidates((previous) =>
        previous.map((candidate) => {
          const edited = payload.find((entry) => entry.row_key === candidate.row_key);
          if (!edited) {
            return candidate;
          }
          return { ...candidate, categoria: edited.categoria, genero: edited.genero };
        }),
      );

      clearEdits();

      // Grabar slots confirmados ANTES de notificar a n8n
      const approvedIds = selectedCandidates
        .map((c) => c.solicitud_id)
        .filter(Boolean);
      const { error: upsertError } = await supabase.schema('silver').rpc('upsert_confirmed_lineup', {
        p_open_mic_id: openMicId,
        p_fecha_evento: rpcEventDate,
        p_approved_solicitud_ids: approvedIds,
      });
      if (upsertError) {
        console.error('Error en upsert_confirmed_lineup:', upsertError);
      }

      // Persistir en localStorage para sobrevivir remounts
      localStorage.setItem(`validated_${openMicId}`, '1');
      setIsValidated(true);

      // n8n es fire-and-forget: si falla no bloquea el estado validado
      const lineupPayload = selectedCandidates.map((c) => ({
        name: c.nombre,
        instagram: (c.instagram || '').replace('@', '').trim(),
      }));
      fetch(normalizedN8nWebhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fecha: rpcEventDate,
          open_mic_id: openMicId,
          status: 'validado',
          total: selectedIds.length,
          lineup: lineupPayload,
          trace: { recovery_notes: recoveryNotes },
        }),
      }).then((res) => {
        if (!res.ok) {
          res.text().then((body) =>
            console.error('n8n webhook error', { status: res.status, body }),
          );
        }
      }).catch((err) => {
        console.error('Error enviando webhook a n8n:', err);
      });

    } catch (n8nError) {
      console.error('Error en validateLineup:', n8nError);
      setError('Error al validar. Revisa la consola para más detalle.');
    } finally {
      setSaving(false);
    }
  }, [openMicId, eventDate, selectedIds, selectedCandidates, getDraft, recoveryNotes, setError, setCandidates, setIsValidated, clearEdits]);

  const handleCambiarAccept = useCallback(async () => {
    await supabase.rpc('reset_lineup_slots', {
      p_open_mic_id: openMicId,
      p_fecha_evento: eventDate || null,
    });
    localStorage.removeItem(`validated_${openMicId}`);
    setIsValidated(false);
    setShowCambiarConfirm(false);
  }, [openMicId, eventDate, setIsValidated]);

  return {
    saving,
    showCambiarConfirm,
    setShowCambiarConfirm,
    validateLineup,
    handleCambiarAccept,
  };
}
