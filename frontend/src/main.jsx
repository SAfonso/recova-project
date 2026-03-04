import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { LoginScreen } from './components/LoginScreen';
import { OpenMicDetail } from './components/OpenMicDetail';
import { OpenMicSelector } from './components/OpenMicSelector';
import { supabase } from './supabaseClient';
import './index.css';

function Root() {
  const [session,   setSession]   = useState(null);
  const [checking,  setChecking]  = useState(true);
  const [openMicId, setOpenMicId] = useState(null);
  const [view,      setView]      = useState('selector'); // 'selector' | 'detail' | 'lineup'

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setChecking(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_, newSession) => {
        setSession(newSession);
        if (!newSession) { setOpenMicId(null); setView('selector'); }
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

  const handleSelect = (id) => { setOpenMicId(id); setView('detail'); };
  const handleBack   = ()   => { setOpenMicId(null); setView('selector'); };

  if (!session)            return <LoginScreen />;
  if (view === 'selector') return <OpenMicSelector session={session} onSelect={handleSelect} />;
  if (view === 'detail')   return <OpenMicDetail session={session} openMicId={openMicId} onBack={handleBack} onEnterLineup={() => setView('lineup')} />;
  return <App session={session} openMicId={openMicId} />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
