import { useEffect, useState } from 'react';
import { supabase } from '../supabaseClient';
import { OpenMicIcon } from './open-mic/openmic-icons';

const PlusIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const STAGGER_CLASSES = ['stagger-1','stagger-2','stagger-3','stagger-4','stagger-5','stagger-6'];

export function OpenMicSelector({ session, onSelect }) {
  const [openMics,    setOpenMics]    = useState([]);
  const [memberships, setMemberships] = useState([]);
  const [canCreate,   setCanCreate]   = useState(false);
  const [loading,     setLoading]     = useState(true);
  const [creating,    setCreating]    = useState(false);
  const [newName,     setNewName]     = useState('');
  const [saving,      setSaving]      = useState(false);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    async function fetchOpenMics() {
      setLoading(true); setError(null);
      const { data: membershipData, error: membershipError } = await supabase
        .schema('silver').from('organization_members')
        .select('proveedor_id, role').eq('user_id', session.user.id);
      if (membershipError) { setError(membershipError.message); setLoading(false); return; }
      const memberships = membershipData ?? [];
      setMemberships(memberships);
      setCanCreate(memberships.some((m) => m.role === 'host'));
      const proveedorIds = memberships.map((m) => m.proveedor_id);
      if (proveedorIds.length === 0) { setOpenMics([]); setLoading(false); return; }
      const { data: micsData, error: micsError } = await supabase
        .schema('silver').from('open_mics')
        .select('id, nombre, proveedor_id, created_at, config')
        .in('proveedor_id', proveedorIds).order('created_at', { ascending: true });
      if (micsError) setError(micsError.message);
      else setOpenMics(micsData ?? []);
      setLoading(false);
    }
    fetchOpenMics();
  }, [session.user.id]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setSaving(true); setError(null);
    const hostMembership = memberships.find((m) => m.role === 'host');
    const { data: newMic, error: insertError } = await supabase
      .schema('silver').from('open_mics')
      .insert({ proveedor_id: hostMembership.proveedor_id, nombre: newName.trim(), config: {} })
      .select('id, nombre').single();
    if (insertError) { setSaving(false); setError(insertError.message); return; }
    const backendUrl = import.meta.env.VITE_BACKEND_URL;
    const apiKey     = import.meta.env.VITE_WEBHOOK_API_KEY;
    if (backendUrl && apiKey) {
      fetch(`${backendUrl}/api/open-mic/create-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
        body: JSON.stringify({ open_mic_id: newMic.id, nombre: newMic.nombre }),
      }).catch(() => {});
    }
    setSaving(false);
    onSelect(newMic.id, { isNew: true });
  };

  const handleLogout = () => supabase.auth.signOut();

  if (loading) {
    return (
      <main className="paint-bg flex min-h-screen items-center justify-center">
        <p className="font-['Bangers'] text-2xl tracking-widest text-[#fff8e7]">Cargando...</p>
      </main>
    );
  }

  const showEmptyForm  = openMics.length === 0 && canCreate;
  const showCreateForm = creating || showEmptyForm;

  return (
    <main className="paint-bg flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">

        <div className="mb-6 text-center">
          <h1 className="font-['Bangers'] text-5xl tracking-wide text-[#fff8e7] drop-shadow-[3px_3px_0px_rgba(0,0,0,0.4)]">
            AI LineUp Architect
          </h1>
          <p className="mt-1 text-sm font-bold text-[#fff8e7]/70">{session.user.email}</p>
        </div>

        {/* Card rugosa */}
        <div className="animate-pop-in paper-drop paper-tape">
          <div className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-6">
            <h2 className="mb-4 font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a]">Tus Open Mics</h2>

            {error && (
              <p className="mb-4 rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">{error}</p>
            )}

            {openMics.length > 0 && (
              <ul className="mb-4 flex flex-col gap-2">
                {openMics.map((mic, index) => (
                  <li key={mic.id} className={`animate-slide-up ${STAGGER_CLASSES[index] ?? 'stagger-6'}`}>
                    <button
                      type="button"
                      onClick={() => onSelect(mic.id)}
                      className="group flex w-full cursor-pointer items-center gap-3 rounded-lg border-[3px] border-[#1a1a1a] bg-[#F5F0E1] px-4 py-3 text-left font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#DC2626] hover:text-[#fff8e7] hover:shadow-[3px_3px_0px_rgba(0,0,0,0.3)]"
                    >
                      <OpenMicIcon iconId={mic.config?.info?.icono} className="h-4 w-4 shrink-0" />
                      <span className="flex-1 truncate">{mic.nombre}</span>
                      <svg className="h-4 w-4 opacity-40 transition-opacity group-hover:opacity-100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {openMics.length === 0 && !canCreate && (
              <p className="mb-4 text-sm text-[#6B5C4A]">No tienes acceso a ningún open mic todavía.</p>
            )}

            {showCreateForm ? (
              <div className="flex flex-col gap-3 border-t-2 border-dashed border-[#C8B89A] pt-4">
                <label className="text-sm font-bold text-[#1a1a1a]">Nombre del nuevo Open Mic</label>
                <input
                  type="text" value={newName} autoFocus
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  placeholder="Ej: Recova Open Mic — Marzo 2026"
                  className="rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-2 text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
                />
                <div className="flex gap-2">
                  {!showEmptyForm && (
                    <button
                      type="button"
                      onClick={() => { setCreating(false); setNewName(''); setError(null); }}
                      className="flex-1 cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#C8B89A] py-2 text-sm font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#B8A88A]"
                    >
                      Cancelar
                    </button>
                  )}
                  <button
                    type="button" disabled={!newName.trim() || saving} onClick={handleCreate}
                    className={`flex-1 rounded-lg border-[3px] border-[#1a1a1a] py-2 text-sm font-bold transition-all duration-200
                      ${!newName.trim() || saving
                        ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
                        : 'comic-shadow cursor-pointer bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626]'}`}
                  >
                    {saving ? 'Creando...' : 'Crear'}
                  </button>
                </div>
              </div>
            ) : canCreate ? (
              <button
                type="button" onClick={() => setCreating(true)}
                className="mt-2 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-[3px] border-dashed border-[#1a1a1a] bg-transparent py-2 text-sm font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#C8B89A]"
              >
                <PlusIcon />Nuevo Open Mic
              </button>
            ) : null}
          </div>
        </div>

        <div className="mt-4 flex justify-center">
          <button type="button" onClick={handleLogout} className="cursor-pointer text-xs font-bold text-[#fff8e7]/60 underline hover:text-[#fff8e7]">
            Cerrar sesión
          </button>
        </div>
      </div>
    </main>
  );
}
