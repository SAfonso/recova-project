/**
 * Tests Sprint 13 — Smart Form Generation
 *
 * Cubre:
 *  - InfoConfigurator: selector cadencia + campo fecha_inicio + popup aviso
 *  - FormWarningBadges: badge info_changed (⚠️) + badge expiración (🗓️)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { InfoConfigurator } from '../components/open-mic/InfoConfigurator';
import { FormWarningBadges } from '../components/open-mic/FormWarningBadges';

// ---------------------------------------------------------------------------
// Mock Supabase — cadena schema().from().update().eq()
// ---------------------------------------------------------------------------

const { mockEq, mockUpdate, mockFrom } = vi.hoisted(() => {
  const mockEq     = vi.fn().mockResolvedValue({ error: null });
  const mockUpdate = vi.fn().mockReturnValue({ eq: mockEq });
  const mockFrom   = vi.fn().mockReturnValue({ update: mockUpdate });
  return { mockEq, mockUpdate, mockFrom };
});

vi.mock('../supabaseClient', () => ({
  supabase: {
    schema: vi.fn().mockReturnValue({ from: mockFrom }),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeOpenMic(overrides = {}) {
  return {
    nombre: 'Test Open Mic',
    config: {
      info: { dia_semana: 'Miércoles', hora: '20:00' },
      ...(overrides.config ?? {}),
    },
    ...(overrides.top ?? {}),
  };
}

// ---------------------------------------------------------------------------
// InfoConfigurator — cadencia + fecha_inicio
// ---------------------------------------------------------------------------

describe('InfoConfigurator — Sprint 13', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('renders_cadencia_selector', () => {
    render(<InfoConfigurator openMicId="om-1" openMic={makeOpenMic()} onSaved={vi.fn()} />);
    expect(screen.getByText(/frecuencia/i)).toBeInTheDocument();
  });

  it('shows_fecha_inicio_field', () => {
    render(<InfoConfigurator openMicId="om-1" openMic={makeOpenMic()} onSaved={vi.fn()} />);
    expect(screen.getByLabelText(/fecha de inicio/i)).toBeInTheDocument();
  });

  it('persists_cadencia_on_save', async () => {
    const openMic = makeOpenMic({ config: { info: { cadencia: 'semanal' } } });
    render(<InfoConfigurator openMicId="om-1" openMic={openMic} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByText('Guardar información'));
    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        expect.objectContaining({
          config: expect.objectContaining({
            info: expect.objectContaining({ cadencia: 'semanal' }),
          }),
        })
      );
    });
  });

  it('shows_popup_on_save_when_form_exists', async () => {
    const openMic = makeOpenMic({ config: { form: { form_id: 'form-123' } } });
    render(<InfoConfigurator openMicId="om-1" openMic={openMic} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByText('Guardar información'));
    await waitFor(() => {
      expect(screen.getByText(/formulario.*desactualizado/i)).toBeInTheDocument();
    });
  });

  it('no_popup_if_no_form', async () => {
    render(<InfoConfigurator openMicId="om-1" openMic={makeOpenMic()} onSaved={vi.fn()} />);
    fireEvent.click(screen.getByText('Guardar información'));
    await waitFor(() => {
      expect(screen.queryByText(/formulario.*desactualizado/i)).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// FormWarningBadges — badge ⚠️ info_changed + badge 🗓️ expiración
// ---------------------------------------------------------------------------

describe('FormWarningBadges', () => {
  it('shows_info_changed_badge', () => {
    render(<FormWarningBadges formConfig={{ info_changed: true }} />);
    expect(screen.getByRole('img', { name: /formulario desactualizado/i })).toBeInTheDocument();
  });

  it('hides_info_changed_badge', () => {
    render(<FormWarningBadges formConfig={{ info_changed: false }} />);
    expect(screen.queryByRole('img', { name: /formulario desactualizado/i })).not.toBeInTheDocument();
  });

  it('shows_expiry_badge_last_week', () => {
    // last_date = 4 días desde hoy
    const d = new Date();
    d.setDate(d.getDate() + 4);
    const last_date = `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getFullYear()).slice(2)}`;
    render(<FormWarningBadges formConfig={{ last_date }} />);
    expect(screen.getByRole('img', { name: /fechas.*caducan/i })).toBeInTheDocument();
  });

  it('shows_expiry_badge_expired', () => {
    // last_date = ayer
    const d = new Date();
    d.setDate(d.getDate() - 1);
    const last_date = `${String(d.getDate()).padStart(2, '0')}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getFullYear()).slice(2)}`;
    render(<FormWarningBadges formConfig={{ last_date }} />);
    expect(screen.getByRole('img', { name: /fechas.*pasado/i })).toBeInTheDocument();
  });

  it('no_expiry_badge_if_no_last_date', () => {
    render(<FormWarningBadges formConfig={{}} />);
    expect(screen.queryByRole('img', { name: /fechas/i })).not.toBeInTheDocument();
  });
});
