import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { LoginScreen } from './components/LoginScreen';
import { supabase } from './supabaseClient';
import './index.css';

function Root() {
  const [session,  setSession]  = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    // Comprueba sesión existente (persisted en localStorage)
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setChecking(false);
    });

    // Escucha cambios de sesión (login via magic link, logout)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_, newSession) => setSession(newSession),
    );

    return () => subscription.unsubscribe();
  }, []);

  if (checking) {
    return (
      <main className="paint-bg flex min-h-screen items-center justify-center">
        <p className="text-sm font-bold text-[#6B5C4A]">Cargando...</p>
      </main>
    );
  }

  return session ? <App session={session} /> : <LoginScreen />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
