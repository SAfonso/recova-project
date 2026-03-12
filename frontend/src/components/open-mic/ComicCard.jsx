const CheckIcon = () => (
  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const CATEGORY_BUTTONS = [
  { value: 'gold',       label: 'Gold',       className: 'bg-[#C4905A] text-[#0D0D0D]' },
  { value: 'priority',   label: 'Priority',   className: 'bg-[#3D5F6C] text-[#F5F5F0]' },
  { value: 'restricted', label: 'Restricted', className: 'bg-[#0D0D0D] text-[#F5F5F0]' },
];

const GENDER_OPTIONS = [
  { value: 'm',  label: 'M' },
  { value: 'f',  label: 'F' },
  { value: 'nb', label: 'NB' },
];

const CARD_BORDER = {
  gold:       'border-[#C4905A] bg-[#EDE8DC]',
  priority:   'border-[#3D5F6C] bg-[#EDE8DC]',
  restricted: 'restricted-overlay border-[#A34A42] bg-[#FDF0F0]',
  default:    'border-[#0D0D0D] bg-[#EDE8DC]',
};

const DROP_SHADOW = {
  gold:       'drop-shadow(4px 4px 0px #000000)',
  priority:   'drop-shadow(4px 4px 0px #000000)',
  restricted: 'drop-shadow(4px 4px 0px #000000)',
  default:    'drop-shadow(4px 4px 0px #000000)',
};

function categoryBadge(category) {
  if (category === 'gold')       return <span className="rounded-none border-[2px] border-[#0D0D0D] bg-[#C4905A] px-2.5 py-0.5 text-xs font-bold uppercase text-[#0D0D0D]">GOLD</span>;
  if (category === 'priority')   return <span className="rounded-none border-[2px] border-[#0D0D0D] bg-[#3D5F6C] px-2.5 py-0.5 text-xs font-bold uppercase text-[#F5F5F0]">PRIO</span>;
  if (category === 'restricted') return <span className="rounded-none border-[2px] border-[#0D0D0D] bg-[#0D0D0D] px-2.5 py-0.5 text-xs font-bold uppercase text-[#F5F5F0]">REST</span>;
  return <span className="rounded-none border-[2px] border-[#0D0D0D]/30 bg-[#EDE8DC] px-2.5 py-0.5 text-xs font-bold uppercase text-[#0D0D0D]/60">NEW</span>;
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
          className="flex w-full cursor-pointer items-center gap-3 px-4 py-3.5 text-left"
          aria-expanded={expanded}
        >
          <span className="relative z-10 flex-1 truncate text-lg font-bold text-[#1a1a1a]">
            {candidate.nombre ?? candidate.instagram ?? 'Sin nombre'}
          </span>
          <span className="relative z-10">{categoryBadge(draft.categoria)}</span>
        </button>

        {expanded && (
          <div className="relative z-10 border-t-2 border-dashed border-[#1a1a1a]/20 px-3 pb-4 pt-3">
            <div className="flex flex-col gap-4">

              {/* Fila 1: controles + botón lineup */}
              <div className="flex items-start gap-3">
                <div className="flex flex-1 flex-col gap-2.5">
                  {/* Categoría */}
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-[#6B5C4A]">Categoría <span className="text-[#9ca3af]">(clic activo = quitar)</span></span>
                    <div className="flex gap-1.5">
                      {CATEGORY_BUTTONS.map((btn) => {
                        const active = draft.categoria === btn.value;
                        return (
                          <button
                            key={btn.value}
                            type="button"
                            onClick={(e) => { e.stopPropagation(); handleCategoryClick(btn.value); }}
                            className={`h-8 min-w-16 cursor-pointer rounded-none border-[3px] border-[#0D0D0D] px-2 text-xs font-bold transition-all duration-150 ${btn.className} ${active ? 'ring-2 ring-[#1a1a1a] ring-offset-1' : 'opacity-70 hover:opacity-100'}`}
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
                    <span className="text-xs text-[#6B5C4A]">Género</span>
                    <div className="flex gap-1.5">
                      {GENDER_OPTIONS.map((opt) => {
                        const active = draft.genero === opt.value;
                        return (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onUpdateGenero(opt.value); }}
                            className={`h-8 w-12 cursor-pointer rounded-none border-[3px] border-[#0D0D0D] text-xs font-bold transition-all duration-150
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

                <div className="flex flex-col items-center gap-1">
                  <span className="text-xs text-[#6B5C4A]">LineUp</span>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); if (!selected && !canSelect) return; onToggleSelected(); }}
                    disabled={!selected && !canSelect}
                    className={`flex h-8 w-8 cursor-pointer items-center justify-center rounded-none border-[3px] border-[#0D0D0D] transition-all duration-150 ${selected ? 'bg-[#5E7260] text-[#F5F5F0]' : 'bg-[#EDE8DC] text-transparent'} ${!selected && !canSelect ? 'cursor-not-allowed opacity-40' : ''}`}
                    aria-label={selected ? 'Quitar del LineUp' : 'Añadir al LineUp'}
                  >
                    <CheckIcon />
                  </button>
                </div>
              </div>

              {/* Fila 2: info contacto — full width, centrado, fuente grande */}
              <div className="border-t border-dashed border-[#1a1a1a]/20 pt-3 text-center">
                <p className="text-base font-bold tracking-wide text-[#3D2A1A]">
                  @{candidate.instagram ?? 'sin_instagram'}
                </p>
                <p className="mt-1 text-base font-semibold text-[#3D2A1A]">
                  {candidate.contacto ?? candidate.telefono ?? 'sin contacto'}
                </p>
                <p className="mt-1 text-sm font-medium uppercase tracking-widest text-[#6B5C4A]">
                  {candidate.estado ?? 'sin_estado'}
                </p>
                {hasPendingEdit && (
                  <span className="mt-2 inline-block rounded-full bg-[#f59e0b]/25 px-3 py-0.5 text-xs font-bold text-[#7c2d12]">
                    Editado
                  </span>
                )}
              </div>

            </div>
          </div>
        )}
      </article>
    </div>
  );
}
