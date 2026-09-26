/**
 * Die Notizen zu einer Aufgabe, und der Weg, eine anzuhaengen.
 *
 * ★ Die Verknuepfung wird **in der Notizen-App gefuehrt**, nicht hier: dort
 * liegt die Tabelle `verknuepfungen` (`notiz_id`, `typ`, `ref`, `label`), und
 * sie kann auf Termin, Aufgabe, Ziel, Projekt, Kontakt und Brief zeigen. Diese
 * App liest dieselbe Beziehung nur von der anderen Seite.
 *
 * Das ist bewusst so und nicht gespiegelt: eine zweite Tabelle „Notizen zu
 * meinen Aufgaben" waere dieselbe Aussage an zwei Orten, und beim Loeschen
 * einer Notiz bliebe hier eine Karteileiche stehen. Die Rueckwaerts-Suche
 * (`?verknuepft=aufgabe:<id>`) gab es in der notizen-api bereits; sie wurde
 * genau fuer diesen Fall gebaut.
 *
 * Alles hier ist **fail-soft**: faellt die notizen-api aus, verliert die
 * Aufgabenliste ihre Notiz-Hinweise, bleibt aber vollstaendig bedienbar. Ein
 * Fehler beim Nachschlagen einer Nebeninformation darf die Hauptsache nicht
 * kippen.
 */
import { env } from '$env/dynamic/private';
import { issueBackendToken, type SagantaUser } from '@saganta/auth';

export const NOTIZEN_API_AUDIENCE = 'notizen-api';

/** Eine Notiz, soweit die Aufgabenliste sie anzeigt. */
export interface NotizKurz {
  id: number;
  titel: string;
  tags?: string;
  geaendert_am?: string;
}

function token(user: SagantaUser, secret: string): string {
  return issueBackendToken({ user, secret, audience: NOTIZEN_API_AUDIENCE, ttlSeconds: 60 });
}

async function api<T>(
  pfad: string,
  user: SagantaUser,
  secret: string,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const basis = env.NOTIZEN_API_BASE_URL;
  if (!basis) throw new Error('NOTIZEN_API_BASE_URL ist nicht gesetzt.');
  const res = await fetcher(`${basis.replace(/\/$/, '')}${pfad}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token(user, secret)}`,
      Accept: 'application/json',
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`notizen-api ${res.status}: ${body.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/**
 * Notizen, die auf diese Aufgaben zeigen, als Abbildung Aufgaben-Kennung zu
 * Notizen.
 *
 * ★ Ein Aufruf je Aufgabe waere bei sechzig offenen Aufgaben ein Sturm von
 * sechzig Anfragen, und genau daran ist am 2026-09-13 schon einmal eine Kette
 * in den Anfragedeckel gelaufen (`feedback_anfragedeckel_plus_nachsicht_...`).
 * Deshalb wird **einmal** die Liste aller verknuepften Notizen geholt und hier
 * zugeordnet.
 *
 * Faellt der Aufruf aus, kommt eine leere Abbildung zurueck **und** `stumm` ist
 * gesetzt. Der Unterschied zaehlt: ohne ihn saehe ein Ausfall der notizen-api
 * genauso aus wie „keine Notizen verknuepft".
 */
export async function notizenZuAufgaben(
  aufgabenIds: string[],
  user: SagantaUser,
  secret: string,
  fetcher: typeof fetch,
): Promise<{ nach: Map<string, NotizKurz[]>; stumm: boolean }> {
  const nach = new Map<string, NotizKurz[]>();
  if (aufgabenIds.length === 0 || !env.NOTIZEN_API_BASE_URL) return { nach, stumm: false };

  // Die Route deckelt bei 200 Kennungen. Mehr offene Aufgaben auf einem Bildschirm
  // gibt es nicht; wer doch dort landet, bekommt fuer den Rest keine Notiz-Marke
  // statt einer 400 fuer die ganze Seite.
  const kennungen = aufgabenIds.slice(0, 200);
  try {
    const treffer = await api<Record<string, NotizKurz[]>>(
      `/api/notizen/verknuepft?typ=aufgabe&refs=${encodeURIComponent(kennungen.join(','))}`,
      user,
      secret,
      fetcher,
    );
    for (const [ref, notizen] of Object.entries(treffer ?? {})) {
      if (Array.isArray(notizen) && notizen.length > 0) nach.set(ref, notizen);
    }
    return { nach, stumm: false };
  } catch {
    return { nach, stumm: true };
  }
}

/** Notizen zu genau einer Aufgabe. Fuer die Detailansicht. */
export async function notizenZuAufgabe(
  aufgabeId: string,
  user: SagantaUser,
  secret: string,
  fetcher: typeof fetch,
): Promise<NotizKurz[]> {
  if (!env.NOTIZEN_API_BASE_URL) return [];
  try {
    return (
      (await api<NotizKurz[]>(
        `/api/notizen?verknuepft=${encodeURIComponent(`aufgabe:${aufgabeId}`)}`,
        user,
        secret,
        fetcher,
      )) ?? []
    );
  } catch {
    return [];
  }
}

/** Auswahl-Liste fuer „Notiz anhaengen": die zuletzt geaenderten Notizen. */
export async function notizenSuchen(
  suche: string,
  user: SagantaUser,
  secret: string,
  fetcher: typeof fetch,
): Promise<NotizKurz[]> {
  if (!env.NOTIZEN_API_BASE_URL) return [];
  const frage = new URLSearchParams({ limit: '20' });
  if (suche.trim()) frage.set('q', suche.trim());
  try {
    return (await api<NotizKurz[]>(`/api/notizen?${frage}`, user, secret, fetcher)) ?? [];
  } catch {
    return [];
  }
}

/**
 * Eine Notiz an eine Aufgabe haengen.
 *
 * Das `label` ist eine **Kopie** des Aufgabentitels zum Zeitpunkt des
 * Verknuepfens, so will es das Schema der notizen-api: benennt jemand die
 * Aufgabe um, zeigt die Notiz weiter, worauf sie sich bezog, und die Liste
 * bleibt lesbar, auch wenn diese App gerade nicht antwortet.
 */
export async function notizVerknuepfen(
  notizId: number,
  aufgabeId: string,
  aufgabeTitel: string,
  user: SagantaUser,
  secret: string,
  fetcher: typeof fetch,
): Promise<void> {
  await api(`/api/notizen/${notizId}/verknuepfungen`, user, secret, fetcher, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ typ: 'aufgabe', ref: aufgabeId, label: aufgabeTitel.slice(0, 300) }),
  });
}
