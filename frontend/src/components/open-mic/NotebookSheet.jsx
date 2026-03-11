const TABS = [
  { value: 'lineup',     label: 'Line Up',    bg: 'bg-[#EDE8DC]', activeText: 'text-[#0D0D0D]' },
  { value: 'gold',       label: 'Gold',       bg: 'bg-[#C4905A]', activeText: 'text-[#0D0D0D]' },
  { value: 'priority',   label: 'Priority',   bg: 'bg-[#3D5F6C]', activeText: 'text-[#F5F5F0]' },
  { value: 'restricted', label: 'Restricted', bg: 'bg-[#0D0D0D]', activeText: 'text-[#F5F5F0]' },
];

function getFilteredCandidates({ activeTab, candidates, selectedCandidates, getDraft }) {
  if (activeTab === 'lineup') return selectedCandidates;
  return candidates.filter((c) => getDraft(c).categoria === activeTab);
}

function BindingHole() {
  return (
    <div
      className="h-4 w-4 rounded-full"
      style={{
        background: 'radial-gradient(circle at 38% 35%, rgba(255,255,255,0.5) 0%, rgba(220,38,38,0.85) 55%, rgba(150,20,20,0.95) 100%)',
        boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.45), 0 1px 2px rgba(0,0,0,0.2)',
        border: '1.5px solid rgba(0,0,0,0.25)',
      }}
      aria-hidden="true"
    />
  );
}

export function NotebookSheet({
  activeTab, onTabChange, candidates, selectedCandidates,
  getDraft, onOpenExpanded,
}) {
  const filteredCandidates = getFilteredCandidates({ activeTab, candidates, selectedCandidates, getDraft });

  return (
    <section className="relative mx-auto w-full max-w-lg lg:max-w-4xl">

      {/* Pestañas */}
      <div className="flex flex-wrap items-end gap-1">
        {TABS.map((tab, index) => {
          const isActive = activeTab === tab.value;
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => onTabChange(tab.value)}
              className={`relative z-10 cursor-pointer rounded-none border-[3px] border-b-0 border-[#0D0D0D] px-3 py-1 text-sm font-bold transition-all duration-150 sm:px-4 sm:text-base ${
                isActive
                  ? `${tab.bg} ${tab.activeText}`
                  : 'bg-[#EDE8DC] text-[#0D0D0D]/50 hover:bg-[#E4DDD0] hover:text-[#0D0D0D]'
              } ${index === 0 ? 'mr-auto' : ''}`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Hoja rugosa con drop-shadow */}
      <div className="paper-drop rotate-[0.9deg]">
        <div className="scrapbook-panel pin-corner notebook-lines paper-rough paper-note relative overflow-hidden px-4 pb-14 pt-5">

          {/* Franja encuadernación izquierda */}
          <div
            className="absolute bottom-0 left-0 top-0 w-10"
            style={{
              background: 'linear-gradient(90deg, rgba(200,184,154,0.22) 0%, rgba(200,184,154,0.06) 80%, transparent 100%)',
              borderRight: '1px solid rgba(200,184,154,0.35)',
            }}
            aria-hidden="true"
          />

          {/* Línea de margen roja */}
          <div
            className="absolute bottom-0 left-10 top-0 w-px"
            style={{ background: 'rgba(220,38,38,0.32)' }}
            aria-hidden="true"
          />

          {/* Agujeros de encuadernación */}
          <div className="absolute bottom-0 left-2 top-0 z-10 flex flex-col justify-evenly" aria-hidden="true">
            {Array.from({ length: 8 }).map((_, i) => <BindingHole key={i} />)}
          </div>

          {/* Cabecera de sección */}
          <div className="mb-3 ml-10 border-b border-dashed border-[#C8B89A]/60 pb-1">
            <h3 className="font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a]">
              {TABS.find((t) => t.value === activeTab)?.label}
            </h3>
          </div>

          {/* Contenido */}
          <div className="ml-10 min-h-[240px]">
            {filteredCandidates.length === 0 ? (
              <p className="pt-4 font-['Patrick_Hand'] text-xl italic text-[#6B5C4A]/60">
                No hay cómicos para esta vista...
              </p>
            ) : (
              <ol className="flex flex-col">
                {filteredCandidates.map((candidate, index) => {
                  const draft = getDraft(candidate);
                  const stagger = index < 6 ? `stagger-${index + 1}` : 'stagger-6';
                  return (
                    <li key={candidate.row_key} className={`animate-slide-up tilt-soft ${stagger} paper-strip mb-2 flex items-center gap-2 px-2 py-[7px] text-[#0D0D0D] last:border-0`}>
                      <span className="w-5 shrink-0 text-right text-xs font-bold text-[#0D0D0D]/40">{index + 1}</span>
                      <span className="truncate font-['Patrick_Hand'] text-xl font-bold md:text-2xl">{candidate.nombre ?? candidate.instagram ?? 'Sin nombre'}</span>
                      <span
                        className={`ml-auto rounded-none border-[2px] border-[#0D0D0D] px-2 py-0.5 text-xs font-bold uppercase tracking-wide ${
                          draft.categoria === 'gold'       ? 'bg-[#C4905A] text-[#0D0D0D]'
                          : draft.categoria === 'priority' ? 'bg-[#3D5F6C] text-[#F5F5F0]'
                          : draft.categoria === 'restricted' ? 'bg-[#0D0D0D] text-[#F5F5F0]'
                          : 'bg-[#EDE8DC] text-[#0D0D0D]'
                        }`}
                        aria-label={`Categoria ${draft.categoria}`}
                      >{draft.categoria ?? 'new'}</span>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>

          {/* Botón editar */}
          <div className="absolute bottom-3 left-3 right-3 flex justify-center">
            <button
              type="button"
              onClick={onOpenExpanded}
              className="comic-shadow flex cursor-pointer items-center gap-2 rounded-none border-[3px] border-[#0D0D0D] bg-[#3D5F6C] px-4 py-1.5 font-bold text-[#F5F5F0] transition-all duration-150 hover:bg-[#2D4A57]"
              aria-label="Abrir vista ampliada"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              <span>Editar</span>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
