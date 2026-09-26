import { describe, expect, it } from 'vitest';
import { zerlegen } from './hervorheben';

describe('zerlegen', () => {
  it('markiert Treffer unabhängig von der Schreibweise', () => {
    expect(zerlegen('Strom und Wasser', ['strom'])).toEqual([
      { text: 'Strom', treffer: true },
      { text: ' und Wasser', treffer: false },
    ]);
  });

  it('findet mehrere Begriffe und mehrfache Vorkommen', () => {
    const stuecke = zerlegen('Milch, Brot, Milch', ['milch', 'brot']);
    expect(stuecke.filter((s) => s.treffer).map((s) => s.text)).toEqual([
      'Milch',
      'Brot',
      'Milch',
    ]);
  });

  it('lässt Regex-Zeichen aus der Eingabe nicht wirken', () => {
    // ".*" als Suchbegriff darf nur die zwei Zeichen ".*" treffen, nicht alles.
    expect(zerlegen('a.*b und ab', ['.*'])).toEqual([
      { text: 'a', treffer: false },
      { text: '.*', treffer: true },
      { text: 'b und ab', treffer: false },
    ]);
  });

  it('gibt bei Überlappung dem längeren Begriff den Vorrang', () => {
    const stuecke = zerlegen('Hausrat', ['haus', 'hausrat']);
    expect(stuecke).toEqual([{ text: 'Hausrat', treffer: true }]);
  });

  it('ignoriert Ein-Zeichen-Begriffe und leere Eingaben', () => {
    expect(zerlegen('abc', ['a', ' '])).toEqual([{ text: 'abc', treffer: false }]);
    expect(zerlegen('', ['abc'])).toEqual([]);
  });

  it('trifft Umlaute in beiden Schreibungen des Textes', () => {
    expect(zerlegen('Käse und KÄSE', ['käse']).filter((s) => s.treffer)).toHaveLength(2);
  });
});
