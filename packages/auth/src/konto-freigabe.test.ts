/**
 * Die zweite Tuer vor dem Konto.
 *
 * Die Saganta-Sitzung haelt 90 Tage und gilt in allen Apps. Vor
 * Konto-Aenderungen steht deshalb eine erneute Passwortabfrage, deren Ergebnis
 * ein signierter, kurzlebiger Zettel ist. Diese Tests halten fest, was an ihm
 * nicht verrutschen darf: er gehoert genau einem Konto, er laeuft ab, und eine
 * gefaelschte Unterschrift zaehlt nicht.
 */

import { describe, expect, it, vi } from 'vitest';
import type { Cookies } from '@sveltejs/kit';
import {
  FREIGABE_COOKIE,
  FREIGABE_DAUER_S,
  hatFreigabe,
  kontoadresseFuer,
  loescheFreigabe,
  setzeFreigabe,
} from './konto-freigabe.js';

const GEHEIM = 'pruef-geheimnis-nicht-in-betrieb';
const SUB = 'konto-eins';

/** Minimaler Cookie-Speicher, der sich wie SvelteKits `cookies` verhaelt. */
function keksdose(start: Record<string, string> = {}) {
  const inhalt = new Map(Object.entries(start));
  const optionen: Record<string, unknown> = {};
  const dose = {
    get: (name: string) => inhalt.get(name),
    set: (name: string, wert: string, opts: Record<string, unknown>) => {
      inhalt.set(name, wert);
      optionen[name] = opts;
    },
    delete: (name: string) => {
      inhalt.delete(name);
    },
  } as unknown as Cookies;
  return { dose, inhalt, optionen };
}

describe('Freigabe ausstellen und pruefen', () => {
  it('erkennt die eigene frische Freigabe an', () => {
    const { dose } = keksdose();
    setzeFreigabe(dose, SUB, GEHEIM, true);
    expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(true);
  });

  it('gilt nicht fuer ein anderes Konto', () => {
    // Der Kern: wer sich freigeschaltet hat, hat sich selbst freigeschaltet.
    // Ohne die sub-Bindung waere ein abgefangener Zettel ein Generalschluessel.
    const { dose } = keksdose();
    setzeFreigabe(dose, SUB, GEHEIM, true);
    expect(hatFreigabe(dose, 'konto-zwei', GEHEIM)).toBe(false);
  });

  it('gilt nicht mit einem anderen Geheimnis', () => {
    const { dose } = keksdose();
    setzeFreigabe(dose, SUB, GEHEIM, true);
    expect(hatFreigabe(dose, SUB, 'anderes-geheimnis')).toBe(false);
  });

  it('ohne Cookie gibt es keine Freigabe', () => {
    const { dose } = keksdose();
    expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(false);
  });

  it('laeuft ab', () => {
    const { dose } = keksdose();
    setzeFreigabe(dose, SUB, GEHEIM, true);
    expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(true);

    // Eine Sekunde nach Ablauf zaehlt der Zettel nicht mehr. Geprueft wird die
    // Zeit, nicht das Cookie-Ablaufdatum: auf das Verfallsdatum im Browser darf
    // sich der Server nicht verlassen, es steht beim Aufrufer.
    vi.useFakeTimers();
    try {
      vi.setSystemTime(Date.now() + (FREIGABE_DAUER_S + 1) * 1000);
      expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it('weist eine gefaelschte Unterschrift ab', () => {
    const inZehnMinuten = Math.floor(Date.now() / 1000) + 300;
    const { dose } = keksdose({ [FREIGABE_COOKIE]: `${inZehnMinuten}.frei-erfunden` });
    expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(false);
  });

  it('weist eine Zeitangabe ohne Unterschrift ab', () => {
    const inZehnMinuten = Math.floor(Date.now() / 1000) + 300;
    const { dose } = keksdose({ [FREIGABE_COOKIE]: String(inZehnMinuten) });
    expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(false);
  });

  it('laesst sich zuruecknehmen', () => {
    const { dose } = keksdose();
    setzeFreigabe(dose, SUB, GEHEIM, true);
    loescheFreigabe(dose);
    expect(hatFreigabe(dose, SUB, GEHEIM)).toBe(false);
  });

  it('streut die Freigabe NICHT ueber die Registrar-Domain', () => {
    // Anders als das Sitzungs-Cookie bleibt sie host-only. Sonst gaelte eine
    // einmal erteilte Freigabe in jeder App der Suite.
    const { dose, optionen } = keksdose();
    setzeFreigabe(dose, SUB, GEHEIM, true);
    expect((optionen[FREIGABE_COOKIE] as Record<string, unknown>).domain).toBeUndefined();
    expect((optionen[FREIGABE_COOKIE] as Record<string, unknown>).httpOnly).toBe(true);
  });
});

describe('Konto-Adresse im richtigen Domain-Raum', () => {
  const raeume = { 'home.arpa': 'https://shell.home.arpa' };

  it('bleibt im .home-Raum, wenn die Anfrage von dort kam', () => {
    // Die Falle, die bei der Anmeldung schon einmal zugeschlagen hat: ein Link
    // in den anderen Raum fuehrt zu einer Anmeldemaske statt zum Konto, weil
    // das Sitzungs-Cookie dort nicht gilt.
    expect(kontoadresseFuer('notizen.home.arpa', 'https://saganta.de', raeume)).toBe(
      'https://shell.home.arpa/konto',
    );
  });

  it('nimmt den .home-Raum auch beim nackten Namen', () => {
    expect(kontoadresseFuer('home.arpa', 'https://saganta.de', raeume)).toBe(
      'https://shell.home.arpa/konto',
    );
  });

  it('bleibt sonst bei der Vorgabe', () => {
    expect(kontoadresseFuer('kalender.saganta.de', 'https://saganta.de', raeume)).toBe(
      'https://saganta.de/konto',
    );
  });

  it('kommt ohne bekannten Host aus', () => {
    expect(kontoadresseFuer(undefined, 'https://saganta.de', raeume)).toBe(
      'https://saganta.de/konto',
    );
  });

  it('haengt keinen zweiten Schraegstrich an', () => {
    expect(kontoadresseFuer('kalender.saganta.de', 'https://saganta.de/', raeume)).toBe(
      'https://saganta.de/konto',
    );
  });

  it('laesst sich von einem aehnlich aussehenden Fremdnamen nicht taeuschen', () => {
    // `home.arpa.fremd.de` endet nicht auf `.home.arpa`, sondern gehoert
    // `fremd.de`. Eine Pruefung mit `includes` faele darauf herein.
    expect(kontoadresseFuer('home.arpa.fremd.de', 'https://saganta.de', raeume)).toBe(
      'https://saganta.de/konto',
    );
  });
});
