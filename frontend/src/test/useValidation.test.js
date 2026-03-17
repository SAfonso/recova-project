import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

const mockRpc = vi.fn();

vi.mock('../supabaseClient', () => ({
  supabase: {
    rpc: (...args) => mockRpc(...args),
  },
}));

// Stub import.meta.env
vi.stubEnv('VITE_N8N_WEBHOOK_URL', 'https://n8n.example.com/webhook');

import { useValidation } from '../hooks/useValidation';

function makeConfig(overrides = {}) {
  return {
    openMicId: 'om-1',
    eventDate: '2026-03-20',
    selectedIds: ['s1', 's2', 's3', 's4', 's5'],
    selectedCandidates: Array.from({ length: 5 }, (_, i) => ({
      row_key: `s${i + 1}`, solicitud_id: `s${i + 1}`, comico_id: `c${i + 1}`,
      fecha_evento: '2026-03-20', nombre: `Comic ${i + 1}`, instagram: `@comic${i + 1}`,
      categoria: 'standard', genero: 'f',
    })),
    getDraft: (c) => ({ categoria: c.categoria, genero: c.genero }),
    recoveryNotes: '',
    setError: vi.fn(),
    setCandidates: vi.fn(),
    setIsValidated: vi.fn(),
    clearEdits: vi.fn(),
    ...overrides,
  };
}

describe('useValidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    global.fetch = vi.fn(() => Promise.resolve({ ok: true }));
  });

  it('rejects validation if not exactly 5 selected', async () => {
    const config = makeConfig({ selectedIds: ['s1', 's2'] });
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.validateLineup();
    });

    expect(config.setError).toHaveBeenCalledWith(
      expect.stringContaining('5'),
    );
  });

  it('calls RPCs in order on successful validation', async () => {
    mockRpc.mockResolvedValueOnce({ error: null }) // validate_lineup
      .mockResolvedValueOnce({ error: null }); // upsert_confirmed_lineup

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.validateLineup();
    });

    expect(mockRpc).toHaveBeenCalledTimes(2);
    expect(mockRpc.mock.calls[0][0]).toBe('validate_lineup');
    expect(mockRpc.mock.calls[1][0]).toBe('upsert_confirmed_lineup');
  });

  it('calls setIsValidated(true) on success', async () => {
    mockRpc.mockResolvedValue({ error: null });

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.validateLineup();
    });

    expect(config.setIsValidated).toHaveBeenCalledWith(true);
  });

  it('calls clearEdits on success', async () => {
    mockRpc.mockResolvedValue({ error: null });

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.validateLineup();
    });

    expect(config.clearEdits).toHaveBeenCalled();
  });

  it('sets error on RPC failure', async () => {
    mockRpc.mockResolvedValueOnce({ error: { message: 'RPC failed' } });

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.validateLineup();
    });

    expect(config.setError).toHaveBeenCalledWith('RPC failed');
    expect(config.setIsValidated).not.toHaveBeenCalled();
  });

  it('skips n8n if URL is empty', async () => {
    vi.stubEnv('VITE_N8N_WEBHOOK_URL', '');
    mockRpc.mockResolvedValue({ error: null });

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    // Should not throw, but also should not call fetch
    await act(async () => {
      await result.current.validateLineup();
    });

    expect(global.fetch).not.toHaveBeenCalled();

    // Restore for other tests
    vi.stubEnv('VITE_N8N_WEBHOOK_URL', 'https://n8n.example.com/webhook');
  });

  it('handleCambiarAccept resets validated state', async () => {
    mockRpc.mockResolvedValue({ error: null });
    localStorage.setItem('validated_om-1', '1');

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.handleCambiarAccept();
    });

    expect(config.setIsValidated).toHaveBeenCalledWith(false);
    expect(localStorage.getItem('validated_om-1')).toBeNull();
  });

  it('handleCambiarAccept calls reset_lineup_slots RPC', async () => {
    mockRpc.mockResolvedValue({ error: null });

    const config = makeConfig();
    const { result } = renderHook(() => useValidation(config));

    await act(async () => {
      await result.current.handleCambiarAccept();
    });

    expect(mockRpc).toHaveBeenCalledWith('reset_lineup_slots', {
      p_open_mic_id: 'om-1',
      p_fecha_evento: '2026-03-20',
    });
  });
});
