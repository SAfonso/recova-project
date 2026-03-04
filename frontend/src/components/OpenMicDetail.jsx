import { useCallback, useEffect, useState } from 'react';
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
};

function mergeDefaults(config) {
  return {
    ...DEFAULTS,
    ...(config ?? {}),
    categories:        { ...DEFAULTS.categories,        ...(config?.categories        ?? {}) },
    recency_penalty:   { ...DEFAULTS.recency_penalty,   ...(config?.recency_penalty   ?? {}) },
    single_date_boost: { ...DEFAULTS.single_date_boost, ...(config?.single_date_boost ?? {}) },
    gender_parity:     { ...DEFAULTS.gender_parity,     ...(config?.gender_parity     ?? {}) },
  };
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-[#C8B89A] py-1.5 last:border-0">
      <span className="text-xs text-[#6B5C4A]">{label}</span>
      <span className="text-sm font-bold text-[#1a1a1a]">{value}</span>
    </div>
  );
}

function InfoCard({ openMic }) {
  const cfg = mergeDefaults(openMic.config);
  const createdAt = new Date(openMic.created_at).toLocaleDateString('es-ES', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });

  const CATEGORY_LABELS = { standard: 'Standard', priority: 'Priority', gold: 'Gold', restricted: 'Restricted' };

  return (
    <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-6 py-4 shadow-[6px_6px_0px_rgba(0,0,0,0.3)]">
      <h1 className="font-['Bangers'] text-3xl tracking-wide text-[#1a1a1a]">
        {openMic.nombre}
      </h1>
      <p className="mb-4 mt-1 text-xs text-[#6B5C4A]">Creado el {createdAt}</p>

      <div className="flex flex-col">
        <InfoRow label="Slots disponibles" value={cfg.available_slots} />

        {Object.entries(cfg.categories).map(([cat, rule]) => (
          <InfoRow
            key={cat}
            label={CATEGORY_LABELS[cat] ?? cat}
            value={
              cat === 'restricted'
                ? 'bloqueado'
                : rule.enabled
                  ? `${rule.base_score} pts`
                  : 'desactivado'
            }
          />
        ))}

        <InfoRow
          label="Penalización recencia"
          value={
            cfg.recency_penalty.enabled
              ? `-${cfg.recency_penalty.penalty_points} pts (últimas ${cfg.recency_penalty.last_n_editions})`
              : 'desactivada'
          }
        />
        <InfoRow
          label="Bono fecha única"
          value={
            cfg.single_date_boost.enabled
              ? `+${cfg.single_date_boost.boost_points} pts`
              : 'desactivado'
          }
        />
        <InfoRow
          label="Paridad de género"
          value={
            cfg.gender_parity.enabled
              ? `${cfg.gender_parity.target_female_nb_pct}% objetivo f/nb`
              : 'desactivada'
          }
        />
      </div>
    </div>
  );
}

export function OpenMicDetail({ session, openMicId, initialView = 'info', onBack, onEnterLineup }) {
  const [openMic,  setOpenMic]  = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [view,     setView]     = useState(initialView); // 'info' | 'config'

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

  return (
    <main className="paint-bg min-h-screen px-4 pb-8">
      <div className="mx-auto flex max-w-lg flex-col gap-4 lg:max-w-3xl">

        {/* Header */}
        <div className="flex items-center justify-between pt-6">
          <button
            type="button"
            onClick={view === 'config' ? () => setView('info') : onBack}
            className="flex items-center gap-1 text-sm font-bold text-[#fff8e7] hover:text-[#DC2626]"
          >
            ← {view === 'config' ? 'Volver' : 'Atrás'}
          </button>
          <p className="text-xs font-bold text-[#fff8e7]/60">{session.user.email}</p>
        </div>

        {loading ? (
          <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-8 text-center text-sm text-[#6B5C4A]">
            Cargando...
          </div>
        ) : error ? (
          <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fee2e2] p-6 text-sm text-[#7f1d1d]">
            {error}
          </div>
        ) : view === 'info' ? (
          <>
            <InfoCard openMic={openMic} />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setView('config')}
                className="flex-1 rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] py-3 font-bold text-[#1a1a1a] transition-all hover:bg-[#C8B89A]"
              >
                Configurar
              </button>
              <button
                type="button"
                onClick={onEnterLineup}
                className="flex-1 rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] py-3 font-bold text-[#fff8e7] transition-all hover:bg-[#DC2626]"
              >
                Ver Lineup →
              </button>
            </div>
          </>
        ) : (
          <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-6 py-4 shadow-[6px_6px_0px_rgba(0,0,0,0.3)]">
            <h2 className="mb-4 font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">
              Configuración de scoring
            </h2>
            <ScoringConfigurator openMicId={openMicId} onSaved={handleSaved} />
          </div>
        )}

      </div>
    </main>
  );
}
