import { describe, expect, it } from 'vitest';
import { offenerVerweis, verweisEinsetzen } from './verweis-eingabe';

describe('offenerVerweis', () => {
  it('erkennt das offene [[ vor dem Cursor', () => {
    const text = 'Siehe [[Gar';
    expect(offenerVerweis(text, text.length)).toEqual({ start: 6, anfrage: 'Gar' });
    expect(offenerVerweis('[[', 2)).toEqual({ start: 0, anfrage: '' });
  });

  it('ist zu nach ]], |, Zeilenumbruch und in Code', () => {
    expect(offenerVerweis('[[Garten]] und', 14)).toBeNull();
    expect(offenerVerweis('[[Garten|Anz', 12)).toBeNull();
    expect(offenerVerweis('[[Gar\nten', 9)).toBeNull();
    expect(offenerVerweis('`[[Gar', 6)).toBeNull();
    expect(offenerVerweis('```\n[[Gar', 9)).toBeNull();
    expect(offenerVerweis('```\nx\n```\n[[Gar', 15)).toEqual({ start: 10, anfrage: 'Gar' });
    expect(offenerVerweis('ohne', 4)).toBeNull();
  });

  it('nimmt das letzte [[ der Zeile', () => {
    const text = '[[A]] dann [[B';
    expect(offenerVerweis(text, text.length)).toEqual({ start: 11, anfrage: 'B' });
  });
});

describe('verweisEinsetzen', () => {
  it('schließt mit ]] und setzt den Cursor dahinter', () => {
    const text = 'Siehe [[Gar und mehr';
    const offen = offenerVerweis(text, 11)!;
    const neu = verweisEinsetzen(text, 11, offen, 'Garten  plan');
    expect(neu.text).toBe('Siehe [[Garten plan]] und mehr');
    expect(neu.cursor).toBe('Siehe [[Garten plan]]'.length);
  });

  it('ersetzt einen schon geschlossenen Verweis ganz und behält die Anzeige', () => {
    const text = 'x [[Gar]] y';
    const offen = offenerVerweis(text, 6)!;
    expect(verweisEinsetzen(text, 6, offen, 'Garten').text).toBe('x [[Garten]] y');
    const mitAnzeige = 'x [[Gar|der Garten]] y';
    const o2 = offenerVerweis(mitAnzeige, 6)!;
    expect(verweisEinsetzen(mitAnzeige, 6, o2, 'Garten').text).toBe('x [[Garten|der Garten]] y');
  });

  it('greift nicht in einen späteren Verweis derselben Zeile', () => {
    const text = '[[Ga und [[B]]';
    const offen = offenerVerweis(text, 4)!;
    expect(verweisEinsetzen(text, 4, offen, 'Garten').text).toBe('[[Garten]] und [[B]]');
  });
});
