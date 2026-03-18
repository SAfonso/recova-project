import { useEffect, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { supabase } from '../supabaseClient';
import { authFetch } from '../utils/authFetch';
import { OpenMicIcon } from './open-mic/openmic-icons';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

const PlusIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const TelegramIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.96 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
  </svg>
);

const STAGGER_CLASSES = ['stagger-1','stagger-2','stagger-3','stagger-4','stagger-5','stagger-6'];

const MIC_HOVER_COLORS = [
  'hover:bg-[#2C4A52] hover:text-[#FEFDF8]',
  'hover:bg-[#5E7260] hover:text-[#FEFDF8]',
  'hover:bg-[#C9A66B] hover:text-[#0D0D0D]',
  'hover:bg-[#A34A42] hover:text-[#FEFDF8]',
  'hover:bg-[#3D5F6C] hover:text-[#FEFDF8]',
  'hover:bg-[#7B6D4A] hover:text-[#FEFDF8]',
];


const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
  || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

export function OpenMicSelector({ session, onSelect }) {
  const [openMics,    setOpenMics]    = useState([]);
  const [memberships, setMemberships] = useState([]);
  const [canCreate,   setCanCreate]   = useState(false);
  const [loading,     setLoading]     = useState(true);
  const [creating,    setCreating]    = useState(false);
  const [newName,     setNewName]     = useState('');
  const [newDia,      setNewDia]      = useState('');
  const [newHora,     setNewHora]     = useState('');
  const [saving,      setSaving]      = useState(false);
  const [error,       setError]       = useState(null);
  const [tgSeen,      setTgSeen]      = useState(() => !!localStorage.getItem('tg_btn_seen'));
  const [showTgTooltip, setShowTgTooltip] = useState(() => !localStorage.getItem('tg_btn_seen'));
  const [showTgModal,   setShowTgModal]   = useState(false);
  const [tgData,        setTgData]        = useState(null);
  const [tgLoading,     setTgLoading]     = useState(false);
  const [tgError,       setTgError]       = useState(null);
  const [tgProveedorId, setTgProveedorId] = useState('');

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
      // Proveedor por defecto para Telegram
      const firstHost = memberships.find((m) => m.role === 'host');
      if (firstHost) setTgProveedorId(firstHost.proveedor_id);
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

  const canCreate_ = () => newName.trim() && newDia && newHora;

  const handleCreate = async () => {
    if (!canCreate_()) return;
    setSaving(true); setError(null);
    const hostMembership = memberships.find((m) => m.role === 'host');
    const { data: newMic, error: insertError } = await supabase
      .schema('silver').from('open_mics')
      .insert({
        proveedor_id: hostMembership.proveedor_id,
        nombre: newName.trim(),
        config: { info: { dia_semana: newDia, hora: newHora } },
      })
      .select('id, nombre').single();
    if (insertError) { setSaving(false); setError(insertError.message); return; }
    authFetch('/api/open-mic/create-form', { open_mic_id: newMic.id, nombre: newMic.nombre }).catch(() => {});
    setSaving(false);
    onSelect(newMic.id, { isNew: true });
  };

  const handleLogout = () => supabase.auth.signOut();

  const hostMemberships = memberships.filter((m) => m.role === 'host');
  const multiOrg = hostMemberships.length > 1;

  const handleTelegramClick = async () => {
    localStorage.setItem('tg_btn_seen', '1');
    setShowTgTooltip(false);
    setTgSeen(true);
    setShowTgModal(true);
    if (tgData) return;
    setTgLoading(true);
    setTgError(null);
    try {
      const res = await authFetch('/api/telegram/generate-code', { proveedor_id: tgProveedorId });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || `HTTP ${res.status}`);
      setTgData(data);
    } catch (e) {
      setTgError(e.message || 'Error desconocido');
    }
    setTgLoading(false);
  };

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
    <main className="paint-bg relative flex min-h-screen items-center justify-center overflow-hidden px-4 md:px-8">

      <div className="w-full max-w-md md:max-w-lg lg:max-w-xl">

        <div className="mb-6 rotate-[0.8deg] text-center">
          <h1 className="font-['Bangers'] text-6xl tracking-widest text-[#0D0D0D] md:text-7xl lg:text-8xl">
            AI LINEUP ARCHITECT
          </h1>
          <p className="mt-1 text-xs font-bold uppercase tracking-widest text-[#0D0D0D]/50 md:text-sm">{session.user.email}</p>
        </div>

        {/* Card rugosa + botón Telegram en esquina superior derecha */}
        <div className="relative">
        <div className="animate-pop-in -rotate-[1deg] paper-drop">
          <div data-tutorial="open-mic-selector" className="scrapbook-panel pin-corner paper-rough paper-note p-6">
            <h2 className="mb-4 font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a] md:text-3xl">Tus Open Mics</h2>

            {error && (
              <p className="mb-4 rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">{error}</p>
            )}

            {openMics.length > 0 && (
              <ul className="mb-4 flex flex-col gap-2">
                {openMics.map((mic, index) => (
                  <li key={mic.id} className={`animate-slide-up ${STAGGER_CLASSES[index] ?? 'stagger-6'} tilt-soft`}>
                    <button
                      type="button"
                      onClick={() => onSelect(mic.id)}
                      className={`paper-strip group flex w-full cursor-pointer items-center gap-3 rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] px-4 py-3 text-left text-base font-bold text-[#1a1a1a] transition-all duration-200 md:px-5 md:py-4 md:text-lg ${MIC_HOVER_COLORS[index % MIC_HOVER_COLORS.length]}`}
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

            <div data-tutorial="create-open-mic">
            {showCreateForm ? (
              <div className="flex flex-col gap-3 border-t-2 border-dashed border-[#C8B89A] pt-4">
                <label className="text-sm font-bold text-[#1a1a1a]">Nombre del nuevo Open Mic</label>
                <input
                  type="text" value={newName} autoFocus
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  placeholder="Ej: Recova Open Mic — Marzo 2026"
                  className="paper-strip rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-2 text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#3D5F6C]"
                />
                <div className="grid grid-cols-2 gap-2">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-bold text-[#1a1a1a]">
                      Día <span className="text-[#DC2626]">*</span>
                    </label>
                    <select
                      value={newDia}
                      onChange={(e) => setNewDia(e.target.value)}
                      className="paper-strip rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-2 py-2 text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#3D5F6C]"
                    >
                      <option value="">— Día —</option>
                      {DIAS.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-bold text-[#1a1a1a]">
                      Hora <span className="text-[#DC2626]">*</span>
                    </label>
                    <input
                      type="time"
                      value={newHora}
                      onChange={(e) => setNewHora(e.target.value)}
                      className="paper-strip rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-2 py-2 text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#3D5F6C]"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  {!showEmptyForm && (
                    <button
                      type="button"
                      onClick={() => { setCreating(false); setNewName(''); setNewDia(''); setNewHora(''); setError(null); }}
                      className="flex-1 cursor-pointer rounded-none border-[3px] border-[#0D0D0D] bg-[#5E7260] py-2 text-sm font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#4A5C4C]"
                    >
                      Cancelar
                    </button>
                  )}
                  <button
                    type="button" disabled={!canCreate_() || saving} onClick={handleCreate}
                    className={`flex-1 rounded-lg border-[3px] border-[#1a1a1a] py-2 text-sm font-bold transition-all duration-200
                      ${!canCreate_() || saving
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
                className="mt-2 flex w-full cursor-pointer items-center justify-center gap-2 rounded-none border-[3px] border-dashed border-[#0D0D0D] bg-transparent py-2 text-sm font-bold text-[#1a1a1a] transition-all duration-200 hover:bg-[#C8B89A]"
              >
                <PlusIcon />Nuevo Open Mic
              </button>
            ) : null}
            </div>
          </div>
        </div>

        {/* Telegram connect — esquina superior derecha */}
        <div className={`absolute flex flex-col items-center transition-all duration-500 ${
          tgSeen
            ? '-right-2 -top-2'
            : '-right-5 -top-5'
        }`}>
          {showTgTooltip && (
            <div className="absolute bottom-full mb-2 animate-bounce whitespace-nowrap">
              <div className="rounded-xl bg-[#229ED9] px-3 py-1.5 text-xs font-bold text-white shadow-lg">
                ¡Click Me!
              </div>
              <div className="mx-auto mt-0.5 h-0 w-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-[#229ED9]" />
            </div>
          )}
          <button
            type="button"
            onClick={handleTelegramClick}
            data-tutorial="telegram-button"
            className={`flex cursor-pointer items-center justify-center rounded-full bg-[#229ED9] text-white transition-all duration-300 hover:scale-110 ${
              tgSeen
                ? 'h-10 w-10 opacity-50 shadow-none hover:opacity-90'
                : 'h-16 w-16 shadow-[3px_3px_0px_rgba(0,0,0,0.35)] hover:shadow-[4px_4px_0px_rgba(0,0,0,0.4)]'
            }`}
            title="Conectar bot de Telegram"
          >
            <TelegramIcon className={tgSeen ? 'h-5 w-5' : 'h-9 w-9'} />
          </button>
        </div>
        </div>{/* fin relative wrapper */}

        <div className="mt-4 flex justify-center">
          <button type="button" onClick={handleLogout} className="cursor-pointer text-xs font-bold text-[#0D0D0D]/50 underline hover:text-[#3D5F6C]">
            Cerrar sesión
          </button>
        </div>
      </div>

      {/* Modal Telegram */}
      {showTgModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
          onClick={() => setShowTgModal(false)}
        >
          <div
            className="paper-drop rotate-[1.3deg] scrapbook-panel pin-corner paper-crumpled w-full max-w-xs p-6 text-center"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a]">
              Conecta el bot
            </h3>
            <p className="mb-4 text-xs text-[#6B5C4A]">
              {isMobile ? 'Conecta el bot directamente desde tu dispositivo' : 'Escanea el QR desde Telegram en tu móvil'}
            </p>

            {/* Selector de organización si hay más de una */}
            {multiOrg && (
              <div className="mb-4 flex flex-col gap-1.5 text-left">
                <label className="text-xs font-bold text-[#6B5C4A]">Organización</label>
                <select
                  value={tgProveedorId}
                  onChange={(e) => { setTgProveedorId(e.target.value); setTgData(null); setTgError(null); }}
                  className="paper-strip rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-2 py-1.5 text-sm text-[#1a1a1a] outline-none"
                >
                  {hostMemberships.map((m) => {
                    const mic = openMics.find((o) => o.proveedor_id === m.proveedor_id);
                    return (
                      <option key={m.proveedor_id} value={m.proveedor_id}>
                        {mic?.nombre ?? m.proveedor_id}
                      </option>
                    );
                  })}
                </select>
              </div>
            )}

            {tgLoading ? (
              <div className="flex h-[120px] items-center justify-center">
                <p className="text-sm text-[#6B5C4A]">Generando...</p>
              </div>
            ) : tgData?.qr_url ? (
              isMobile ? (
                <div className="flex flex-col gap-3 w-full">
                  <a
                    href={tgData.qr_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-center gap-2 rounded-lg border-[3px] border-[#1a1a1a] bg-[#229ED9] py-3 text-sm font-bold text-white transition-all duration-200 hover:bg-[#1a8bbf]"
                  >
                    <TelegramIcon className="h-5 w-5" />
                    Sí, abrir Telegram
                  </a>
                  <a
                    href="https://telegram.org/"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-center gap-2 rounded-lg border-[3px] border-dashed border-[#C8B89A] bg-[#F5F0E1] py-2.5 text-xs font-bold text-[#6B5C4A] transition-all duration-200 hover:bg-[#e8e0d0]"
                  >
                    No tengo Telegram — Descargar
                  </a>
                  <ol className="mt-1 space-y-1 text-left text-xs text-[#6B5C4A]">
                    <li>1. Pulsa <strong>Sí, abrir Telegram</strong></li>
                    <li>2. En el bot, pulsa <strong>Enviar</strong></li>
                    <li>3. El bot confirmará la conexión</li>
                  </ol>
                </div>
              ) : (
                <div className="flex justify-center">
                  <div className="rounded-xl border-[3px] border-[#1a1a1a] bg-white p-3 shadow-inner">
                    <QRCodeSVG value={tgData.qr_url} size={160} level="M" />
                  </div>
                </div>
              )
            ) : (
              <div className="flex h-[120px] flex-col items-center justify-center gap-2">
                <p className="text-sm font-bold text-[#DC2626]">Error al generar el código</p>
                {tgError && <p className="text-center text-xs text-[#6B5C4A]">{tgError}</p>}
              </div>
            )}

            {tgData?.code && !isMobile && (
              <div className="mt-4 rounded-lg border-2 border-dashed border-[#C8B89A] bg-[#F5F0E1] py-2">
                <p className="font-mono text-lg font-bold tracking-widest text-[#1a1a1a]">{tgData.code}</p>
              </div>
            )}

            {!isMobile && (
              <ol className="mt-4 space-y-1 text-left text-xs text-[#6B5C4A]">
                <li>1. Escanea el QR con tu cámara</li>
                <li>2. Se abrirá Telegram — pulsa <strong>Enviar</strong></li>
                <li>3. El bot confirmará la conexión</li>
              </ol>
            )}
            <p className="mt-3 text-[10px] text-[#C8B89A]">El código expira en 15 minutos</p>

            <button
              type="button"
              onClick={() => setShowTgModal(false)}
              className="mt-4 w-full cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] py-2 text-sm font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626]"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
