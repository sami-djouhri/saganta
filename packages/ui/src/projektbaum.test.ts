import { describe, expect, it } from 'vitest';
import { ausDeck, eingerueckt, projektBaum, teilbaeume, teilbaumSlugs, type BaumProjekt } from './projektbaum';

// Erfundene Gliederung: Gartiko-Bot steht unter Discord-Bots UND Gartiko,
// beide unter Homelab. Dazu ein loses Projekt ohne Eltern.
const deck = [
  { id: 1, slug: 'homelab', name: 'Homelab', kinder_ids: [2, 3] },
  { id: 2, slug: 'discord-bots', name: 'Discord-Bots', eltern_ids: [1], kinder_ids: [4] },
  { id: 3, slug: 'gartiko', name: 'Gartiko', eltern_ids: [1], kinder_ids: [4] },
  { id: 4, slug: 'gartiko-bot', name: 'Gartiko-Bot', eltern_ids: [2, 3], kinder_ids: [5] },
  { id: 5, slug: 'bot-doktor', name: 'Bot-Doktor', eltern_ids: [4] },
  { id: 6, slug: 'allein', name: 'Allein' },
].map(ausDeck);

describe('projektBaum', () => {
  it('rueckt ein und zeigt ein Projekt mit zwei Eltern unter beiden', () => {
    const zeilen = projektBaum(deck).map((z) => `${z.tiefe}:${z.slug}`);
    expect(zeilen).toEqual([
      '0:allein',
      '0:homelab',
      '1:discord-bots',
      '2:gartiko-bot',
      '3:bot-doktor',
      '1:gartiko',
      '2:gartiko-bot',
      '3:bot-doktor',
    ]);
  });

  it('markiert nur das erste Auftreten und haelt die Schluessel eindeutig', () => {
    const zeilen = projektBaum(deck);
    const bot = zeilen.filter((z) => z.slug === 'gartiko-bot');
    expect(bot.map((z) => z.erstes)).toEqual([true, false]);
    expect(new Set(zeilen.map((z) => z.schluessel)).size).toBe(zeilen.length);
  });

  it('nimmt eine Seite der Kante, wenn die andere fehlt', () => {
    const nurEltern: BaumProjekt[] = [
      { slug: 'oben', name: 'Oben', deck_id: 1 },
      { slug: 'unten', name: 'Unten', deck_id: 2, eltern_ids: [1] },
    ];
    expect(projektBaum(nurEltern).map((z) => `${z.tiefe}:${z.slug}`)).toEqual(['0:oben', '1:unten']);
  });

  it('rueckt ein Kind nach oben, wenn sein Elternteil weggefiltert ist', () => {
    const ohneHomelab = deck.filter((p) => p.slug !== 'homelab');
    const oben = projektBaum(ohneHomelab).filter((z) => z.tiefe === 0).map((z) => z.slug);
    expect(oben).toEqual(['allein', 'discord-bots', 'gartiko']);
  });

  it('verliert bei einem Kreis nichts und haengt nicht', () => {
    const kreis: BaumProjekt[] = [
      { slug: 'a', name: 'A', deck_id: 1, kinder_ids: [2] },
      { slug: 'b', name: 'B', deck_id: 2, kinder_ids: [1] },
    ];
    const zeilen = projektBaum(kreis);
    expect(new Set(zeilen.map((z) => z.slug))).toEqual(new Set(['a', 'b']));
    expect(zeilen.length).toBeLessThan(5);
  });

  it('stellt Projekte ohne Deck-Kennung (nur Slug an einer Aufgabe) oben hin', () => {
    const zeilen = projektBaum([...deck, { slug: 'nur-slug', name: 'Nur Slug' }]);
    expect(zeilen.find((z) => z.slug === 'nur-slug')?.tiefe).toBe(0);
  });
});

describe('teilbaumSlugs', () => {
  it('liefert den Slug und alle Nachfahren, jeden einmal', () => {
    expect(teilbaumSlugs('homelab', deck)).toEqual(['homelab', 'discord-bots', 'gartiko', 'gartiko-bot', 'bot-doktor']);
  });

  it('liefert fuer ein Blatt und einen unbekannten Slug nur sich selbst', () => {
    expect(teilbaumSlugs('bot-doktor', deck)).toEqual(['bot-doktor']);
    expect(teilbaumSlugs('gibt-es-nicht', deck)).toEqual(['gibt-es-nicht']);
  });

  it('teilbaeume nennt nur Projekte mit Unterprojekten', () => {
    const t = teilbaeume(deck);
    expect(Object.keys(t).sort()).toEqual(['discord-bots', 'gartiko', 'gartiko-bot', 'homelab']);
    expect(t['gartiko']).toEqual(['gartiko', 'gartiko-bot', 'bot-doktor']);
  });
});

describe('eingerueckt', () => {
  it('laesst die oberste Ebene unveraendert und rueckt darunter mit geschuetzten Leerzeichen ein', () => {
    expect(eingerueckt({ name: 'Homelab', tiefe: 0 })).toBe('Homelab');
    expect(eingerueckt({ name: 'Gartiko', tiefe: 2 })).toBe('\u00a0'.repeat(6) + '·\u00a0Gartiko');
  });
});
