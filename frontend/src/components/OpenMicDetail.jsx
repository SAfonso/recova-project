import { useCallback, useEffect, useState } from 'react';
import { InfoConfigurator } from './open-mic/InfoConfigurator';
import { ScoringConfigurator } from './ScoringConfigurator';
import { DevToolsPanel } from './DevToolsPanel';
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


function InfoRow({ label, value, dot }) {
  return (
    <div className="flex items-center justify-between border-b border-[#C8B89A] py-2.5 last:border-0">
      <div className="flex items-center gap-2">
        {dot && <span className={`h-2.5 w-2.5 shrink-0 rounded-full border border-[#1a1a1a]/20 ${dot}`} />}
        <span className="text-sm text-[#6B5C4A] md:text-base">{label}</span>
      </div>
      <span className="text-sm font-bold text-[#1a1a1a] md:text-base">{value}</span>
    </div>
  );
}

function InfoCard({ openMic }) {
  const info = openMic.config?.info ?? {};
  const createdAt = new Date(openMic.created_at).toLocaleDateString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });

  return (
    <div className="animate-pop-in comic-panel rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] px-6 py-5" style={{ boxShadow: '4px 4px 0 #000000' }}>
      <h1 className="font-['Bangers'] text-3xl tracking-wide text-[#1a1a1a] md:text-4xl lg:text-5xl">
        {openMic.nombre}
      </h1>
      <p className="mb-4 mt-1 text-sm text-[#6B5C4A] md:text-base">Creado el {createdAt}</p>

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
    <main className="paint-bg min-h-screen px-4 pb-8 md:px-8">
      <div className="mx-auto flex max-w-xl flex-col gap-4 md:max-w-2xl lg:max-w-4xl xl:max-w-5xl">

        {/* Header */}
        <div className="flex rotate-[0.7deg] items-center justify-between pt-6">
          <button type="button" onClick={view === 'config' ? () => setView('info') : onBack} className="btn-back">
            <BackIcon />
            {view === 'config' ? 'Volver' : 'Atrás'}
          </button>
          <p className="text-xs font-bold text-[#0D0D0D]/50">{session.user.email}</p>
        </div>

        {loading ? (
          <div className="animate-pop-in scrapbook-panel paper-note rounded-none bg-[#EDE8DC] p-8">
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
                className="comic-shadow flex-1 cursor-pointer rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] py-3 text-base font-bold text-[#0D0D0D] transition-all duration-150 hover:bg-[#5E7260] hover:text-[#F5F5F0] md:py-4 md:text-lg"
              >
                Configurar
              </button>
              <button
                type="button"
                onClick={onEnterLineup}
                className="comic-shadow flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-none border-[3px] border-[#0D0D0D] bg-[#0D0D0D] py-3 text-base font-bold text-[#F5F5F0] transition-all duration-150 hover:bg-[#3D5F6C] md:py-4 md:text-lg"
              >
                Ver Lineup
                <ChevronRightIcon />
              </button>
            </div>

            {/* Zona de peligro */}
            <div className="animate-slide-up stagger-2 rotate-[1.2deg] paper-drop"><div className="scrapbook-panel paper-crumpled paper-rough border-[3px] border-[#DC2626]/60 px-6 py-4">
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
                    className="paper-strip mb-3 w-full rounded-md border-2 border-[#DC2626] bg-[#F5F0E1] px-3 py-2 text-sm font-bold text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
                  />
                  {deleteError && (
                    <p className="mb-2 text-xs text-[#DC2626]">{deleteError}</p>
                  )}
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => { setShowDeletePanel(false); setDeleteConfirm(''); setDeleteError(''); }}
                      className="flex-1 cursor-pointer rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] py-2 text-sm font-bold text-[#0D0D0D] transition-all duration-150 hover:bg-[#5E7260] hover:text-[#F5F5F0]"
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      disabled={deleteConfirm !== openMic.nombre || deleting}
                      className="flex-1 cursor-pointer rounded-none border-[3px] border-[#DC2626] bg-[#DC2626] py-2 text-sm font-bold text-white transition-all duration-150 hover:bg-[#7f1d1d] disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {deleting ? 'Borrando...' : 'Borrar definitivamente'}
                    </button>
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowDeletePanel(true)}
                  className="w-full cursor-pointer rounded-none border-[3px] border-[#DC2626] bg-[#DC2626] py-2.5 text-sm font-bold text-white transition-all duration-150 hover:bg-[#7f1d1d]"
                >
                  Borrar open mic
                </button>
              )}
            </div></div>
          </>
        ) : (
          <div className="animate-pop-in">
            {/* Tabs fuera del panel — mismo patrón que NotebookSheet */}
            <div className="relative z-10 flex items-end gap-1 -mb-[3px]">
              {[{ id: 'info', label: 'INFO' }, { id: 'scoring', label: 'SCORING' }, { id: 'dev', label: 'DEV' }].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setConfigTab(tab.id)}
                  data-tutorial={tab.id === 'info' ? 'open-mic-detail-info' : tab.id === 'scoring' ? 'open-mic-detail-scoring' : undefined}
                  className={`paper-note relative z-10 cursor-pointer rounded-none border-[3px] border-[#0D0D0D] px-5 py-1.5 text-sm font-bold tracking-wide transition-all duration-150
                    ${configTab === tab.id
                      ? 'border-b-0 text-[#0D0D0D]'
                      : 'border-b-[3px] text-[#0D0D0D]/50 hover:text-[#0D0D0D]'
                    }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <div className="-rotate-[1deg] paper-drop">
            <div className="scrapbook-panel pin-corner paper-rough paper-note px-6 py-4">

              {configTab === 'info' ? (
                <InfoConfigurator openMicId={openMicId} openMic={openMic} onSaved={handleSaved} />
              ) : configTab === 'scoring' ? (
                <>
                  <h2 className="mb-4 font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">
                    Configuración de scoring
                  </h2>
                  <ScoringConfigurator openMicId={openMicId} openMicName={openMic?.nombre} onSaved={handleSaved} />
                </>
              ) : (
                <>
                  <h2 className="mb-4 font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">
                    Herramientas de prueba
                  </h2>
                  <DevToolsPanel
                    openMicId={openMicId}
                    openMic={openMic}
                    onSeedDone={handleSaved}
                  />
                </>
              )}
            </div>
            </div>{/* /paper-drop */}
          </div>
        )}

      </div>
    </main>
  );
}
