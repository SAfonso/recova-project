/**
 * Tests — OnboardingTutorial (v0.21.0)
 *
 * Cubre (spec onboarding_tutorial_spec §Tests):
 *   - No renderiza Joyride si recova_tutorial_done=true en localStorage
 *   - Renderiza Joyride si la key no existe
 *   - Al llamar callback con 'finished' → setea localStorage
 *   - Al llamar callback con 'skipped' → setea localStorage
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';

// Mock react-joyride para capturar props y simular callbacks
let capturedCallback = null;
let capturedRun = false;

vi.mock('react-joyride', () => ({
  default: ({ run, callback }) => {
    capturedRun = run;
    capturedCallback = callback;
    return run ? <div data-testid="joyride-mock" /> : null;
  },
}));

import { OnboardingTutorial } from '../components/OnboardingTutorial';

const STORAGE_KEY = 'recova_tutorial_done';

beforeEach(() => {
  localStorage.clear();
  capturedCallback = null;
  capturedRun = false;
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('OnboardingTutorial', () => {
  it('no activa el tutorial si recova_tutorial_done=true', async () => {
    localStorage.setItem(STORAGE_KEY, 'true');
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(capturedRun).toBe(false);
  });

  it('activa el tutorial si la key no existe', async () => {
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(capturedRun).toBe(true);
  });

  it('setea localStorage al recibir status=finished', async () => {
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(capturedCallback).not.toBeNull();
    act(() => { capturedCallback({ status: 'finished' }); });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('true');
  });

  it('setea localStorage al recibir status=skipped', async () => {
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(capturedCallback).not.toBeNull();
    act(() => { capturedCallback({ status: 'skipped' }); });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('true');
  });
});
