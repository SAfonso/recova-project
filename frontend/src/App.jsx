import { useEffect, useMemo, useState } from 'react';
import { supabase } from './supabaseClient';

const CATEGORY_OPTIONS = [
  { value: 'gold', label: 'Gold' },
  { value: 'priority', label: 'Preferred' },
  { value: 'restricted', label: 'Restricted' },
];

const GENDER_OPTIONS = [
  { value: 'm', label: 'm' },
  { value: 'f', label: 'f' },
  { value: 'nb', label: 'nb' },
];

function App() {
  const [candidates, setCandidates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [edits, setEdits] = useState({});
  const [activeId, setActiveId] = useState(null);
  const [activeTab, setActiveTab] = useState('lineup');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [eventDate, setEventDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState('');

  const activeCandidate = useMemo(
    () => candidates.find((candidate) => candidate.comico_id === activeId),
    [candidates, activeId],
  );

  useEffect(() => {
    const fetchCandidates = async () => {
      setLoading(true);
      setError('');

      const { data, error: fetchError } = await supabase
        .from('lineup_candidates')
        .select('nombre,genero,categoria,score_final,comico_id,telefono,instagram')
        .order('score_final', { ascending: false, nullsFirst: false });

      if (fetchError) {
        setError(fetchError.message);
        setLoading(false);
        return;
      }

      const normalized = (data ?? []).map((row) => ({
        ...row,
        genero: row.genero === 'unknown' ? 'nb' : row.genero ?? 'nb',
        categoria: row.categoria === 'standard' ? 'priority' : row.categoria ?? 'priority',
      }));

      setCandidates(normalized);
      setSelectedIds(normalized.slice(0, 5).map((candidate) => candidate.comico_id));
      setLoading(false);
    };

    fetchCandidates();
  }, []);

  const getDraft = (candidate) => {
    const existing = edits[candidate.comico_id];
    if (existing) {
      return existing;
    }
    return { categoria: candidate.categoria, genero: candidate.genero };
  };

  const hasPendingEdit = (candidate) => {
    const draft = edits[candidate.comico_id];
    return !!draft && (draft.categoria !== candidate.categoria || draft.genero !== candidate.genero);
  };

  const updateDraft = (field, value) => {
    if (!activeCandidate) return;

    setEdits((previous) => ({
      ...previous,
      [activeCandidate.comico_id]: {
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
    () => candidates.filter((candidate) => selectedIds.includes(candidate.comico_id)),
    [candidates, selectedIds],
  );

  const validateLineup = async () => {
    if (selectedIds.length !== 5) {
      setError('Debes seleccionar exactamente 5 cómicos para validar el lineup.');
      return;
    }

    setSaving(true);
    setError('');

    const payload = selectedCandidates.map((candidate) => {
      const draft = getDraft(candidate);
      return {
        comico_id: candidate.comico_id,
        categoria: draft.categoria,
        genero: draft.genero,
      };
    });

    const { error: rpcError } = await supabase.rpc('validate_lineup', {
      p_selection: payload,
      p_event_date: eventDate,
    });

    if (rpcError) {
      setError(rpcError.message);
      setSaving(false);
      return;
    }

    setCandidates((previous) =>
      previous.map((candidate) => {
        const edited = payload.find((entry) => entry.comico_id === candidate.comico_id);
        if (!edited) {
          return candidate;
        }
        return { ...candidate, categoria: edited.categoria, genero: edited.genero };
      }),
    );

    setEdits({});
    setSaving(false);
  };

  return (
    <main className="mx-auto min-h-screen max-w-7xl bg-slate-950 p-6 text-slate-100">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">LineUp Curator</h1>
          <p className="text-sm text-slate-300">Gestiona la selección y curación de solicitudes desde el esquema gold.</p>
        </div>

        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-xl font-semibold text-emerald-300">
          {selectedIds.length}/5
        </div>
      </header>

      <section className="mb-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => setActiveTab('lineup')}
          className={`rounded-md px-4 py-2 text-sm font-medium ${
            activeTab === 'lineup' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-200'
          }`}
        >
          Propuestos (5)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('curation')}
          className={`rounded-md px-4 py-2 text-sm font-medium ${
            activeTab === 'curation' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-200'
          }`}
        >
          Curation
        </button>

        <label className="ml-auto flex items-center gap-2 text-sm text-slate-300">
          Fecha del evento
          <input
            type="date"
            value={eventDate}
            onChange={(event) => setEventDate(event.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100"
          />
        </label>
      </section>

      {error && <p className="mb-4 rounded-md border border-rose-700 bg-rose-900/30 p-3 text-sm text-rose-200">{error}</p>}

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-3">
          {loading ? (
            <p className="text-slate-300">Cargando candidatos...</p>
          ) : (
            (activeTab === 'lineup' ? selectedCandidates : candidates).map((candidate) => {
              const draft = getDraft(candidate);
              const selected = selectedIds.includes(candidate.comico_id);
              return (
                <article
                  key={candidate.comico_id}
                  className={`rounded-xl border p-4 ${
                    selected ? 'border-emerald-500/70 bg-slate-900' : 'border-slate-800 bg-slate-900/60'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold">{candidate.nombre ?? candidate.instagram}</h2>
                      <p className="text-sm text-slate-400">@{candidate.instagram}</p>
                      <p className="text-sm text-slate-400">{candidate.telefono}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-slate-300">Score: {candidate.score_final?.toFixed?.(2) ?? '-'}</p>
                      {hasPendingEdit(candidate) && (
                        <span className="mt-1 inline-block rounded-full bg-amber-400/20 px-2 py-0.5 text-xs font-medium text-amber-200">
                          Editado
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-300">
                    <span className="rounded-full bg-slate-800 px-2 py-0.5">Categoría: {draft.categoria}</span>
                    <span className="rounded-full bg-slate-800 px-2 py-0.5">Género: {draft.genero}</span>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => toggleSelected(candidate.comico_id)}
                      className="rounded-md border border-emerald-500/60 px-3 py-1.5 text-sm text-emerald-200"
                    >
                      {selected ? 'Quitar del lineup' : 'Añadir al lineup'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveId(candidate.comico_id)}
                      className="rounded-md border border-indigo-500/60 px-3 py-1.5 text-sm text-indigo-200"
                    >
                      Abrir ficha
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </div>

        <aside className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h3 className="mb-3 text-lg font-semibold">Ficha de cómico</h3>
          {!activeCandidate ? (
            <p className="text-sm text-slate-400">Selecciona "Abrir ficha" para editar categoría o género antes de validar.</p>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-slate-300">
                <span className="font-semibold">{activeCandidate.nombre ?? activeCandidate.instagram}</span> · @{activeCandidate.instagram}
              </p>

              <label className="block text-sm text-slate-300">
                Categoría
                <select
                  value={getDraft(activeCandidate).categoria}
                  onChange={(event) => updateDraft('categoria', event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
                >
                  {CATEGORY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm text-slate-300">
                Género
                <select
                  value={getDraft(activeCandidate).genero}
                  onChange={(event) => updateDraft('genero', event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
                >
                  {GENDER_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          <button
            type="button"
            disabled={saving || selectedIds.length !== 5}
            onClick={validateLineup}
            className="mt-6 w-full rounded-md bg-emerald-500 px-4 py-2 font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? 'Validando...' : 'Validar LineUp'}
          </button>
        </aside>
      </section>
    </main>
  );
}

export default App;
