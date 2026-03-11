import { ComicCard } from './ComicCard';

function BindingHole() {
  return (
    <div
      className="h-4 w-4 rounded-full"
      style={{
        background: 'radial-gradient(circle at 38% 35%, rgba(255,255,255,0.4) 0%, rgba(74,109,124,0.85) 55%, rgba(40,80,95,0.95) 100%)',
        boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.35), 0 1px 0px rgba(0,0,0,0.5)',
        border: '1.5px solid rgba(0,0,0,0.3)',
      }}
      aria-hidden="true"
    />
  );
}

const XIcon = () => (
  <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

export function ExpandedView({
  candidates,
  selectedIds,
  activeId,
  onClose,
  onCardExpand,
  onToggleSelected,
  onUpdateCategory,
  onUpdateGenero,
  getDraft,
  hasPendingEdit,
}) {
  const selectedCount = selectedIds.length;
  const canSelect = selectedCount < 5;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#1a1a1a]/60 p-4 backdrop-blur-sm">
      <div className="paper-drop paper-tape h-[92vh] w-full max-w-md lg:max-w-3xl">
      <div className="notebook-lines paper-rough paper-note relative flex h-full w-full flex-col overflow-hidden border-[3px] border-[#1a1a1a] bg-[#fffef5]">
        {/* Franja encuadernación */}
        <div
          className="absolute bottom-0 left-0 top-0 w-10"
          style={{
            background: 'linear-gradient(90deg, rgba(74,109,124,0.12) 0%, rgba(74,109,124,0.05) 80%, transparent 100%)',
            borderRight: '1px solid rgba(74,109,124,0.25)',
          }}
          aria-hidden="true"
        />
        {/* Línea margen petróleo */}
        <div
          className="absolute bottom-0 left-10 top-0 w-px"
          style={{ background: 'rgba(74,109,124,0.4)' }}
          aria-hidden="true"
        />

        <div className="absolute bottom-0 left-2 top-0 z-10 flex flex-col justify-evenly" aria-hidden="true">
          {Array.from({ length: 16 }).map((_, index) => (
            <BindingHole key={index} />
          ))}
        </div>

        <div className="relative z-10 flex items-center justify-between border-b-[3px] border-[#0D0D0D] bg-[#EDE8DC] px-4 py-3 pl-14">
          <h2 className="font-['Bangers'] text-xl tracking-wide text-[#0D0D0D]">Edicion completa</h2>
          <span
            className={`rounded-none border-[3px] border-[#0D0D0D] px-3 py-0.5 text-sm font-bold ${
              selectedCount === 5 ? 'bg-[#5E7260] text-[#F5F5F0]' : 'bg-[#3D5F6C] text-[#F5F5F0]'
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
                onUpdateGenero={(value) => onUpdateGenero(candidate.row_key, value)}
                hasPendingEdit={hasPendingEdit(candidate)}
              />
            ))}
          </div>
        </div>

        <div className="absolute bottom-4 right-4 z-20">
          <button
            type="button"
            onClick={onClose}
            className="comic-shadow flex h-14 w-14 cursor-pointer items-center justify-center rounded-none border-[3px] border-[#0D0D0D] bg-[#3D5F6C] text-[#F5F5F0] transition-all duration-150 hover:bg-[#2D4A57]"
            aria-label="Cerrar vista de edicion"
          >
            <XIcon />
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}
