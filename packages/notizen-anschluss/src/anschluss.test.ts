/**
 * Was hier geprüft wird, und was bewusst nicht.
 *
 * Geprüft wird der **Vertrag nach außen**: wie viele Aufrufe entstehen, was im
 * Rumpf steht, was bei einem Ausfall passiert, und welche Eingaben abgelehnt
 * werden. Das sind genau die Stellen, an denen drei Apps auseinanderlaufen
 * würden, wenn jede ihren eigenen Aufruf baute.
 *
 * ⚠️ Nicht geprüft wird, ob die notizen-api das Gesendete richtig verarbeitet.
 * Das steht in deren eigenen Tests (`test_anhaenge_und_verknuepfungen.py`), und
 * ein Test, der beide Seiten selbst nachbaut, bestätigt nur sich selbst. Der
 * gemeinsame Riegel über beide Seiten ist `scripts/notizen-rauchtest.sh`.
 */
import { describe, expect, it } from 'vitest';
// Über den Index, nicht über die einzelnen Dateien: geprüft werden soll der
// Vertrag nach außen. Nach der Trennung von `typen.ts` und `anschluss.ts` lag
// `istVerknuepfungsTyp` nicht mehr dort, wo der Test sie holte, und das fiel
// erst beim Lauf über alle Pakete auf.
import {
  anschlussAus,
  istVerknuepfungsTyp,
  notizDazuAusFormular,
  notizenZu,
  notizenZuEinem,
  notizenSuchen,
  type Anschluss,
} from './index.js';

const NUTZER = { sub: 'nutzer-eins', email: 'eins@example.invalid', groups: [] } as never;

/** Ein fetch-Ersatz, der mitschreibt, was er bekommt. */
function horcher(antworten: Array<{ status?: number; rumpf?: unknown }> = [{ rumpf: {} }]) {
  const rufe: Array<{ url: string; methode: string; rumpf: unknown }> = [];
  let i = 0;
  const fetcher = (async (url: string, init: RequestInit = {}) => {
    const antwort = antworten[Math.min(i, antworten.length - 1)]!;
    i += 1;
    rufe.push({
      url: String(url),
      methode: init.method ?? 'GET',
      rumpf: typeof init.body === 'string' ? JSON.parse(init.body) : undefined,
    });
    const status = antwort.status ?? 200;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => antwort.rumpf ?? {},
      text: async () => JSON.stringify(antwort.rumpf ?? ''),
    };
  }) as unknown as typeof fetch;
  return { rufe, fetcher };
}

function anschluss(fetcher: typeof fetch): Anschluss {
  return { basis: 'http://notizen-api:8000', secret: 'geheim-fuer-den-test', user: NUTZER, fetcher };
}

function formular(felder: Record<string, string>) {
  return { get: (name: string) => (name in felder ? felder[name]! : null) };
}

describe('anschlussAus', () => {
  it('gibt null, wenn Basis oder Geheimnis fehlen', () => {
    // Kein Fehler, sondern „hier nicht angeschlossen": die Oberflaeche zeigt
    // den Knopf dann nicht, statt ihn anzubieten und beim Klick zu scheitern.
    expect(anschlussAus({}, NUTZER, fetch)).toBeNull();
    expect(anschlussAus({ NOTIZEN_API_BASE_URL: 'http://x' }, NUTZER, fetch)).toBeNull();
    expect(anschlussAus({ SAGANTA_BACKEND_SECRET: 's' }, NUTZER, fetch)).toBeNull();
  });

  it('gibt null ohne angemeldeten Nutzer', () => {
    const umgebung = { NOTIZEN_API_BASE_URL: 'http://x', SAGANTA_BACKEND_SECRET: 's' };
    expect(anschlussAus(umgebung, null, fetch)).toBeNull();
  });

  it('schneidet den Schrägstrich am Ende ab', () => {
    // Sonst entsteht `http://x//api/notizen`, und manche Proxys antworten
    // darauf mit 404, was wie ein fehlender Endpunkt aussieht.
    const a = anschlussAus(
      { NOTIZEN_API_BASE_URL: 'http://x:8000/', SAGANTA_BACKEND_SECRET: 's' },
      NUTZER,
      fetch,
    );
    expect(a?.basis).toBe('http://x:8000');
  });
});

describe('notizDazuAusFormular: anlegen', () => {
  it('legt Notiz und Verknüpfung in EINEM Aufruf an', async () => {
    const { rufe, fetcher } = horcher([{ status: 201, rumpf: { id: 7, titel: 'Fragen' } }]);
    const erg = await notizDazuAusFormular(
      formular({
        typ: 'termin',
        ref: 'ev-42',
        label: 'Elterngespräch Di 14:00',
        titel: 'Fragen',
        inhalt: '- Zeitplan',
      }),
      anschluss(fetcher),
    );

    expect(erg).toEqual({ ok: true, notiz: { id: 7, titel: 'Fragen' } });
    // Der Kern dieses Pakets. Zwei Aufrufe koennten zwischen sich
    // abbrechen und eine Notiz ohne Bezug hinterlassen.
    expect(rufe).toHaveLength(1);
    expect(rufe[0]!.methode).toBe('POST');
    expect(rufe[0]!.url).toBe('http://notizen-api:8000/api/notizen');
    expect(rufe[0]!.rumpf).toEqual({
      titel: 'Fragen',
      inhalt: '- Zeitplan',
      verknuepfung: { typ: 'termin', ref: 'ev-42', label: 'Elterngespräch Di 14:00' },
    });
  });

  it('nimmt einen Text ohne Titel und macht daraus den Titel', async () => {
    const { rufe, fetcher } = horcher([{ status: 201, rumpf: { id: 8, titel: 'x' } }]);
    await notizDazuAusFormular(
      formular({ typ: 'aufgabe', ref: '3', label: 'Angebot', titel: '', inhalt: '  Rückruf Mo  ' }),
      anschluss(fetcher),
    );
    const rumpf = rufe[0]!.rumpf as { titel: string; inhalt: string };
    expect(rumpf.titel).toBe('Rückruf Mo');
    // Der Text bleibt vollstaendig, auch der Zeilenumbruch am Rand: der Titel
    // ist eine Ableitung davon, kein Ersatz.
    expect(rumpf.inhalt).toBe('  Rückruf Mo  ');
  });

  it('lehnt eine Notiz ohne Titel und ohne Text ab, ohne etwas zu senden', async () => {
    const { rufe, fetcher } = horcher();
    const erg = await notizDazuAusFormular(
      formular({ typ: 'projekt', ref: 'saganta', label: 'Saganta', titel: '  ', inhalt: ' \n ' }),
      anschluss(fetcher),
    );
    expect(erg.ok).toBe(false);
    expect(rufe).toHaveLength(0);
  });

  it('lehnt einen unbekannten Typ ab, ohne etwas zu senden', async () => {
    const { rufe, fetcher } = horcher();
    const erg = await notizDazuAusFormular(
      formular({ typ: 'raumschiff', ref: 'x', titel: 'T' }),
      anschluss(fetcher),
    );
    expect(erg.ok).toBe(false);
    expect(rufe).toHaveLength(0);
  });

  it('lehnt ein fehlendes Gegenstück ab', async () => {
    const { rufe, fetcher } = horcher();
    const erg = await notizDazuAusFormular(
      formular({ typ: 'termin', ref: '', titel: 'T' }),
      anschluss(fetcher),
    );
    expect(erg.ok).toBe(false);
    expect(rufe).toHaveLength(0);
  });

  it('kürzt ein zu langes Label auf das Maß der notizen-api', async () => {
    // Sonst antwortet sie mit 422, und das sieht in der Oberflaeche aus wie
    // „Verknuepfen geht nicht", obwohl nur die Beschriftung zu lang war.
    const { rufe, fetcher } = horcher([{ status: 201, rumpf: { id: 9, titel: 'T' } }]);
    await notizDazuAusFormular(
      formular({ typ: 'termin', ref: 'e1', label: 'L'.repeat(500), titel: 'T' }),
      anschluss(fetcher),
    );
    const rumpf = rufe[0]!.rumpf as { verknuepfung: { label: string } };
    expect(rumpf.verknuepfung.label).toHaveLength(300);
  });

  it('meldet einen Ausfall als Fehler statt stillschweigend Erfolg', async () => {
    const { fetcher } = horcher([{ status: 502, rumpf: 'bad gateway' }]);
    const erg = await notizDazuAusFormular(
      formular({ typ: 'termin', ref: 'e1', titel: 'T' }),
      anschluss(fetcher),
    );
    expect(erg.ok).toBe(false);
    if (!erg.ok) {
      expect(erg.fehler).toContain('nicht gespeichert');
      // Der Rohtext der Antwort gehoert nicht auf den Bildschirm.
      expect(erg.fehler).not.toContain('bad gateway');
      expect(erg.fehler).not.toContain('502');
    }
  });

  it('sagt es, wenn die App gar nicht angeschlossen ist', async () => {
    const erg = await notizDazuAusFormular(formular({ typ: 'termin', ref: 'e1', titel: 'T' }), null);
    expect(erg.ok).toBe(false);
  });
});

describe('notizDazuAusFormular: vorhandene Notiz anhängen', () => {
  it('verknüpft statt anzulegen, wenn eine Kennung mitkommt', async () => {
    const { rufe, fetcher } = horcher([{ status: 201, rumpf: { id: 1 } }]);
    const erg = await notizDazuAusFormular(
      formular({ typ: 'aufgabe', ref: '12', label: 'Angebot', notiz: '5', titel: 'Alte Notiz' }),
      anschluss(fetcher),
    );
    expect(erg.ok).toBe(true);
    expect(rufe).toHaveLength(1);
    expect(rufe[0]!.url).toBe('http://notizen-api:8000/api/notizen/5/verknuepfungen'); // gitleaks:allow (URL-Pfad, kein Schluessel)
    expect(rufe[0]!.rumpf).toEqual({ typ: 'aufgabe', ref: '12', label: 'Angebot' });
  });

  it('weist eine unsinnige Notiz-Kennung ab', async () => {
    const { rufe, fetcher } = horcher();
    for (const notiz of ['0', '-3', 'abc', '2.5']) {
      const erg = await notizDazuAusFormular(
        formular({ typ: 'aufgabe', ref: '12', notiz }),
        anschluss(fetcher),
      );
      expect(erg.ok, notiz).toBe(false);
    }
    expect(rufe).toHaveLength(0);
  });
});

describe('Lesen bleibt fail-soft', () => {
  it('unterscheidet „keine Notizen" von „antwortet nicht"', async () => {
    const leer = horcher([{ status: 200, rumpf: {} }]);
    expect(await notizenZu('aufgabe', ['a-1'], anschluss(leer.fetcher))).toEqual({
      nach: {},
      stumm: false,
    });

    // Ohne `stumm` sieht ein Ausfall genauso aus wie ein leerer Bestand,
    // und die Oberflaeche behauptet dann etwas, das sie nicht weiss.
    const tot = horcher([{ status: 503, rumpf: '' }]);
    expect(await notizenZu('aufgabe', ['a-1'], anschluss(tot.fetcher))).toEqual({
      nach: {},
      stumm: true,
    });
  });

  it('fragt ohne Kennungen gar nicht und ist nicht stumm', async () => {
    const { rufe, fetcher } = horcher();
    expect(await notizenZu('aufgabe', [], anschluss(fetcher))).toEqual({ nach: {}, stumm: false });
    expect(await notizenZu('aufgabe', ['', ''], anschluss(fetcher))).toEqual({
      nach: {},
      stumm: false,
    });
    expect(rufe).toHaveLength(0);
  });

  it('fragt jede Kennung nur einmal und deckelt bei 200', async () => {
    const { rufe, fetcher } = horcher([{ rumpf: {} }]);
    await notizenZu('aufgabe', ['a', 'a', 'b'], anschluss(fetcher));
    expect(new URL(rufe[0]!.url).searchParams.get('refs')).toBe('a,b');

    const viele = horcher([{ rumpf: {} }]);
    await notizenZu('aufgabe', Array.from({ length: 250 }, (_, i) => `a-${i}`), anschluss(viele.fetcher));
    const refs = new URL(viele.rufe[0]!.url).searchParams.get('refs')!.split(',');
    expect(refs).toHaveLength(200);
  });

  it('lässt leere Trefferlisten weg', async () => {
    // Die Sammelroute meldet „keine Notiz" durch einen fehlenden Schluessel.
    // Eine leere Liste mitzuschleppen hiesse, dass die Gegenseite zwischen
    // „nichts" und „etwas, das verschwunden ist" nicht unterscheiden kann.
    const { fetcher } = horcher([
      { rumpf: { 'a-1': [{ id: 1, titel: 'X' }], 'a-2': [], 'a-3': null } },
    ]);
    const { nach } = await notizenZu('aufgabe', ['a-1', 'a-2', 'a-3'], anschluss(fetcher));
    expect(Object.keys(nach)).toEqual(['a-1']);
  });

  it('gibt bei Ausfall leere Listen zurück, statt die Seite zu kippen', async () => {
    const { fetcher } = horcher([{ status: 500, rumpf: '' }]);
    expect(await notizenZuEinem('termin', 'e1', anschluss(fetcher))).toEqual([]);
    expect(await notizenSuchen('x', anschluss(fetcher))).toEqual([]);
  });

  it('liest ohne Anschluss gar nicht', async () => {
    expect(await notizenZuEinem('termin', 'e1', null)).toEqual([]);
    expect(await notizenSuchen('x', null)).toEqual([]);
    expect(await notizenZu('termin', ['e1'], null)).toEqual({ nach: {}, stumm: false });
  });
});

describe('istVerknuepfungsTyp', () => {
  it('kennt genau die sechs Typen der notizen-api', () => {
    for (const typ of ['termin', 'aufgabe', 'ziel', 'projekt', 'kontakt', 'brief']) {
      expect(istVerknuepfungsTyp(typ), typ).toBe(true);
    }
    for (const nicht of ['Termin', 'notiz', '', null, undefined, 3]) {
      expect(istVerknuepfungsTyp(nicht)).toBe(false);
    }
  });
});
