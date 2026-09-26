/**
 * Der Tageskontext aus dem Kalender.
 *
 * Warum das hier steht und nicht im Kalender: der Tagestyp ist dort kein
 * eigenes Feld, sondern ein Termin in einem der vier Steuerkalender
 * (`daytype-arbeit-…`, `daytype-urlaub-…` und so fort). Ein einziger Abruf des
 * Tagesfensters liefert deshalb beides auf einmal, den Tagestyp und die
 * wirklichen Termine, wenn man sie auseinandersortiert. Genau das tut diese
 * Datei, und zwar nach derselben Erkennungsregel wie
 * `kalender-bff/app/routes_feierabend.py` (`calendar_id` beginnt mit
 * `daytype-`).
 *
 * ★ Erkannt wird an der Kalender-Kennung, nicht am Titel. Ein Termin, den
 * jemand "Urlaub" nennt, ist kein Tagestyp, und ein Tagestyp bleibt einer,
 * auch wenn sein Titel sich einmal aendert.
 *
 * Der Kontext dient dem Erinnern beim Schreiben. Er fliesst in keine
 * Auswertung und wird nirgends gespeichert: was im Eintrag landet, hat der
 * Schreibende selbst getippt.
 */

export interface Termin {
  titel: string;
  von: string | null;
  bis: string | null;
  ganztags: boolean;
}

export interface Tageskontext {
  tagestyp: string | null;
  termine: Termin[];
}

interface RohEvent {
  title?: unknown;
  calendar_id?: unknown;
  start?: unknown;
  end?: unknown;
  start_at?: unknown;
  end_at?: unknown;
  all_day?: unknown;
}

function alsText(wert: unknown): string {
  return typeof wert === 'string' ? wert : '';
}

/** "2026-09-06T07:00:00" wird zu "07:00". Naive Zeiten sind Berliner Wanduhr. */
function uhrzeit(iso: unknown): string | null {
  const s = alsText(iso);
  return s.length >= 16 ? s.slice(11, 16) : null;
}

export function kontextAusEreignissen(ereignisse: unknown): Tageskontext {
  if (!Array.isArray(ereignisse)) return { tagestyp: null, termine: [] };

  let tagestyp: string | null = null;
  const termine: Termin[] = [];

  for (const roh of ereignisse as RohEvent[]) {
    const kalender = alsText(roh?.calendar_id);
    const titel = alsText(roh?.title).trim();

    if (kalender.startsWith('daytype-')) {
      // Der erste gewinnt. Der Kalender loest Mehrfachbelegungen bereits nach
      // Prioritaet auf (feiertag > krank > urlaub > schule > arbeit), hier
      // wird nicht nachgerechnet: eine zweite Tagestyp-Logik ist ausdruecklich
      // verboten (Root-Policy).
      if (!tagestyp) tagestyp = titel || (kalender.replace(/^daytype-/, '').split('-')[0] ?? null);
      continue;
    }
    if (kalender.startsWith('system-geburtstage')) {
      termine.push({ titel, von: null, bis: null, ganztags: true });
      continue;
    }

    const von = uhrzeit(roh?.start_at ?? roh?.start);
    termine.push({
      titel: titel || 'Ohne Titel',
      von,
      bis: uhrzeit(roh?.end_at ?? roh?.end),
      ganztags: roh?.all_day === true || von === null,
    });
  }

  return { tagestyp, termine };
}
