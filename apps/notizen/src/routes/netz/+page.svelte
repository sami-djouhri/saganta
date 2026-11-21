<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Icon } from '@saganta/ui';
  import NetzKarte from '$lib/components/NetzKarte.svelte';
  import { verweisSchluessel } from '$lib/markdown';
  import { mitNotizbuechern, type NetzKanteMitBuch, type NetzKnotenMitBuch } from '$lib/netz-layout';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let suche = $state('');
  let ohneVerbindung = $state(true);
  let buecherZeigen = $state(true);
  let auswahl = $state<number | null>(null);
  let karte = $state<ReturnType<typeof NetzKarte> | null>(null);

  let farben = $derived(
    new Map(data.notizbuecher.filter((b) => b.farbe).map((b) => [b.id, b.farbe as string])),
  );
  let buchName = $derived(new Map(data.notizbuecher.map((b) => [b.id, b.name])));
  let notizKnoten = $derived(
    ohneVerbindung ? data.netz.knoten : data.netz.knoten.filter((n) => n.grad > 0 || n.id === data.fokus),
  );
  // Notizbücher als eigene Knoten, verbunden mit ihren gezeigten Notizen.
  let gezeigt: { knoten: NetzKnotenMitBuch[]; kanten: NetzKanteMitBuch[] } = $derived(
    buecherZeigen
      ? mitNotizbuechern(notizKnoten, data.netz.kanten, data.notizbuecher)
      : { knoten: notizKnoten, kanten: data.netz.kanten },
  );
  let gewaehlt = $derived(gezeigt.knoten.find((n) => n.id === auswahl) ?? null);
  let nachbarn = $derived.by(() => {
    if (auswahl === null) return [];
    const ids = new Map<number, 'verbunden' | 'hin' | 'her' | 'buch' | 'drin'>();
    for (const k of gezeigt.kanten) {
      if (k.a === auswahl) ids.set(k.b, k.art === 'text' ? 'hin' : k.art === 'buch' ? 'drin' : 'verbunden');
      else if (k.b === auswahl) ids.set(k.a, k.art === 'text' ? 'her' : k.art === 'buch' ? 'buch' : 'verbunden');
    }
    return gezeigt.knoten
      .filter((n) => ids.has(n.id))
      .map((n) => ({ ...n, wie: ids.get(n.id)! }));
  });
  const WIE = { verbunden: 'verbunden', hin: 'verweist darauf', her: 'verweist hierher', buch: 'Notizbuch', drin: '' };

  let anzahlKanten = $derived(data.netz.kanten.length);
  let ohneAnzahl = $derived(data.netz.knoten.filter((n) => n.grad === 0).length);

  function sucheBestaetigen() {
    const s = verweisSchluessel(suche);
    if (!s) return;
    const erster = gezeigt.knoten.find((n) => verweisSchluessel(n.titel).includes(s));
    if (erster) {
      auswahl = erster.id;
      karte?.zentrieren(erster.id);
    }
  }

  function archivUmschalten() {
    const ziel = new URL($page.url);
    if (data.archivierte) ziel.searchParams.delete('archiv');
    else ziel.searchParams.set('archiv', '1');
    goto(`${ziel.pathname}${ziel.search}`, { noScroll: true });
  }
</script>

<svelte:head><title>Netz · Notizen</title></svelte:head>

<div class="flex flex-col gap-3">
  <div class="flex flex-wrap items-center gap-2">
    <h1 class="mr-2 font-display text-2xl">Netz</h1>
    <label class="relative min-w-48 flex-1">
      <span class="sr-only">Im Netz suchen</span>
      <span class="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-muted"><Icon name="search" size={14} /></span>
      <input
        bind:value={suche}
        onkeydown={(e) => e.key === 'Enter' && sucheBestaetigen()}
        placeholder="Titel suchen, Enter springt hin"
        class="w-full rounded-md border border-border-stark bg-surface py-1.5 pr-3 pl-8 text-sm max-md:min-h-11"
      />
    </label>
    <label class="flex items-center gap-1.5 text-sm text-muted max-md:min-h-11">
      <input type="checkbox" bind:checked={ohneVerbindung} class="accent-[var(--color-akzent)]" />
      Ohne Verbindung ({ohneAnzahl})
    </label>
    {#if data.notizbuecher.length}
      <label class="flex items-center gap-1.5 text-sm text-muted max-md:min-h-11">
        <input type="checkbox" bind:checked={buecherZeigen} class="accent-[var(--color-akzent)]" />
        Notizbücher
      </label>
    {/if}
    <label class="flex items-center gap-1.5 text-sm text-muted max-md:min-h-11">
      <input type="checkbox" checked={data.archivierte} onchange={archivUmschalten} class="accent-[var(--color-akzent)]" />
      Archiv
    </label>
  </div>

  <div class="grid gap-3 lg:grid-cols-[1fr_18rem]">
    <div class="netz-flaeche h-[68dvh] min-h-80 overflow-hidden rounded-lg border border-border-stark">
      {#if data.netz.knoten.length === 0}
        <p class="grid h-full place-items-center p-6 text-center text-sm text-muted">Noch keine Notizen.</p>
      {:else}
        <NetzKarte bind:this={karte} bind:auswahl knoten={gezeigt.knoten} kanten={gezeigt.kanten} {farben} {suche} fokus={data.fokus} />
      {/if}
    </div>

    <aside class="flex flex-col gap-3 text-sm">
      {#if gewaehlt?.buch}
        <section class="rounded-lg border border-akzent/60 p-3 shadow-[0_0_18px_-6px_var(--color-akzent)]">
          <p class="text-xs uppercase tracking-wide text-muted">Notizbuch</p>
          <h2 class="font-semibold break-words">{gewaehlt.titel}</h2>
          <p class="mt-1 text-xs text-muted">{gewaehlt.grad === 1 ? '1 Notiz' : `${gewaehlt.grad} Notizen`} im Netz</p>
          <a href="/?buch={gewaehlt.notizbuch_id}" class="mt-3 inline-flex min-h-11 items-center gap-1.5 rounded-md bg-accent-500 px-3 font-medium text-accent-ink md:min-h-9">
            <Icon name="folder" size={14} /> Notizen ansehen
          </a>
          {#if nachbarn.length}
            <ul class="mt-3 flex flex-col gap-0.5">
              {#each nachbarn as n (n.id)}
                <li>
                  <button
                    type="button"
                    class="flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-2 max-md:min-h-11"
                    onclick={() => {
                      auswahl = n.id;
                      karte?.zentrieren(n.id);
                    }}
                  >
                    <span class="min-w-0 flex-1 truncate">{n.titel || 'Ohne Titel'}</span>
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {:else if gewaehlt}
        <section class="rounded-lg border border-akzent/60 p-3 shadow-[0_0_18px_-6px_var(--color-akzent)]">
          <h2 class="font-semibold break-words">{gewaehlt.titel || 'Ohne Titel'}</h2>
          <p class="mt-1 text-xs text-muted">
            {gewaehlt.notizbuch_id ? (buchName.get(gewaehlt.notizbuch_id) ?? 'Notizbuch') : 'Ohne Notizbuch'}
            · {gewaehlt.grad === 1 ? '1 Verbindung' : `${gewaehlt.grad} Verbindungen`}
            {#if gewaehlt.archiviert}· Archiv{/if}
          </p>
          {#if gewaehlt.offene_verweise}
            <p class="mt-1 text-xs text-muted">
              {gewaehlt.offene_verweise === 1 ? '1 Verweis' : `${gewaehlt.offene_verweise} Verweise`} auf Notizen, die es noch nicht gibt
            </p>
          {/if}
          <a href="/notiz/{gewaehlt.id}" class="mt-3 inline-flex min-h-11 items-center gap-1.5 rounded-md bg-accent-500 px-3 font-medium text-accent-ink md:min-h-9">
            <Icon name="file-text" size={14} /> Öffnen
          </a>
          {#if nachbarn.length}
            <ul class="mt-3 flex flex-col gap-0.5">
              {#each nachbarn as n (n.id)}
                <li>
                  <button
                    type="button"
                    class="flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-2 max-md:min-h-11"
                    onclick={() => {
                      auswahl = n.id;
                      karte?.zentrieren(n.id);
                    }}
                  >
                    <span class="min-w-0 flex-1 truncate">{n.titel || 'Ohne Titel'}</span>
                    <span class="shrink-0 text-xs text-muted">{WIE[n.wie]}</span>
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
      {:else}
        <section class="rounded-lg border border-border p-3 text-muted">
          <p>
            {data.netz.knoten.length === 1 ? '1 Notiz' : `${data.netz.knoten.length} Notizen`},
            {anzahlKanten === 1 ? '1 Verbindung' : `${anzahlKanten} Verbindungen`}.
          </p>
          <p class="mt-2">
            Tippe auf einen Punkt, um die Notiz und ihre Nachbarn zu sehen. Doppelklick öffnet sie.
          </p>
          {#if anzahlKanten === 0}
            <p class="mt-2">
              Noch ist nichts verbunden. Schreib <code>[[Titel]]</code> in eine Notiz oder verbinde in
              der Liste mehrere über „Auswählen“.
            </p>
          {/if}
        </section>
      {/if}

      <section class="rounded-lg border border-border p-3 text-xs text-muted">
        <h2 class="mb-2 font-semibold text-text">Legende</h2>
        <p class="flex items-center gap-2"><svg width="32" height="8" aria-hidden="true"><line x1="0" y1="4" x2="32" y2="4" stroke="currentColor" stroke-width="1.5" /></svg> von Hand verbunden</p>
        <p class="mt-1 flex items-center gap-2"><svg width="32" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" stroke="currentColor" stroke-width="1.5" stroke-dasharray="5 4" /><path d="M26 0 L32 4 L26 8 z" fill="currentColor" /></svg> [[Verweis]] im Text</p>
        <p class="mt-1 flex items-center gap-2"><svg width="32" height="12" aria-hidden="true"><circle cx="16" cy="6" r="4.5" fill="none" stroke="currentColor" stroke-width="1.5" /></svg> ohne Verbindung</p>
        <p class="mt-1 flex items-center gap-2"><svg width="32" height="14" aria-hidden="true"><rect x="10" y="1" width="9" height="9" rx="1.5" transform="rotate(45 14.5 5.5)" fill="none" stroke="currentColor" stroke-width="1.5" /></svg> Notizbuch, gepunktet zu seinen Notizen</p>
        <p class="mt-1">Farbe = Notizbuch, Größe = Zahl der Verbindungen.</p>
      </section>
    </aside>
  </div>
</div>

<style>
  .netz-flaeche {
    background:
      radial-gradient(circle at 50% 45%, color-mix(in srgb, var(--color-akzent) 7%, transparent), transparent 65%),
      color-mix(in srgb, var(--color-surface) 70%, black);
  }
</style>
