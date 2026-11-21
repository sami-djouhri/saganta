import { describe, expect, it } from 'vitest';
import { projektFeld } from './projektfeld';

describe('projektFeld', () => {
  it('legt nur mit gesetztem Projekt an', () => {
    expect(projektFeld('gartiko', null, false)).toEqual({ projekt: 'gartiko' });
    expect(projektFeld('', null, false)).toEqual({});
  });
  it('schickt beim Bearbeiten nur Aenderungen, leer loest den Bezug', () => {
    expect(projektFeld('gartiko', 'gartiko', true)).toEqual({});
    expect(projektFeld('karten', 'gartiko', true)).toEqual({ projekt: 'karten' });
    expect(projektFeld('', 'gartiko', true)).toEqual({ projekt: '' });
  });
  it('laesst ohne alten Wert (Formular ohne Feld) alles stehen', () => {
    expect(projektFeld('', null, true)).toEqual({});
  });
  it('lehnt fremde Werte ab', () => {
    expect(projektFeld('Nicht gueltig', null, false)).toHaveProperty('fehler');
  });
});
