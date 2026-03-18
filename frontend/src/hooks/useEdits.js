import { useState, useCallback } from 'react';

export const CATEGORY_OPTIONS = [
  { value: 'gold', label: 'Gold' },
  { value: 'priority', label: 'Preferred' },
  { value: 'restricted', label: 'Restricted' },
  { value: 'standard', label: 'Standard' },
];

export function useEdits(candidates, activeId, setActiveId) {
  const [edits, setEdits] = useState({});

  const getDraft = useCallback(
    (candidate) => {
      const existing = edits[candidate.row_key];
      if (existing) {
        return existing;
      }
      return { categoria: candidate.categoria, genero: candidate.genero };
    },
    [edits],
  );

  const hasPendingEdit = useCallback(
    (candidate) => {
      const draft = edits[candidate.row_key];
      return !!draft && (draft.categoria !== candidate.categoria || draft.genero !== candidate.genero);
    },
    [edits],
  );

  const updateDraft = useCallback(
    (field, value) => {
      const activeCandidate = candidates.find((c) => c.row_key === activeId);
      if (!activeCandidate) return;

      setEdits((previous) => ({
        ...previous,
        [activeCandidate.row_key]: {
          ...getDraft(activeCandidate),
          [field]: value,
        },
      }));
    },
    [candidates, activeId, getDraft],
  );

  const handleGeneroUpdate = useCallback(
    (candidateId, genero) => {
      const targetCandidate = candidates.find((c) => c.row_key === candidateId);
      if (!targetCandidate) return;
      setEdits((previous) => ({
        ...previous,
        [candidateId]: {
          ...getDraft(targetCandidate),
          genero,
        },
      }));
    },
    [candidates, getDraft],
  );

  const handleCategoryUpdate = useCallback(
    (candidateId, category) => {
      const targetCandidate = candidates.find((c) => c.row_key === candidateId);
      if (!targetCandidate) return;

      if (activeId !== candidateId) {
        setActiveId(candidateId);
        setEdits((previous) => ({
          ...previous,
          [candidateId]: {
            ...getDraft(targetCandidate),
            categoria: category,
          },
        }));
        return;
      }

      if (!CATEGORY_OPTIONS.some((option) => option.value === category)) {
        return;
      }

      updateDraft('categoria', category);
    },
    [candidates, activeId, setActiveId, getDraft, updateDraft],
  );

  const clearEdits = useCallback(() => setEdits({}), []);

  return {
    getDraft,
    hasPendingEdit,
    updateDraft,
    handleGeneroUpdate,
    handleCategoryUpdate,
    clearEdits,
  };
}
