import { useState } from 'react';
import { authFetch } from '../utils/authFetch';

async function devFetch(path, body) {
  const res = await authFetch(path, body);
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error ?? `Error ${res.status}`);
  return json;
}

function DevButton({ label, onClick, disabled, loading }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex items-center gap-2 rounded border-2 border-[#1a1a1a] px-4 py-2 text-sm font-bold transition-all
        ${disabled
          ? 'cursor-not-allowed border-[#C8B89A] bg-[#F5F0E1] text-[#C8B89A]'
          : loading
            ? 'cursor-wait bg-[#1a1a1a] text-[#fff8e7] opacity-70'
            : 'bg-[#fff8e7] text-[#1a1a1a] hover:bg-[#1a1a1a] hover:text-[#fff8e7]'
        }`}
    >
      {loading && (
        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {label}
    </button>
  );
}

export function DevToolsPanel({ openMicId, openMic, onSeedDone }) {
  const [seedLoading,   setSeedLoading]   = useState(false);
  const [ingestLoading, setIngestLoading] = useState(false);
  const [scoreLoading,  setScoreLoading]  = useState(false);
  const [toast,         setToast]         = useState(null);

  const seedUsed = openMic?.config?.seed_used === true;

  function showToast(msg, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  }

  async function handleSeed() {
    setSeedLoading(true);
    try {
      const res = await devFetch('/api/dev/seed-open-mic', { open_mic_id: openMicId });
      showToast(`✓ ${res.seeded} usuarios de prueba insertados`);
      onSeedDone?.();
    } catch (e) {
      showToast(e.message, false);
    } finally {
      setSeedLoading(false);
    }
  }

  async function handleIngest() {
    setIngestLoading(true);
    try {
      await devFetch('/api/dev/trigger-ingest', { open_mic_id: openMicId });
      showToast('✓ Ingesta lanzada en background');
    } catch (e) {
      showToast(e.message, false);
    } finally {
      setIngestLoading(false);
    }
  }

  async function handleScoring() {
    setScoreLoading(true);
    try {
      await devFetch('/api/dev/trigger-scoring', { open_mic_id: openMicId });
      showToast('✓ Scoring ejecutado');
    } catch (e) {
      showToast(e.message, false);
    } finally {
      setScoreLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-xs text-[#6B5C4A]">
        Herramientas solo para pruebas. No usar en producción real.
      </p>

      {/* Seed */}
      <div className="space-y-2">
        <h3 className="text-sm font-bold text-[#1a1a1a]">Poblar datos de prueba</h3>
        <p className="text-xs text-[#6B5C4A]">
          Inserta 10 usuarios aleatorios del pool de prueba en este open mic.
          Solo se puede hacer una vez.
        </p>
        <DevButton
          label={seedUsed ? 'Ya sembrado' : 'Poblar datos de prueba'}
          onClick={handleSeed}
          disabled={seedUsed}
          loading={seedLoading}
        />
      </div>

      <hr className="border-[#C8B89A]" />

      {/* Ingesta */}
      <div className="space-y-2">
        <h3 className="text-sm font-bold text-[#1a1a1a]">Forzar ingesta</h3>
        <p className="text-xs text-[#6B5C4A]">
          Lanza el pipeline de ingesta (sheets + forms) en background, igual que el schedule de n8n.
        </p>
        <DevButton
          label="Forzar ingesta"
          onClick={handleIngest}
          loading={ingestLoading}
        />
      </div>

      <hr className="border-[#C8B89A]" />

      {/* Tutorial */}
      <div className="space-y-2">
        <h3 className="text-sm font-bold text-[#1a1a1a]">Tutorial onboarding</h3>
        <p className="text-xs text-[#6B5C4A]">
          Resetea el tutorial para que vuelva a aparecer al recargar.
        </p>
        <DevButton
          label="Resetear tutorial"
          onClick={() => {
            localStorage.removeItem('recova_tutorial_done');
            showToast('✓ Tutorial reseteado — recarga la página');
          }}
        />
      </div>

      <hr className="border-[#C8B89A]" />

      {/* Scoring */}
      <div className="space-y-2">
        <h3 className="text-sm font-bold text-[#1a1a1a]">Forzar scoring</h3>
        <p className="text-xs text-[#6B5C4A]">
          Ejecuta el scoring para este open mic y actualiza los candidatos.
        </p>
        <DevButton
          label="Forzar scoring"
          onClick={handleScoring}
          loading={scoreLoading}
        />
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-6 right-6 z-50 rounded border-2 border-[#1a1a1a] px-4 py-2 text-sm font-bold shadow-lg
          ${toast.ok ? 'bg-[#d4edda] text-[#155724]' : 'bg-[#f8d7da] text-[#721c24]'}`}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
