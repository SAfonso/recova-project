import { useEffect, useState } from 'react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? '';

function StampValidado() {
  return (
    <div className="flex justify-center">
      <div className="-rotate-6">
        <div className="animate-stamp-in flex items-center gap-2 rounded-lg border-[4px] border-double border-[#15803D] bg-[#dcfce7]/90 px-6 py-2 text-2xl font-black uppercase tracking-widest text-[#15803D] shadow-[3px_3px_0px_rgba(0,0,0,0.2)]">
          <svg className="h-6 w-6 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          VALIDADO
        </div>
      </div>
    </div>
  );
}

export function ValidateView() {
  const token = new URLSearchParams(window.location.search).get('token') ?? '';

  const [state, setState] = useState('loading'); // loading | error | ready | validated
  const [errorMsg, setErrorMsg] = useState('');
  const [data, setData] = useState(null);        // { open_mic_id, fecha_evento, candidates, is_validated }
  const [selectedIds, setSelectedIds] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) {
      setErrorMsg('Link invalido. Genera uno nuevo desde la app.');
      setState('error');
      return;
    }

    fetch(`${BACKEND_URL}/api/validate-view/lineup?token=${token}`)
      .then((r) => {
        if (r.status === 410) throw new Error('El link ha expirado. Genera uno nuevo desde la app.');
        if (r.status === 404) throw new Error('Link no encontrado.');
        if (!r.ok) throw new Error('Error al cargar el lineup.');
        return r.json();
      })
      .then((d) => {
        setData(d);
        if (d.is_validated) {
          setState('validated');
        } else {
          setSelectedIds(d.candidates.slice(0, 5).map((c) => c.solicitud_id));
          setState('ready');
        }
      })
      .catch((err) => {
        setErrorMsg(err.message);
        setState('error');
      });
  }, [token]);

  const toggle = (id) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 5) return prev;
      return [...prev, id];
    });
  };

  const handleValidate = async () => {
    if (selectedIds.length !== 5) return;
    setSaving(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/validate-view/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, solicitud_ids: selectedIds }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.message ?? `Error ${r.status}`);
      }
      setState('validated');
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSaving(false);
    }
  };

  const fechaFormateada = data?.fecha_evento
    ? new Date(data.fecha_evento + 'T12:00:00').toLocaleDateString('es-ES', {
        weekday: 'long', day: 'numeric', month: 'long',
      })
    : '';

  /* ── Loading ── */
  if (state === 'loading') {
    return (
      <main className="paint-bg flex min-h-screen items-center justify-center px-4">
        <p className="text-sm font-bold text-[#6B5C4A]">Cargando lineup...</p>
      </main>
    );
  }

  /* ── Error ── */
  if (state === 'error') {
    return (
      <main className="paint-bg flex min-h-screen items-center justify-center px-4">
        <div className="paper-drop w-full max-w-sm">
          <div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-6 text-center">
            <p className="text-base font-bold text-[#7f1d1d]">{errorMsg}</p>
          </div>
        </div>
      </main>
    );
  }

  /* ── Validated ── */
  if (state === 'validated') {
    return (
      <main className="paint-bg flex min-h-screen flex-col items-center justify-center gap-6 px-4">
        <StampValidado />
        {fechaFormateada && (
          <p className="text-center text-sm font-bold text-[#fff8e7]">
            Lineup del {fechaFormateada} validado correctamente.
          </p>
        )}
      </main>
    );
  }

  /* ── Ready ── */
  return (
    <main className="paint-bg min-h-screen px-4 pb-10 pt-6">
      <div className="mx-auto flex max-w-lg flex-col gap-5">

        {/* Header */}
        <div className="paper-drop rotate-[1deg]">
          <div className="scrapbook-panel pin-corner paper-rough paper-note px-5 py-4">
            <h1 className="font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a]">
              Valida el Lineup
            </h1>
            {fechaFormateada && (
              <p className="mt-1 text-sm font-bold capitalize text-[#6B5C4A]">
                {fechaFormateada}
              </p>
            )}
          </div>
        </div>

        {/* Error inline */}
        {errorMsg && (
          <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">
            {errorMsg}
          </p>
        )}

        {/* Lista de candidatos */}
        <section className="scrapbook-panel notebook-lines relative mx-auto w-full overflow-hidden rounded-lg bg-[#fff8e7] px-6 py-4">
          <div className="flex flex-col gap-2">
            {data.candidates.map((c, i) => {
              const selected = selectedIds.includes(c.solicitud_id);
              return (
                <button
                  key={c.solicitud_id}
                  type="button"
                  onClick={() => toggle(c.solicitud_id)}
                  className={`paper-strip tilt-soft flex w-full items-center gap-3 rounded-md border-2 px-3 py-2.5 text-left transition-all duration-150
                    ${selected
                      ? 'border-[#1a1a1a] bg-[#1a1a1a] text-[#fff8e7]'
                      : 'border-[#C8B89A] bg-[#F5F0E1] text-[#1a1a1a] hover:border-[#1a1a1a]'
                    }`}
                >
                  <span className="w-5 shrink-0 text-right text-xs opacity-60">{i + 1}.</span>
                  <div className="flex flex-1 flex-col min-w-0">
                    <span className="truncate text-sm font-bold">{c.nombre}</span>
                    {c.instagram && (
                      <span className={`truncate text-xs ${selected ? 'text-[#C8B89A]' : 'text-[#6B5C4A]'}`}>
                        @{c.instagram}
                      </span>
                    )}
                  </div>
                  {c.score != null && (
                    <span className={`shrink-0 text-xs font-bold ${selected ? 'text-[#C8B89A]' : 'text-[#6B5C4A]'}`}>
                      {c.score}
                    </span>
                  )}
                  <div className={`h-3 w-3 shrink-0 rounded-full border-2 ${selected ? 'border-[#fff8e7] bg-[#fff8e7]' : 'border-[#C8B89A]'}`} />
                </button>
              );
            })}
          </div>
        </section>

        {/* Contador */}
        <p className="text-center text-sm font-bold text-[#fff8e7]">
          {selectedIds.length === 5
            ? 'LineUp completo — listo para validar'
            : `Selecciona ${5 - selectedIds.length} cómico${5 - selectedIds.length !== 1 ? 's' : ''} más`}
        </p>

        {/* Botón validar */}
        <div className="flex justify-center">
          <button
            type="button"
            disabled={saving || selectedIds.length !== 5}
            onClick={handleValidate}
            className={`comic-shadow rounded-lg border-[3px] border-[#1a1a1a] px-8 py-3 text-base font-black uppercase tracking-wide transition-all duration-200
              ${saving || selectedIds.length !== 5
                ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                : 'cursor-pointer bg-[#15803D] text-white hover:bg-[#166534] hover:scale-[1.02] active:scale-[0.98]'
              }`}
          >
            {saving ? 'Validando...' : 'Validar Lineup'}
          </button>
        </div>

      </div>
    </main>
  );
}
