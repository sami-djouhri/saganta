<script lang="ts">
  import { untrack } from 'svelte';
  import { enhance } from '$app/forms';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button, Icon } from '@saganta/ui';
  import Hervorhebung from '$lib/components/Hervorhebung.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  // Die Wörter der laufenden Suche, für die Markierung in den Treffern.
  let suchbegriffe = $derived((data.suche ?? '').split(/\s+/).filter(Boolean));

  // Einmal übernehmen, danach gehört das Feld der Tastatur (siehe untrack).
  let sucheFeld = $state(untrack(() => data.suche ?? ''));
  let neuesBuch = $state('');
  let buchFormOffen = $state(false);

  // Die Suche läuft über die Adresse, nicht über einen lokalen Zustand: so ist
  // ein Suchergebnis teilbar, im Verlauf auffindbar und übersteht das Neuladen.
  let entprellung: ReturnType<typeof setTimeout> | undefined;
  function suchen(wert: string) {
    clearTimeout(entprellung);
    entprellung = setTimeout(() => {
      const ziel = new URL($page.url);
      if (wert.trim()) ziel.searchParams.set('q', wert.trim());
      else ziel.searchParams.delete('q');
      goto(`${ziel.pathname}${ziel.search}`, { keepFocus: true, noScroll: true });
    }, 250);
  }

  function filterAdresse(feld: string, wert: string | null): string {
    const ziel = new URL($page.url);
    if (wert === null) ziel.searchParams.delete(feld);
    else ziel.searchParams.set(feld, wert);
    return `${ziel.pathname}${ziel.search}` || '/';
  }

  function datum(roh: string): string {
    const d = new Date(roh);
    return Number.isNaN(d.getTime())
      ? ''
      : d.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' });
  }
</script>

<div class="flex flex-col gap-6">
  <header class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="font-display text-2xl">Notizen</h1>
    <form method="POST" action="?/anlegen" use:enhance class="flex items-center gap-2">
      {#if data.notizbuch}
        <input type="hidden" name="notizbuch_id" value={data.notizbuch} />
      {/if}
      <input
        name="titel"
        placeholder="Titel der neuen Notiz"
        class="w-56 rounded-md border border-border bg-surface px-3 py-2 text-sm"
      />
      <Button type="submit" size="sm">
        <Icon name="plus" size={16} /> Neue Notiz
      </Button>
    </form>
  </header>

  <div class="relative">
    <span class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted">
      <Icon name="search" size={16} />
    </span>
    <input
      bind:value={sucheFeld}
      oninput={() => suchen(sucheFeld)}
      placeholder="Volltextsuche über Titel, Text und Tags…"
      class="w-full rounded-md border border-border bg-surface py-2 pl-10 pr-3 text-sm"
      aria-label="Notizen durchsuchen"
    />
  </div>

  <div class="flex flex-col gap-6 lg:flex-row">
    <!-- Notizbücher und Tags -->
    <aside class="w-full shrink-0 lg:w-56">
      <div class="flex items-center justify-between">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-muted">Notizbücher</h2>
        <button
          type="button"
          class="text-muted hover:text-text"
          onclick={() => (buchFormOffen = !buchFormOffen)}
          aria-label="Notizbuch anlegen"
          title="Notizbuch anlegen"
        >
          <Icon name="plus" size={14} />
        </button>
      </div>

      {#if buchFormOffen}
        <form
          method="POST"
          action="?/notizbuchAnlegen"
          use:enhance={() =>
            ({ update }) => {
              neuesBuch = '';
              buchFormOffen = false;
              return update();
            }}
          class="mt-2 flex gap-1"
        >
          <input
            name="name"
            bind:value={neuesBuch}
            placeholder="Name"
            class="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1 text-sm"
          />
          <Button type="submit" size="sm" variant="ghost">OK</Button>
        </form>
      {/if}

      <nav class="mt-2 flex flex-col gap-0.5 text-sm">
        <a
          href={filterAdresse('buch', null)}
          class="rounded-md px-2 py-1.5 {!data.notizbuch
            ? 'bg-surface-2 text-text'
            : 'text-muted hover:text-text'}">Alle</a
        >
        {#each data.notizbuecher as buch (buch.id)}
          <div class="group flex items-center gap-1">
            <a
              href={filterAdresse('buch', String(buch.id))}
              class="min-w-0 flex-1 truncate rounded-md px-2 py-1.5 {data.notizbuch ===
              String(buch.id)
                ? 'bg-surface-2 text-text'
                : 'text-muted hover:text-text'}"
            >
              {buch.name}
              <span class="ml-1 text-xs opacity-60">{buch.anzahl_notizen}</span>
            </a>
            <form
              method="POST"
              action="?/notizbuchLoeschen"
              use:enhance
              class="opacity-0 transition-opacity group-hover:opacity-100"
            >
              <input type="hidden" name="id" value={buch.id} />
              <button
                type="submit"
                class="text-muted hover:text-text"
                aria-label="Notizbuch {buch.name} entfernen"
                title="Entfernen, die Notizen darin bleiben"
              >
                <Icon name="x" size={14} />
              </button>
            </form>
          </div>
        {/each}
      </nav>

      {#if data.tags.length}
        <h2 class="mt-6 text-xs font-semibold uppercase tracking-wide text-muted">Tags</h2>
        <div class="mt-2 flex flex-wrap gap-1">
          {#each data.tags as tag (tag)}
            <a
              href={filterAdresse('tag', data.tag === tag ? null : tag)}
              class="rounded-full border px-2 py-0.5 text-xs {data.tag === tag
                ? 'border-accent-500 bg-accent-500/10 text-accent-300'
                : 'border-border text-muted hover:text-text'}">{tag}</a
            >
          {/each}
        </div>
      {/if}

      <a
        href={filterAdresse('archiv', data.archivierte ? null : '1')}
        class="mt-6 flex items-center gap-2 text-sm {data.archivierte
          ? 'text-text'
          : 'text-muted hover:text-text'}"
      >
        <Icon name="archive" size={14} />
        {data.archivierte ? 'Archiv verlassen' : 'Archiv zeigen'}
      </a>
    </aside>

    <!-- Notizen -->
    <section class="min-w-0 flex-1">
      {#if data.notizen.length === 0}
        <p class="rounded-lg border border-dashed border-border px-6 py-16 text-center text-muted">
          {#if data.suche}
            Keine Notiz enthält „{data.suche}".
          {:else if data.archivierte}
            Nichts im Archiv.
          {:else}
            Noch keine Notiz. Titel eintippen und anlegen.
          {/if}
        </p>
      {:else}
        <ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {#each data.notizen as notiz (notiz.id)}
            <li>
              <a
                href="/notiz/{notiz.id}"
                class="flex h-full flex-col rounded-lg border border-border bg-surface-2/40 p-4 transition-colors hover:border-accent-700"
              >
                <div class="flex items-start justify-between gap-2">
                  <h3 class="font-medium leading-tight">
                    {#if data.suche}
                      <Hervorhebung text={notiz.titel || 'Ohne Titel'} begriffe={suchbegriffe} />
                    {:else}
                      {notiz.titel || 'Ohne Titel'}
                    {/if}
                  </h3>
                  {#if notiz.angeheftet}
                    <span class="shrink-0 text-accent-400" title="Angeheftet">
                      <Icon name="bookmark" size={14} />
                    </span>
                  {/if}
                </div>
                {#if notiz.ausschnitt}
                  <p class="mt-2 line-clamp-3 text-sm text-muted">
                    {#if data.suche}
                      <Hervorhebung text={notiz.ausschnitt} begriffe={suchbegriffe} />
                    {:else}
                      {notiz.ausschnitt}
                    {/if}
                  </p>
                {/if}
                <div class="mt-auto flex flex-wrap items-center gap-2 pt-3 text-xs text-muted">
                  <span>{datum(notiz.geaendert_am)}</span>
                  {#if notiz.anzahl_anhaenge}
                    <span class="flex items-center gap-1" title="Anhänge">
                      <Icon name="download" size={12} />{notiz.anzahl_anhaenge}
                    </span>
                  {/if}
                  {#if notiz.anzahl_verknuepfungen}
                    <span class="flex items-center gap-1" title="Verknüpfungen">
                      <Icon name="infinity" size={12} />{notiz.anzahl_verknuepfungen}
                    </span>
                  {/if}
                  {#if notiz.anzahl_freigaben}
                    <span class="flex items-center gap-1 text-accent-400" title="Geteilte Links">
                      <Icon name="globe" size={12} />{notiz.anzahl_freigaben}
                    </span>
                  {/if}
                </div>
                {#if notiz.tags.length}
                  <div class="mt-2 flex flex-wrap gap-1">
                    {#each notiz.tags.slice(0, 4) as tag (tag)}
                      <span class="rounded-full border border-border px-2 py-0.5 text-xs text-muted"
                        >{tag}</span
                      >
                    {/each}
                  </div>
                {/if}
              </a>
            </li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>
</div>
