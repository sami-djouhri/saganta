<script lang="ts">
  import { Icon } from '@saganta/ui';
  import { artefaktPlattformen, platforms, type Platform } from '$lib/catalog';
  import type { PageData } from './$types';

  // Seit 2026-11-01 eine schlichte Seite hinter der Anmeldung, im Rahmen der
  // Shell. Vorher war sie Teil der Werbeflaeche (eigene Navigation, „Kostenlos
  // starten", Plattform-Versprechen) und oeffentlich; der Entscheid vom
  // 01.11. hat die Werbeflaeche geloescht. Die Download-Liste bleibt, weil sie
  // der einzige Weg zu APK und Linux-Paket im Browser ist.
  // data.apps und data.releases kommen aus +page.server.ts: die Apps im Raum
  // des Aufrufers und die tatsächlich ausgelieferten Artefakte. Ein Release,
  // das im Volume liegt, ist damit sofort sichtbar, ohne dass jemand einen
  // Katalog nachziehen muss.
  let { data }: { data: PageData } = $props();

  const releases = $derived(data.releases ?? {});
  const apps = $derived(data.apps ?? []);

  /** Ausgeliefertes Artefakt einer App für eine Plattform, falls vorhanden. */
  function release(pf: Platform, releaseName: string) {
    return releases[pf]?.[releaseName];
  }

  /**
   * Dateiname des Artefakts unter `/downloads/`.
   *
   * Android bleibt beim festen Namen, auf den die Seite seit immer verlinkt
   * (die versionierte Kopie gehört dem Updater). Linux nennt seine Datei im
   * Manifest, weil der Paketname die Fassung trägt.
   */
  function dateiname(pf: Platform, releaseName: string): string | undefined {
    if (pf === 'android') return `saganta-${releaseName}.apk`;
    return release(pf, releaseName)?.datei;
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
</svelte:head>

<section class="space-y-8">
  <header class="space-y-1">
    <h1 class="font-display text-3xl">Apps & Downloads</h1>
    <p class="text-muted">Jede App im Browser, als Android-App und als Programm für Linux.</p>
  </header>

    <div class="space-y-4">
      {#each apps as app (app.id)}
        <div
          class="flex flex-col gap-5 rounded-2xl border border-border bg-surface-2/50 p-6 backdrop-blur-sm transition-colors duration-base ease-saganta hover:border-accent-500/40 sm:flex-row sm:items-center"
        >
          <div class="flex min-w-0 flex-1 items-start gap-4">
            <div class="grid size-12 shrink-0 place-items-center rounded-xl bg-accent-500/12 text-akzent">
              <Icon name={app.icon} size={24} />
            </div>
            <div class="min-w-0">
              <h2 class="font-display text-xl">{app.name}</h2>
              <p class="mt-1 text-sm leading-relaxed text-muted">{app.description}</p>
              {#each artefaktPlattformen as pf (pf)}
                {@const rel = release(pf, app.release)}
                {#if rel}
                  {@const label = platforms.find((p) => p.id === pf)?.label ?? pf}
                  <p class="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-muted/80">
                    <span class="font-mono text-akzent/80">{label} {rel.versionName}</span>
                    <span>{formatSize(rel.size)}</span>
                    {#if rel.publishedAt}<span>{formatDate(rel.publishedAt)}</span>{/if}
                  </p>
                  {#if rel.changelog}
                    <p class="mt-1 text-xs leading-relaxed text-muted/70">{rel.changelog}</p>
                  {/if}
                {/if}
              {/each}
            </div>
          </div>

          <div class="flex flex-wrap gap-2 sm:justify-end">
            {#each platforms.filter((p) => !app.plattformen || app.plattformen.includes(p.id)) as pf (pf.id)}
              {@const href =
                pf.id === 'web'
                  ? app.web
                  : release(pf.id, app.release)
                    ? `/downloads/${dateiname(pf.id, app.release)}`
                    : undefined}
              {#if href}
                <a
                  href={href}
                  class="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-sm font-medium transition-colors duration-fast ease-saganta hover:border-accent-500/50 hover:text-akzent-stark"
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
            {/each}
          </div>
        </div>
      {/each}
    </div>

  <p class="text-sm text-muted">
      Android-Apps werden außerhalb des Play Stores als signierte APK bereitgestellt.
      Die Linux-Programme kommen aus der Saganta-Paketquelle für pacman. Sie wird einmal mit
      <code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">sudo bash saganta-installieren</code>
      eingerichtet, danach hält
      <code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">sudo pacman -Syu</code>
      sie aktuell. Eine einzelne Datei mit <code class="font-mono text-xs">pacman -U</code> genügt nicht,
      die Programme teilen sich das Paket <code class="font-mono text-xs">saganta-runtime</code>.
  </p>
</section>
