<script lang="ts">
  import { enhance } from '$app/forms';
  import { AppTile, Icon } from '@saganta/ui';
  import Landing from '$lib/Landing.svelte';
  import { inview } from '$lib/inview';
  import type { PageData } from './$types';

  interface Props {
    data: PageData;
  }
  let { data }: Props = $props();

  // Feste Haus-Zeitzone: der SSR-Node-Container läuft ohne TZ-Env auf UTC, der
  // Browser auf Europe/Berlin. Datums-/Tagesvergleiche müssen deterministisch in
  // EINER Zone laufen, sonst rendert SSR andere "heute"-Events/Zeiten als der
  // Client → Hydration-Mismatch (z.B. ein Event nahe Mitternacht).
  const BERLIN = 'Europe/Berlin';
  const berlinYmdFmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: BERLIN,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  function berlinYmd(d: Date): string {
    const p = berlinYmdFmt.formatToParts(d);
    const g = (t: string) => p.find((x) => x.type === t)?.value ?? '';
    return `${g('year')}-${g('month')}-${g('day')}`;
  }

  function isToday(iso: string): boolean {
    return berlinYmd(new Date(iso)) === berlinYmd(new Date());
  }

  function fmtTime(iso: string): string {
    return new Date(iso).toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: BERLIN,
    });
  }

  // Dedup gegen Svelte-5 `each_key_duplicate`: dynamische Backend-Daten (apps,
  // Kalender-Events mit mehrtägigen/wiederkehrenden Einträgen, Briefing-Punkte)
  // können denselben id-Key doppelt liefern. Der SSR rendert tolerant, aber die
  // Client-Hydration crasht hart → Dashboard verschwindet, JS tot, Login-Submit
  // (use:enhance) bricht. Eindeutige Keys hier erzwingen. (2026-06-28)
  function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
    const seen = new Set<unknown>();
    return arr.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  const appTiles = $derived(uniqueBy(data.apps ?? [], (a) => a.id));

  // Launchpad-Filter (rein client): ab vielen Kacheln wird Suchen schneller als
  // Scannen. Filtert nach Name/Beschreibung; leere Query = alle Kacheln.
  let appQuery = $state('');
  const filteredTiles = $derived.by(() => {
    const q = appQuery.trim().toLowerCase();
    if (!q) return appTiles;
    return appTiles.filter(
      (a) => a.name.toLowerCase().includes(q) || (a.description ?? '').toLowerCase().includes(q),
    );
  });

  const todaysEvents = $derived(
    uniqueBy(
      (data.briefing?.calendar ?? [])
        .filter((e) => isToday(e.start))
        .sort((a, b) => a.start.localeCompare(b.start)),
      (e) => e.id,
    ),
  );

  const openPoints = $derived(uniqueBy(data.briefing?.open_points ?? [], (p) => p.id));

  const failedBackends = $derived(
    Object.entries(data.failures ?? {}).filter(([, reason]) => reason) as [string, string][],
  );

  // Die Status-Karte zeigt Sagantas eigene Welt. Homelab-Betriebszustand stand
  // hier bis 2026-08-29 mit drei Kacheln (Knowledge-Adapter, Service-Risiken,
  // offene Memory-Eintraege) und ist raus: Saganta ist eigenstaendig. Wer den
  // Zustand des Hauses sehen will, nimmt Cockpit oder das dev-portal.
  const mailStats = $derived(data.briefkastenStats);
  const aufgaben = $derived(data.aufgaben);
  const notizen = $derived(data.notizen);
</script>

{#if !data.user}
  <Landing verified={data.verified} />
{:else}
<!-- Dezente Atmosphäre, konsistent mit der Landing (ruhiger gehalten, Arbeitsfläche). -->
<div
  class="pointer-events-none fixed inset-x-0 top-0 -z-10 h-96"
  style="background: radial-gradient(50% 100% at 50% 0%, rgba(207,133,36,0.12), transparent 70%);"
  aria-hidden="true"
></div>

<section class="space-y-10">
  <header use:inview class="space-y-2">
    <p class="font-mono text-sm uppercase tracking-widest text-muted">Saganta</p>
    <h1 class="font-display text-5xl leading-tight">
      {greeting(data.user?.name ?? data.user?.email)}
    </h1>
    <p class="max-w-xl text-muted">
      Deine Suite. Alles, was du heute brauchst, leise im Hintergrund, präsent wenn du sie aufrufst.
    </p>
  </header>

  {#if failedBackends.length > 0}
    <div class="rounded border border-warm-500/40 bg-warm-500/10 p-3 text-sm">
      <div class="font-medium">
        {failedBackends.length === 1
          ? 'Backend-Aufruf fehlgeschlagen, Anzeige eingeschränkt.'
          : `${failedBackends.length} Backend-Aufrufe fehlgeschlagen, Anzeige eingeschränkt.`}
      </div>
      <ul class="mt-1 space-y-0.5 text-muted">
        {#each failedBackends as [key, reason] (key)}
          <li>
            <span class="font-mono text-xs">{key}</span>: {reason}
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  <div use:inview>
    <div class="mb-4 flex items-center justify-between gap-4">
      <div class="flex items-baseline gap-3">
        <h2 class="text-sm font-medium uppercase tracking-wider text-muted">Apps</h2>
        <!-- Der einzige Weg zu den Downloads war bis 2026-08-29 das Konto-Menue
             oben rechts. Wer nicht wusste, dass es sie gibt, fand sie auch nicht. -->
        <a
          href="/apps"
          class="inline-flex items-center gap-1.5 text-xs text-muted transition-colors duration-fast ease-saganta hover:text-accent-300"
        >
          <Icon name="smartphone" size={13} /> Für Android
        </a>
      </div>
      {#if appTiles.length > 6}
        <label class="relative w-full max-w-56">
          <span class="pointer-events-none absolute inset-y-0 left-2.5 grid place-items-center text-muted">
            <Icon name="search" size={15} />
          </span>
          <input
            type="search"
            bind:value={appQuery}
            placeholder="Apps filtern…"
            aria-label="Apps filtern"
            class="w-full rounded-lg border border-border bg-surface-2/60 py-1.5 pl-8 pr-3 text-sm text-text outline-none transition-colors duration-fast ease-saganta placeholder:text-muted focus:border-accent-400"
          />
        </label>
      {/if}
    </div>
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each filteredTiles as app (app.id)}
        <div class="relative">
          <AppTile
            href={app.href}
            name={app.name}
            description={app.description}
            icon={app.icon}
            badge={app.badge}
          />
          <form
            method="POST"
            action="?/togglePin"
            use:enhance
            class="absolute bottom-3 right-3"
          >
            <input type="hidden" name="id" value={app.id} />
            <input type="hidden" name="pinned" value={String(!app.pinned)} />
            <button
              type="submit"
              aria-label={app.pinned ? 'Pin entfernen' : 'Anpinnen'}
              title={app.pinned ? 'Pin entfernen' : 'Anpinnen'}
              class="rounded-md p-1.5 leading-none transition-colors duration-fast ease-saganta hover:bg-surface"
              class:text-warm-500={app.pinned}
              class:text-muted={!app.pinned}
            >
              <Icon name="star" size={18} filled={app.pinned} />
            </button>
          </form>
        </div>
      {/each}
    </div>
    {#if appQuery.trim() && filteredTiles.length === 0}
      <p class="mt-3 text-sm text-muted">Keine App passt zu „{appQuery}".</p>
    {/if}
  </div>

  {#if !data.briefing}
    <!-- Nicht-Owner (bzw. Briefing nicht verfügbar): schlanker Hinweis statt leerer
         Fläche, keine fabrizierten Widgets, nur echte Bedien-Hilfen. -->
    <p use:inview class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted">
      <span class="inline-flex items-center gap-1.5">
        <Icon name="star" size={14} /> Mit dem Stern heftest du Apps nach oben.
      </span>
      <span class="hidden text-border sm:inline">·</span>
      <span class="inline-flex items-center gap-1.5">
        <kbd class="rounded border border-border px-1.5 py-0.5 font-mono text-xs">⌘K</kbd> öffnet die Befehlspalette.
      </span>
    </p>
  {/if}

  {#if data.briefing}
    <div use:inview class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <div class="rounded-2xl border border-border bg-surface-2/70 p-6 backdrop-blur-sm transition-colors duration-base ease-saganta hover:border-accent-500/40">
        <h2 class="mb-3 font-display text-2xl">Offene Punkte</h2>
        {#if data.briefing.open_points?.length}
          <ul class="space-y-2">
            {#each openPoints.slice(0, 5) as point (point.id)}
              <li class="flex items-start gap-2 text-sm">
                <span
                  class="mt-1 size-2 shrink-0 rounded-full"
                  class:bg-fehler={point.severity === 'urgent'}
                  class:bg-warm-500={point.severity === 'soft'}
                  class:bg-accent-500={point.severity === 'info'}
                  aria-hidden="true"
                ></span>
                <span>{point.title}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="text-sm text-muted">Keine offenen Punkte. Genieß den Tag.</p>
        {/if}
      </div>

      <div class="rounded-2xl border border-border bg-surface-2/70 p-6 backdrop-blur-sm transition-colors duration-base ease-saganta hover:border-accent-500/40">
        <h2 class="mb-3 font-display text-2xl">Heute</h2>
        {#if todaysEvents.length}
          <ul class="space-y-2 text-sm">
            {#each todaysEvents.slice(0, 6) as ev (ev.id)}
              <li class="flex items-start gap-3">
                <span class="font-mono text-xs text-muted shrink-0 mt-0.5">
                  {fmtTime(ev.start)}
                </span>
                <span class="min-w-0 truncate">{ev.title}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="text-sm text-muted">Keine Termine heute.</p>
        {/if}
      </div>

      <div class="rounded-2xl border border-border bg-surface-2/70 p-6 backdrop-blur-sm transition-colors duration-base ease-saganta hover:border-accent-500/40">
        <h2 class="mb-3 font-display text-2xl">Status</h2>
        <div class="space-y-3 text-sm">
          {#if mailStats}
            <div class="flex items-start gap-2">
              <span
                class="mt-1 size-2 shrink-0 rounded-full"
                class:bg-accent-500={mailStats.active > 0}
                class:bg-erfolg={mailStats.active === 0}
                aria-hidden="true"
              ></span>
              <div class="min-w-0 flex-1">
                <div>
                  <span class="font-medium">{mailStats.active}</span>
                  <span class="text-muted">aktive Briefe</span>
                  {#if mailStats.archived > 0}
                    <span class="text-xs text-muted">· {mailStats.archived} archiviert</span>
                  {/if}
                </div>
                {#if mailStats.pending_ocr > 0}
                  <div class="text-xs text-warm-500">{mailStats.pending_ocr} ohne OCR</div>
                {/if}
              </div>
            </div>
          {/if}

          {#if aufgaben}
            <div class="flex items-start gap-2">
              <span
                class="mt-1 size-2 shrink-0 rounded-full"
                class:bg-erfolg={aufgaben.offen === 0}
                class:bg-accent-500={aufgaben.offen > 0}
                aria-hidden="true"
              ></span>
              <div class="min-w-0 flex-1">
                {#if aufgaben.offen === 0}
                  <span class="text-muted">Keine offenen Aufgaben</span>
                {:else}
                  <div>
                    <span class="font-medium">{aufgaben.offen}</span>
                    <span class="text-muted">offene Aufgabe{aufgaben.offen > 1 ? 'n' : ''}</span>
                  </div>
                  {#if aufgaben.titel.length}
                    <ul class="mt-1 space-y-0.5 text-xs text-muted">
                      {#each aufgaben.titel as t, i (i)}
                        <li class="truncate">{t}</li>
                      {/each}
                    </ul>
                  {/if}
                {/if}
              </div>
            </div>
          {/if}

          {#if notizen && notizen.anzahl > 0}
            <div class="flex items-start gap-2">
              <span class="mt-1 size-2 shrink-0 rounded-full bg-accent-500" aria-hidden="true"></span>
              <div class="min-w-0 flex-1">
                <span class="font-medium">{notizen.anzahl}</span>
                <span class="text-muted">Notiz{notizen.anzahl > 1 ? 'en' : ''}</span>
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</section>
{/if}

<script lang="ts" module>
  function greeting(who: string | undefined): string {
    // Stunde in Europe/Berlin statt Laufzeit-TZ (SSR-Container = UTC), sonst
    // grüßt der Server nach UTC-Stunde und der Client korrigiert beim Hydrate.
    const raw = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/Berlin',
      hour: '2-digit',
      hour12: false,
    }).format(new Date());
    const h = Number(raw) % 24; // % 24 fängt den "24:00"-Mitternachts-Quirk ab
    const greet = h < 5 ? 'Späte Nacht' : h < 11 ? 'Guten Morgen' : h < 18 ? 'Hallo' : 'Guten Abend';
    return who ? `${greet}, ${who.split(' ')[0]}.` : `${greet}.`;
  }
</script>
