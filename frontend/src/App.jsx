import { useEffect, useMemo, useState } from 'react';
import { supabase } from './supabaseClient';
import { ExpandedView } from './components/open-mic/ExpandedView';
import { Header } from './components/open-mic/Header';
import { NotebookSheet } from './components/open-mic/NotebookSheet';
import { ValidateButton } from './components/open-mic/ValidateButton';

const CATEGORY_OPTIONS = [
  { value: 'gold', label: 'Gold' },
  { value: 'priority', label: 'Preferred' },
  { value: 'restricted', label: 'Restricted' },
];

function App() {
  const [candidates, setCandidates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [edits, setEdits] = useState({});
  const [activeId, setActiveId] = useState(null);
  const [activeTab, setActiveTab] = useState('lineup');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [eventDate, setEventDate] = useState('');
  const [error, setError] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [recoveryNotes, setRecoveryNotes] = useState('');

  const activeCandidate = useMemo(
    () => candidates.find((candidate) => candidate.row_key === activeId),
    [candidates, activeId],
  );

  const fetchCandidates = async () => {
    setLoading(true);
    setError('');

    let rows = [];
    let useLegacyView = false;
    let hasFechaEvento = true;

    const { data: dataV2, error: errorV2 } = await supabase
      .from('lineup_candidates')
      .select('solicitud_id,fecha_evento,nombre,genero,categoria,estado,score_final,comico_id,contacto,telefono,instagram')
      .order('score_final', { ascending: false, nullsFirst: false });

    if (errorV2) {
      const isSchemaDrift = String(errorV2.message || '').includes('solicitud_id');
      if (!isSchemaDrift) {
        setError(errorV2.message);
        setLoading(false);
        return;
      }

      console.warn(
        'lineup_candidates sin columna solicitud_id en este entorno. Usando modo compatibilidad legacy.',
        { message: errorV2.message },
      );

      useLegacyView = true;
      const { data: dataLegacyWithDate, error: errorLegacyWithDate } = await supabase
        .from('lineup_candidates')
        .select('fecha_evento,nombre,genero,categoria,estado,score_final,comico_id,contacto,telefono,instagram')
        .order('score_final', { ascending: false, nullsFirst: false });

      if (errorLegacyWithDate) {
        const missingFechaEvento = String(errorLegacyWithDate.message || '').includes('fecha_evento');
        if (!missingFechaEvento) {
          setError(errorLegacyWithDate.message);
          setLoading(false);
          return;
        }

        hasFechaEvento = false;
        const { data: dataLegacy, error: errorLegacy } = await supabase
          .from('lineup_candidates')
          .select('nombre,genero,categoria,estado,score_final,comico_id,contacto,telefono,instagram')
          .order('score_final', { ascending: false, nullsFirst: false });

        if (errorLegacy) {
          setError(errorLegacy.message);
          setLoading(false);
          return;
        }

        rows = dataLegacy ?? [];
      } else {
        rows = dataLegacyWithDate ?? [];
      }
    } else {
      rows = dataV2 ?? [];
    }

    const normalized = rows.map((row, index) => ({
      ...row,
      solicitud_id: useLegacyView ? null : (row.solicitud_id ?? null),
      row_key: useLegacyView
        ? `${row.comico_id ?? 'unknown'}-${index}`
        : (row.solicitud_id ?? `${row.comico_id ?? 'unknown'}-${index}`),
      fecha_evento: hasFechaEvento ? (row.fecha_evento ?? null) : null,
      genero: row.genero === 'unknown' ? 'nb' : row.genero ?? 'nb',
      categoria: row.categoria === 'standard' ? 'priority' : row.categoria ?? 'priority',
    }));
    const scoredFirst = normalized.filter((candidate) => candidate.estado === 'scorado');
    const pendingLegacy = normalized.filter((candidate) => candidate.estado === 'pendiente');
    const selectionSource =
      scoredFirst.length > 0 ? scoredFirst : (pendingLegacy.length > 0 ? pendingLegacy : normalized);
    const firstEventDate = selectionSource.find((candidate) => candidate.fecha_evento)?.fecha_evento;

    setCandidates(normalized);
    setSelectedIds(selectionSource.slice(0, 5).map((candidate) => candidate.row_key));
    if (firstEventDate) {
      setEventDate(firstEventDate);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchCandidates();
  }, []);

  const getDraft = (candidate) => {
    const existing = edits[candidate.row_key];
    if (existing) {
      return existing;
    }
    return { categoria: candidate.categoria, genero: candidate.genero };
  };

  const hasPendingEdit = (candidate) => {
    const draft = edits[candidate.row_key];
    return !!draft && (draft.categoria !== candidate.categoria || draft.genero !== candidate.genero);
  };

  const updateDraft = (field, value) => {
    if (!activeCandidate) return;

    setEdits((previous) => ({
      ...previous,
      [activeCandidate.row_key]: {
        ...getDraft(activeCandidate),
        [field]: value,
      },
    }));
  };

  const toggleSelected = (candidateId) => {
    setSelectedIds((current) => {
      if (current.includes(candidateId)) {
        return current.filter((id) => id !== candidateId);
      }
      if (current.length >= 5) {
        return current;
      }
      return [...current, candidateId];
    });
  };

  const selectedCandidates = useMemo(
    () => candidates.filter((candidate) => selectedIds.includes(candidate.row_key)),
    [candidates, selectedIds],
  );

  const validateLineup = async () => {
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
        selectedCandidates.find((candidate) => candidate.fecha_evento)?.fecha_evento ?? null;
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

      setEdits({});

      const n8nResponse = await fetch(normalizedN8nWebhookUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fecha: rpcEventDate,
          status: 'validado',
          total: selectedIds.length,
          trace: {
            recovery_notes: recoveryNotes,
          },
        }),
      });

      if (!n8nResponse.ok) {
        const n8nErrorBody = await n8nResponse.text();
        console.error('Error HTTP desde n8n webhook', {
          status: n8nResponse.status,
          statusText: n8nResponse.statusText,
          body: n8nErrorBody,
          webhookUrl: normalizedN8nWebhookUrl,
        });
        throw new Error(`HTTP ${n8nResponse.status}`);
      }

      alert('✅ ¡LineUp validado! Enviando a n8n para generar el póster...');
      window.location.reload();
    } catch (n8nError) {
      console.error('Error enviando webhook a n8n:', n8nError);
      setError('No se pudo notificar a n8n. Revisa la consola para más detalle.');
    } finally {
      setSaving(false);
    }
  };

  const handleCategoryUpdate = (candidateId, category) => {
    const targetCandidate = candidates.find((candidate) => candidate.row_key === candidateId);
    if (!targetCandidate) {
      return;
    }

    if (activeId !== candidateId) {
      setActiveId(candidateId);
      setEdits((previous) => ({
        ...previous,
        [candidateId]: {
          ...getDraft(targetCandidate),
          categoria: category,
        },
      }));
      return;
    }

    if (!CATEGORY_OPTIONS.some((option) => option.value === category)) {
      return;
    }

    updateDraft('categoria', category);
  };

  const openExpanded = () => {
    setIsExpanded(true);
    if (!activeId && candidates.length > 0) {
      setActiveId(candidates[0].row_key);
    }
  };

  return (
    <main className="paint-bg min-h-screen px-4 pb-8">
      <div className="mx-auto flex max-w-lg flex-col gap-4 lg:max-w-5xl">
        <Header
          eventDate={eventDate}
          onEventDateChange={setEventDate}
          selectedCount={selectedIds.length}
        />

        {error && (
          <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">
            {error}
          </p>
        )}

        {loading ? (
          <section className="notebook-lines rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-8 text-center text-[#6B5C4A]">
            Cargando candidatos...
          </section>
        ) : (
          <NotebookSheet
            activeTab={activeTab}
            onTabChange={setActiveTab}
            candidates={candidates}
            selectedCandidates={selectedCandidates}
            getDraft={getDraft}
            onOpenExpanded={openExpanded}
          />
        )}

        <section className="mx-auto w-full max-w-3xl rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-4">
          <label htmlFor="recovery-notes" className="mb-2 block text-sm font-bold text-[#1a1a1a]">
            Notas de recuperación (SDD)
          </label>
          <textarea
            id="recovery-notes"
            value={recoveryNotes}
            onChange={(event) => setRecoveryNotes(event.target.value)}
            placeholder="Contexto para Telegram/n8n si el flujo necesita recovery..."
            className="min-h-24 w-full rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] p-3 text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
          />
        </section>

        <div className="flex justify-center pt-2">
          <ValidateButton
            disabled={saving || selectedIds.length !== 5}
            saving={saving}
            onClick={validateLineup}
          />
        </div>

        <p className="text-center text-sm font-bold text-[#fff8e7]">
          {selectedIds.length === 5 ? 'LineUp completo para validar' : 'Selecciona exactamente 5 cómicos'}
        </p>
      </div>

      {isExpanded && (
        <ExpandedView
          candidates={candidates}
          selectedIds={selectedIds}
          activeId={activeId}
          onClose={() => setIsExpanded(false)}
          onCardExpand={setActiveId}
          onToggleSelected={toggleSelected}
          onUpdateCategory={handleCategoryUpdate}
          getDraft={getDraft}
          hasPendingEdit={hasPendingEdit}
        />
      )}
    </main>
  );
}

export default App;
