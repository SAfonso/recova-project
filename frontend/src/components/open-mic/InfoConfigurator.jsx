import { useState } from 'react';
import { supabase } from '../../supabaseClient';
import { OPEN_MIC_ICONS } from './openmic-icons';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

const CADENCIAS = [
  { id: 'semanal',   label: 'Semanalmente' },
  { id: 'quincenal', label: 'Quincenalmente' },
  { id: 'mensual',   label: 'Mensualmente' },
  { id: 'unico',     label: 'Evento único' },
];

const INPUT = 'w-full rounded-none border-[3px] border-[#0D0D0D] bg-[#EDE8DC] px-3 py-2.5 text-base text-[#0D0D0D] outline-none focus:ring-2 focus:ring-[#3D5F6C]';

const CheckIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const XSmallIcon = () => (
  <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-bold uppercase tracking-wide text-[#6B5C4A] md:text-base">{label}</span>
      {children}
    </div>
  );
}

export function InfoConfigurator({ openMicId, openMic, onSaved }) {
  const info = openMic.config?.info ?? {};

  const [form, setForm] = useState({
    nombre:       openMic.nombre ?? '',
    local:        info.local ?? '',
    direccion:    info.direccion ?? '',
    hosts:        info.hosts ?? [],
    dia_semana:   info.dia_semana ?? '',
    hora:         info.hora ?? '',
    instagram:    info.instagram ?? '',
    icono:        info.icono ?? 'mic',
    cadencia:     info.cadencia ?? '',
    fecha_inicio: info.fecha_inicio ?? '',
  });
  const [hostInput,      setHostInput]      = useState('');
  const [saving,         setSaving]         = useState(false);
  const [saved,          setSaved]          = useState(false);
  const [error,          setError]          = useState(null);
  const [showFormPopup,  setShowFormPopup]  = useState(false);

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const addHost = () => {
    const trimmed = hostInput.trim();
    if (!trimmed || form.hosts.includes(trimmed)) return;
    set('hosts', [...form.hosts, trimmed]);
    setHostInput('');
  };

  const handleSave = async () => {
    if (!form.nombre.trim()) return;
    setSaving(true);
    setError(null);

    const hasExistingForm = !!openMic.config?.form?.form_id;

    // Si hay form creado, marcar info_changed en config
    const formConfig = hasExistingForm
      ? { ...(openMic.config?.form ?? {}), info_changed: true }
      : openMic.config?.form;

    const newConfig = {
      ...(openMic.config ?? {}),
      info: {
        local:        form.local,
        direccion:    form.direccion,
        hosts:        form.hosts,
        dia_semana:   form.dia_semana,
        hora:         form.hora,
        instagram:    form.instagram,
        icono:        form.icono,
        cadencia:     form.cadencia,
        fecha_inicio: form.fecha_inicio,
      },
      ...(formConfig !== undefined ? { form: formConfig } : {}),
    };

    const { error: err } = await supabase
      .schema('silver')
      .from('open_mics')
      .update({ nombre: form.nombre.trim(), config: newConfig })
      .eq('id', openMicId);
    setSaving(false);
    if (err) { setError(err.message); return; }

    if (hasExistingForm) setShowFormPopup(true);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
    onSaved?.();
  };

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">{error}</p>
      )}

      {/* Nombre */}
      <Field label="Nombre del Open Mic">
        <input
          type="text"
          value={form.nombre}
          onChange={(e) => set('nombre', e.target.value)}
          className={INPUT}
          placeholder="Ej: Recova Open Mic"
        />
      </Field>

      {/* Local */}
      <Field label="Local (bar / venue)">
        <input
          type="text"
          value={form.local}
          onChange={(e) => set('local', e.target.value)}
          className={INPUT}
          placeholder="Ej: Bar La Recova"
        />
      </Field>

      {/* Dirección */}
      <Field label="Dirección">
        <input
          type="text"
          value={form.direccion}
          onChange={(e) => set('direccion', e.target.value)}
          className={INPUT}
          placeholder="Ej: Calle Gran Vía 28, Madrid"
        />
      </Field>

      {/* Hosts */}
      <Field label="Host(s)">
        <div className="flex gap-2">
          <input
            type="text"
            value={hostInput}
            onChange={(e) => setHostInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addHost(); } }}
            className={`${INPUT} flex-1`}
            placeholder="Nombre del host..."
          />
          <button
            type="button"
            onClick={addHost}
            className="cursor-pointer rounded-lg border-2 border-[#1a1a1a] bg-[#C8B89A] px-3 text-base font-bold text-[#1a1a1a] transition-all hover:bg-[#B8A88A]"
          >
            +
          </button>
        </div>
        {form.hosts.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {form.hosts.map((h) => (
              <span key={h} className="flex items-center gap-1.5 rounded-full border-2 border-[#1a1a1a] bg-[#F5F0E1] px-2.5 py-0.5 text-sm font-bold text-[#1a1a1a]">
                {h}
                <button
                  type="button"
                  onClick={() => set('hosts', form.hosts.filter((x) => x !== h))}
                  className="cursor-pointer text-[#6B5C4A] hover:text-[#DC2626]"
                  aria-label={`Eliminar host ${h}`}
                >
                  <XSmallIcon />
                </button>
              </span>
            ))}
          </div>
        )}
      </Field>

      {/* Frecuencia (cadencia) */}
      <Field label="Frecuencia">
        <div className="flex flex-wrap gap-2">
          {CADENCIAS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => set('cadencia', id)}
              aria-pressed={form.cadencia === id}
              className={`cursor-pointer rounded-full border-2 px-3 py-1 text-xs font-bold transition-all duration-150
                ${form.cadencia === id
                  ? 'border-[#1a1a1a] bg-[#1a1a1a] text-[#fff8e7]'
                  : 'border-[#C8B89A] bg-[#F5F0E1] text-[#6B5C4A] hover:border-[#1a1a1a]'
                }`}
            >
              {label}
            </button>
          ))}
        </div>
      </Field>

      {/* Fecha de inicio */}
      <Field label="Fecha de inicio">
        <input
          id="fecha-inicio"
          type="date"
          value={form.fecha_inicio}
          onChange={(e) => set('fecha_inicio', e.target.value)}
          aria-label="Fecha de inicio"
          className={INPUT}
        />
        {form.fecha_inicio && (
          <span className="text-xs text-[#6B5C4A]">
            {form.fecha_inicio.split('-').reverse().join('/')}
          </span>
        )}
      </Field>

      {/* Día y Hora */}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Día de la semana">
          <select
            value={form.dia_semana}
            onChange={(e) => set('dia_semana', e.target.value)}
            className={INPUT}
          >
            <option value="">— Sin especificar —</option>
            {DIAS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
        <Field label="Hora">
          <input
            type="time"
            value={form.hora}
            onChange={(e) => set('hora', e.target.value)}
            className={INPUT}
          />
        </Field>
      </div>

      {/* Instagram */}
      <Field label="Instagram">
        <div className="flex items-center rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] focus-within:ring-2 focus-within:ring-[#DC2626]">
          <span className="pl-3 text-sm font-bold text-[#6B5C4A]">@</span>
          <input
            type="text"
            value={form.instagram.replace(/^@/, '')}
            onChange={(e) => set('instagram', e.target.value.replace(/^@/, ''))}
            className="flex-1 bg-transparent px-2 py-2 text-sm text-[#1a1a1a] outline-none"
            placeholder="recova_comedy"
          />
        </div>
      </Field>

      {/* Icono */}
      <Field label="Icono del Open Mic">
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {OPEN_MIC_ICONS.map(({ id, label, Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => set('icono', id)}
              aria-pressed={form.icono === id}
              aria-label={`Icono ${label}`}
              className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border-2 px-2 py-2.5 text-[10px] font-bold transition-all duration-150
                ${form.icono === id
                  ? 'border-[#1a1a1a] bg-[#1a1a1a] text-[#fff8e7] shadow-[2px_2px_0_rgba(0,0,0,0.25)]'
                  : 'border-[#C8B89A] bg-[#F5F0E1] text-[#6B5C4A] hover:border-[#1a1a1a] hover:bg-[#E8DFC8]'
                }`}
            >
              <Icon className="h-5 w-5" />
              <span className="leading-tight">{label}</span>
            </button>
          ))}
        </div>
      </Field>

      {/* Guardar */}
      <div className="flex items-center justify-end gap-3 pt-1">
        {saved && (
          <span className="flex animate-pop-in items-center gap-1.5 text-sm font-bold text-[#22C55E]">
            <CheckIcon /> Guardado
          </span>
        )}
        <button
          type="button"
          disabled={saving || !form.nombre.trim()}
          onClick={handleSave}
          className={`rounded-lg border-[3px] border-[#1a1a1a] px-6 py-2.5 text-sm font-bold transition-all duration-200
            ${saving || !form.nombre.trim()
              ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
              : 'comic-shadow cursor-pointer bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626] hover:scale-[1.02] active:scale-[0.98]'
            }`}
        >
          {saving ? 'Guardando...' : 'Guardar información'}
        </button>
      </div>

      {/* Modal: formulario desactualizado */}
      {showFormPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-xl border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-6 shadow-[8px_8px_0px_rgba(0,0,0,0.3)]">
            <p className="mb-1 font-['Bangers'] text-xl tracking-wide text-[#DC2626]">
              ⚠️ El formulario puede haber quedado desactualizado
            </p>
            <p className="mb-5 text-sm text-[#1a1a1a]">
              Has modificado información del open mic. El formulario de Google que tienes creado
              puede contener fechas o descripción incorrectas.
              <br /><br />
              Te recomendamos borrarlo y volver a generarlo para que refleje los nuevos datos.
            </p>
            <button
              type="button"
              onClick={() => setShowFormPopup(false)}
              className="comic-shadow w-full cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] py-2.5 text-sm font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626]"
            >
              Entendido
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
