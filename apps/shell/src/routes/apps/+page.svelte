<script lang="ts">
  import { page } from '$app/stores';
  import { Icon } from '@saganta/ui';
  import { inview } from '$lib/inview';
  import MarketingChrome from '$lib/MarketingChrome.svelte';
  import { downloads, platforms } from '$lib/catalog';
  import type { PageData } from './$types';

  // data.user kommt aus dem Root-Layout (Parent-Merge) → eingeloggte Besucher
  // sehen passende Nav-CTAs und erreichen die Downloads aus dem Konto-Menü.
  // data.releases kommt aus +page.server.ts: die tatsächlich ausgelieferten
  // Artefakte. Ein Release, das im Volume liegt, ist damit sofort sichtbar,
  // ohne dass jemand den Katalog nachziehen muss.
  let { data }: { data: PageData } = $props();

  const releases = $derived(data.releases ?? {});

  /** Ausgeliefertes Android-Artefakt einer App, falls vorhanden. */
  function release(appId: string) {
    return releases[appId];
  }

  function formatSize(bytes: number): string {
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function formatDate(iso: string | undefined): string {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime())
      ? ''
      : d.toLocaleDateString('de-DE', { day: '2-digit', month: 'long', year: 'numeric' });
  }
</script>

<svelte:head>
  <title>Apps & Downloads · Saganta</title>
  <meta
    name="description"
    content="Alle Saganta-Apps im Browser, für Android und bald für Windows und Linux. Eine Suite, überall verfügbar."
  />
  <meta name="theme-color" content="#161310" />
  <!-- ★ Aus der aufgerufenen Adresse gebaut (2026-09-06). Vorher stand hier
       die Domaene der Ursprungs-Instanz fest: eine selbst betriebene
       Installation haette Suchmaschinen damit auf eine fremde Seite
       verwiesen, also die eigenen Seiten aktiv entwertet. -->
  <link rel="canonical" href={`${$page.url.origin}/apps`} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Saganta" />
  <meta property="og:title" content="Apps & Downloads · Saganta" />
  <meta
    property="og:description"
    content="Alle Saganta-Apps im Browser, für Android und bald für Windows und Linux. Eine Suite, überall verfügbar."
  />
  <meta property="og:url" content="https://saganta.de/apps" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Apps & Downloads · Saganta" />
  <meta
    name="twitter:description"
    content="Alle Saganta-Apps im Browser, für Android und bald für Windows und Linux. Eine Suite, überall verfügbar."
  />
</svelte:head>

<MarketingChrome active="apps" user={data.user}>
  <section class="mx-auto max-w-6xl px-6 pb-12 pt-20 text-center sm:pt-24">
    <p class="font-mono text-xs uppercase tracking-widest text-accent-400">Apps & Downloads</p>
    <h1 class="mt-4 font-display text-4xl tracking-tight sm:text-6xl">
      Deine Suite, überall
    </h1>
    <p class="mx-auto mt-5 max-w-xl text-lg text-muted">
      Wenige, tiefe Apps statt einer Flut von Einzeltools. Im Browser und als native
      Android-App, mit einem Konto auf allen deinen Geräten.
    </p>
    <div class="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-sm text-muted">
      {#each platforms as pf (pf.id)}
        <span class="inline-flex items-center gap-2">
          <Icon name={pf.icon} size={18} />
          {pf.label}
        </span>
      {/each}
    </div>
  </section>

  <!-- App-Liste mit Plattform-Buttons -->
  <section class="mx-auto max-w-5xl px-6 pb-24">
    <div class="space-y-4">
      {#each downloads as app, i (app.id)}
        <div
          use:inview={{ delay: i * 60 }}
          class="flex flex-col gap-5 rounded-2xl border border-border bg-surface-2/50 p-6 backdrop-blur-sm transition-colors duration-base ease-saganta hover:border-accent-500/40 sm:flex-row sm:items-center"
        >
          <div class="flex min-w-0 flex-1 items-start gap-4">
            <div class="grid size-12 shrink-0 place-items-center rounded-xl bg-accent-500/12 text-accent-300">
              <Icon name={app.icon} size={24} />
            </div>
            <div class="min-w-0">
              <h2 class="font-display text-xl">{app.name}</h2>
              <p class="mt-1 text-sm leading-relaxed text-muted">{app.description}</p>
              {#if release(app.id)}
                {@const rel = release(app.id)}
                <p class="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-muted/80">
                  <span class="font-mono text-accent-300/80">Android {rel.versionName}</span>
                  <span>{formatSize(rel.size)}</span>
                  {#if rel.publishedAt}<span>{formatDate(rel.publishedAt)}</span>{/if}
                </p>
                {#if rel.changelog}
                  <p class="mt-1 text-xs leading-relaxed text-muted/70">{rel.changelog}</p>
                {/if}
              {/if}
            </div>
          </div>

          <div class="flex flex-wrap gap-2 sm:justify-end">
            {#each platforms as pf (pf.id)}
              {@const rel = pf.id === 'android' ? release(app.id) : undefined}
              {@const t = rel
                ? { status: 'available' as const, href: `/downloads/saganta-${app.id}.apk` }
                : app.targets[pf.id]}
              {#if t}
                {#if t.status === 'available' && t.href}
                  <a
                    href={t.href}
                    class="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium transition-colors duration-fast ease-saganta hover:border-accent-500/50 hover:text-accent-300"
                  >
                    <Icon name={pf.icon} size={16} />
                    {pf.label}
                    {#if pf.id !== 'web'}<Icon name="download" size={14} />{/if}
                  </a>
                {:else}
                  <span
                    class="inline-flex items-center gap-2 rounded-lg border border-dashed border-border px-3.5 py-2 text-sm text-muted/70"
                    title="In Vorbereitung"
                  >
                    <Icon name={pf.icon} size={16} />
                    {pf.label}
                    <span class="text-xs">bald</span>
                  </span>
                {/if}
              {/if}
            {/each}
          </div>
        </div>
      {/each}
    </div>

    <p class="mt-8 text-center text-sm text-muted">
      Android-Apps werden außerhalb des Play Stores als signierte APK bereitgestellt.
      Ein Konto genügt für alle Apps auf allen Geräten.
    </p>

    <!-- Kostenlose Kleber-Features, in jedem Plan enthalten -->
    <div use:inview class="mt-10 grid gap-4 sm:grid-cols-2">
      <div class="flex items-start gap-4 rounded-2xl border border-dashed border-border bg-surface-2/30 p-6">
        <div class="grid size-11 shrink-0 place-items-center rounded-xl bg-erfolg/12 text-erfolg">
          <Icon name="square-check" size={22} />
        </div>
        <div>
          <h3 class="font-display text-lg">Einkaufsliste <span class="ml-1 text-xs text-erfolg">kostenlos</span></h3>
          <p class="mt-1 text-sm leading-relaxed text-muted">
            Sammelt automatisch aus Mealprep und Lager, dazu eigene Einträge, ob Lebensmittel oder nicht.
            Überall dabei, in jedem Plan enthalten.
          </p>
        </div>
      </div>
      <div class="flex items-start gap-4 rounded-2xl border border-dashed border-border bg-surface-2/30 p-6">
        <div class="grid size-11 shrink-0 place-items-center rounded-xl bg-erfolg/12 text-erfolg">
          <Icon name="calendar" size={22} />
        </div>
        <div>
          <h3 class="font-display text-lg">Geburtstage <span class="ml-1 text-xs text-erfolg">kostenlos</span></h3>
          <p class="mt-1 text-sm leading-relaxed text-muted">
            Erscheinen automatisch im Kalender, gespeist aus deinen Kontakten. Kein doppeltes Pflegen,
            in jedem Plan enthalten.
          </p>
        </div>
      </div>
    </div>
  </section>

  <!-- Plattform-Versprechen -->
  <section class="border-t border-border">
    <div use:inview class="mx-auto grid max-w-6xl gap-8 px-6 py-20 sm:grid-cols-3">
      <div>
        <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
          <Icon name="globe" size={20} />
        </div>
        <h3 class="font-display text-xl">Ohne Installation</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">
          Jede App läuft direkt im Browser. Anmelden, loslegen, fertig.
        </p>
      </div>
      <div>
        <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
          <Icon name="smartphone" size={20} />
        </div>
        <h3 class="font-display text-xl">Nativ auf Android</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">
          Echte Kotlin-Apps, kein WebView-Behelf. Schnell, offline-fähig, sauber integriert.
        </p>
      </div>
      <div>
        <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
          <Icon name="monitor" size={20} />
        </div>
        <h3 class="font-display text-xl">Desktop in Arbeit</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">
          Anwendungen für Windows und Linux sind in Vorbereitung. Dieselben Daten, dasselbe Konto.
        </p>
      </div>
    </div>
  </section>

  <section class="mx-auto max-w-3xl px-6 py-24 text-center">
    <h2 class="font-display text-4xl tracking-tight sm:text-5xl">Ein Konto, alle Geräte</h2>
    <p class="mx-auto mt-4 max-w-md text-lg text-muted">
      Erstelle dein Konto und nutze jede App im Browser und auf dem Smartphone.
    </p>
    <a
      href="/login?mode=register"
      class="mt-8 inline-block rounded-xl bg-accent-500 px-8 py-3.5 text-base font-semibold text-accent-ink shadow-[0_10px_40px_-8px] shadow-accent-500/40 transition-all duration-base ease-saganta hover:-translate-y-0.5 hover:bg-accent-400"
    >
      Kostenlos starten
    </a>
  </section>
</MarketingChrome>
