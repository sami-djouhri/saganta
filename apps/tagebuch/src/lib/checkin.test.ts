/**
 * Der Waechter über die einzige Stelle, an der etwas das Tagebuch verlaesst.
 *
 * Geprüft wird eine Eigenschaft, nicht eine Aufzaehlung: die Nutzlast enthaelt
 * **ausschliesslich** erlaubte Felder. Ein Test, der nur `note` abfragt, waere
 * beim naechsten neuen Freitextfeld im Kalender-Schema still wirkungslos.
 */

import { describe, expect, it } from 'vitest';
import { checkinNutzlast } from './checkin';

const ERLAUBT = new Set(['date', 'mood', 'energy', 'sleep_quality']);

describe('Nutzlast an den Kalender', () => {
  it('nimmt die drei Skalen mit', () => {
    const nutzlast = checkinNutzlast('2026-09-06', {
      stimmung: 'gut',
      energie: 'hoch',
      schlaf: 'mittel',
    });
    expect(nutzlast).toEqual({
      date: '2026-09-06',
      mood: 'gut',
      energy: 'hoch',
      sleep_quality: 'mittel',
    });
  });

  it('laesst den Text zurueck, auch wenn er mitgeschickt wird', () => {
    const nutzlast = checkinNutzlast('2026-09-06', {
      stimmung: 'mies',
      text: 'Sehr persoenlicher Absatz, der niemanden etwas angeht.',
      note: 'Auch das nicht.',
      inhalt: 'Und das erst recht nicht.',
    });
    expect(Object.keys(nutzlast).every((k) => ERLAUBT.has(k))).toBe(true);
    expect(JSON.stringify(nutzlast)).not.toContain('persoenlicher');
  });

  it('gibt kein einziges unbekanntes Feld weiter', () => {
    /** ★ Die Eigenschaft, nicht die Liste: was immer hereinkommt, hinaus geht
     * nur, was ausdruecklich erlaubt ist. */
    const allerlei = Object.fromEntries(
      Array.from({ length: 30 }, (_, i) => [`feld_${i}`, `wert ${i}`]),
    );
    const nutzlast = checkinNutzlast('2026-09-06', { ...allerlei, stimmung: 'gut' });
    expect(Object.keys(nutzlast).every((k) => ERLAUBT.has(k))).toBe(true);
  });

  it('verwirft Werte, die nicht auf der Skala liegen', () => {
    const nutzlast = checkinNutzlast('2026-09-06', {
      stimmung: 'ganz wunderbar heute, weil naemlich',
      energie: 'hoch',
    });
    expect(nutzlast.mood).toBeUndefined();
    expect(nutzlast.energy).toBe('hoch');
  });

  it('meldet nichts, wenn nichts angegeben wurde', () => {
    const nutzlast = checkinNutzlast('2026-09-06', { text: 'nur geschrieben, nichts angekreuzt' });
    expect(Object.keys(nutzlast)).toEqual(['date']);
  });
});
