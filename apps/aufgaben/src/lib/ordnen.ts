/**
 * Reihenfolge und Gruppierung der Aufgaben.
 *
 * Bewusst reine Funktionen ohne Zugriff auf Netz oder Uhr: das „heute" kommt
 * als Parameter herein. Sonst waere jeder Test zeitabhaengig, und eine
 * Datumsgrenze liesse sich nur um Mitternacht pruefen.
 *
 * Alle Datumsangaben sind **Etiketten**, keine Zeitpunkte. Verglichen wird
 * deshalb auf Zeichenketten (ISO sortiert lexikografisch richtig) und nie ueber
 * `new Date(...)`. Ein `new Date('2026-03-29')` ist UTC-Mitternacht, und an den
 * beiden Zeitumstellungen im Jahr rutscht eine Tagesrechnung darueber um einen
 * Tag. Dieselbe Entscheidung wie in `apps/tagebuch/src/lib/datum.ts`.
 */
import type { Aufgabe, Unteraufgabe } from './aufgaben-bff';

// Drei Worte seit dem Aufgaben-Dienst (2026-11-03). `dringend` bleibt unten in Rang
// und Stil, damit ein Altbestand nicht ohne Farbe dasteht.
export const PRIORITAETEN = ['hoch', 'mittel', 'niedrig'] as const;
export type Prioritaet = (typeof PRIORITAETEN)[number];

const PRIO_RANG: Record<string, number> = {
  dringend: 0,
  hoch: 1,
  mittel: 2,
  niedrig: 3,
};

/** Farbe und Beschriftung je Prioritaet. Eine Quelle fuer alle Ansichten. */
export const PRIO_STIL: Record<string, { label: string; klasse: string }> = {
  dringend: { label: 'Dringend', klasse: 'border-fehler/60 text-fehler' },
  hoch: { label: 'Hoch', klasse: 'border-warnung/60 text-warnung' },
  mittel: { label: 'Mittel', klasse: 'border-border text-muted' },
  niedrig: { label: 'Niedrig', klasse: 'border-border text-muted' },
};

/**
 * Energiebedarf einer Aufgabe.
 *
 * ⚠️ Die Werte sind **englisch**, im Gegensatz zur Prioritaet. So steht es im
 * nativen Kalender (`backend/schemas.py: _ENERGY = ^(low|medium|high)$`), waehrend
 * `priority` dort deutsch ist. Der Sprachmix stammt aus dem Bestand; er wird hier
 * nicht umbenannt, sondern nur an dieser einen Stelle uebersetzt. Wer ihn
 * stillschweigend eindeutscht, schickt Werte hoch, die das Muster nicht
 * annimmt, und bekommt eine 422 ohne erkennbaren Bezug.
 */
export const ENERGIEN = ['low', 'medium', 'high'] as const;

export const ENERGIE_STIL: Record<string, { label: string; symbol: string }> = {
  high: { label: 'anstrengend', symbol: 'zap' },
  medium: { label: 'mittel', symbol: 'battery' },
  low: { label: 'nebenbei', symbol: 'armchair' },
};

export function prioRang(p: string | null | undefined): number {
  return PRIO_RANG[p ?? 'mittel'] ?? 2;
}

/** Ist die Aufgabe offen? `completed` und `status` koennen beide sprechen. */
export function istOffen(a: Aufgabe): boolean {
  return !a.completed && a.status !== 'done' && a.status !== 'cancelled';
}

/**
 * Faellig heute oder frueher.
 *
 * Eine Aufgabe **ohne** Faelligkeit ist nie ueberfaellig: sie liegt im Pool und
 * wartet darauf, geplant zu werden. Wer sie mitzaehlt, macht aus jedem
 * gesammelten Gedanken eine Mahnung.
 */
export function istFaellig(a: Aufgabe, heute: string): boolean {
  return !!a.due_date && a.due_date <= heute;
}

export function istUeberfaellig(a: Aufgabe, heute: string): boolean {
  return !!a.due_date && a.due_date < heute;
}

/** Fuer heute eingeplant: entweder ein Zeitfenster oder ein Plantag. */
export function istHeuteGeplant(a: Aufgabe, heute: string): boolean {
  // Auch ein vergangener Tag: was gestern dran war und liegen blieb, gehoert
  // auf heute (wie in der Android-App und im Planer, seit 2026-11-03).
  if (a.planned_date && a.planned_date <= heute) return true;
  return !!a.scheduled_start && a.scheduled_start.slice(0, 10) === heute;
}

/**
 * Gehoert die Aufgabe heute auf den Tisch?
 *
 * Drei Gruende, und alle drei sind bewusst getrennt von „alles Offene": faellig,
 * eingeplant, oder ein Tagesziel haengt daran.
 */
export function gehoertZuHeute(a: Aufgabe, heute: string): boolean {
  return istOffen(a) && (istFaellig(a, heute) || istHeuteGeplant(a, heute) || !!a.goal_id);
}

/**
 * Sortierung fuer die Tagesansicht.
 *
 * Zuerst, was eine Uhrzeit hat, in ihrer Reihenfolge: der Tag laeuft von oben
 * nach unten ab. Danach das Ungeplante nach Dringlichkeit. Eine Liste, die
 * Geplantes und Ungeplantes vermischt, zwingt zum Suchen, was als naechstes
 * kommt.
 */
export function nachTagesablauf(heute: string) {
  return (a: Aufgabe, b: Aufgabe): number => {
    const za = zeitAm(a, heute);
    const zb = zeitAm(b, heute);
    if (za && zb) return za.localeCompare(zb);
    if (za) return -1;
    if (zb) return 1;
    return nachDringlichkeit(a, b);
  };
}

function zeitAm(a: Aufgabe, heute: string): string | null {
  if (a.scheduled_start && a.scheduled_start.slice(0, 10) === heute) {
    return a.scheduled_start.slice(11, 16);
  }
  if (a.due_date === heute && a.due_time) return a.due_time;
  return null;
}

/**
 * Sortierung fuer alle Listen ohne Tagesbezug.
 *
 * Prioritaet schlaegt Datum, Datum schlaegt Titel. Aufgaben **ohne**
 * Faelligkeit landen hinter den datierten (Platzhalter `9999-…`), nicht davor:
 * ein Termin ist ein Versprechen, ein Pool-Eintrag ist eine Absicht.
 */
export function nachDringlichkeit(a: Aufgabe, b: Aufgabe): number {
  const pa = prioRang(a.priority);
  const pb = prioRang(b.priority);
  if (pa !== pb) return pa - pb;
  const da = a.due_date ?? '9999-99-99';
  const db = b.due_date ?? '9999-99-99';
  if (da !== db) return da.localeCompare(db);
  return (a.title ?? '').localeCompare(b.title ?? '', 'de');
}

export interface Gruppe {
  schluessel: string;
  titel: string;
  /** Icon-Name aus der Registry in `@saganta/ui`. */
  symbol: string;
  aufgaben: Aufgabe[];
  /** Nur bei Bereichen: nach aussen neutral. */
  vertraulich?: boolean;
}

/**
 * Die Tagesansicht in vier Gruppen.
 *
 * Die Reihenfolge ist die Reihenfolge der Aufmerksamkeit: was schon zu spaet
 * ist, dann was heute ansteht, dann was fest im Kalender liegt, dann der Rest.
 * Leere Gruppen fallen weg, damit ein ruhiger Tag auch ruhig aussieht.
 */
export function tagesGruppen(alle: Aufgabe[], heute: string): Gruppe[] {
  const offen = alle.filter(istOffen);
  const gruppen: Gruppe[] = [
    {
      schluessel: 'ueberfaellig',
      titel: 'Überfällig',
      symbol: 'alert-triangle',
      aufgaben: offen.filter((a) => istUeberfaellig(a, heute)),
    },
    {
      schluessel: 'heute',
      titel: 'Heute fällig',
      symbol: 'flag',
      aufgaben: offen.filter((a) => a.due_date === heute),
    },
    {
      schluessel: 'geplant',
      titel: 'Heute eingeplant',
      symbol: 'calendar-clock',
      aufgaben: offen.filter((a) => istHeuteGeplant(a, heute) && a.due_date !== heute),
    },
  ];
  const schonDrin = new Set(gruppen.flatMap((g) => g.aufgaben.map((a) => a.id)));
  gruppen.push({
    schluessel: 'ziel',
    titel: 'Zu einem Tagesziel',
    symbol: 'target',
    aufgaben: offen.filter((a) => a.goal_id && !schonDrin.has(a.id)),
  });
  for (const g of gruppen) g.aufgaben.sort(nachTagesablauf(heute));
  return gruppen.filter((g) => g.aufgaben.length > 0);
}

/**
 * Gehoert die Aufgabe zu einem Projekt?
 *
 * Projektaufgaben stehen unter „Projekte", nicht im Vorrat und nicht im
 * Ausblick der Startseite. Auf „Heute" kommen sie nur, wenn sie faellig oder
 * eingeplant sind (`tagesGruppen` fragt genau das). Sonst gehen die eigenen
 * Aufgaben zwischen den Entwicklungsaufgaben unter (ZIELBILD 108).
 */
export function istProjektaufgabe(a: Aufgabe): boolean {
  return !!a.project_id;
}

/** Ein lesbarer Name aus dem Slug, solange das ProjectDeck keinen liefert. */
export function nameAusSlug(slug: string): string {
  return slug
    .split('-')
    .filter(Boolean)
    .map((t) => t.charAt(0).toUpperCase() + t.slice(1))
    .join(' ');
}

/**
 * Die Projektliste fuer Gruppen und Auswahl.
 *
 * Alle laufenden Projekte des ProjectDecks, dazu jeder Slug, an dem eine
 * Aufgabe haengt, auch wenn das ProjectDeck ihn nicht (mehr) kennt oder nicht
 * erreichbar war. Kennung ist der Slug, so wie der Aufgaben-Dienst ihn traegt.
 */
export function projekteAus(
  aufgaben: Aufgabe[],
  deck: { slug: string; name: string; status?: string }[],
): { id: string; slug: string; name: string; status?: string }[] {
  const nach = new Map<string, { id: string; slug: string; name: string; status?: string }>();
  for (const p of deck) {
    if (p.status === 'archived' || p.status === 'shutdown') continue;
    nach.set(p.slug, { id: p.slug, slug: p.slug, name: p.name, status: p.status });
  }
  for (const a of aufgaben) {
    const slug = a.project_id;
    if (!slug || nach.has(slug)) continue;
    const bekannt = deck.find((p) => p.slug === slug);
    nach.set(slug, { id: slug, slug, name: bekannt?.name ?? nameAusSlug(slug), status: bekannt?.status });
  }
  return [...nach.values()].sort((x, y) => x.name.localeCompare(y.name, 'de'));
}

/**
 * Der Pool: offen, ohne Termin und ohne Planung.
 *
 * Das ist die Menge, aus der „Tag planen" schoepft. Sie getrennt zu zeigen ist
 * der Unterschied zwischen einer Liste und einem Vorrat.
 */
export function pool(alle: Aufgabe[], heute: string): Aufgabe[] {
  return alle
    // Ohne Frist UND ohne Tag: eine auf naechste Woche geschobene Aufgabe
    // ist kein Vorrat, sonst schoepfte „Tag planen" sie heute wieder ab.
    .filter((a) => istOffen(a) && !istProjektaufgabe(a) && !gehoertZuHeute(a, heute) && !a.due_date && !a.planned_date)
    .sort(nachDringlichkeit);
}

/** Offen, datiert, aber noch nicht heute. Der Blick nach vorn. */
export function demnaechst(alle: Aufgabe[], heute: string, tage = 7): Aufgabe[] {
  const grenze = tagePlus(heute, tage);
  return alle
    .filter((a) => istOffen(a) && !istProjektaufgabe(a) && !!a.due_date && a.due_date > heute && a.due_date <= grenze)
    .sort(nachDringlichkeit);
}

/**
 * Datum plus n Tage, rein auf Zeichenketten.
 *
 * `Date.UTC` rechnet ohne Zeitzone, also ohne Sommerzeitsprung; das Ergebnis
 * wird sofort wieder zum Etikett.
 */
export function tagePlus(datum: string, tage: number): string {
  const [j, m, t] = datum.split('-').map(Number);
  const ms = Date.UTC(j || 1970, (m || 1) - 1, t || 1) + tage * 86_400_000;
  return new Date(ms).toISOString().slice(0, 10);
}

/** Gruppierung nach Projekt. Ohne Projekt kommt zuletzt. */
export function nachProjekt(
  alle: Aufgabe[],
  projekte: { id: string; name: string }[],
): Gruppe[] {
  const namen = new Map(projekte.map((p) => [p.id, p.name]));
  const eimer = new Map<string, Aufgabe[]>();
  for (const a of alle.filter(istOffen)) {
    const schluessel = a.project_id ?? '';
    eimer.set(schluessel, [...(eimer.get(schluessel) ?? []), a]);
  }
  const gruppen: Gruppe[] = [];
  for (const [schluessel, aufgaben] of eimer) {
    if (!schluessel) continue;
    gruppen.push({
      schluessel,
      titel: namen.get(schluessel) ?? 'Unbekanntes Projekt',
      symbol: 'folder',
      aufgaben: aufgaben.sort(nachDringlichkeit),
    });
  }
  gruppen.sort((a, b) => a.titel.localeCompare(b.titel, 'de'));
  const ohne = eimer.get('') ?? [];
  if (ohne.length > 0) {
    gruppen.push({
      schluessel: '',
      titel: 'Ohne Projekt',
      symbol: 'circle',
      aufgaben: ohne.sort(nachDringlichkeit),
    });
  }
  return gruppen;
}

/** Minuten menschlich. `90` wird zu `1,5 h`, `45` bleibt `45 min`. */
export function dauer(minuten: number | null | undefined): string {
  if (!minuten) return '';
  if (minuten < 60) return `${Math.round(minuten)} min`;
  const stunden = Math.round((minuten / 60) * 10) / 10;
  return `${String(stunden).replace('.', ',')} h`;
}

/** Ein Turnus in Tagen als kurzes Wort: „wöchentlich“, „alle 14 T“, „monatlich“. */
export function turnusEtikett(tage: number | null | undefined): string {
  if (!tage) return '';
  const worte: Record<number, string> = { 1: 'täglich', 7: 'wöchentlich', 30: 'monatlich', 365: 'jährlich' };
  return worte[tage] ?? `alle ${tage} T`;
}

/** Ein Datum als „Heute", „Morgen", „Gestern" oder `Mo, 15.09.`. */
export function datumsEtikett(datum: string, heute: string): string {
  if (datum === heute) return 'Heute';
  if (datum === tagePlus(heute, 1)) return 'Morgen';
  if (datum === tagePlus(heute, -1)) return 'Gestern';
  const [j, m, t] = datum.split('-').map(Number);
  const d = new Date(Date.UTC(j || 1970, (m || 1) - 1, t || 1));
  const tage = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  return `${tage[d.getUTCDay()]}, ${String(t).padStart(2, '0')}.${String(m).padStart(2, '0')}.`;
}

/**
 * Stand der Unteraufgaben als `erledigt/gesamt`, `null` ohne Liste. Die Zeile
 * zeigt die Zahl, der Dialog die Liste; beide lesen dieselbe Rechnung.
 */
export function unterFortschritt(a: Aufgabe): { erledigt: number; gesamt: number } | null {
  const liste = a.unteraufgaben ?? [];
  if (liste.length === 0) return null;
  return { erledigt: liste.filter((u) => u.erledigt).length, gesamt: liste.length };
}

/**
 * Die Unteraufgaben nach einem Griff aus dem Dialog, als neue Liste. `null`
 * statt leerer Liste, so wie die App es schickt: der Dienst unterscheidet
 * „keine Checkliste" von „leere Checkliste" nicht, und `null` haelt die Spalte
 * sauber.
 */
export function unteraufgabenNach(
  liste: Unteraufgabe[] | null | undefined,
  griff: { art: 'umschalten' | 'entfernen'; index: number } | { art: 'anlegen'; text: string },
): Unteraufgabe[] | null {
  const alt = liste ?? [];
  let neu: Unteraufgabe[];
  if (griff.art === 'anlegen') {
    const text = griff.text.trim();
    neu = text ? [...alt, { text, erledigt: false }] : alt;
  } else if (griff.art === 'umschalten') {
    neu = alt.map((u, i) => (i === griff.index ? { ...u, erledigt: !u.erledigt } : u));
  } else {
    neu = alt.filter((_, i) => i !== griff.index);
  }
  return neu.length ? neu : null;
}
