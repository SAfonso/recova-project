import { useCallback, useEffect, useState } from 'react';
import { InfoConfigurator } from './open-mic/InfoConfigurator';
import { ScoringConfigurator } from './ScoringConfigurator';
import { supabase } from '../supabaseClient';

const DEFAULTS = {
  available_slots: 8,
  categories: {
    standard:   { base_score: 50,   enabled: true },
    priority:   { base_score: 70,   enabled: true },
    gold:       { base_score: 90,   enabled: true },
    restricted: { base_score: null, enabled: true },
  },
  recency_penalty:   { enabled: true,  last_n_editions: 2,  penalty_points: 20 },
  single_date_boost: { enabled: true,  boost_points: 10 },
  gender_parity:     { enabled: false, target_female_nb_pct: 40 },
  poster:            { enabled: false, base_image_url: null },
};

function mergeDefaults(config) {
  return {
    ...DEFAULTS,
    ...(config ?? {}),
    categories:        { ...DEFAULTS.categories,        ...(config?.categories        ?? {}) },
    recency_penalty:   { ...DEFAULTS.recency_penalty,   ...(config?.recency_penalty   ?? {}) },
    single_date_boost: { ...DEFAULTS.single_date_boost, ...(config?.single_date_boost ?? {}) },
    gender_parity:     { ...DEFAULTS.gender_parity,     ...(config?.gender_parity     ?? {}) },
    poster:            { ...DEFAULTS.poster,            ...(config?.poster            ?? {}) },
  };
}

const CATEGORY_DOT = {
  gold:       'bg-[#D4A017]',
  priority:   'bg-[#A0A0A0]',
  restricted: 'bg-[#DC2626]',
  standard:   'bg-[#6B5C4A]',
};

const BackIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="15 18 9 12 15 6" />
  </svg>
);

const ChevronRightIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const LinkIcon = () => (
  <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </svg>
);

const UploadIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="16 16 12 12 8 16" />
    <line x1="12" y1="12" x2="12" y2="21" />
    <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3" />
  </svg>
);

function InfoRow({ label, value, dot }) {
  return (
    <div className="flex items-center justify-between border-b border-[#C8B89A] py-2 last:border-0">
      <div className="flex items-center gap-2">
        {dot && <span className={`h-2 w-2 shrink-0 rounded-full border border-[#1a1a1a]/20 ${dot}`} />}
        <span className="text-xs text-[#6B5C4A]">{label}</span>
      </div>
      <span className="text-sm font-bold text-[#1a1a1a]">{value}</span>
    </div>
  );
}

function InfoCard({ openMic }) {
  const info = openMic.config?.info ?? {};
  const createdAt = new Date(openMic.created_at).toLocaleDateString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });

  return (
    <div className="animate-pop-in comic-panel rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-6 py-4 shadow-[6px_6px_0px_rgba(0,0,0,0.3)]">
      <h1 className="font-['Bangers'] text-3xl tracking-wide text-[#1a1a1a]">
        {openMic.nombre}
      </h1>
      <p className="mb-4 mt-1 text-xs text-[#6B5C4A]">Creado el {createdAt}</p>

      <div className="flex flex-col">
        {info.local     && <InfoRow label="Local"       value={info.local} />}
        {info.direccion && <InfoRow label="Dirección"   value={info.direccion} />}
        {info.hosts?.length > 0 && (
          <InfoRow label="Host(s)" value={info.hosts.join(', ')} />
        )}
        {info.dia_semana && (
          <InfoRow
            label="Día"
            value={info.hora ? `${info.dia_semana} · ${info.hora}` : info.dia_semana}
          />
        )}
        {!info.dia_semana && info.hora && <InfoRow label="Hora" value={info.hora} />}
        {info.instagram && <InfoRow label="Instagram" value={`@${info.instagram}`} />}
        {!info.local && !info.direccion && !info.hosts?.length && !info.dia_semana && !info.instagram && (
          <p className="py-2 text-sm italic text-[#6B5C4A]">
            Sin información adicional — edita en Configurar → Info
          </p>
        )}
      </div>
    </div>
  );
}

export function OpenMicDetail({ session, openMicId, initialView = 'info', onBack, onEnterLineup }) {
  const [openMic,         setOpenMic]         = useState(null);
  const [loading,         setLoading]         = useState(true);
  const [error,           setError]           = useState(null);
  const [view,            setView]            = useState(initialView);
  const [configTab,       setConfigTab]       = useState('info');
  const [showDeletePanel, setShowDeletePanel] = useState(false);
  const [deleting,        setDeleting]        = useState(false);
  const [deleteConfirm,   setDeleteConfirm]   = useState('');
  const [deleteError,     setDeleteError]     = useState('');
  const [creatingForm,    setCreatingForm]    = useState(false);
  const [formError,       setFormError]       = useState('');
  const [formUrlInput,    setFormUrlInput]    = useState('');
  const [analyzing,       setAnalyzing]       = useState(false);
  const [analyzeResult,   setAnalyzeResult]   = useState(null);
  const [analyzeError,    setAnalyzeError]    = useState('');

  const fetchOpenMic = useCallback(() => {
    setLoading(true);
    setError(null);
    supabase
      .schema('silver')
      .from('open_mics')
      .select('id, nombre, created_at, config')
      .eq('id', openMicId)
      .single()
      .then(({ data, error: err }) => {
        if (err) setError(err.message);
        else setOpenMic(data);
        setLoading(false);
      });
  }, [openMicId]);

  useEffect(() => { fetchOpenMic(); }, [fetchOpenMic]);

  const handleSaved = () => {
    fetchOpenMic();
    setView('info');
  };

  const handleCreateForm = async () => {
    const backendUrl = import.meta.env.VITE_BACKEND_URL;
    const apiKey = import.meta.env.VITE_WEBHOOK_API_KEY;
    setCreatingForm(true);
    setFormError('');
    try {
      const res = await fetch(`${backendUrl}/api/open-mic/create-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
        body: JSON.stringify({ open_mic_id: openMicId, nombre: openMic.nombre }),
      });
      const data = await res.json();
      if (!res.ok) {
        setFormError(data.message ?? 'Error creando el form');
        return;
      }
      fetchOpenMic();
    } catch {
      setFormError('No se pudo conectar con el backend.');
    } finally {
      setCreatingForm(false);
    }
  };

  const extractFormId = (urlOrId) => {
    const match = urlOrId.match(/\/forms\/d\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : urlOrId.trim();
  };

  const handleAnalyzeForm = async () => {
    const formId = extractFormId(formUrlInput);
    if (!formId) return;
    const backendUrl = import.meta.env.VITE_BACKEND_URL;
    const apiKey = import.meta.env.VITE_WEBHOOK_API_KEY;
    setAnalyzing(true);
    setAnalyzeError('');
    setAnalyzeResult(null);
    try {
      const res = await fetch(`${backendUrl}/api/open-mic/analyze-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
        body: JSON.stringify({ open_mic_id: openMicId, form_id: formId }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAnalyzeError(data.message ?? 'Error al analizar el formulario');
        return;
      }
      setAnalyzeResult(data);
      fetchOpenMic();
    } catch {
      setAnalyzeError('No se pudo conectar con el backend.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDelete = async () => {
    if (deleteConfirm !== openMic.nombre) {
      setDeleteError('El nombre no coincide.');
      return;
    }
    setDeleting(true);
    setDeleteError('');
    const { error: err } = await supabase
      .schema('silver')
      .from('open_mics')
      .delete()
      .eq('id', openMicId);
    setDeleting(false);
    if (err) { setDeleteError(err.message); return; }
    onBack();
  };

  return (
    <main className="paint-bg min-h-screen px-4 pb-8">
      <div className="mx-auto flex max-w-lg flex-col gap-4 lg:max-w-3xl">

        {/* Header */}
        <div className="flex items-center justify-between pt-6">
          <button type="button" onClick={view === 'config' ? () => setView('info') : onBack} className="btn-back">
            <BackIcon />
            {view === 'config' ? 'Volver' : 'Atrás'}
          </button>
          <p className="text-xs font-bold text-[#fff8e7]/60">{session.user.email}</p>
        </div>

        {loading ? (
          <div className="animate-pop-in rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-8">
            <div className="flex flex-col gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between border-b border-[#C8B89A] py-2">
                  <div className="h-3 w-24 rounded" style={{ background: 'linear-gradient(90deg, #e8dfc8 25%, #f5f0e1 50%, #e8dfc8 75%)', backgroundSize: '200% 100%', animation: `shimmer 1.4s infinite ${i * 0.1}s` }} />
                  <div className="h-3 w-16 rounded" style={{ background: 'linear-gradient(90deg, #e8dfc8 25%, #f5f0e1 50%, #e8dfc8 75%)', backgroundSize: '200% 100%', animation: `shimmer 1.4s infinite ${i * 0.1 + 0.2}s` }} />
                </div>
              ))}
            </div>
            <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
          </div>
        ) : error ? (
          <div className="rounded-lg border-[3px] border-[#DC2626] bg-[#fee2e2] p-6 text-sm text-[#7f1d1d]">
            {error}
          </div>
        ) : view === 'info' ? (
          <>
            <InfoCard openMic={openMic} />

            {/* Acciones principales */}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setView('config')}
                className="flex-1 cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] py-3 font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#C8B89A] hover:shadow-[3px_3px_0px_rgba(0,0,0,0.25)]"
              >
                Configurar
              </button>
              <button
                type="button"
                onClick={onEnterLineup}
                className="comic-shadow flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] py-3 font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626] hover:scale-[1.02] active:scale-[0.98]"
              >
                Ver Lineup
                <ChevronRightIcon />
              </button>
            </div>

            {/* Google Form */}
            <div className="animate-slide-up stagger-1 paper-drop paper-tape"><div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] px-6 py-4">
              <h3 className="mb-3 font-['Bangers'] text-lg tracking-wide text-[#1a1a1a]">Google Form</h3>

              {/* Links al form auto-creado */}
              {openMic.config?.form && (
                <div className="mb-4 flex flex-col gap-2">
                  <a
                    href={openMic.config.form.form_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex cursor-pointer items-center gap-1.5 text-sm font-bold text-[#DC2626] underline underline-offset-2 hover:text-[#7f1d1d]"
                  >
                    <LinkIcon />
                    Abrir formulario
                  </a>
                  <a
                    href={openMic.config.form.sheet_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex cursor-pointer items-center gap-1.5 text-sm font-bold text-[#DC2626] underline underline-offset-2 hover:text-[#7f1d1d]"
                  >
                    <LinkIcon />
                    Ver respuestas (Sheet)
                  </a>
                </div>
              )}

              {/* Botón crear form si no existe */}
              {!openMic.config?.form && (
                <div className="mb-4">
                  {formError && <p className="mb-2 text-xs text-[#DC2626]">{formError}</p>}
                  <button
                    type="button"
                    onClick={handleCreateForm}
                    disabled={creatingForm}
                    className="comic-shadow flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] py-2.5 text-sm font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <UploadIcon />
                    {creatingForm ? 'Creando form...' : 'Crear Google Form'}
                  </button>
                </div>
              )}

              {/* Separador */}
              <div className="mb-3 border-t border-[#C8B89A]" />

              {/* Análisis de campos */}
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-[#6B5C4A]">
                {openMic.config?.field_mapping ? 'Re-analizar formulario' : 'Analizar campos del form'}
              </p>
              {openMic.config?.field_mapping && (
                <p className="mb-2 flex items-center gap-1.5 text-xs text-[#22C55E]">
                  <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>
                  Campos mapeados — {Object.values(openMic.config.field_mapping).filter(Boolean).length} de {Object.keys(openMic.config.field_mapping).length}
                </p>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={formUrlInput || openMic.config?.external_form_id || ''}
                  onChange={(e) => setFormUrlInput(e.target.value)}
                  placeholder="URL o ID del Google Form"
                  className="flex-1 rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-2 text-xs text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
                />
                <button
                  type="button"
                  onClick={handleAnalyzeForm}
                  disabled={analyzing || !(formUrlInput || openMic.config?.external_form_id || openMic.config?.form?.form_id)}
                  className="shrink-0 cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] px-3 py-2 text-xs font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {analyzing ? 'Analizando...' : 'Analizar'}
                </button>
              </div>

              {analyzeError && (
                <p className="mt-2 text-xs text-[#DC2626]">{analyzeError}</p>
              )}

              {analyzeResult && (
                <div className="mt-3 rounded-md border-2 border-[#22C55E]/40 bg-[#f0fdf4] p-3">
                  <p className="mb-1 text-xs font-bold text-[#15803d]">
                    {analyzeResult.canonical_coverage} de {analyzeResult.total_questions} campos mapeados
                  </p>
                  {analyzeResult.unmapped_fields.length > 0 && (
                    <p className="text-xs text-[#6B5C4A]">
                      Sin mapeo: {analyzeResult.unmapped_fields.join(', ')}
                    </p>
                  )}
                </div>
              )}
            </div></div>

            {/* Zona de peligro */}
            <div className="animate-slide-up stagger-2 paper-drop paper-tape"><div className="paper-rough paper-note border-[3px] border-[#DC2626]/60 bg-[#fffef5] px-6 py-4">
              <h3 className="mb-3 font-['Bangers'] text-lg tracking-wide text-[#7f1d1d]">Zona de peligro</h3>
              {showDeletePanel ? (
                <>
                  <p className="mb-3 text-sm text-[#1a1a1a]">
                    Escribe <span className="font-mono font-bold">{openMic.nombre}</span> para confirmar:
                  </p>
                  <input
                    type="text"
                    value={deleteConfirm}
                    onChange={(e) => { setDeleteConfirm(e.target.value); setDeleteError(''); }}
                    placeholder={openMic.nombre}
                    className="mb-3 w-full rounded-md border-2 border-[#DC2626] bg-[#F5F0E1] px-3 py-2 text-sm font-bold text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
                  />
                  {deleteError && (
                    <p className="mb-2 text-xs text-[#DC2626]">{deleteError}</p>
                  )}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => { setShowDeletePanel(false); setDeleteConfirm(''); setDeleteError(''); }}
                      className="flex-1 cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] py-2 text-sm font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#C8B89A]"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      disabled={deleteConfirm !== openMic.nombre || deleting}
                      className="flex-1 cursor-pointer rounded-lg border-[3px] border-[#DC2626] bg-[#DC2626] py-2 text-sm font-bold text-white transition-all duration-200 hover:bg-[#7f1d1d] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {deleting ? 'Borrando...' : 'Borrar definitivamente'}
                    </button>
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowDeletePanel(true)}
                  className="w-full cursor-pointer rounded-lg border-[3px] border-[#DC2626] bg-[#DC2626] py-2.5 text-sm font-bold text-white transition-all duration-200 hover:bg-[#7f1d1d]"
                >
                  Borrar open mic
                </button>
              )}
            </div></div>
          </>
        ) : (
          <div className="animate-pop-in paper-drop paper-tape">
            <div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] px-6 py-4">
              {/* Subtabs Info / Scoring */}
              <div className="mb-4 flex gap-1 border-b-2 border-[#C8B89A] pb-0">
                {[{ id: 'info', label: 'Info' }, { id: 'scoring', label: 'Scoring' }].map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setConfigTab(tab.id)}
                    className={`cursor-pointer rounded-t-md border-2 border-b-0 border-[#1a1a1a] px-5 py-1.5 text-sm font-bold transition-all duration-150
                      ${configTab === tab.id
                        ? 'relative z-10 -mb-[2px] bg-[#1a1a1a] text-[#fff8e7]'
                        : 'bg-[#F5F0E1] text-[#6B5C4A] hover:bg-[#E8DFC8]'
                      }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {configTab === 'info' ? (
                <InfoConfigurator openMicId={openMicId} openMic={openMic} onSaved={handleSaved} />
              ) : (
                <>
                  <h2 className="mb-4 font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">
                    Configuración de scoring
                  </h2>
                  <ScoringConfigurator openMicId={openMicId} onSaved={handleSaved} />
                </>
              )}
            </div>
          </div>
        )}

      </div>
    </main>
  );
}
