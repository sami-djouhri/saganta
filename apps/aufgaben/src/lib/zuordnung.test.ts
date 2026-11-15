import { describe, expect, it } from 'vitest';
import type { Aufgabe, Liste } from './aufgaben-bff';
import { listenAus, nachListe, zuordnungAus, zuordnungVon } from './zuordnung';

function a(teil: Partial<Aufgabe> & { id: string }): Aufgabe {
  return { title: teil.id, priority: 'mittel', completed: false, ...teil } as Aufgabe;
}

const LISTEN: Liste[] = [
  { id: 'l2', name: 'Gesundheit & Körper', position: 2 },
  { id: 'l1', name: 'Wohnung & Haushalt', position: 1 },
];

describe('zuordnungVon', () => {
  it('nennt Projekt, Liste oder nichts', () => {
    expect(zuordnungVon(a({ id: 'x', project_id: 'karten' }))).toBe('projekt:karten');
    expect(zuordnungVon(a({ id: 'x', liste_id: 'l1' }))).toBe('liste:l1');
    expect(zuordnungVon(a({ id: 'x' }))).toBe('');
  });
});

describe('zuordnungAus', () => {
  it('setzt immer beide Felder, damit ein Wechsel das alte leert', () => {
    expect(zuordnungAus('liste:l1')).toEqual({ projekt: null, liste_id: 'l1' });
    expect(zuordnungAus('projekt:karten')).toEqual({ projekt: 'karten', liste_id: null });
    expect(zuordnungAus('')).toEqual({ projekt: null, liste_id: null });
    expect(zuordnungAus(null)).toEqual({ projekt: null, liste_id: null });
  });

  it('lehnt Unbekanntes ab, statt still zu leeren', () => {
    expect(zuordnungAus('liste:')).toBeNull();
    expect(zuordnungAus('ordner:x')).toBeNull();
    expect(zuordnungAus('karten')).toBeNull();
  });

  it('ist die Umkehrung von zuordnungVon', () => {
    for (const x of [a({ id: '1', project_id: 'saganta-lager' }), a({ id: '2', liste_id: 'l2' }), a({ id: '3' })]) {
      const felder = zuordnungAus(zuordnungVon(x))!;
      expect(felder.projekt ?? null).toBe(x.project_id ?? null);
      expect(felder.liste_id ?? null).toBe(x.liste_id ?? null);
    }
  });
});

describe('listenAus', () => {
  it('ordnet nach Position', () => {
    expect(listenAus([], LISTEN).map((l) => l.id)).toEqual(['l1', 'l2']);
  });

  it('behaelt eine Liste, an der eine Aufgabe haengt, auch ohne Abruf', () => {
    const listen = listenAus([a({ id: 'x', liste_id: 'weg' })], []);
    expect(listen).toHaveLength(1);
    expect(listen[0]?.id).toBe('weg');
  });
});

describe('nachListe', () => {
  it('zeigt jede Liste, auch leere, und nur offene Aufgaben', () => {
    const gruppen = nachListe(
      [
        a({ id: 'putzen', liste_id: 'l1' }),
        a({ id: 'erledigt', liste_id: 'l1', completed: true, status: 'done' }),
        a({ id: 'projekt', project_id: 'karten' }),
      ],
      listenAus([], LISTEN),
    );
    expect(gruppen.map((g) => g.titel)).toEqual(['Wohnung & Haushalt', 'Gesundheit & Körper']);
    expect(gruppen[0]?.aufgaben.map((x) => x.id)).toEqual(['putzen']);
    expect(gruppen[1]?.aufgaben).toEqual([]);
  });
});
