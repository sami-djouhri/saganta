/**
 * Der eine Weg, aus einer anderen App eine Notiz anzulegen und zu lesen.
 *
 * **Warum dieses Paket existiert.** Am 2026-10-24 war gemessen: sechs
 * Verknüpfungstypen gebaut, im BFF auflösbar, und **null** benutzt. Der Grund
 * war nicht fehlende Funktion, sondern die Richtung. Niemand sitzt in den
 * Notizen und sucht einen Termin; man sitzt im Kalender und will etwas
 * notieren. Der Knopf gehört also auf die andere Seite, und zwar in vier Apps.
 *
 * ⚠️ Vier Apps, vier Oberflächen, aber nur EIN Weg zum Anlegen. Wenn jede App
 * ihren eigenen Aufruf baut, driften sie: eine schneidet das Label anders ab,
 * eine vergisst `fail-soft`, eine schickt zwei Aufrufe statt einem. Deshalb
 * liegt hier die ganze Mechanik und in den Apps nur der Aufruf.
 *
 * Zwei Entscheidungen, die das Paket trägt:
 *
 * - **Kein `$env`, keine SvelteKit-Abhängigkeit.** Basis und Geheimnis kommen
 *   als Werte herein (`anschlussAus`). Dadurch ist alles hier ohne laufenden
 *   Server testbar, und die Variablennamen stehen an genau einer Stelle statt
 *   in drei Apps.
 * - **Lesen ist fail-soft, Schreiben nicht.** Fällt die notizen-api aus,
 *   verliert eine Aufgabenliste ihre Notiz-Hinweise und bleibt bedienbar; ein
 *   fehlgeschlagenes Anlegen muss dagegen als Fehler sichtbar werden, sonst
 *   tippt jemand eine Notiz und sie ist weg.
 */
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import {
  LABEL_MAX,
  TITEL_MAX,
  istVerknuepfungsTyp,
  type NotizKurz,
  type VerknuepfungsTyp,
  type Ziel,
} from './typen.js';

export interface Anschluss {
  basis: string;
  secret: string;
  user: SagantaUser;
  fetcher: typeof fetch;
}

/** Die Zielgruppe des Tokens. Muss zur `aud`-Prüfung der notizen-api passen. */
export const NOTIZEN_API_AUDIENCE = 'notizen-api';

/**
 * Anschluss aus der Umgebung bauen, oder `null`, wenn er nicht konfiguriert ist.
 *
 * `null` ist ein gültiger Zustand und kein Fehler: eine App darf ohne
 * Notizen-Anschluss laufen (etwa in der Entwicklung). Die Oberfläche zeigt den
 * Knopf dann nicht, statt ihn anzubieten und beim Klick zu scheitern.
 */
export function anschlussAus(
  umgebung: Record<string, string | undefined>,
  user: SagantaUser | null | undefined,
  fetcher: typeof fetch,
): Anschluss | null {
  const basis = umgebung.NOTIZEN_API_BASE_URL;
  const secret = umgebung.SAGANTA_BACKEND_SECRET;
  if (!basis || !secret || !user) return null;
  return { basis: basis.replace(/\/$/, ''), secret, user, fetcher };
}

function token(a: Anschluss): string {
  return issueBackendToken({
    user: a.user,
    secret: a.secret,
    audience: NOTIZEN_API_AUDIENCE,
    ttlSeconds: 60,
  });
}

async function api<T>(a: Anschluss, pfad: string, init: RequestInit = {}): Promise<T> {
  const res = await a.fetcher(`${a.basis}${pfad}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token(a)}`,
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const rumpf = await res.text().catch(() => '');
    throw new Error(`notizen-api ${res.status}: ${rumpf.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// --- Lesen (fail-soft) ---------------------------------------------------

/**
 * Notizen zu **mehreren** Gegenstücken auf einmal.
 *
 * Ein Aufruf je Zeile wäre bei sechzig offenen Aufgaben ein Sturm von
 * sechzig Anfragen; genau daran ist am 2026-09-13 schon einmal eine App-Kette
 * in den Anfragedeckel des Gegenübers gelaufen. Die Sammelroute der
 * notizen-api ist für diesen Fall gebaut.
 *
 * `stumm` unterscheidet „keine Notizen verknüpft" von „die notizen-api
 * antwortet nicht". Ohne diesen Unterschied sieht ein Ausfall wie ein leerer
 * Bestand aus, und die Oberfläche behauptet etwas, das sie nicht weiß.
 */
export async function notizenZu(
  typ: VerknuepfungsTyp,
  refs: readonly string[],
  a: Anschluss | null,
): Promise<{ nach: Record<string, NotizKurz[]>; stumm: boolean }> {
  if (!a || refs.length === 0) return { nach: {}, stumm: false };
  // Die Route deckelt bei 200 Kennungen. Mehr Zeilen auf einem Bildschirm gibt
  // es nicht; wer doch dort landet, bekommt für den Rest keine Notiz-Marke
  // statt einer 400 für die ganze Seite.
  const kennungen = [...new Set(refs.filter(Boolean))].slice(0, 200);
  if (kennungen.length === 0) return { nach: {}, stumm: false };
  try {
    const treffer = await api<Record<string, NotizKurz[]>>(
      a,
      `/api/notizen/verknuepft?typ=${encodeURIComponent(typ)}&refs=${encodeURIComponent(kennungen.join(','))}`,
    );
    const nach: Record<string, NotizKurz[]> = {};
    for (const [ref, notizen] of Object.entries(treffer ?? {})) {
      if (Array.isArray(notizen) && notizen.length > 0) nach[ref] = notizen;
    }
    return { nach, stumm: false };
  } catch {
    return { nach: {}, stumm: true };
  }
}

/** Notizen zu genau einem Gegenstück. Für eine Detailansicht. */
export async function notizenZuEinem(
  typ: VerknuepfungsTyp,
  ref: string,
  a: Anschluss | null,
): Promise<NotizKurz[]> {
  if (!a || !ref) return [];
  try {
    return (
      (await api<NotizKurz[]>(
        a,
        `/api/notizen?verknuepft=${encodeURIComponent(`${typ}:${ref}`)}`,
      )) ?? []
    );
  } catch {
    return [];
  }
}

/** Auswahl-Liste für „vorhandene Notiz anhängen": zuletzt geändert, oder gesucht. */
export async function notizenSuchen(suche: string, a: Anschluss | null): Promise<NotizKurz[]> {
  if (!a) return [];
  const frage = new URLSearchParams({ limit: '20' });
  if (suche.trim()) frage.set('q', suche.trim());
  try {
    return (await api<NotizKurz[]>(a, `/api/notizen?${frage}`)) ?? [];
  } catch {
    return [];
  }
}

// --- Schreiben (Fehler sind sichtbar) ------------------------------------

export interface Angelegt {
  id: number;
  titel: string;
}

/**
 * Notiz anlegen, direkt am Gegenstück.
 *
 * **Ein Aufruf, nicht zwei.** Die notizen-api legt Notiz und Verknüpfung in
 * einer Transaktion an (`NotizAn.verknuepfung`). Zwei Aufrufe könnten zwischen
 * sich abbrechen, und was dann bliebe, wäre eine Notiz ohne Bezug: von der
 * Gegenseite nicht zu finden und im Notizen-Bestand ein scheinbar
 * versehentlicher Eintrag.
 */
export async function notizAnlegenZu(
  wunsch: { titel: string; inhalt?: string; ziel: Ziel },
  a: Anschluss,
): Promise<Angelegt> {
  const angelegt = await api<{ id: number; titel: string }>(a, '/api/notizen', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      titel: wunsch.titel.slice(0, TITEL_MAX),
      inhalt: wunsch.inhalt ?? '',
      verknuepfung: {
        typ: wunsch.ziel.typ,
        ref: wunsch.ziel.ref,
        label: wunsch.ziel.label.slice(0, LABEL_MAX),
      },
    }),
  });
  return { id: angelegt.id, titel: angelegt.titel };
}

/** Eine **vorhandene** Notiz an ein Gegenstück hängen. */
export async function notizVerknuepfen(notizId: number, ziel: Ziel, a: Anschluss): Promise<void> {
  await api(a, `/api/notizen/${notizId}/verknuepfungen`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      typ: ziel.typ,
      ref: ziel.ref,
      label: ziel.label.slice(0, LABEL_MAX),
    }),
  });
}

// --- Der Weg aus einem Formular ------------------------------------------

export type FormularErgebnis = { ok: true; notiz: Angelegt } | { ok: false; fehler: string };

/**
 * Felder lesen, prüfen, anlegen. Das ist der EINE Weg, den alle Apps nehmen.
 *
 * Erwartete Felder: `typ`, `ref`, `label`, `titel`, `inhalt`. Ist zusätzlich
 * `notiz` gesetzt, wird diese vorhandene Notiz verknüpft statt einer neuen
 * angelegt. Beides liegt hier, damit der Knopf und die Suche nicht zwei Wege
 * mit zwei Fehlerbildern werden.
 *
 * Eine Notiz ganz ohne Titel UND ohne Text wird abgelehnt. Sonst erzeugt ein
 * versehentlicher Klick auf „Anlegen" einen leeren Eintrag, und leere Einträge
 * sind genau der Grund, warum man einem Notizbestand irgendwann nicht mehr
 * traut. Der Titel ist beim Öffnen des Dialogs mit der Beschriftung des
 * Gegenstücks vorbelegt, dieser Fall tritt also nur ein, wenn jemand ihn
 * ausdrücklich leert.
 */
export async function notizDazuAusFormular(
  formular: {
    get(name: string): FormDataEntryValue | null;
  },
  a: Anschluss | null,
): Promise<FormularErgebnis> {
  if (!a) return { ok: false, fehler: 'Die Notizen-App ist hier nicht angeschlossen.' };

  const feld = (name: string): string => {
    const wert = formular.get(name);
    return typeof wert === 'string' ? wert.trim() : '';
  };

  const typ = feld('typ');
  if (!istVerknuepfungsTyp(typ)) {
    return { ok: false, fehler: 'Unbekannte Art der Verknüpfung.' };
  }
  const ref = feld('ref');
  if (!ref) return { ok: false, fehler: 'Es fehlt, woran die Notiz hängen soll.' };
  const ziel: Ziel = { typ, ref, label: feld('label') };

  // Eine vorhandene Notiz anhängen: derselbe Knopf, derselbe Weg.
  const vorhanden = feld('notiz');
  if (vorhanden) {
    const id = Number(vorhanden);
    if (!Number.isInteger(id) || id <= 0) {
      return { ok: false, fehler: 'Diese Notiz gibt es nicht.' };
    }
    try {
      await notizVerknuepfen(id, ziel, a);
      return { ok: true, notiz: { id, titel: feld('titel') } };
    } catch (fehler) {
      return { ok: false, fehler: lesbar(fehler) };
    }
  }

  const titel = feld('titel');
  const roh = formular.get('inhalt');
  const inhalt = typeof roh === 'string' ? roh : '';
  if (!titel && !inhalt.trim()) {
    return { ok: false, fehler: 'Bitte einen Titel oder einen Text eingeben.' };
  }

  try {
    const notiz = await notizAnlegenZu(
      { titel: titel || inhalt.trim().slice(0, 80), inhalt, ziel },
      a,
    );
    return { ok: true, notiz };
  } catch (fehler) {
    return { ok: false, fehler: lesbar(fehler) };
  }
}

/**
 * Aus einem technischen Fehler eine Zeile machen, die jemandem etwas sagt.
 *
 * Der Rohtext (`notizen-api 502: <html>`) gehört ins Log, nicht auf den
 * Bildschirm: dort ist er nicht nur unverständlich, er kann auch Innenleben
 * nach draußen tragen.
 */
function lesbar(fehler: unknown): string {
  const text = String(fehler);
  if (/\b4\d\d\b/.test(text)) {
    return 'Die Notiz wurde nicht angenommen. Bitte Eingaben prüfen.';
  }
  return 'Die Notizen-App antwortet gerade nicht. Die Notiz wurde nicht gespeichert.';
}
