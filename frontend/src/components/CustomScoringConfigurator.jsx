import { useState } from 'react';

function RuleCard({ rule, index, onChange }) {
  return (
    <div className="paper-drop">
      <section className="paper-rough paper-note border-[3px] border-[#1a1a1a] bg-[#fffef5] p-4 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <span className="font-bold text-sm text-[#1a1a1a]">{rule.field}</span>
          <button
            type="button"
            role="switch"
            aria-checked={rule.enabled}
            onClick={() => onChange(index, { ...rule, enabled: !rule.enabled })}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-[#1a1a1a] transition-colors
              ${rule.enabled ? 'bg-[#22C55E]' : 'bg-[#D1D5DB]'}`}
          >
            <span
              className={`inline-block h-4 w-4 rounded-full bg-[#fff8e7] border border-[#1a1a1a] shadow transition-transform
                ${rule.enabled ? 'translate-x-5' : 'translate-x-0.5'}`}
            />
          </button>
        </div>

        <p className="text-xs text-[#6B5C4A]">
          Si respuesta = <strong>"{rule.value}"</strong> → {rule.points >= 0 ? '+' : ''}{rule.points} pts
        </p>

        <div className="flex items-center gap-3">
          <label className="text-xs text-[#6B5C4A] w-24">Puntos ({rule.points >= 0 ? '+' : ''}{rule.points})</label>
          <input
            type="range"
            role="slider"
            min={-50}
            max={50}
            step={5}
            value={rule.points}
            onChange={(e) => onChange(index, { ...rule, points: parseInt(e.target.value, 10) })}
            disabled={!rule.enabled}
            className={`flex-1 accent-[#1a1a1a] ${!rule.enabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          />
        </div>

        {rule.description && (
          <p className="text-xs text-[#6B5C4A] italic">{rule.description}</p>
        )}
      </section>
    </div>
  );
}

export function CustomScoringConfigurator({ openMicId, rules, onRulesChanged, onPropose, proposing }) {
  const handleRuleChange = (index, updatedRule) => {
    const newRules = rules.map((r, i) => (i === index ? updatedRule : r));
    onRulesChanged(newRules);
  };

  if (rules.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-[#6B5C4A]">
          No hay reglas definidas aún. Pulsa el botón para que Gemini proponga reglas
          basadas en los campos no canónicos de tu formulario.
        </p>
        <button
          type="button"
          disabled={proposing}
          onClick={onPropose}
          className={`self-start rounded-lg border-[3px] border-[#1a1a1a] px-4 py-2 text-sm font-bold transition-all
            ${proposing
              ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
              : 'comic-shadow cursor-pointer bg-[#1a1a1a] text-[#fff8e7] hover:bg-[#DC2626]'
            }`}
        >
          {proposing ? 'Proponiendo...' : 'Proponer reglas automáticas'}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[#6B5C4A]">{rules.length} regla{rules.length !== 1 ? 's' : ''} definida{rules.length !== 1 ? 's' : ''}</p>
        <button
          type="button"
          disabled={proposing}
          onClick={onPropose}
          className={`rounded-lg border-2 border-[#1a1a1a] px-3 py-1 text-xs font-bold transition-all
            ${proposing
              ? 'cursor-not-allowed bg-[#D1D5DB] text-[#6B5C4A]'
              : 'cursor-pointer bg-[#fff8e7] hover:bg-[#C8B89A]'
            }`}
        >
          {proposing ? 'Proponiendo...' : 'Re-proponer reglas'}
        </button>
      </div>

      {rules.map((rule, i) => (
        <RuleCard key={rule.field} rule={rule} index={i} onChange={handleRuleChange} />
      ))}
    </div>
  );
}
