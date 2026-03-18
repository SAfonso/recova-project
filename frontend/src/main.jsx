import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { BgIcons } from './components/BgIcons';
import { OnboardingTutorial } from './components/OnboardingTutorial';
import { LoginScreen } from './components/LoginScreen';
import { OnboardingScreen } from './components/OnboardingScreen';
import { OpenMicDetail } from './components/OpenMicDetail';
import { OpenMicSelector } from './components/OpenMicSelector';
import { ValidateView } from './components/ValidateView';
import { ErrorBoundary } from './components/ErrorBoundary';
import { supabase } from './supabaseClient';
import './index.css';

async function checkMembership(userId) {
  const { data } = await supabase
    .schema('silver')
    .from('organization_members')
    .select('id')
    .eq('user_id', userId)
    .limit(1);
  return (data ?? []).length > 0;
}

function Root() {
  if (window.location.pathname === '/validate') return <ValidateView />;

  // appState: 'checking' | 'no-session' | 'onboarding' | 'ready'
  const [appState,     setAppState]     = useState('checking');
  const [session,      setSession]      = useState(null);
  const [openMicId,    setOpenMicId]    = useState(null);
  const [view,         setView]         = useState('selector'); // 'selector' | 'detail' | 'lineup'
  const [initialView,  setInitialView]  = useState('info');

  const resolveState = async (newSession) => {
    if (!newSession) { setSession(null); setAppState('no-session'); return; }
    setSession(newSession);
    const hasMembership = await checkMembership(newSession.user.id);
    setAppState(hasMembership ? 'ready' : 'onboarding');
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => resolveState(data.session));

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, newSession) => {
        if (event === 'SIGNED_OUT') {
          setOpenMicId(null); setView('selector'); setAppState('no-session');
        } else if (newSession) {
          resolveState(newSession);
        }
      },
    );

    return () => subscription.unsubscribe();
  }, []);

  if (appState === 'checking') {
    return (
      <main className="paint-bg flex min-h-screen items-center justify-center">
        <p className="text-sm font-bold text-[#6B5C4A]">Cargando...</p>
      </main>
    );
  }

  const handleSelect = (id, options = {}) => {
    setOpenMicId(id);
    setInitialView(options.isNew ? 'config' : 'info');
    setView('detail');
  };
  const handleBack = () => { setOpenMicId(null); setView('selector'); };

  if (appState === 'no-session')  return <><BgIcons /><LoginScreen /></>;
  if (appState === 'onboarding')  return <><BgIcons /><OnboardingScreen session={session} onComplete={() => setAppState('ready')} /></>;
  if (view === 'selector') return <><BgIcons /><OpenMicSelector session={session} onSelect={handleSelect} /></>;
  if (view === 'detail')   return <><BgIcons /><OpenMicDetail session={session} openMicId={openMicId} initialView={initialView} onBack={handleBack} onEnterLineup={() => setView('lineup')} /></>;
  return <><BgIcons /><App session={session} openMicId={openMicId} onBack={() => setView('detail')} /></>;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <OnboardingTutorial />
      <Root />
    </ErrorBoundary>
  </React.StrictMode>,
);
