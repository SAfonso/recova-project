import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useEdits, CATEGORY_OPTIONS } from '../hooks/useEdits';

const makeCandidates = (overrides = []) => [
  { row_key: 'sol-1', categoria: 'standard', genero: 'f', ...overrides[0] },
  { row_key: 'sol-2', categoria: 'gold', genero: 'm', ...overrides[1] },
  { row_key: 'sol-3', categoria: 'priority', genero: 'nb', ...overrides[2] },
];

describe('useEdits', () => {
  it('getDraft returns candidate defaults when no edits exist', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, null, () => {}));

    const draft = result.current.getDraft(candidates[0]);
    expect(draft).toEqual({ categoria: 'standard', genero: 'f' });
  });

  it('getDraft returns edited values when edit exists', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, 'sol-1', () => {}));

    act(() => {
      result.current.handleGeneroUpdate('sol-1', 'm');
    });

    const draft = result.current.getDraft(candidates[0]);
    expect(draft.genero).toBe('m');
  });

  it('hasPendingEdit returns false when no edits', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, null, () => {}));

    expect(result.current.hasPendingEdit(candidates[0])).toBe(false);
  });

  it('hasPendingEdit returns true when edit differs from candidate', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, 'sol-1', () => {}));

    act(() => {
      result.current.handleGeneroUpdate('sol-1', 'm');
    });

    expect(result.current.hasPendingEdit(candidates[0])).toBe(true);
  });

  it('hasPendingEdit returns false when edit matches candidate values', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, 'sol-1', () => {}));

    // Edit to same value as original
    act(() => {
      result.current.handleGeneroUpdate('sol-1', 'f');
    });

    expect(result.current.hasPendingEdit(candidates[0])).toBe(false);
  });

  it('handleCategoryUpdate rejects invalid category', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, 'sol-1', () => {}));

    act(() => {
      result.current.handleCategoryUpdate('sol-1', 'invalid_cat');
    });

    const draft = result.current.getDraft(candidates[0]);
    expect(draft.categoria).toBe('standard');
  });

  it('handleCategoryUpdate sets activeId when different from candidateId', () => {
    const candidates = makeCandidates();
    const setActiveId = vi.fn();
    const { result } = renderHook(() => useEdits(candidates, 'sol-2', setActiveId));

    act(() => {
      result.current.handleCategoryUpdate('sol-1', 'gold');
    });

    expect(setActiveId).toHaveBeenCalledWith('sol-1');
  });

  it('handleCategoryUpdate updates draft when activeId matches', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, 'sol-1', () => {}));

    act(() => {
      result.current.handleCategoryUpdate('sol-1', 'gold');
    });

    const draft = result.current.getDraft(candidates[0]);
    expect(draft.categoria).toBe('gold');
  });

  it('clearEdits resets all edits', () => {
    const candidates = makeCandidates();
    const { result } = renderHook(() => useEdits(candidates, 'sol-1', () => {}));

    act(() => {
      result.current.handleGeneroUpdate('sol-1', 'm');
      result.current.handleGeneroUpdate('sol-2', 'f');
    });

    expect(result.current.hasPendingEdit(candidates[0])).toBe(true);

    act(() => {
      result.current.clearEdits();
    });

    expect(result.current.hasPendingEdit(candidates[0])).toBe(false);
    expect(result.current.hasPendingEdit(candidates[1])).toBe(false);
  });

  it('CATEGORY_OPTIONS has expected values', () => {
    const values = CATEGORY_OPTIONS.map((o) => o.value);
    expect(values).toEqual(['gold', 'priority', 'restricted', 'standard']);
  });
});
