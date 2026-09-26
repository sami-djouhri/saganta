import { describe, expect, it } from 'vitest';
import { istKuenftig, sprungZiel, vorwaertsMoeglich } from './navigation';

const HEUTE = '2026-09-13';

describe('vorwaertsMoeglich', () => {
  it('erlaubt vorwaerts nur vor heute', () => {
    expect(vorwaertsMoeglich('2026-09-12', HEUTE)).toBe(true);
    expect(vorwaertsMoeglich(HEUTE, HEUTE)).toBe(false);
    expect(vorwaertsMoeglich('2026-09-14', HEUTE)).toBe(false);
  });
});

describe('istKuenftig', () => {
  it('trennt heute von morgen', () => {
    // ★★ Die Regel, an der sich Pfeile und Jahresleiste widersprachen. Die
    // Leiste verlinkte jeden Tag des Jahres, auch den 31. Dezember; wer dort
    // klickte, landete in der Zukunft und fand den Vorwaerts-Knopf ausgegraut.
    expect(istKuenftig('2026-09-14', HEUTE)).toBe(true);
    expect(istKuenftig(HEUTE, HEUTE)).toBe(false);
    expect(istKuenftig('2026-09-12', HEUTE)).toBe(false);
    expect(istKuenftig('2026-12-31', HEUTE)).toBe(true);
  });
});

describe('sprungZiel', () => {
  it('springt gewoehnlich um die volle Weite', () => {
    expect(sprungZiel('2026-09-13', -7, HEUTE)).toBe('2026-09-06');
    expect(sprungZiel('2026-09-01', 7, HEUTE)).toBe('2026-09-08');
    expect(sprungZiel('2026-09-12', -1, HEUTE)).toBe('2026-09-11');
  });

  it('deckelt einen Sprung, der ueber heute hinausschiesst', () => {
    // ★ Eine Woche vorwaerts von vorgestern landete ohne Deckel in fuenf Tagen
    // Zukunft, obwohl jeder einzelne Tagesschritt dorthin gesperrt ist.
    expect(sprungZiel('2026-09-11', 7, HEUTE)).toBe(HEUTE);
    expect(sprungZiel(HEUTE, 1, HEUTE)).toBe(HEUTE);
    expect(sprungZiel(HEUTE, 7, HEUTE)).toBe(HEUTE);
  });

  it('deckelt nicht in die Vergangenheit', () => {
    // Rueckwaerts gibt es keine Grenze: ein Tagebuch darf beliebig weit zurueck.
    expect(sprungZiel('2026-01-01', -7, HEUTE)).toBe('2025-12-25');
  });

  it('rechnet ueber die Zeitumstellung richtig', () => {
    // Die Rechnung liegt in `datum.ts` und arbeitet auf Zeichenketten; hier wird
    // nur belegt, dass der Deckel sie nicht verbiegt. 2026: Sommerzeit ab 29.03.
    expect(sprungZiel('2026-03-25', 7, '2026-12-31')).toBe('2026-04-01');
    expect(sprungZiel('2026-10-28', -7, '2026-12-31')).toBe('2026-10-21');
  });
});
