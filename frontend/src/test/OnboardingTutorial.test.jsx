/**
 * Tests — OnboardingTutorial (v0.21.1)
 *
 * Cubre:
 *   - No activa si recova_tutorial_done=true
 *   - Activa cuando el target aparece en el DOM
 *   - STATUS.FINISHED → setea localStorage
 *   - STATUS.SKIPPED → setea localStorage
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';

// Mock react-joyride para capturar props y simular callbacks
let capturedCallback = null;
let capturedRun = false;
let capturedStepIndex = 0;

vi.mock('react-joyride', () => ({
  default: ({ run, callback, stepIndex }) => {
    capturedRun = run;
    capturedCallback = callback;
    capturedStepIndex = stepIndex;
    return run ? <div data-testid="joyride-mock" /> : null;
  },
  EVENTS: {
    STEP_AFTER: 'step:after',
    TARGET_NOT_FOUND: 'error:target_not_found',
  },
  ACTIONS: {
    PREV: 'prev',
  },
  STATUS: {
    FINISHED: 'finished',
    SKIPPED: 'skipped',
  },
}));

import { OnboardingTutorial } from '../components/OnboardingTutorial';

const STORAGE_KEY = 'recova_tutorial_done';

let targetEl;

beforeEach(() => {
  localStorage.clear();
  capturedCallback = null;
  capturedRun = false;
  capturedStepIndex = 0;
  vi.useFakeTimers();
  targetEl = document.createElement('div');
  targetEl.setAttribute('data-tutorial', 'open-mic-selector');
  document.body.appendChild(targetEl);
});

afterEach(() => {
  vi.useRealTimers();
  targetEl?.remove();
});

describe('OnboardingTutorial', () => {
  it('no activa el tutorial si recova_tutorial_done=true', async () => {
    localStorage.setItem(STORAGE_KEY, 'true');
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(capturedRun).toBe(false);
  });

  it('activa el tutorial cuando el target aparece en el DOM', async () => {
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(capturedRun).toBe(true);
  });

  it('setea localStorage al recibir status=finished', async () => {
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(capturedCallback).not.toBeNull();
    act(() => { capturedCallback({ status: 'finished', type: 'tour:end', index: 9, action: 'next' }); });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('true');
  });

  it('setea localStorage al recibir status=skipped', async () => {
    render(<OnboardingTutorial />);
    await act(async () => { vi.advanceTimersByTime(400); });
    expect(capturedCallback).not.toBeNull();
    act(() => { capturedCallback({ status: 'skipped', type: 'tour:end', index: 0, action: 'skip' }); });
    expect(localStorage.getItem(STORAGE_KEY)).toBe('true');
  });
});
