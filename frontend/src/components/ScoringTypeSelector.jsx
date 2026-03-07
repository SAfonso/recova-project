import { useState } from 'react';
import { supabase } from '../supabaseClient';

const OPTIONS = [
  {
    id: 'none',
    label: 'Sin scoring',
    description: 'Selecciona el lineup manualmente',
  },
  {
    id: 'basic',
    label: 'Scoring básico',
    description: 'Algoritmo estándar (experiencia + recencia + género)',
  },
  {
    id: 'custom',
    label: 'Scoring personalizado',
    description: 'Reglas basadas en los campos de tu formulario',
    requiresMapping: true,
  },
];

export function ScoringTypeSelector({ openMicId, currentType, hasFieldMapping, onChanged }) {
  const [selected, setSelected] = useState(currentType ?? 'basic');
  const [saving, setSaving] = useState(false);

  const handleChange = async (id) => {
    if (id === selected) return;
    setSelected(id);
    setSaving(true);
    await supabase.schema('silver').rpc('update_open_mic_config_keys', {
      p_open_mic_id: openMicId,
      p_keys: { scoring_type: id },
    });
    setSaving(false);
    onChanged?.();
  };

  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-bold uppercase tracking-wide text-[#6B5C4A]">
        Tipo de scoring
        {saving && <span className="ml-2 font-normal normal-case opacity-60">Guardando...</span>}
      </span>
      <div className="flex flex-col gap-2">
        {OPTIONS.map((opt) => {
          const disabled = opt.requiresMapping && !hasFieldMapping;
          const active = selected === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={disabled}
              onClick={() => !disabled && handleChange(opt.id)}
              title={disabled ? 'Primero analiza tu formulario en la pestaña Info' : undefined}
              className={`flex items-start gap-3 rounded-lg border-2 px-3 py-2.5 text-left transition-all duration-150
                ${active
                  ? 'border-[#1a1a1a] bg-[#1a1a1a] text-[#fff8e7]'
                  : disabled
                    ? 'cursor-not-allowed border-[#C8B89A] bg-[#F5F0E1] opacity-40'
                    : 'cursor-pointer border-[#C8B89A] bg-[#F5F0E1] text-[#1a1a1a] hover:border-[#1a1a1a] hover:bg-[#E8DFC8]'
                }`}
            >
              {/* Radio dot */}
              <span className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2
                ${active ? 'border-[#fff8e7] bg-[#fff8e7]' : 'border-[#6B5C4A] bg-transparent'}`}
              >
                {active && <span className="h-2 w-2 rounded-full bg-[#1a1a1a]" />}
              </span>
              <div>
                <p className={`text-sm font-bold leading-tight ${active ? 'text-[#fff8e7]' : 'text-[#1a1a1a]'}`}>
                  {opt.label}
                  {disabled && <span className="ml-1.5 text-[10px] font-normal opacity-70">(requiere análisis de form)</span>}
                </p>
                <p className={`text-xs leading-snug ${active ? 'text-[#fff8e7]/70' : 'text-[#6B5C4A]'}`}>
                  {opt.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
