import { env } from '$env/dynamic/private';
import { fail } from '@sveltejs/kit';
import { issueBackendToken } from '@saganta/auth';
import { LifeOpsClient, type TodayBriefing } from '@saganta/sdk-lifeops';
import { appsFallback, type SagantaApp } from '$lib/apps';
import {
  backendSecret,
  shellApiFetch,
  shellApiToken,
  type ShellApiApp,
  type ShellApiSettings,
} from '$lib/shell-api';
import type { Actions, PageServerLoad } from './$types';

interface AppTile extends SagantaApp {
  badge?: string;
  pinned?: boolean;
}

interface BriefkastenStats {
  total: number;
  active: number;
  archived: number;
  pending_ocr: number;
}

interface AufgabenStand {
  offen: number;
  titel: string[];
}

interface NotizenStand {
  anzahl: number;
}

// Aufgaben und Notizen sind tenant-gebunden: der Nutzer-Token entscheidet, wessen
// Daten kommen. Anders als das Briefing und die Briefkasten-Zahl sind sie deshalb
// bewusst NICHT owner-gated -- jeder Tenant sieht seine eigenen.
//
// Beide werfen im Fehlerfall (wie shellApiFetch, das dominante Muster dieser
// Datei) und werden vom Aufrufer gefangen. Ein stiller `null`-Rueckgabewert waere
// hier falsch: eine fehlende Zeile saehe dann aus wie „nichts offen".
async function ladeAufgaben(
  fetcher: typeof fetch,
  user: Parameters<typeof issueBackendToken>[0]['user'],
  secret: string,
): Promise<AufgabenStand | null> {
  const base = env.KALENDER_BFF_BASE_URL;
  if (!base) return null;
  const token = issueBackendToken({ user, secret, audience: 'kalender-bff', ttlSeconds: 60 });
  // Ohne `include_completed` liefert der BFF nur offene Aufgaben (routes_tasks.py).
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/todos`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`kalender-bff /api/todos: ${res.status}`);
  const liste: unknown = await res.json();
  if (!Array.isArray(liste)) return null;
  return {
    offen: liste.length,
    titel: liste
      .slice(0, 3)
      .map((t) => (t as { title?: string }).title)
      .filter((t): t is string => typeof t === 'string' && t.length > 0),
  };
}

async function ladeNotizen(
  fetcher: typeof fetch,
  user: Parameters<typeof issueBackendToken>[0]['user'],
  secret: string,
): Promise<NotizenStand | null> {
  const base = env.NOTIZEN_API_BASE_URL;
  if (!base) return null;
  const token = issueBackendToken({ user, secret, audience: 'notizen-api', ttlSeconds: 60 });
  // `limit` deckelt nur die Antwortgroesse; gezaehlt wird, was zurueckkommt.
  // Archivierte sind standardmaessig aus (routes_notizen.py: archivierte=False).
  const res = await fetcher(`${base.replace(/\/$/, '')}/api/notizen?limit=100`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`notizen-api /api/notizen: ${res.status}`);
  const liste: unknown = await res.json();
  if (!Array.isArray(liste)) return null;
  return { anzahl: liste.length };
}

async function loadBriefkastenStats(fetcher: typeof fetch): Promise<BriefkastenStats | null> {
  const base = env.BRIEFKASTEN_BASE_URL;
  const token = env.BRIEFKASTEN_INTERNAL_TOKEN;
  // briefkasten interne API akzeptiert NUR den statischen KG_INTERNAL_TOKEN
  // (String-Vergleich in routes_internal._check_token), KEIN better-auth-JWT.
  // Frueher wurde hier faelschlich issueBackendToken(audience:'briefkasten')
  // geschickt → immer 401 → Stats-Badge erschien nie. Gleiches Token wie post.
  if (!base || !token) return null;
  try {
    const res = await fetcher(`${base.replace(/\/$/, '')}/api/internal/stats`, {
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
    });
    if (!res.ok) return null;
    return (await res.json()) as BriefkastenStats;
  } catch {
    return null;
  }
}

export const load: PageServerLoad = async ({ locals, fetch, setHeaders, url }) => {
  // Authentifiziertes, nutzer-spezifisches Dashboard nie zwischenspeichern,
  // verhindert, dass ein (z. B. während Wartung) leer gerendertes Launchpad in
  // Browser-/Edge-Cache hängenbleibt.
  setHeaders({ 'cache-control': 'no-store' });

  // Nicht eingeloggt → öffentliche Landing. Kein Dashboard-Backend-Load nötig.
  // (+page.svelte rendert die Landing-Komponente, wenn kein user gesetzt ist.)
  if (!locals.user) {
    return {
      verified: url.searchParams.get('verified') === '1',
      apps: [] as AppTile[],
      briefing: undefined as TodayBriefing | undefined,
      briefkastenStats: null as BriefkastenStats | null,
      aufgaben: null as AufgabenStand | null,
      notizen: null as NotizenStand | null,
      failures: {} as {
        shellApi?: string;
        lifeops?: string;
        kalender?: string;
        notizen?: string;
      },
    };
  }

  // Owner-Gate fuers Homelab-Briefing: life-ops (Personal-COO) + briefkasten-Stats
  // sind Sami-eigene, NICHT multi-tenant. Ohne diese Pruefung saehe jeder Tenant
  // das Homelab-Briefing des Owners (offene Punkte, Service-Risiken, KG, Memory).
  // Passend zum backend-Multi-Tenancy (lager/fitness/mealprep).
  //
  // ★ Ohne OWNER_SUB ist NIEMAND Owner (seit 2026-09-05). Vorher stand hier die
  // Kennung eines konkreten Menschen als Vorbelegung. Sie gehoert nicht in ein
  // Repo, das veroeffentlicht werden soll, und ein Selbsthoster hat ohnehin eine
  // andere. Fail-closed ist hier die richtige Richtung: nicht konfiguriert
  // heisst kein Homelab-Briefing, nicht das Briefing von jemand anderem.
  const ownerSub = env.OWNER_SUB ?? '';
  const isOwner = ownerSub !== '' && locals.user.sub === ownerSub;

  let registry: SagantaApp[] = appsFallback(url.host);
  let pinnedIds = new Set<string>();
  let briefing: TodayBriefing | undefined;
  let briefkastenStats: BriefkastenStats | null = null;
  let aufgaben: AufgabenStand | null = null;
  let notizen: NotizenStand | null = null;
  const failures: {
    shellApi?: string;
    lifeops?: string;
    kalender?: string;
    notizen?: string;
  } = {};

  if (locals.user) {
    const secret = backendSecret();

    if (env.SHELL_API_BASE_URL) {
      const token = shellApiToken(locals.user, secret);
      // Apps und Settings ENTKOPPELT laden: eine Settings-Störung darf die
      // App-Liste nicht leeren (und umgekehrt). Apps fallen sonst auf den
      // statischen Fallback zurück → Launchpad bleibt immer navigierbar.
      try {
        // Den eigenen Host mitgeben: die Registry bildet die Kachel-Adressen
        // darin, damit ein Klick nicht aus dem Raum herausfuehrt, in dem der
        // Nutzer gerade angemeldet ist (`services/shell-api/app/registry.py`).
        const apps = await shellApiFetch<ShellApiApp[]>(
          env.SHELL_API_BASE_URL,
          `/api/apps?raum=${encodeURIComponent(url.host)}`,
          token,
          fetch,
        );
        if (apps.length > 0) {
          registry = apps.map((a) => ({
            id: a.id,
            name: a.name,
            description: a.description,
            href: a.href,
            icon: a.icon,
            tags: a.tags as SagantaApp['tags'],
          }));
        }
      } catch (err) {
        failures.shellApi = String(err);
      }
      try {
        const settings = await shellApiFetch<ShellApiSettings>(
          env.SHELL_API_BASE_URL,
          '/api/settings',
          token,
          fetch,
        );
        pinnedIds = new Set(settings.pinned_apps ?? []);
      } catch (err) {
        failures.shellApi = failures.shellApi ?? String(err);
      }
    }

    if (isOwner && env.LIFEOPS_BASE_URL) {
      const client = new LifeOpsClient({
        baseUrl: env.LIFEOPS_BASE_URL,
        token: issueBackendToken({
          user: locals.user,
          secret,
          audience: 'lifeops',
          ttlSeconds: 60,
        }),
        fetch,
      });
      try {
        briefing = await client.today();
      } catch (err) {
        failures.lifeops = String(err);
      }
    }

    if (isOwner) {
      briefkastenStats = await loadBriefkastenStats(fetch);
    }

    // Parallel, weil unabhaengig: eine langsame Notiz-Suche soll die Aufgaben
    // nicht aufhalten. Beide Stoerungen getrennt melden, sonst verdeckt die
    // erste die zweite.
    const [aufgabenErgebnis, notizenErgebnis] = await Promise.allSettled([
      ladeAufgaben(fetch, locals.user, secret),
      ladeNotizen(fetch, locals.user, secret),
    ]);
    if (aufgabenErgebnis.status === 'fulfilled') aufgaben = aufgabenErgebnis.value;
    else failures.kalender = String(aufgabenErgebnis.reason);
    if (notizenErgebnis.status === 'fulfilled') notizen = notizenErgebnis.value;
    else failures.notizen = String(notizenErgebnis.reason);
  }

  const apps: AppTile[] = registry
    .map((a) => ({ ...a, pinned: pinnedIds.has(a.id) }))
    .sort((a, b) => {
      if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
      return a.name.localeCompare(b.name, 'de');
    });

  if (briefing?.open_points?.length) {
    const calIdx = apps.findIndex((a) => a.id === 'calendar');
    if (calIdx >= 0) {
      apps[calIdx] = { ...apps[calIdx]!, badge: String(briefing.open_points.length) };
    }
  }

  if (briefkastenStats && briefkastenStats.active > 0) {
    const mailIdx = apps.findIndex((a) => a.id === 'mail');
    if (mailIdx >= 0) {
      apps[mailIdx] = { ...apps[mailIdx]!, badge: String(briefkastenStats.active) };
    }
  }

  return { apps, briefing, briefkastenStats, aufgaben, notizen, failures, verified: false, isOwner };
};

export const actions: Actions = {
  togglePin: async ({ request, locals, fetch }) => {
    if (!locals.user) return fail(401, { error: 'no session' });
    if (!env.SHELL_API_BASE_URL) return fail(503, { error: 'shell-api not configured' });

    const data = await request.formData();
    const id = (data.get('id') as string | null)?.trim() ?? '';
    const shouldPin = data.get('pinned') === 'true';
    if (!id) return fail(400, { error: 'id fehlt' });

    const secret = backendSecret();
    const token = shellApiToken(locals.user, secret);

    try {
      const current = await shellApiFetch<ShellApiSettings>(
        env.SHELL_API_BASE_URL,
        '/api/settings',
        token,
        fetch,
      );
      const pinned = new Set(current.pinned_apps ?? []);
      if (shouldPin) pinned.add(id);
      else pinned.delete(id);

      await shellApiFetch<ShellApiSettings>(env.SHELL_API_BASE_URL, '/api/settings', token, fetch, {
        method: 'PATCH',
        body: JSON.stringify({ pinned_apps: Array.from(pinned) }),
        headers: { 'Content-Type': 'application/json' },
      });
      return { success: true };
    } catch (err) {
      return fail(502, { error: String(err) });
    }
  },
};
