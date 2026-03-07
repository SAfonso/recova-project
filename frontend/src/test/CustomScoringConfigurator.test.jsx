import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CustomScoringConfigurator } from '../components/CustomScoringConfigurator';

const RULES = [
  {
    field: '¿Haces humor negro?',
    condition: 'equals',
    value: 'Sí',
    points: 10,
    enabled: true,
    description: 'Bono por humor negro',
  },
  {
    field: '¿Tienes material nuevo?',
    condition: 'equals',
    value: 'Sí',
    points: 5,
    enabled: false,
    description: 'Bono por material nuevo',
  },
];

const defaultProps = {
  openMicId: 'om-test-uuid',
  rules: RULES,
  onRulesChanged: vi.fn(),
  onPropose: vi.fn(),
  proposing: false,
};

describe('CustomScoringConfigurator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders_rules_list', () => {
    render(<CustomScoringConfigurator {...defaultProps} />);

    expect(screen.getByText('¿Haces humor negro?')).toBeInTheDocument();
    expect(screen.getByText('¿Tienes material nuevo?')).toBeInTheDocument();
    expect(screen.getByText('Bono por humor negro')).toBeInTheDocument();
  });

  it('renders_empty_state_with_propose_button', () => {
    render(<CustomScoringConfigurator {...defaultProps} rules={[]} />);

    expect(screen.getByText(/Proponer reglas/i)).toBeInTheDocument();
    expect(screen.queryByText('¿Haces humor negro?')).not.toBeInTheDocument();
  });

  it('toggle_calls_onRulesChanged', () => {
    const onRulesChanged = vi.fn();
    render(<CustomScoringConfigurator {...defaultProps} onRulesChanged={onRulesChanged} />);

    // El toggle de la primera regla (enabled: true) → debe llamar con enabled: false
    const toggles = screen.getAllByRole('switch');
    fireEvent.click(toggles[0]);

    expect(onRulesChanged).toHaveBeenCalledOnce();
    const newRules = onRulesChanged.mock.calls[0][0];
    expect(newRules[0].enabled).toBe(false);
    // La segunda regla no debe cambiar
    expect(newRules[1].enabled).toBe(false);
  });

  it('slider_updates_points', () => {
    const onRulesChanged = vi.fn();
    render(<CustomScoringConfigurator {...defaultProps} onRulesChanged={onRulesChanged} />);

    const sliders = screen.getAllByRole('slider');
    fireEvent.change(sliders[0], { target: { value: '20' } });

    expect(onRulesChanged).toHaveBeenCalledOnce();
    const newRules = onRulesChanged.mock.calls[0][0];
    expect(newRules[0].points).toBe(20);
  });

  it('propose_button_calls_onPropose', () => {
    const onPropose = vi.fn();
    render(<CustomScoringConfigurator {...defaultProps} rules={[]} onPropose={onPropose} />);

    fireEvent.click(screen.getByText(/Proponer reglas/i));

    expect(onPropose).toHaveBeenCalledOnce();
  });

  it('shows_spinner_when_proposing', () => {
    render(<CustomScoringConfigurator {...defaultProps} rules={[]} proposing={true} />);

    const btn = screen.getByRole('button', { name: /propon/i });
    expect(btn).toBeDisabled();
  });
});
