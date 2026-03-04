import { useState } from 'react';
import { supabase } from '../supabaseClient';

export function LoginScreen() {
  const [email,   setEmail]   = useState('');
  const [loading, setLoading] = useState(false);
  const [sent,    setSent]    = useState(false);
  const [error,   setError]   = useState(null);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError(null);

    const { error: err } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: false },  // solo Hosts registrados
    });

    setLoading(false);

    if (err) {
      setError(err.message);
      return;
    }

    setSent(true);
  };

  return (
    <main className="paint-bg flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Cabecera */}
        <div className="mb-8 text-center">
          <h1 className="font-['Bangers'] text-4xl tracking-wider text-[#1a1a1a] drop-shadow-[2px_2px_0px_rgba(255,255,255,0.3)]">
            AI LINEUP ARCHITECT
          </h1>
          <p className="mt-2 text-sm font-bold text-[#6B5C4A]">Acceso para hosts</p>
        </div>

        <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-6">
          {!sent ? (
            <form onSubmit={handleSend} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="email" className="text-xs font-bold uppercase tracking-wide text-[#6B5C4A]">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                  className="rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-2 text-sm text-[#1a1a1a] outline-none placeholder:text-[#6B5C4A]/60 focus:ring-2 focus:ring-[#1a1a1a]"
                />
              </div>

              {error && (
                <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] px-3 py-2 text-xs text-[#7f1d1d]">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || !email.trim()}
                className={`rounded-lg border-[3px] border-[#1a1a1a] py-2.5 text-sm font-bold transition-all
                  ${loading || !email.trim()
                    ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                    : 'bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626]'
                  }`}
              >
                {loading ? 'Enviando...' : 'Enviar enlace de acceso'}
              </button>
            </form>
          ) : (
            <div className="flex flex-col items-center gap-4 text-center">
              <span className="text-3xl">✓</span>
              <div>
                <p className="font-bold text-[#1a1a1a]">Enlace enviado</p>
                <p className="mt-1 text-sm text-[#6B5C4A]">
                  Revisa tu bandeja de entrada en<br />
                  <span className="font-bold text-[#1a1a1a]">{email}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => { setSent(false); setEmail(''); }}
                className="text-xs font-bold text-[#6B5C4A] underline underline-offset-2 hover:text-[#DC2626]"
              >
                Cambiar email
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
