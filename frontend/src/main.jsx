import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { LoginScreen } from './components/LoginScreen';
import { OpenMicSelector } from './components/OpenMicSelector';
import { supabase } from './supabaseClient';
import './index.css';

function Root() {
  const [session,      setSession]      = useState(null);
  const [checking,     setChecking]     = useState(true);
  const [openMicId,    setOpenMicId]    = useState(null);
  const [initialTab,   setInitialTab]   = useState('lineup');

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setChecking(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_, newSession) => {
        setSession(newSession);
        if (!newSession) setOpenMicId(null);
      },
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

  const handleSelectOpenMic = (id, options = {}) => {
    setOpenMicId(id);
    setInitialTab(options.isNew ? 'config' : 'lineup');
  };

  if (!session) return <LoginScreen />;
  if (!openMicId) return <OpenMicSelector session={session} onSelect={handleSelectOpenMic} />;
  return <App session={session} openMicId={openMicId} initialTab={initialTab} />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
