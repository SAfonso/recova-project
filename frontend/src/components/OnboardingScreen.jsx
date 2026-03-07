import { useState } from 'react';
import { supabase } from '../supabaseClient';

const SparkIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
  </svg>
);

export function OnboardingScreen({ session, onComplete }) {
  const [nombre,  setNombre]  = useState('');
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!nombre.trim()) return;
    setLoading(true);
    setError(null);
    const { error: err } = await supabase
      .schema('silver')
      .rpc('onboard_new_host', { p_nombre_comercial: nombre.trim() });
    setLoading(false);
    if (err) { setError(err.message); return; }
    onComplete();
  };

  return (
    <main className="paint-bg flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">

        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2">
            <SparkIcon className="animate-spark h-6 w-6 text-[#F97316]" />
            <h1 className="font-['Bangers'] text-5xl tracking-wider text-[#1a1a1a] drop-shadow-[3px_3px_0px_rgba(255,255,255,0.4)]">
              BIENVENIDO/A
            </h1>
            <SparkIcon className="animate-spark h-6 w-6 text-[#F97316]" style={{ animationDelay: '0.9s' }} />
          </div>
          <p className="mt-2 text-sm font-bold uppercase tracking-widest text-[#1a1a1a]/70">
            {session?.user?.email}
          </p>
        </div>

        <div className="animate-pop-in paper-drop paper-tape">
          <div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-6">
            <form onSubmit={handleCreate} className="flex flex-col gap-4">

              <p className="text-sm text-[#6B5C4A] leading-snug">
                Para empezar, dinos el nombre de tu sala o evento.
              </p>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="nombre" className="text-xs font-bold uppercase tracking-wide text-[#6B5C4A]">
                  Nombre de tu local / evento
                </label>
                <input
                  id="nombre"
                  type="text"
                  required
                  autoFocus
                  maxLength={80}
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  placeholder="Comedy Club Madrid"
                  className="rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-2 text-sm text-[#1a1a1a] outline-none placeholder:text-[#6B5C4A]/60 focus:ring-2 focus:ring-[#DC2626]"
                />
              </div>

              {error && (
                <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] px-3 py-2 text-xs text-[#7f1d1d]">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || !nombre.trim()}
                className={`comic-shadow cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] py-2.5 text-sm font-bold transition-all duration-200
                  ${loading || !nombre.trim()
                    ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                    : 'bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626] hover:scale-[1.02] active:scale-[0.98]'
                  }`}
              >
                {loading ? 'Creando...' : 'Crear mi espacio'}
              </button>

            </form>
          </div>
        </div>
      </div>
    </main>
  );
}
