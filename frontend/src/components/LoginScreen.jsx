import { useState } from 'react';
import { supabase } from '../supabaseClient';

const SparkIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
  </svg>
);

const CheckIcon = () => (
  <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

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
      options: { shouldCreateUser: false },
    });
    setLoading(false);
    if (err) { setError(err.message); return; }
    setSent(true);
  };

  return (
    <main className="paint-bg flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">

        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2">
            <SparkIcon className="animate-spark h-6 w-6 text-[#F97316]" />
            <h1 className="font-['Bangers'] text-5xl tracking-wider text-[#1a1a1a] drop-shadow-[3px_3px_0px_rgba(255,255,255,0.4)]">
              AI LINEUP ARCHITECT
            </h1>
            <SparkIcon className="animate-spark h-6 w-6 text-[#F97316]" style={{ animationDelay: '0.9s' }} />
          </div>
          <p className="mt-2 text-sm font-bold uppercase tracking-widest text-[#1a1a1a]/70">
            Acceso para hosts
          </p>
        </div>

        {/* Hoja rugosa */}
        <div className="animate-pop-in paper-drop paper-tape">
          <div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-6">
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
                  disabled={loading || !email.trim()}
                  className={`comic-shadow cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] py-2.5 text-sm font-bold transition-all duration-200
                    ${loading || !email.trim()
                      ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                      : 'bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626] hover:scale-[1.02] active:scale-[0.98]'
                    }`}
                >
                  {loading ? 'Enviando...' : 'Enviar enlace de acceso'}
                </button>
              </form>
            ) : (
              <div className="animate-pop-in flex flex-col items-center gap-4 text-center">
                <span className="flex h-14 w-14 items-center justify-center rounded-full border-[3px] border-[#15803D] bg-[#dcfce7] text-[#15803D]">
                  <CheckIcon />
                </span>
                <div>
                  <p className="font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a]">Enlace enviado!</p>
                  <p className="mt-1 text-sm text-[#6B5C4A]">
                    Revisa tu bandeja en<br />
                    <span className="font-bold text-[#1a1a1a]">{email}</span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => { setSent(false); setEmail(''); }}
                  className="cursor-pointer text-xs font-bold text-[#6B5C4A] underline underline-offset-2 hover:text-[#DC2626]"
                >
                  Cambiar email
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
