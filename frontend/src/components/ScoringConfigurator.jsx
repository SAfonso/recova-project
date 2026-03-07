import { useEffect, useState } from 'react';
import { supabase } from '../supabaseClient';
import { ScoringTypeSelector } from './ScoringTypeSelector';
import { CustomScoringConfigurator } from './CustomScoringConfigurator';
import { extractFormId } from '../utils/formUtils';

// ---------------------------------------------------------------------------
// Valores por defecto — deben mantenerse sincronizados con
// backend/src/core/scoring_config.py → _DEFAULTS
// ---------------------------------------------------------------------------
const DEFAULTS = {
  available_slots: 8,
  categories: {
    standard:   { base_score: 50,   enabled: true },
    priority:   { base_score: 70,   enabled: true },
    gold:       { base_score: 90,   enabled: true },
    restricted: { base_score: null, enabled: true },
  },
  recency_penalty: {
    enabled:          true,
    last_n_editions:  2,
    penalty_points:   20,
  },
  single_date_boost: {
    enabled:      true,
    boost_points: 10,
  },
  gender_parity: {
    enabled:              false,
    target_female_nb_pct: 40,
  },
  poster: {
    enabled:         false,
    base_image_url:  null,
  },
};

// Actualización inmutable de rutas anidadas en el JSONB.
// setIn({a:{b:1}}, ['a','b'], 2) → {a:{b:2}}
function setIn(obj, [key, ...rest], value) {
  return rest.length === 0
    ? { ...obj, [key]: value }
    : { ...obj, [key]: setIn(obj[key] ?? {}, rest, value) };
}

// Fusiona la config de BD con DEFAULTS para garantizar que no falte ninguna clave.
function mergeWithDefaults(raw) {
  return {
    ...DEFAULTS,
    ...raw,
    categories: { ...DEFAULTS.categories, ...(raw?.categories ?? {}) },
    recency_penalty:   { ...DEFAULTS.recency_penalty,   ...(raw?.recency_penalty   ?? {}) },
    single_date_boost: { ...DEFAULTS.single_date_boost, ...(raw?.single_date_boost ?? {}) },
    gender_parity:     { ...DEFAULTS.gender_parity,     ...(raw?.gender_parity     ?? {}) },
    poster:            { ...DEFAULTS.poster,            ...(raw?.poster            ?? {}) },
  };
}

// Validaciones por campo. Devuelve un objeto { campo: 'mensaje' } con los errores.
function validate(config) {
  const errors = {};
  if (!Number.isInteger(config.available_slots) || config.available_slots < 1 || config.available_slots > 20) {
    errors.available_slots = 'Debe ser un entero entre 1 y 20';
  }
  for (const [cat, rule] of Object.entries(config.categories)) {
    if (cat === 'restricted') continue;
    if (!Number.isInteger(rule.base_score) || rule.base_score < 0 || rule.base_score > 200) {
      errors[`categories.${cat}.base_score`] = 'Debe ser un entero entre 0 y 200';
    }
  }
  const rp = config.recency_penalty;
  if (!Number.isInteger(rp.last_n_editions) || rp.last_n_editions < 1 || rp.last_n_editions > 10) {
    errors['recency_penalty.last_n_editions'] = 'Debe ser un entero entre 1 y 10';
  }
  if (!Number.isInteger(rp.penalty_points) || rp.penalty_points < 1 || rp.penalty_points > 100) {
    errors['recency_penalty.penalty_points'] = 'Debe ser un entero entre 1 y 100';
  }
  const sb = config.single_date_boost;
  if (!Number.isInteger(sb.boost_points) || sb.boost_points < 1 || sb.boost_points > 50) {
    errors['single_date_boost.boost_points'] = 'Debe ser un entero entre 1 y 50';
  }
  const gp = config.gender_parity;
  if (!Number.isInteger(gp.target_female_nb_pct) || gp.target_female_nb_pct < 0 || gp.target_female_nb_pct > 100) {
    errors['gender_parity.target_female_nb_pct'] = 'Debe ser un entero entre 0 y 100';
  }
  return errors;
}

// ---------------------------------------------------------------------------
// Sub-componentes
// ---------------------------------------------------------------------------

function SectionCard({ title, children }) {
  return (
    <div className="paper-drop">
      <section className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-4">
        <h3 className="mb-3 font-['Bangers'] text-lg tracking-wide text-[#1a1a1a]">{title}</h3>
        {children}
      </section>
    </div>
  );
}

function FieldError({ errors, field }) {
  if (!errors[field]) return null;
  return <p className="mt-1 text-xs text-[#DC2626]">{errors[field]}</p>;
}

function Toggle({ checked, onChange, disabled = false }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-[#1a1a1a] transition-colors
        ${checked ? 'bg-[#22C55E]' : 'bg-[#D1D5DB]'}
        ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-[#fff8e7] border border-[#1a1a1a] shadow transition-transform
          ${checked ? 'translate-x-5' : 'translate-x-0.5'}`}
      />
    </button>
  );
}

function NumberInput({ value, onChange, min, max, disabled = false, error = false }) {
  return (
    <input
      type="number"
      value={value ?? ''}
      min={min}
      max={max}
      disabled={disabled}
      onChange={(e) => {
        const parsed = parseInt(e.target.value, 10);
        onChange(Number.isNaN(parsed) ? value : parsed);
      }}
      className={`w-20 rounded-md border-2 bg-[#F5F0E1] px-2 py-1 text-center text-sm font-bold text-[#1a1a1a] outline-none
        ${error ? 'border-[#DC2626]' : 'border-[#1a1a1a]'}
        ${disabled ? 'cursor-not-allowed opacity-50' : 'focus:ring-2 focus:ring-[#1a1a1a]'}`}
    />
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export function ScoringConfigurator({ openMicId, openMicName, onSaved }) {
  const [config, setConfig]   = useState(mergeWithDefaults({}));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);
  const [saved, setSaved]     = useState(false);   // feedback temporal
  const [error, setError]     = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [uploading, setUploading] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [formUrlInput, setFormUrlInput] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState('');
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [creatingForm, setCreatingForm] = useState(false);
  const [formCreateError, setFormCreateError] = useState('');

  // Carga/recarga config desde silver.open_mics
  const fetchConfig = () => {
    if (!openMicId) return;
    setLoading(true);
    setError(null);
    supabase
      .schema('silver')
      .from('open_mics')
      .select('config')
      .eq('id', openMicId)
      .single()
      .then(({ data, error: err }) => {
        if (err) {
          setError(err.message);
        } else {
          setConfig(mergeWithDefaults(data?.config ?? {}));
        }
        setLoading(false);
      });
  };

  useEffect(() => { fetchConfig(); }, [openMicId]);

  const update = (path, value) =>
    setConfig((prev) => setIn(prev, path, value));

  const handlePosterUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    const path = `${openMicId}/background.png`;
    const { error: uploadError } = await supabase.storage
      .from('poster-backgrounds')
      .upload(path, file, { upsert: true, contentType: 'image/png' });
    if (uploadError) {
      setError(`Error subiendo imagen: ${uploadError.message}`);
      setUploading(false);
      return;
    }
    const { data: { publicUrl } } = supabase.storage
      .from('poster-backgrounds')
      .getPublicUrl(path);
    update(['poster', 'base_image_url'], publicUrl);
    setUploading(false);
  };

  const handlePropose = async () => {
    setProposing(true);
    setError(null);
    try {
      const apiKey = import.meta.env.VITE_WEBHOOK_API_KEY ?? '';
      const apiUrl = import.meta.env.VITE_BACKEND_URL ?? '';
      const resp = await fetch(`${apiUrl}/api/open-mic/propose-custom-rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
        body: JSON.stringify({ open_mic_id: openMicId }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setError(data.message ?? 'Error al proponer reglas');
        return;
      }
      update(['custom_scoring_rules'], data.rules);
    } catch (e) {
      setError('Error de red al proponer reglas');
    } finally {
      setProposing(false);
    }
  };

  const handleCreateForm = async () => {
    setCreatingForm(true);
    setFormCreateError('');
    try {
      const apiKey = import.meta.env.VITE_WEBHOOK_API_KEY ?? '';
      const apiUrl = import.meta.env.VITE_BACKEND_URL ?? '';
      const res = await fetch(`${apiUrl}/api/open-mic/create-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
        body: JSON.stringify({ open_mic_id: openMicId, nombre: openMicName }),
      });
      const data = await res.json();
      if (!res.ok) {
        setFormCreateError(data.message ?? 'Error creando el form');
        return;
      }
      fetchConfig();
    } catch {
      setFormCreateError('Error de red al crear el formulario');
    } finally {
      setCreatingForm(false);
    }
  };

  const handleAnalyzeForm = async () => {
    const formId = extractFormId(formUrlInput) || config.external_form_id || config.form?.form_id;
    if (!formId) return;
    setAnalyzing(true);
    setAnalyzeError('');
    setAnalyzeResult(null);
    try {
      const apiKey = import.meta.env.VITE_WEBHOOK_API_KEY ?? '';
      const apiUrl = import.meta.env.VITE_BACKEND_URL ?? '';
      const res = await fetch(`${apiUrl}/api/open-mic/analyze-form`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-KEY': apiKey },
        body: JSON.stringify({ open_mic_id: openMicId, form_id: formId }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAnalyzeError(data.message ?? 'Error al analizar el formulario');
      } else {
        setAnalyzeResult(data);
        fetchConfig();
      }
    } catch {
      setAnalyzeError('Error de red al analizar el formulario');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSave = async () => {
    const errors = validate(config);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setFieldErrors({});
    setSaving(true);
    setError(null);

    const { error: err } = await supabase
      .schema('silver')
      .from('open_mics')
      .update({ config })
      .eq('id', openMicId);

    setSaving(false);

    if (err) {
      setError(err.message);
      return;
    }

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    onSaved?.();
  };

  if (loading) {
    return (
      <div className="rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] p-8 text-center text-sm text-[#6B5C4A]">
        Cargando configuración...
      </div>
    );
  }

  const CATEGORY_LABELS = {
    standard:   'Standard',
    priority:   'Priority',
    gold:       'Gold',
    restricted: 'Restricted',
  };

  const scoringType = config.scoring_type ?? 'basic';
  const isNone   = scoringType === 'none';
  const isBasic  = scoringType === 'basic';
  const isCustom = scoringType === 'custom';

  return (
    <div className="flex flex-col gap-4">

      {/* Error global */}
      {error && (
        <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">
          {error}
        </p>
      )}

      {/* ── 0. Tipo de scoring ───────────────────────────────────── */}
      <SectionCard title="Tipo de scoring">
        <ScoringTypeSelector
          openMicId={openMicId}
          currentType={scoringType}
          hasFieldMapping={!!config.field_mapping}
          onChanged={fetchConfig}
        />
      </SectionCard>

      {/* ── Google Form — siempre visible ────────────────────────── */}
      {isCustom ? (
        <SectionCard title="Subir formulario">
          <div className="flex flex-col gap-3">
            {config.field_mapping && (
              <p className="flex items-center gap-1.5 text-xs text-[#22C55E]">
                <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>
                {Object.values(config.field_mapping).filter(Boolean).length} de {Object.keys(config.field_mapping).length} campos mapeados
              </p>
            )}
            <div className="flex gap-2">
              <input
                type="text"
                value={formUrlInput || config.external_form_id || ''}
                onChange={(e) => setFormUrlInput(e.target.value)}
                placeholder="URL o ID del Google Form"
                className="flex-1 rounded-md border-2 border-[#1a1a1a] bg-[#F5F0E1] px-3 py-2 text-xs text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#DC2626]"
              />
              <button
                type="button"
                onClick={handleAnalyzeForm}
                disabled={analyzing || !(formUrlInput || config.external_form_id || config.form?.form_id)}
                className="shrink-0 cursor-pointer rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] px-3 py-2 text-xs font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {analyzing ? 'Analizando...' : config.field_mapping ? 'Re-analizar' : 'Analizar'}
              </button>
            </div>
            {analyzeError && <p className="text-xs text-[#DC2626]">{analyzeError}</p>}
            {analyzeResult && (
              <p className="text-xs text-[#22C55E]">
                {analyzeResult.canonical_coverage} de {analyzeResult.total_questions} campos mapeados
                {analyzeResult.unmapped_fields?.length > 0 && ` · sin mapear: ${analyzeResult.unmapped_fields.join(', ')}`}
              </p>
            )}
          </div>
        </SectionCard>
      ) : (
        <SectionCard title="Google Form">
          <div className="flex flex-col gap-3">
            {config.form?.form_url && (
              <div className="flex flex-col gap-2">
                <a href={config.form.form_url} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm font-bold text-[#DC2626] underline underline-offset-2 hover:text-[#7f1d1d]">
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                  Abrir formulario
                </a>
                {config.form.sheet_url && (
                  <a href={config.form.sheet_url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm font-bold text-[#DC2626] underline underline-offset-2 hover:text-[#7f1d1d]">
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                    Ver respuestas (Sheet)
                  </a>
                )}
              </div>
            )}
            {!config.form?.form_url && (
              <>
                {formCreateError && <p className="text-xs text-[#DC2626]">{formCreateError}</p>}
                <button
                  type="button"
                  onClick={handleCreateForm}
                  disabled={creatingForm}
                  className="comic-shadow flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-[3px] border-[#1a1a1a] bg-[#1a1a1a] py-2.5 text-sm font-bold text-[#fff8e7] transition-all duration-200 hover:bg-[#DC2626] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {creatingForm ? 'Creando form...' : 'Crear Google Form'}
                </button>
              </>
            )}
          </div>
        </SectionCard>
      )}

      {/* ── Reglas custom (solo si custom) ───────────────────────── */}
      {isCustom && (
        <SectionCard title="Reglas de scoring personalizadas">
          <CustomScoringConfigurator
            openMicId={openMicId}
            rules={config.custom_scoring_rules ?? []}
            onRulesChanged={(r) => update(['custom_scoring_rules'], r)}
            onPropose={handlePropose}
            proposing={proposing}
          />
        </SectionCard>
      )}

      {/* ── Paneles visibles solo si scoring != 'none' ───────────── */}
      {!isNone && (
        <>

      {/* ── 1. Slots disponibles ─────────────────────────────────── */}
      <SectionCard title="Slots disponibles">
        <div className="flex items-center gap-3">
          <NumberInput
            value={config.available_slots}
            min={1}
            max={20}
            error={!!fieldErrors.available_slots}
            onChange={(v) => update(['available_slots'], v)}
          />
          <span className="text-sm text-[#6B5C4A]">plazas por edición</span>
        </div>
        <FieldError errors={fieldErrors} field="available_slots" />
      </SectionCard>

      {/* ── 2. Categorías ────────────────────────────────────────── */}
      <SectionCard title="Puntuación base por categoría">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b-2 border-[#1a1a1a]/20 text-left text-[10px] uppercase tracking-wide text-[#6B5C4A]">
                <th className="pb-2 pr-4">Categoría</th>
                <th className="pb-2 pr-4">Puntos base</th>
                <th className="pb-2">Activa</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1a1a]/10">
              {Object.entries(config.categories).map(([cat, rule]) => {
                const isRestricted = cat === 'restricted';
                const enabled      = rule.enabled;
                return (
                  <tr key={cat} className={`py-2 transition-opacity ${!enabled ? 'opacity-50' : ''}`}>
                    <td className="py-2 pr-4 font-bold text-[#1a1a1a]">
                      {CATEGORY_LABELS[cat] ?? cat}
                    </td>
                    <td className="py-2 pr-4">
                      {isRestricted ? (
                        <span className="text-xs text-[#6B5C4A] italic">bloqueado</span>
                      ) : (
                        <>
                          <NumberInput
                            value={rule.base_score}
                            min={0}
                            max={200}
                            disabled={!enabled}
                            error={!!fieldErrors[`categories.${cat}.base_score`]}
                            onChange={(v) => update(['categories', cat, 'base_score'], v)}
                          />
                          <FieldError errors={fieldErrors} field={`categories.${cat}.base_score`} />
                        </>
                      )}
                    </td>
                    <td className="py-2">
                      <Toggle
                        checked={enabled}
                        onChange={(v) => update(['categories', cat, 'enabled'], v)}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* ── 3. Penalización de recencia (solo básico) ────────────── */}
      {isBasic && <SectionCard title="Penalización por recencia">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Toggle
              checked={config.recency_penalty.enabled}
              onChange={(v) => update(['recency_penalty', 'enabled'], v)}
            />
            <span className="text-sm text-[#1a1a1a]">
              Penalizar a cómicos que actuaron recientemente en este open mic
            </span>
          </div>

          <div className={`flex flex-col gap-2 pl-2 ${!config.recency_penalty.enabled ? 'opacity-50' : ''}`}>
            <div className="flex items-center gap-3">
              <label className="w-44 text-xs text-[#6B5C4A]">Últimas N ediciones</label>
              <NumberInput
                value={config.recency_penalty.last_n_editions}
                min={1}
                max={10}
                disabled={!config.recency_penalty.enabled}
                error={!!fieldErrors['recency_penalty.last_n_editions']}
                onChange={(v) => update(['recency_penalty', 'last_n_editions'], v)}
              />
            </div>
            <FieldError errors={fieldErrors} field="recency_penalty.last_n_editions" />

            <div className="flex items-center gap-3">
              <label className="w-44 text-xs text-[#6B5C4A]">Puntos de penalización</label>
              <NumberInput
                value={config.recency_penalty.penalty_points}
                min={1}
                max={100}
                disabled={!config.recency_penalty.enabled}
                error={!!fieldErrors['recency_penalty.penalty_points']}
                onChange={(v) => update(['recency_penalty', 'penalty_points'], v)}
              />
            </div>
            <FieldError errors={fieldErrors} field="recency_penalty.penalty_points" />
          </div>
        </div>
      </SectionCard>}

      {/* ── 4. Bono bala única (solo básico) ─────────────────────── */}
      {isBasic && <SectionCard title="Bono por disponibilidad única">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Toggle
              checked={config.single_date_boost.enabled}
              onChange={(v) => update(['single_date_boost', 'enabled'], v)}
            />
            <span className="text-sm text-[#1a1a1a]">
              Bonificar cómicos disponibles solo para una fecha
            </span>
          </div>

          <div className={`flex items-center gap-3 pl-2 ${!config.single_date_boost.enabled ? 'opacity-50' : ''}`}>
            <label className="w-44 text-xs text-[#6B5C4A]">Puntos de bono</label>
            <NumberInput
              value={config.single_date_boost.boost_points}
              min={1}
              max={50}
              disabled={!config.single_date_boost.enabled}
              error={!!fieldErrors['single_date_boost.boost_points']}
              onChange={(v) => update(['single_date_boost', 'boost_points'], v)}
            />
          </div>
          <FieldError errors={fieldErrors} field="single_date_boost.boost_points" />
        </div>
      </SectionCard>}

      {/* ── 5. Paridad de género ─────────────────────────────────── */}
      <SectionCard title="Paridad de género">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Toggle
              checked={config.gender_parity.enabled}
              onChange={(v) => update(['gender_parity', 'enabled'], v)}
            />
            <span className="text-sm text-[#1a1a1a]">
              Activar objetivo de representación femenina / no-binaria
            </span>
          </div>

          <div className={`flex items-center gap-3 pl-2 ${!config.gender_parity.enabled ? 'opacity-50' : ''}`}>
            <label className="w-44 text-xs text-[#6B5C4A]">% objetivo f / nb</label>
            <NumberInput
              value={config.gender_parity.target_female_nb_pct}
              min={0}
              max={100}
              disabled={!config.gender_parity.enabled}
              error={!!fieldErrors['gender_parity.target_female_nb_pct']}
              onChange={(v) => update(['gender_parity', 'target_female_nb_pct'], v)}
            />
            <span className="text-xs text-[#6B5C4A]">%</span>
          </div>
          <FieldError errors={fieldErrors} field="gender_parity.target_female_nb_pct" />
        </div>
      </SectionCard>

      {/* ── 6. Póster del evento ─────────────────────────────────── */}
      <SectionCard title="Póster del evento">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Toggle
              checked={config.poster.enabled}
              onChange={(v) => update(['poster', 'enabled'], v)}
            />
            <span className="text-sm text-[#1a1a1a]">
              Generar póster SVG al validar el lineup
            </span>
          </div>

          {config.poster.enabled && (
            <div className="flex flex-col gap-3 pl-2">
              {config.poster.base_image_url && (
                <img
                  src={config.poster.base_image_url}
                  alt="Fondo del póster"
                  className="h-32 w-auto self-start rounded-md border-2 border-[#1a1a1a] object-cover"
                />
              )}
              <label className={`flex cursor-pointer items-center gap-2 self-start rounded-lg border-[3px] border-[#1a1a1a] px-4 py-2 text-sm font-bold transition-all
                ${uploading ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]' : 'bg-[#fff8e7] text-[#1a1a1a] hover:bg-[#C8B89A]'}`}
              >
                <input
                  type="file"
                  accept="image/png"
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) => handlePosterUpload(e.target.files?.[0])}
                />
                {uploading
                  ? 'Subiendo...'
                  : config.poster.base_image_url
                    ? 'Cambiar imagen de fondo'
                    : 'Subir imagen de fondo (PNG)'}
              </label>
              {!config.poster.base_image_url && (
                <p className="text-xs text-[#6B5C4A]">
                  Sin imagen de fondo — se usará el template por defecto del servidor.
                </p>
              )}
            </div>
          )}
        </div>
      </SectionCard>

        </>
      )}

      {/* ── Guardar ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-end gap-3 pt-1">
        {saved && (
          <span className="flex animate-pop-in items-center gap-1.5 text-sm font-bold text-[#22C55E]">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Guardado
          </span>
        )}
        <button
          type="button"
          disabled={saving || loading}
          onClick={handleSave}
          className={`rounded-lg border-[3px] border-[#1a1a1a] px-6 py-2.5 text-sm font-bold transition-all duration-200
            ${saving || loading
              ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
              : 'comic-shadow cursor-pointer bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626] hover:scale-[1.02] active:scale-[0.98]'
            }`}
        >
          {saving ? 'Guardando...' : 'Guardar configuración'}
        </button>
      </div>
    </div>
  );
}
