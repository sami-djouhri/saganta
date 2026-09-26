/**
 * Die verknüpfbaren Gegenstücke: Termine, Aufgaben, Ziele, Projekte, Kontakte
 * und Briefe.
 *
 * **Aufgelöst wird hier im BFF, nicht im Backend.** `notizen-api` speichert nur
 * Typ, Kennung und Beschriftung und weiß nichts von Kalender, ProjectDeck oder
 * Briefkasten. Das ist der Grund, warum eine neue Quelle dort keine Zeile
 * kostet, und warum ein Ausfall des Kalenders die Notizen nicht mitreißt: dann
 * fehlt die Suche nach Terminen, die vorhandenen Verknüpfungen bleiben lesbar,
 * weil ihre Beschriftung mitgespeichert ist.
 *
 * Die Antwortformate sind durchgereichte Objekte der jeweiligen Dienste. Sie
 * werden deshalb **tolerant** gelesen (`title` oder `name` oder `titel`): eine
 * harte Feldbindung würde bei der nächsten Umbenennung dort still eine leere
 * Liste liefern, und leer sieht aus wie „nichts gefunden".
 */

import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';
import type { Fundstueck, VerknuepfungsTyp } from './types';

// Beschriftungen und Zieladressen stehen in `verknuepfungen.ts`, sie werden
// auch im Browser gebraucht, und dieses Modul darf dort nie ankommen.

const MAX_TREFFER = 12;

function token(user: SagantaUser, audience: string): string {
  const secret = env.SAGANTA_BACKEND_SECRET;
  if (!secret) throw new Error('SAGANTA_BACKEND_SECRET fehlt');
  return issueBackendToken({ user, secret, audience, ttlSeconds: 60 });
}

async function holen(
  url: string,
  kopf: Record<string, string>,
  fetcher: typeof fetch,
): Promise<unknown> {
  const res = await fetcher(url, { headers: { Accept: 'application/json', ...kopf } });
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json();
}

function alsListe(daten: unknown): Record<string, unknown>[] {
  if (Array.isArray(daten)) return daten as Record<string, unknown>[];
  if (daten && typeof daten === 'object') {
    const items = (daten as { items?: unknown }).items;
    if (Array.isArray(items)) return items as Record<string, unknown>[];
  }
  return [];
}

function text(eintrag: Record<string, unknown>, ...felder: string[]): string {
  for (const feld of felder) {
    const wert = eintrag[feld];
    if (typeof wert === 'string' && wert.trim()) return wert.trim();
    if (typeof wert === 'number') return String(wert);
  }
  return '';
}

function passt(suche: string, ...teile: string[]): boolean {
  if (!suche) return true;
  const nadel = suche.toLowerCase();
  return teile.some((t) => t.toLowerCase().includes(nadel));
}

function datumKurz(roh: string): string {
  if (!roh) return '';
  const d = new Date(roh);
  if (Number.isNaN(d.getTime())) return roh.slice(0, 10);
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// --- einzelne Quellen ----------------------------------------------------

async function termine(
  user: SagantaUser,
  suche: string,
  fetcher: typeof fetch,
): Promise<Fundstueck[]> {
  const basis = env.KALENDER_BFF_BASE_URL ?? 'http://saganta-kalender-bff:8000';
  const kopf = { Authorization: `Bearer ${token(user, 'kalender-bff')}` };
  // Ein Fenster um heute herum: Notizen hängen fast immer an etwas, das
  // ansteht oder gerade war. 120 Tage nach vorn, 60 zurück.
  const heute = new Date();
  const von = new Date(heute.getTime() - 60 * 86_400_000).toISOString().slice(0, 10);
  const bis = new Date(heute.getTime() + 120 * 86_400_000).toISOString().slice(0, 10);
  const daten = await holen(
    `${basis}/api/events/range?start=${von}&end=${bis}&limit=800`,
    kopf,
    fetcher,
  );
  return alsListe(daten)
    .map((e) => ({
      typ: 'termin' as VerknuepfungsTyp,
      ref: text(e, 'id', 'uid'),
      label: text(e, 'title', 'titel', 'name', 'summary') || '(ohne Titel)',
      zusatz: datumKurz(text(e, 'start_at', 'start', 'starts_at')),
    }))
    .filter((t) => t.ref && passt(suche, t.label, t.zusatz ?? ''))
    .slice(0, MAX_TREFFER);
}

async function kalenderListe(
  user: SagantaUser,
  suche: string,
  fetcher: typeof fetch,
  pfad: string,
  typ: VerknuepfungsTyp,
  zusatzFelder: string[],
): Promise<Fundstueck[]> {
  const basis = env.KALENDER_BFF_BASE_URL ?? 'http://saganta-kalender-bff:8000';
  const kopf = { Authorization: `Bearer ${token(user, 'kalender-bff')}` };
  const daten = await holen(`${basis}${pfad}`, kopf, fetcher);
  return alsListe(daten)
    .map((e) => ({
      typ,
      ref: text(e, 'id', 'uid'),
      label: text(e, 'title', 'titel', 'name', 'display_name') || '(ohne Titel)',
      zusatz: text(e, ...zusatzFelder),
    }))
    .filter((t) => t.ref && passt(suche, t.label, t.zusatz ?? ''))
    .slice(0, MAX_TREFFER);
}

async function projekte(
  user: SagantaUser,
  suche: string,
  fetcher: typeof fetch,
): Promise<Fundstueck[]> {
  const basis = env.PROJECTDECK_API_BASE_URL ?? 'http://saganta-projectdeck-api:8000';
  const kopf = { Authorization: `Bearer ${token(user, 'projectdeck-api')}` };
  const daten = await holen(`${basis}/api/projects`, kopf, fetcher);
  return alsListe(daten)
    .map((p) => ({
      typ: 'projekt' as VerknuepfungsTyp,
      // Der Slug ist die sprechende Kennung von ProjectDeck und überlebt eine
      // Umbenennung des Projekts, deshalb er und nicht die Zeilennummer.
      ref: text(p, 'slug', 'id'),
      label: text(p, 'name', 'title') || text(p, 'slug'),
      zusatz: text(p, 'status'),
    }))
    .filter((t) => t.ref && passt(suche, t.label, t.ref))
    .slice(0, MAX_TREFFER);
}

async function briefe(suche: string, fetcher: typeof fetch): Promise<Fundstueck[]> {
  const basis = env.BRIEFKASTEN_BASE_URL;
  const geheim = env.BRIEFKASTEN_INTERNAL_TOKEN;
  if (!basis || !geheim) return [];
  const daten = await holen(
    `${basis.replace(/\/$/, '')}/api/internal/letters?limit=200`,
    { Authorization: `Bearer ${geheim}` },
    fetcher,
  );
  return alsListe(daten)
    .map((b) => ({
      typ: 'brief' as VerknuepfungsTyp,
      ref: text(b, 'id'),
      label: text(b, 'subject', 'title', 'sender') || '(Brief ohne Betreff)',
      zusatz: [text(b, 'sender', 'from_name'), datumKurz(text(b, 'received_at', 'date'))]
        .filter(Boolean)
        .join(' · '),
    }))
    .filter((t) => t.ref && passt(suche, t.label, t.zusatz ?? ''))
    .slice(0, MAX_TREFFER);
}

/**
 * Darf dieser Nutzer die Briefe sehen?
 *
 * Der Briefkasten ist single-tenant: die interne API liest mit einem festen
 * Token über alle Nutzer hinweg. Eine Allowlist hält das zusammen, bis der
 * Briefkasten selbst nach Nutzern trennt. Leer = offen (Entwicklung).
 *
 * ★★ Eigene Variable, seit die Notizen für mehrere Konten offen sind
 * (2026-09-18). Vorher stand hier `ALLOWED_SUBS`, also dieselbe Variable, die
 * beim `notizen-api` entscheidet, wer die App überhaupt benutzen darf. Zwei
 * Bedeutungen an einem Namen: wer das App-Gate öffnet, um einen zweiten Nutzer
 * hereinzulassen, öffnet ihm damit zugleich die Post des Owners, und zwar an
 * einer Stelle, an der niemand sie vermutet, nämlich in der Verknüpfungssuche
 * der Notizen-App.
 *
 * Der Rückfall auf `ALLOWED_SUBS` ist Absicht und fail-closed: wer die neue
 * Variable nicht setzt, behält die bisherige Sperre, statt die Briefe
 * stillschweigend für alle zu öffnen. Er entfällt, sobald der Briefkasten
 * selbst nach `owner_sub` trennt (dann trägt die Trennung dort, nicht hier).
 */
function darfBriefeSehen(user: SagantaUser): boolean {
  const erlaubt = (env.BRIEFE_ALLOWED_SUBS ?? env.ALLOWED_SUBS ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  return erlaubt.length === 0 || erlaubt.includes(user.sub);
}

// --- Sammelsuche ---------------------------------------------------------

export interface SuchErgebnis {
  treffer: Fundstueck[];
  /** Quellen, die gerade nicht antworten, die Oberfläche sagt das ehrlich. */
  stumm: VerknuepfungsTyp[];
}

/**
 * In allen (oder einer) Quelle suchen.
 *
 * Die Quellen werden nebeneinander gefragt und einzeln bewertet: fällt eine
 * aus, fehlen ihre Treffer und sie wird benannt. Ein `Promise.all`, das beim
 * ersten Fehler alles verwirft, würde aus einem hakenden Kalender ein
 * „Verknüpfen geht nicht" machen.
 */
export async function suchen(
  user: SagantaUser,
  suche: string,
  fetcher: typeof fetch,
  nurTyp?: VerknuepfungsTyp,
): Promise<SuchErgebnis> {
  const aufgaben: { typ: VerknuepfungsTyp; lauf: () => Promise<Fundstueck[]> }[] = [
    { typ: 'termin', lauf: () => termine(user, suche, fetcher) },
    {
      typ: 'aufgabe',
      lauf: () =>
        kalenderListe(user, suche, fetcher, '/api/todos', 'aufgabe', ['due_date', 'priority']),
    },
    {
      typ: 'ziel',
      lauf: () => kalenderListe(user, suche, fetcher, '/api/goals', 'ziel', ['period', 'status']),
    },
    { typ: 'projekt', lauf: () => projekte(user, suche, fetcher) },
    {
      typ: 'kontakt',
      lauf: () =>
        kalenderListe(user, suche, fetcher, '/api/contacts', 'kontakt', ['email', 'phone']),
    },
  ];
  if (darfBriefeSehen(user)) {
    aufgaben.push({ typ: 'brief', lauf: () => briefe(suche, fetcher) });
  }

  const gewaehlt = nurTyp ? aufgaben.filter((a) => a.typ === nurTyp) : aufgaben;
  const ergebnisse = await Promise.allSettled(gewaehlt.map((a) => a.lauf()));

  const treffer: Fundstueck[] = [];
  const stumm: VerknuepfungsTyp[] = [];
  ergebnisse.forEach((e, i) => {
    const typ = gewaehlt[i]?.typ;
    if (e.status === 'fulfilled') {
      treffer.push(...e.value);
    } else if (typ) {
      stumm.push(typ);
      console.error(
        '[notizen] Quelle stumm',
        JSON.stringify({ typ, fehler: String(e.reason).slice(0, 200) }),
      );
    }
  });
  return { treffer, stumm };
}
