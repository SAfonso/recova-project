import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Mock supabase before importing the hook
const mockSelect = vi.fn();
const mockEq = vi.fn();
const mockOrder = vi.fn();
const mockLimit = vi.fn();
const mockSingle = vi.fn();
const mockFrom = vi.fn();
const mockSchema = vi.fn();
const mockRpc = vi.fn();

vi.mock('../supabaseClient', () => ({
  supabase: {
    from: (...args) => mockFrom(...args),
    schema: (...args) => mockSchema(...args),
    rpc: (...args) => mockRpc(...args),
  },
}));

// Default chain builders
function chainBuilder(resolveWith) {
  const chain = {
    select: vi.fn(() => chain),
    eq: vi.fn(() => chain),
    order: vi.fn(() => chain),
    limit: vi.fn(() => Promise.resolve(resolveWith)),
    single: vi.fn(() => Promise.resolve(resolveWith)),
    then: (fn) => Promise.resolve(resolveWith).then(fn),
  };
  // Make the chain itself thenable for await
  chain[Symbol.for('jest.asymmetricMatch')] = undefined;
  return chain;
}

function setupMocks(rows = [], slotsData = []) {
  // lineup_candidates query chain
  const candidatesChain = chainBuilder({ data: rows, error: null });
  // lineup_slots query chain
  const slotsChain = chainBuilder({ data: slotsData, error: null });
  // open_mics config chain
  const configChain = chainBuilder({ data: { config: {} }, error: null });

  mockFrom.mockImplementation((table) => {
    if (table === 'lineup_candidates') return candidatesChain;
    if (table === 'lineup_slots') return slotsChain;
    if (table === 'open_mics') return configChain;
    return candidatesChain;
  });

  mockSchema.mockImplementation(() => ({
    from: (table) => {
      if (table === 'lineup_slots') return slotsChain;
      if (table === 'open_mics') return configChain;
      return candidatesChain;
    },
    rpc: vi.fn(() => Promise.resolve({ data: null, error: null })),
  }));
}

import { useCandidates } from '../hooks/useCandidates';

describe('useCandidates', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('normalizes rows: unknown genero becomes nb, missing categoria defaults to standard', async () => {
    const rows = [
      { comico_id: 'c1', solicitud_id: 's1', nombre: 'A', genero: 'unknown', categoria: null, estado: 'scorado', score_final: 10, fecha_evento: '2026-03-20' },
    ];
    setupMocks(rows);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.candidates[0].genero).toBe('nb');
    expect(result.current.candidates[0].categoria).toBe('standard');
  });

  it('auto-selects top 5 scored candidates', async () => {
    const rows = Array.from({ length: 7 }, (_, i) => ({
      comico_id: `c${i}`, solicitud_id: `s${i}`, nombre: `Comic ${i}`,
      genero: 'f', categoria: 'standard', estado: 'scorado',
      score_final: 100 - i * 10, fecha_evento: '2026-03-20',
    }));
    setupMocks(rows);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.selectedIds).toHaveLength(5);
    expect(result.current.selectedIds).toEqual(['s0', 's1', 's2', 's3', 's4']);
  });

  it('toggleSelected adds candidate up to cap of 5', async () => {
    const rows = Array.from({ length: 7 }, (_, i) => ({
      comico_id: `c${i}`, solicitud_id: `s${i}`, nombre: `Comic ${i}`,
      genero: 'f', categoria: 'standard', estado: 'scorado',
      score_final: 100 - i * 10, fecha_evento: '2026-03-20',
    }));
    setupMocks(rows);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Already 5 selected, adding 6th should be capped
    act(() => {
      result.current.toggleSelected('s5');
    });
    expect(result.current.selectedIds).toHaveLength(5);
    expect(result.current.selectedIds).not.toContain('s5');
  });

  it('toggleSelected removes already selected candidate', async () => {
    const rows = Array.from({ length: 5 }, (_, i) => ({
      comico_id: `c${i}`, solicitud_id: `s${i}`, nombre: `Comic ${i}`,
      genero: 'f', categoria: 'standard', estado: 'scorado',
      score_final: 100 - i * 10, fecha_evento: '2026-03-20',
    }));
    setupMocks(rows);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.toggleSelected('s0');
    });
    expect(result.current.selectedIds).toHaveLength(4);
    expect(result.current.selectedIds).not.toContain('s0');
  });

  it('detects isValidated from confirmed lineup_slots', async () => {
    const rows = [
      { comico_id: 'c1', solicitud_id: 's1', nombre: 'A', genero: 'f', categoria: 'standard', estado: 'scorado', score_final: 10, fecha_evento: '2026-03-20' },
    ];
    setupMocks(rows, [{ id: 'slot-1' }]);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.isValidated).toBe(true);
    expect(localStorage.getItem('validated_om-1')).toBe('1');
  });

  it('selectedCandidates memo filters correctly', async () => {
    const rows = Array.from({ length: 3 }, (_, i) => ({
      comico_id: `c${i}`, solicitud_id: `s${i}`, nombre: `Comic ${i}`,
      genero: 'f', categoria: 'standard', estado: 'scorado',
      score_final: 100 - i * 10, fecha_evento: '2026-03-20',
    }));
    setupMocks(rows);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.selectedCandidates).toHaveLength(3);
    expect(result.current.selectedCandidates.map((c) => c.row_key)).toEqual(['s0', 's1', 's2']);
  });

  it('isLastMinuteMode is false when no eventDate', async () => {
    setupMocks([]);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.isLastMinuteMode).toBe(false);
  });

  it('singleDateMode is true when config has no explicit single_date_priority.enabled=false', async () => {
    // With empty config {}, single_date_priority?.enabled is undefined,
    // and undefined !== false is true — so singleDateMode defaults on
    setupMocks([]);

    const { result } = renderHook(() => useCandidates('om-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.singleDateMode).toBe(true);
  });
});
