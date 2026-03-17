import { useMemo, useState } from 'react';
import { useCandidates } from './hooks/useCandidates';
import { useEdits } from './hooks/useEdits';
import { useValidation } from './hooks/useValidation';
import { CambiarButton } from './components/open-mic/CambiarButton';
import { CambiarConfirmModal } from './components/open-mic/CambiarConfirmModal';
import { ExpandedView } from './components/open-mic/ExpandedView';
import { Header } from './components/open-mic/Header';
import { LoadingSkeleton } from './components/open-mic/LoadingSkeleton';
import { NotebookSheet } from './components/open-mic/NotebookSheet';
import { RecoveryNotes } from './components/open-mic/RecoveryNotes';
import { ValidadoStamp } from './components/open-mic/ValidadoStamp';
import { ValidateButton } from './components/open-mic/ValidateButton';

function App({ session, openMicId, onBack }) {
  const [activeId, setActiveId] = useState(null);
  const [activeTab, setActiveTab] = useState('lineup');
  const [isExpanded, setIsExpanded] = useState(false);
  const [recoveryNotes, setRecoveryNotes] = useState('');

  const {
    candidates, setCandidates, selectedIds, loading,
    error, setError, eventDate, setEventDate,
    isValidated, setIsValidated, openMicConfig,
    toggleSelected, selectedCandidates, isLastMinuteMode, singleDateMode,
  } = useCandidates(openMicId);

  const {
    getDraft, hasPendingEdit, handleGeneroUpdate, handleCategoryUpdate, clearEdits,
  } = useEdits(candidates, activeId, setActiveId);

  const {
    saving, showCambiarConfirm, setShowCambiarConfirm,
    validateLineup, handleCambiarAccept,
  } = useValidation({
    openMicId, eventDate, selectedIds, selectedCandidates,
    getDraft, recoveryNotes,
    setError, setCandidates, setIsValidated, clearEdits,
  });

  const activeCandidate = useMemo(
    () => candidates.find((candidate) => candidate.row_key === activeId),
    [candidates, activeId],
  );

  const openExpanded = () => {
    setIsExpanded(true);
    if (!activeId && candidates.length > 0) {
      setActiveId(candidates[0].row_key);
    }
  };

  return (
    <main data-tutorial="lineup-view" className="paint-bg min-h-screen px-4 pb-8 md:px-8">
      <div className="mx-auto flex max-w-xl flex-col gap-4 md:max-w-3xl lg:max-w-5xl xl:max-w-6xl">
        <Header
          eventDate={eventDate}
          onEventDateChange={setEventDate}
          selectedCount={selectedIds.length}
          hostEmail={session?.user?.email}
          onBack={onBack}
        />

        {error && (
          <p className="rounded-md border-2 border-[#7f1d1d] bg-[#fee2e2] p-3 text-sm text-[#7f1d1d]">
            {error}
          </p>
        )}

        {loading ? (
          <LoadingSkeleton />
        ) : (
          <NotebookSheet
            activeTab={activeTab}
            onTabChange={setActiveTab}
            candidates={candidates}
            selectedCandidates={selectedCandidates}
            getDraft={getDraft}
            onOpenExpanded={openExpanded}
          />
        )}

        <RecoveryNotes value={recoveryNotes} onChange={setRecoveryNotes} />

        {isValidated && <ValidadoStamp />}

        <div className="flex justify-center gap-4 pt-2" data-tutorial="validate-button">
          <ValidateButton
            disabled={saving || selectedIds.length !== 5 || isValidated}
            saving={saving}
            isValidated={isValidated}
            onClick={validateLineup}
          />
          {isValidated && (
            <CambiarButton onClick={() => setShowCambiarConfirm(true)} />
          )}
        </div>

        <p className="text-center text-sm font-bold text-[#fff8e7]">
          {selectedIds.length === 5 ? 'LineUp completo para validar' : 'Selecciona exactamente 5 cómicos'}
        </p>

        {showCambiarConfirm && (
          <CambiarConfirmModal
            onAccept={handleCambiarAccept}
            onCancel={() => setShowCambiarConfirm(false)}
          />
        )}
      </div>

      {isExpanded && (
        <ExpandedView
          candidates={candidates}
          selectedIds={selectedIds}
          activeId={activeId}
          onClose={() => setIsExpanded(false)}
          onCardExpand={setActiveId}
          onToggleSelected={toggleSelected}
          onUpdateCategory={handleCategoryUpdate}
          onUpdateGenero={handleGeneroUpdate}
          getDraft={getDraft}
          hasPendingEdit={hasPendingEdit}
          isLastMinuteMode={isLastMinuteMode}
          singleDateMode={singleDateMode}
        />
      )}
    </main>
  );
}

export default App;
