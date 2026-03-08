const TABS = [
  { value: 'lineup',     label: 'Line Up',    bg: 'bg-[#fff8e7]', activeText: 'text-[#1a1a1a]' },
  { value: 'gold',       label: 'Gold',       bg: 'bg-[#D4A017]', activeText: 'text-[#1a1a1a]' },
  { value: 'priority',   label: 'Priority',   bg: 'bg-[#A0A0A0]', activeText: 'text-[#fff8e7]' },
  { value: 'restricted', label: 'Restricted', bg: 'bg-[#DC2626]', activeText: 'text-[#fff8e7]' },
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
              className={`relative z-10 cursor-pointer rounded-t-lg border-[3px] border-b-0 border-[#1a1a1a] px-3 py-1 text-sm font-bold transition-all duration-150 sm:px-4 sm:text-base ${
                isActive
                  ? `${tab.bg} ${tab.activeText}`
                  : 'bg-[#C8B89A] text-[#1a1a1a]/60 hover:bg-[#D8C8AA]'
              } ${index === 0 ? 'mr-auto' : ''}`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Hoja rugosa con drop-shadow */}
      <div className="paper-drop">
        <div className="notebook-lines paper-rough paper-note relative overflow-hidden border-[3px] border-[#1a1a1a] bg-[#fffef5] px-4 pb-14 pt-5">

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
                    <li key={candidate.row_key} className={`animate-slide-up ${stagger} flex items-center gap-2 py-[6px] text-[#1a1a1a]`}>
                      <span className="w-5 shrink-0 text-right text-xs text-[#9ca3af]">{index + 1}.</span>
                      <span className="truncate font-['Patrick_Hand'] text-xl">{candidate.nombre ?? candidate.instagram ?? 'Sin nombre'}</span>
                      <span
                        className={`ml-auto h-2.5 w-2.5 shrink-0 rounded-full border border-[#1a1a1a]/20 ${
                          draft.categoria === 'gold' ? 'bg-[#D4A017]'
                          : draft.categoria === 'priority' ? 'bg-[#A0A0A0]'
                          : 'bg-[#DC2626]'
                        }`}
                        aria-label={`Categoria ${draft.categoria}`}
                      />
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
              className="comic-shadow flex cursor-pointer items-center gap-2 rounded-md border-2 border-[#1a1a1a] bg-[#C8B89A] px-4 py-1.5 font-bold text-[#1a1a1a] transition-all duration-150 hover:bg-[#B8A88A]"
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
