import { describe, expect, it } from 'vitest';
import { abstand, anlass, datumLang, gruppenTon, kuerzel, telAdresse } from './anzeige';

describe('anzeige', () => {
  it('schreibt Daten lang und deutsch', () => {
    expect(datumLang('1995-03-10')).toBe('10. März 1995');
    expect(datumLang(null)).toBe('');
    expect(datumLang('kaputt')).toBe('kaputt');
  });

  it('nennt den Abstand in Worten', () => {
    expect([abstand(0), abstand(1), abstand(3)]).toEqual(['heute', 'morgen', 'in 3 Tagen']);
  });

  it('nennt den Anlass', () => {
    expect(anlass({ art: 'geburtstag', bezeichnung: 'Geburtstag', zahl: 31 })).toBe('wird 31');
    expect(anlass({ art: 'jahrestag', bezeichnung: 'Hochzeitstag', zahl: 5 })).toBe('5. Hochzeitstag');
    expect(anlass({ art: 'jahrestag', bezeichnung: 'Hochzeitstag', zahl: 0 })).toBe('Hochzeitstag');
  });

  it('bildet Kuerzel und Telefonadressen', () => {
    expect(kuerzel('anna maria berg')).toBe('AB');
    expect(kuerzel('Oma')).toBe('O');
    expect(telAdresse('+49 (151) 123-45')).toBe('tel:+4915112345');
  });

  it('gibt derselben Gruppe dieselbe Farbe, gleich wie geschrieben', () => {
    expect(gruppenTon('Familie')).toBe(gruppenTon('familie'));
  });
});
