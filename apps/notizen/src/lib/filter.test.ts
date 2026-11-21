import { describe, expect, it } from 'vitest';
import { umschalten } from './filter';

describe('umschalten', () => {
  it('fügt hinzu und nimmt weg', () => {
    expect(umschalten([], 'haus')).toBe('haus');
    expect(umschalten(['haus'], 'garten')).toBe('haus,garten');
    expect(umschalten(['haus', 'garten'], 'haus')).toBe('garten');
  });

  it('gibt null, wenn nichts mehr übrig ist (Parameter fällt aus der Adresse)', () => {
    expect(umschalten(['haus'], 'haus')).toBeNull();
  });
});
