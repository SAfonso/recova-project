/**
 * Tests — ComicCard: flag "Puede Hoy" (v0.19.0)
 *
 * Cubre (spec last_minute_flag_spec §Visual):
 *   - Badge "Puede hoy" visible cuando lastMinuteMode=true && isLastMinute=true
 *   - Sin badge cuando lastMinuteMode=false
 *   - Sin badge cuando isLastMinute=false
 *   - Clase last-minute-glow presente cuando se cumplen ambas condiciones
 *   - Sin glow cuando las condiciones no se cumplen
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ComicCard } from '../components/open-mic/ComicCard';

const defaultCandidate = {
  row_key: 'sol-1',
  solicitud_id: 'sol-1',
  comico_id: 'com-1',
  nombre: 'Juan Cómico',
  instagram: 'juancomico',
  contacto: '+34600000000',
  telefono: '+34600000000',
  estado: 'scorado',
  fecha_evento: '2026-03-14',
  puede_hoy: true,
};

const defaultDraft = { categoria: 'standard', genero: 'f' };

const defaultProps = {
  candidate: defaultCandidate,
  draft: defaultDraft,
  selected: false,
  expanded: false,
  canSelect: true,
  onExpand: vi.fn(),
  onToggleSelected: vi.fn(),
  onUpdateCategory: vi.fn(),
  onUpdateGenero: vi.fn(),
  hasPendingEdit: false,
  lastMinuteMode: false,
  isLastMinute: false,
};

describe('ComicCard — flag Puede Hoy', () => {
  it('muestra el badge "Puede hoy" cuando lastMinuteMode=true e isLastMinute=true', () => {
    render(<ComicCard {...defaultProps} lastMinuteMode={true} isLastMinute={true} />);

    expect(screen.getByText('Puede hoy')).toBeInTheDocument();
  });

  it('no muestra el badge cuando lastMinuteMode=false', () => {
    render(<ComicCard {...defaultProps} lastMinuteMode={false} isLastMinute={true} />);

    expect(screen.queryByText('Puede hoy')).not.toBeInTheDocument();
  });

  it('no muestra el badge cuando isLastMinute=false', () => {
    render(<ComicCard {...defaultProps} lastMinuteMode={true} isLastMinute={false} />);

    expect(screen.queryByText('Puede hoy')).not.toBeInTheDocument();
  });

  it('no muestra el badge cuando ambas condiciones son false', () => {
    render(<ComicCard {...defaultProps} lastMinuteMode={false} isLastMinute={false} />);

    expect(screen.queryByText('Puede hoy')).not.toBeInTheDocument();
  });

  it('aplica la clase last-minute-glow cuando lastMinuteMode=true e isLastMinute=true', () => {
    const { container } = render(
      <ComicCard {...defaultProps} lastMinuteMode={true} isLastMinute={true} />,
    );

    expect(container.firstChild).toHaveClass('last-minute-glow');
  });

  it('no aplica la clase last-minute-glow cuando lastMinuteMode=false', () => {
    const { container } = render(
      <ComicCard {...defaultProps} lastMinuteMode={false} isLastMinute={true} />,
    );

    expect(container.firstChild).not.toHaveClass('last-minute-glow');
  });

  it('no aplica la clase last-minute-glow cuando isLastMinute=false', () => {
    const { container } = render(
      <ComicCard {...defaultProps} lastMinuteMode={true} isLastMinute={false} />,
    );

    expect(container.firstChild).not.toHaveClass('last-minute-glow');
  });
});
