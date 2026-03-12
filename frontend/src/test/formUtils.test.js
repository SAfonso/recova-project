import { describe, it, expect } from 'vitest';
import { extractFormId } from '../utils/formUtils';

describe('extractFormId', () => {
  it('extrae form_id de URL con /viewform', () => {
    const url = 'https://docs.google.com/forms/d/1BxEfoo123/viewform';
    expect(extractFormId(url)).toBe('1BxEfoo123');
  });

  it('extrae form_id de URL con /edit', () => {
    const url = 'https://docs.google.com/forms/d/1BxEfoo123/edit';
    expect(extractFormId(url)).toBe('1BxEfoo123');
  });

  it('extrae form_id de URL sin sufijo de ruta', () => {
    const url = 'https://docs.google.com/forms/d/1BxEfoo123';
    expect(extractFormId(url)).toBe('1BxEfoo123');
  });

  it('devuelve el string tal cual si ya es un ID directo', () => {
    expect(extractFormId('1BxEfoo123')).toBe('1BxEfoo123');
  });

  it('trim de espacios en ID directo', () => {
    expect(extractFormId('  1BxEfoo123  ')).toBe('1BxEfoo123');
  });

  it('devuelve string vacío para entrada vacía', () => {
    expect(extractFormId('')).toBe('');
    expect(extractFormId(null)).toBe('');
    expect(extractFormId(undefined)).toBe('');
  });

  it('maneja form_id con guiones y underscores', () => {
    const url = 'https://docs.google.com/forms/d/1BxE-foo_BAR123/viewform';
    expect(extractFormId(url)).toBe('1BxE-foo_BAR123');
  });
});
