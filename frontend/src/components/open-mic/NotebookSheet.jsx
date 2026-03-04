import { ScoringConfigurator } from '../ScoringConfigurator';

const TABS = [
  { value: 'lineup', label: 'Line Up', bg: 'bg-[#fff8e7]', activeText: 'text-[#1a1a1a]' },
  { value: 'gold', label: 'Gold', bg: 'bg-[#D4A017]', activeText: 'text-[#1a1a1a]' },
  { value: 'priority', label: 'Priority', bg: 'bg-[#A0A0A0]', activeText: 'text-[#fff8e7]' },
  { value: 'restricted', label: 'Restricted', bg: 'bg-[#DC2626]', activeText: 'text-[#fff8e7]' },
  { value: 'config', label: 'Config', bg: 'bg-[#4B5563]', activeText: 'text-[#fff8e7]' },
];

function getFilteredCandidates({ activeTab, candidates, selectedCandidates, getDraft }) {
  if (activeTab === 'lineup') {
    return selectedCandidates;
  }

  return candidates.filter((candidate) => getDraft(candidate).categoria === activeTab);
}

export function NotebookSheet({
  activeTab,
  onTabChange,
  candidates,
  selectedCandidates,
  getDraft,
  onOpenExpanded,
  openMicId,
}) {
  const isConfig = activeTab === 'config';
  const filteredCandidates = isConfig
    ? []
    : getFilteredCandidates({ activeTab, candidates, selectedCandidates, getDraft });

  return (
    <section className="relative mx-auto w-full max-w-lg lg:max-w-4xl">
      <div className="flex flex-wrap items-end gap-1">
        {TABS.map((tab, index) => {
          const isActive = activeTab === tab.value;
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => onTabChange(tab.value)}
              className={`relative z-10 rounded-t-lg border-[3px] border-b-0 border-[#1a1a1a] px-3 py-1 text-sm font-bold transition-all sm:px-4 sm:text-base ${
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

      <div className="notebook-lines relative overflow-hidden rounded-b-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] px-4 pb-14 pt-5 shadow-[6px_6px_0px_rgba(0,0,0,0.3)]">
        <div className="absolute bottom-0 left-10 top-0 w-[2px] bg-[#DC2626]/30" aria-hidden="true" />

        <div className="absolute bottom-0 left-2 top-0 flex flex-col justify-evenly" aria-hidden="true">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={index} className="h-3 w-3 rounded-full border-2 border-[#C8B89A] bg-[#DC2626]" />
          ))}
        </div>

        <div className="mb-3 ml-8 border-b-2 border-dashed border-[#C8B89A] pb-1">
          <h3 className="font-['Bangers'] text-2xl tracking-wide text-[#1a1a1a]">{TABS.find((tab) => tab.value === activeTab)?.label}</h3>
        </div>

        <div className="ml-8 min-h-[240px]">
          {isConfig ? (
            <ScoringConfigurator openMicId={openMicId} />
          ) : filteredCandidates.length === 0 ? (
            <p className="pt-4 font-['Patrick_Hand'] text-xl text-[#6B5C4A]/70 italic">No hay comicos para esta vista...</p>
          ) : (
            <ol className="flex flex-col gap-1">
              {filteredCandidates.map((candidate, index) => {
                const draft = getDraft(candidate);
                return (
                  <li key={candidate.row_key} className="flex items-center gap-2 py-[7px] text-[#1a1a1a]">
                    <span className="w-5 text-right text-xs text-[#6B5C4A]">{index + 1}.</span>
                    <span className="truncate font-['Patrick_Hand'] text-xl">{candidate.nombre ?? candidate.instagram ?? 'Sin nombre'}</span>
                    <span
                      className={`ml-auto h-2.5 w-2.5 shrink-0 rounded-full border border-[#1a1a1a]/20 ${
                        draft.categoria === 'gold'
                          ? 'bg-[#D4A017]'
                          : draft.categoria === 'priority'
                            ? 'bg-[#A0A0A0]'
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

        {!isConfig && (
          <div className="absolute bottom-3 left-3 right-3 flex justify-center">
            <button
              type="button"
              onClick={onOpenExpanded}
              className="comic-shadow flex items-center gap-1 rounded-md border-2 border-[#1a1a1a] bg-[#C8B89A] px-4 py-1.5 font-bold text-[#1a1a1a] transition-all hover:bg-[#B8A88A]"
              aria-label="Abrir vista ampliada"
            >
              <span className="text-lg leading-none">...</span>
              <span>Editar</span>
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
