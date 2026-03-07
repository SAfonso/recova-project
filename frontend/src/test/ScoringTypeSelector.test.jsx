import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ScoringTypeSelector } from '../components/ScoringTypeSelector';

// Mock del cliente Supabase
vi.mock('../supabaseClient', () => ({
  supabase: {
    rpc: vi.fn().mockReturnValue({ execute: vi.fn().mockResolvedValue({ error: null }) }),
  },
}));

import { supabase } from '../supabaseClient';

const defaultProps = {
  openMicId: 'om-test-uuid',
  currentType: 'basic',
  hasFieldMapping: false,
  onChanged: vi.fn(),
};

describe('ScoringTypeSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renderiza las 3 opciones', () => {
    render(<ScoringTypeSelector {...defaultProps} />);

    expect(screen.getByText('Sin scoring')).toBeInTheDocument();
    expect(screen.getByText('Scoring básico')).toBeInTheDocument();
    expect(screen.getByText('Scoring personalizado')).toBeInTheDocument();
  });

  it('la opción currentType aparece seleccionada inicialmente', () => {
    render(<ScoringTypeSelector {...defaultProps} currentType="none" />);

    const noneBtn = screen.getByText('Sin scoring').closest('button');
    expect(noneBtn).toHaveClass('bg-[#1a1a1a]');

    const basicBtn = screen.getByText('Scoring básico').closest('button');
    expect(basicBtn).not.toHaveClass('bg-[#1a1a1a]');
  });

  it('opción custom está disabled cuando hasFieldMapping=false', () => {
    render(<ScoringTypeSelector {...defaultProps} hasFieldMapping={false} />);

    const customBtn = screen.getByText('Scoring personalizado').closest('button');
    expect(customBtn).toBeDisabled();
  });

  it('opción custom está habilitada cuando hasFieldMapping=true', () => {
    render(<ScoringTypeSelector {...defaultProps} hasFieldMapping={true} />);

    const customBtn = screen.getByText('Scoring personalizado').closest('button');
    expect(customBtn).not.toBeDisabled();
  });

  it('al cambiar selección llama a supabase.rpc con scoring_type correcto', async () => {
    render(<ScoringTypeSelector {...defaultProps} currentType="basic" />);

    const noneBtn = screen.getByText('Sin scoring').closest('button');
    fireEvent.click(noneBtn);

    await waitFor(() => {
      expect(supabase.rpc).toHaveBeenCalledWith('update_open_mic_config_keys', {
        p_open_mic_id: 'om-test-uuid',
        p_keys: { scoring_type: 'none' },
      });
    });
  });

  it('al cambiar selección llama a onChanged tras guardar', async () => {
    const onChanged = vi.fn();
    render(<ScoringTypeSelector {...defaultProps} onChanged={onChanged} />);

    fireEvent.click(screen.getByText('Sin scoring').closest('button'));

    await waitFor(() => {
      expect(onChanged).toHaveBeenCalled();
    });
  });

  it('no llama a RPC si se hace clic en la opción ya seleccionada', async () => {
    render(<ScoringTypeSelector {...defaultProps} currentType="basic" />);

    const basicBtn = screen.getByText('Scoring básico').closest('button');
    fireEvent.click(basicBtn);

    await waitFor(() => {
      expect(supabase.rpc).not.toHaveBeenCalled();
    });
  });
});
