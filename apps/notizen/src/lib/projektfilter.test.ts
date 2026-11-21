import { describe, expect, it } from 'vitest';
import { istSlug, notizenDesProjekts } from './projektfilter';
import type { NotizKurz } from './types';

function n(id: number, teil: Partial<NotizKurz> = {}): NotizKurz {
  return {
    id,
    titel: `Notiz ${id}`,
    ausschnitt: '',
    tags: [],
    notizbuch_id: null,
    angeheftet: false,
    archiviert: false,
    anzahl_anhaenge: 0,
    anzahl_verknuepfungen: 1,
    anzahl_freigaben: 0,
    erstellt_am: '2026-11-01T10:00:00',
    geaendert_am: `2026-11-0${id}T10:00:00`,
    ...teil,
  };
}

describe('notizenDesProjekts', () => {
  it('nimmt jede Notiz einmal, auch wenn sie an Ober- und Unterprojekt haengt', () => {
    const doppelt = n(2);
    const liste = notizenDesProjekts({ oben: [n(1), doppelt], unten: [doppelt, n(3)] });
    expect(liste.map((x) => x.id)).toEqual([3, 2, 1]);
  });

  it('stellt Angeheftetes vor', () => {
    const liste = notizenDesProjekts({ a: [n(1, { angeheftet: true }), n(3)] });
    expect(liste.map((x) => x.id)).toEqual([1, 3]);
  });

  it('wendet Notizbuch und Tag an', () => {
    const nach = { a: [n(1, { notizbuch_id: 7, tags: ['Haus'] }), n(2, { notizbuch_id: 7 }), n(3, { tags: ['haus'] })] };
    expect(notizenDesProjekts(nach, { notizbuch: '7' }).map((x) => x.id)).toEqual([2, 1]);
    expect(notizenDesProjekts(nach, { tag: 'haus' }).map((x) => x.id)).toEqual([3, 1]);
  });

  it('folgt bei einer Suche deren Rangfolge und laesst Nicht-Treffer weg', () => {
    const nach = { a: [n(1), n(2), n(3)] };
    expect(notizenDesProjekts(nach, { treffer: [3, 1, 99] }).map((x) => x.id)).toEqual([3, 1]);
  });
});

describe('istSlug', () => {
  it('laesst nur Slugs durch', () => {
    expect(istSlug('gartiko-bot')).toBe(true);
    expect(istSlug('a,b')).toBe(false);
    expect(istSlug('')).toBe(false);
  });
});
