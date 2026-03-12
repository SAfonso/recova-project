import { useState } from 'react';
import { supabase } from '../supabaseClient';

const SparkIcon = ({ className, style }) => (
  <svg className={className} style={style} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
  </svg>
);

const GoogleIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
);

export function LoginScreen() {
  const [loading, setLoading] = useState(false);
  const [step,    setStep]    = useState('email'); // 'email' | 'code'
  const [email,   setEmail]   = useState('');
  const [code,    setCode]    = useState('');
  const [error,   setError]   = useState(null);

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    });
    if (err) { setError(err.message); setLoading(false); }
  };

  const handleSendCode = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    setError(null);
    const { error: err } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { shouldCreateUser: true },
    });
    setLoading(false);
    if (err) { setError(err.message); }
    else      { setStep('code'); }
  };

  const handleVerifyCode = async (e) => {
    e.preventDefault();
    if (!code.trim()) return;
    setLoading(true);
    setError(null);
    const { error: err } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: code.trim(),
      type: 'email',
    });
    setLoading(false);
    if (err) { setError(err.message); }
    // Si OK: onAuthStateChange en main.jsx detecta la sesión automáticamente
  };

  return (
    <main className="paint-bg flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">

        <div className="mb-8 -rotate-1 text-center">
          <div className="inline-flex items-center gap-2">
            <SparkIcon className="animate-spark h-6 w-6 text-[#F97316]" />
            <h1 className="font-['Bangers'] text-5xl tracking-wider text-[#1a1a1a] drop-shadow-[3px_3px_0px_rgba(255,255,255,0.4)]">
              AI LINEUP ARCHITECT
            </h1>
            <SparkIcon className="animate-spark h-6 w-6 text-[#F97316]" style={{ animationDelay: '0.9s' }} />
          </div>
          <p className="mt-2 text-sm font-bold uppercase tracking-widest text-[#1a1a1a]/70">
            Gestiona tu open mic
          </p>
        </div>

        <div className="animate-pop-in -rotate-[1.2deg] paper-drop">
          <div className="scrapbook-panel pin-corner paper-rough paper-note p-6 flex flex-col gap-4">

            {error && (
              <p className="paper-strip rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] px-3 py-2 text-xs text-[#7f1d1d]">
                {error}
              </p>
            )}

            {/* Google OAuth */}
            <button
              type="button"
              onClick={handleGoogleLogin}
              disabled={loading}
              className={`comic-shadow cursor-pointer rounded-none border-[3px] border-[#0D0D0D] py-2.5 px-4 text-sm font-bold transition-all duration-200 flex items-center justify-center gap-3
                ${loading
                  ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                  : 'bg-[#EDE8DC] text-[#0D0D0D] hover:bg-[#0D0D0D] hover:text-[#F5F5F0]'
                }`}
            >
              {!loading && <GoogleIcon />}
              {loading ? 'Redirigiendo...' : 'Continuar con Google'}
            </button>

            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 border-t-2 border-dashed border-[#1a1a1a]/20" />
              <span className="text-xs font-bold uppercase tracking-widest text-[#1a1a1a]/40">o</span>
              <div className="flex-1 border-t-2 border-dashed border-[#1a1a1a]/20" />
            </div>

            {/* Step 1: email */}
            {step === 'email' && (
              <form onSubmit={handleSendCode} className="flex flex-col gap-2">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                  required
                  className="paper-strip rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] px-3 py-2 text-sm text-[#0D0D0D] placeholder-[#0D0D0D]/30 outline-none focus:border-[#3D5F6C] transition-colors"
                />
                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className={`comic-shadow cursor-pointer rounded-none border-[3px] border-[#0D0D0D] py-2.5 px-4 text-sm font-bold transition-all duration-200
                    ${loading || !email.trim()
                      ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                      : 'bg-[#3D5F6C] text-[#F5F5F0] hover:bg-[#2D4A57]'
                    }`}
                >
                  {loading ? 'Enviando...' : '✉️ Enviar código de acceso'}
                </button>
              </form>
            )}

            {/* Step 2: código OTP */}
            {step === 'code' && (
              <form onSubmit={handleVerifyCode} className="flex flex-col gap-2">
                <p className="text-xs text-[#1a1a1a]/60 text-center">
                  Código enviado a <strong className="text-[#1a1a1a]">{email}</strong>
                </p>
                <input
                  type="text"
                  inputMode="numeric"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="000000"
                  maxLength={6}
                  autoFocus
                  required
                  className="paper-strip rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] px-3 py-2 text-2xl font-bold text-center tracking-[0.4em] text-[#0D0D0D] placeholder-[#0D0D0D]/20 outline-none focus:border-[#3D5F6C] transition-colors"
                />
                <button
                  type="submit"
                  disabled={loading || code.length < 6}
                  className={`comic-shadow cursor-pointer rounded-none border-[3px] border-[#0D0D0D] py-2.5 px-4 text-sm font-bold transition-all duration-200
                    ${loading || code.length < 6
                      ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                      : 'bg-[#3D5F6C] text-[#F5F5F0] hover:bg-[#2D4A57]'
                    }`}
                >
                  {loading ? 'Verificando...' : '🔓 Entrar'}
                </button>
                <button
                  type="button"
                  onClick={() => { setStep('email'); setCode(''); setError(null); }}
                  className="text-xs text-[#1a1a1a]/50 underline hover:text-[#1a1a1a]/80 text-center"
                >
                  Usar otro email
                </button>
              </form>
            )}

          </div>
        </div>
      </div>
    </main>
  );
}
