import { describe, expect, it } from 'vitest';
import { kartenKoepfe } from './karten';

describe('kartenKoepfe', () => {
  it('erlaubt nur die Karte, mit Credentials', () => {
    const k = kartenKoepfe('https://karten.home.arpa');
    expect(k['Access-Control-Allow-Origin']).toBe('https://karten.home.arpa');
    expect(k['Access-Control-Allow-Credentials']).toBe('true');
  });

  it('gibt fremden Herkuenften nichts frei', () => {
    for (const o of ['https://evil.example.invalid', 'http://karten.home.arpa',
                     'https://karten.home.arpa.example.invalid', null]) {
      expect(kartenKoepfe(o)['Access-Control-Allow-Origin']).toBeUndefined();
    }
  });
});
