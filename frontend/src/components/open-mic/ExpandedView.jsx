import { ComicCard } from './ComicCard';

export function ExpandedView({
  candidates,
  selectedIds,
  activeId,
  onClose,
  onCardExpand,
  onToggleSelected,
  onUpdateCategory,
  getDraft,
  hasPendingEdit,
}) {
  const selectedCount = selectedIds.length;
  const canSelect = selectedCount < 5;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1a1a1a]/60 p-4 backdrop-blur-sm">
      <div className="notebook-lines relative flex h-[92vh] w-full max-w-md flex-col overflow-hidden rounded-lg border-[3px] border-[#1a1a1a] bg-[#fff8e7] shadow-[8px_8px_0px_rgba(0,0,0,0.3)] lg:max-w-3xl">
        <div className="absolute bottom-0 left-10 top-0 w-[2px] bg-[#DC2626]/30" aria-hidden="true" />

        <div className="absolute bottom-0 left-2 top-0 z-10 flex flex-col justify-evenly" aria-hidden="true">
          {Array.from({ length: 16 }).map((_, index) => (
            <div key={index} className="h-3 w-3 rounded-full border-2 border-[#C8B89A] bg-[#1a1a1a]/60" />
          ))}
        </div>

        <div className="relative z-10 flex items-center justify-between border-b-[3px] border-[#1a1a1a] bg-[#F5F0E1] px-4 py-3 pl-14">
          <h2 className="font-['Bangers'] text-xl tracking-wide text-[#1a1a1a]">Edicion completa</h2>
          <span
            className={`rounded-full border-2 border-[#1a1a1a] px-3 py-0.5 text-sm font-bold ${
              selectedCount === 5 ? 'bg-[#22C55E] text-[#fff8e7]' : 'bg-[#DC2626] text-[#fff8e7]'
            }`}
          >
            {selectedCount}/5
          </span>
        </div>

        <div className="cartoon-scroll flex-1 overflow-y-auto pb-20 pl-14 pr-4 pt-3">
          <div className="flex flex-col gap-2.5">
            {candidates.map((candidate) => (
              <ComicCard
                key={candidate.row_key}
                candidate={candidate}
                draft={getDraft(candidate)}
                selected={selectedIds.includes(candidate.row_key)}
                expanded={activeId === candidate.row_key}
                canSelect={canSelect}
                onExpand={() => onCardExpand(candidate.row_key)}
                onToggleSelected={() => onToggleSelected(candidate.row_key)}
                onUpdateCategory={(value) => onUpdateCategory(candidate.row_key, value)}
                hasPendingEdit={hasPendingEdit(candidate)}
              />
            ))}
          </div>
        </div>

        <div className="absolute bottom-4 right-4 z-20">
          <button
            type="button"
            onClick={onClose}
            className="comic-shadow flex h-14 w-14 items-center justify-center rounded-full border-[3px] border-[#1a1a1a] bg-[#7F1D1D] text-2xl text-[#fff8e7] transition-all hover:bg-[#991B1B]"
            aria-label="Cerrar vista de edicion"
          >
            ✓
          </button>
        </div>
      </div>
    </div>
  );
}
