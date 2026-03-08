const CheckIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const CATEGORY_BUTTONS = [
  { value: 'gold',       label: 'Gold',       className: 'bg-[#FACC15] text-[#1a1a1a]' },
  { value: 'priority',   label: 'Priority',   className: 'bg-[#3B82F6] text-[#fff8e7]' },
  { value: 'restricted', label: 'Restricted', className: 'bg-[#1a1a1a] text-[#fff8e7]' },
];

const GENDER_OPTIONS = [
  { value: 'm',  label: 'M' },
  { value: 'f',  label: 'F' },
  { value: 'nb', label: 'NB' },
];

const CARD_BORDER = {
  gold:       'border-[#D4A017] bg-[#fffef5]',
  priority:   'border-[#A0A0A0] bg-[#fffef5]',
  restricted: 'restricted-overlay border-[#DC2626] bg-[#fee2e2]',
  default:    'border-[#1a1a1a] bg-[#fffef5]',
};

const DROP_SHADOW = {
  gold:       'drop-shadow(0 0 6px rgba(212,160,23,0.5))',
  priority:   'drop-shadow(0 0 5px rgba(160,160,160,0.5))',
  restricted: 'drop-shadow(0 0 6px rgba(220,38,38,0.4))',
  default:    'drop-shadow(3px 3px 0px rgba(0,0,0,0.35))',
};

function categoryBadge(category) {
  if (category === 'gold')       return <span className="rounded-full bg-[#D4A017] px-2 py-0.5 text-[10px] font-bold text-[#1a1a1a]">GOLD</span>;
  if (category === 'priority')   return <span className="rounded-full bg-[#A0A0A0] px-2 py-0.5 text-[10px] font-bold text-[#fff8e7]">PRIO</span>;
  if (category === 'restricted') return <span className="rounded-full bg-[#DC2626] px-2 py-0.5 text-[10px] font-bold text-[#fff8e7]">REST</span>;
  return null;
}

export function ComicCard({
  candidate, draft, selected, expanded, canSelect,
  onExpand, onToggleSelected, onUpdateCategory, onUpdateGenero, hasPendingEdit,
}) {
  const borderClass = CARD_BORDER[draft.categoria] ?? CARD_BORDER.default;
  const shadow = DROP_SHADOW[draft.categoria] ?? DROP_SHADOW.default;

  const handleCategoryClick = (value) => {
    // Si ya está activo, volver a standard (quitar categoría especial)
    if (draft.categoria === value) {
      onUpdateCategory('standard');
    } else {
      onUpdateCategory(value);
    }
  };

  return (
    <div style={{ filter: shadow }}>
      <article className={`paper-rough paper-note relative overflow-hidden border-[3px] transition-all duration-200 ${borderClass}`}>
        <button
          type="button"
          onClick={onExpand}
          className="flex w-full cursor-pointer items-center gap-3 px-3 py-2.5 text-left"
          aria-expanded={expanded}
        >
          <span className="relative z-10 flex-1 truncate text-base font-bold text-[#1a1a1a]">
            {candidate.nombre ?? candidate.instagram ?? 'Sin nombre'}
          </span>
          <span className="relative z-10">{categoryBadge(draft.categoria)}</span>
        </button>

        {expanded && (
          <div className="relative z-10 border-t-2 border-dashed border-[#1a1a1a]/20 px-3 pb-3 pt-2">
            <div className="flex items-start gap-3">
              <div className="flex flex-col gap-2.5">
                {/* Categoría */}
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] text-[#6B5C4A]">Categoría <span className="text-[#9ca3af]">(clic activo = quitar)</span></span>
                  <div className="flex gap-1.5">
                    {CATEGORY_BUTTONS.map((btn) => {
                      const active = draft.categoria === btn.value;
                      return (
                        <button
                          key={btn.value}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); handleCategoryClick(btn.value); }}
                          className={`h-7 min-w-16 cursor-pointer rounded-md border-2 border-[#1a1a1a] px-1 text-[10px] font-bold transition-all duration-150 ${btn.className} ${active ? 'ring-2 ring-[#1a1a1a] ring-offset-1' : 'opacity-70 hover:opacity-100'}`}
                          aria-label={`Asignar categoría ${btn.label}`}
                        >
                          {btn.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Género */}
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] text-[#6B5C4A]">Género</span>
                  <div className="flex gap-1.5">
                    {GENDER_OPTIONS.map((opt) => {
                      const active = draft.genero === opt.value;
                      return (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onUpdateGenero(opt.value); }}
                          className={`h-7 w-10 cursor-pointer rounded-md border-2 border-[#1a1a1a] text-[10px] font-bold transition-all duration-150
                            ${active
                              ? 'bg-[#1a1a1a] text-[#fff8e7] ring-2 ring-[#1a1a1a] ring-offset-1'
                              : 'bg-[#F5F0E1] text-[#1a1a1a] opacity-70 hover:opacity-100'
                            }`}
                          aria-label={`Género ${opt.label}`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-[#6B5C4A]">@{candidate.instagram ?? 'sin_instagram'}</p>
                <p className="truncate text-xs text-[#6B5C4A]">{candidate.contacto ?? candidate.telefono ?? 'sin contacto'}</p>
                <p className="text-[10px] text-[#6B5C4A]">Estado: {candidate.estado ?? 'sin_estado'}</p>
                {hasPendingEdit && (
                  <span className="mt-1 inline-block rounded-full bg-[#f59e0b]/25 px-2 py-0.5 text-[10px] font-bold text-[#7c2d12]">
                    Editado
                  </span>
                )}
              </div>

              <div className="flex flex-col items-center gap-1">
                <span className="text-[10px] text-[#6B5C4A]">LineUp</span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); if (!selected && !canSelect) return; onToggleSelected(); }}
                  disabled={!selected && !canSelect}
                  className={`flex h-8 w-8 cursor-pointer items-center justify-center rounded-md border-[3px] border-[#1a1a1a] transition-all duration-150 ${selected ? 'bg-[#22C55E] text-[#fff8e7]' : 'bg-[#fff8e7] text-transparent'} ${!selected && !canSelect ? 'cursor-not-allowed opacity-40' : 'hover:scale-110'}`}
                  aria-label={selected ? 'Quitar del LineUp' : 'Añadir al LineUp'}
                >
                  <CheckIcon />
                </button>
              </div>
            </div>
          </div>
        )}
      </article>
    </div>
  );
}
