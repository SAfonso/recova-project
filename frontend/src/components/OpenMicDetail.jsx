import { useEffect, useState } from 'react';
import { ScoringConfigurator } from './ScoringConfigurator';
import { supabase } from '../supabaseClient';

export function OpenMicDetail({ session, openMicId, onBack, onEnterLineup }) {
  const [openMic, setOpenMic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    supabase
      .schema('silver')
      .from('open_mics')
      .select('id, nombre, created_at')
      .eq('id', openMicId)
      .single()
      .then(({ data, error: err }) => {
        if (err) setError(err.message);
        else setOpenMic(data);
        setLoading(false);
      });
  }, [openMicId]);

  const createdAt = openMic?.created_at
    ? new Date(openMic.created_at).toLocaleDateString('es-ES', {
        day: '2-digit', month: '2-digit', year: 'numeric',
      })
    : null;

  return (
    <main className="paint-bg min-h-screen px-4 pb-8">
      <div className="mx-auto flex max-w-lg flex-col gap-4 lg:max-w-3xl">

        {/* Header */}
        <div className="flex items-center justify-between pt-6">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-1 text-sm font-bold text-[#fff8e7] hover:text-[#DC2626]"
          >
            ← Atrás
          </button>
          <p className="text-xs font-bold text-[#fff8e7]/60">{session.user.email}</p>
        </div>

        {/* Info del open mic */}
        <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-6 py-4 shadow-[6px_6px_0px_rgba(0,0,0,0.3)]">
          {loading ? (
            <p className="text-sm text-[#6B5C4A]">Cargando...</p>
          ) : error ? (
            <p className="text-sm text-[#DC2626]">{error}</p>
          ) : (
            <>
              <h1 className="font-['Bangers'] text-3xl tracking-wide text-[#1a1a1a]">
                {openMic.nombre}
              </h1>
              {createdAt && (
                <p className="mt-1 text-xs text-[#6B5C4A]">Creado el {createdAt}</p>
              )}
            </>
          )}
        </div>

        {/* Configuración */}
        <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-6 py-4 shadow-[6px_6px_0px_rgba(0,0,0,0.3)]">
          <h2 className="mb-4 font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">
            Configuración de scoring
          </h2>
          <ScoringConfigurator openMicId={openMicId} />
        </div>

        {/* Botón Ver Lineup */}
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={onEnterLineup}
            className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] px-8 py-3 font-bold text-[#fff8e7] transition-all hover:bg-[#DC2626]"
          >
            Ver Lineup →
          </button>
        </div>

      </div>
    </main>
  );
}
