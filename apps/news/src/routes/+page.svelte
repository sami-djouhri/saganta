<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon, kalenderCaptureUrl } from '@saganta/ui';
  import Landing from '$lib/Landing.svelte';
  import type { PageData } from './$types';

  interface Props {
    data: PageData;
  }
  let { data }: Props = $props();

  // Dedup gegen Svelte-5 `each_key_duplicate`: Feed-Items aus mehreren Quellen
  // (oder dieselbe Quelle doppelt) können denselben id-Key tragen → Client-
  // Hydration-Crash legt die Seite lahm. Eindeutige Keys erzwingen. (2026-06-28)
  function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
    const seen = new Set<unknown>();
    return arr.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '';
    const d = new Date(iso);
    // timeZone pinnen: der SSR-Node-Container hat kein TZ-Env (läuft auf UTC),
    // der Browser auf Europe/Berlin. Ohne Pinning rendert der Server UTC-Zeiten,
    // der Client Berlin-Zeiten → Hydration-Mismatch + falsche Initial-Anzeige.
    return d.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Berlin',
    });
  }

  function stripHtml(s: string | null): string {
    if (!s) return '';
    const text = s.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    return text.length > 240 ? `${text.slice(0, 240)}…` : text;
  }

  const failure = $derived(data.failures?.api);

  /** Artikel, die es ins heutige Briefing geschafft haben, der Feed zeigt damit,
   *  was die Auswahl übernommen hat, statt beide Listen unverbunden nebeneinander
   *  stehen zu lassen. */
  const imBriefing = $derived(new Set(data.briefingIds ?? []));

  function buildHref(params: { source?: string; bookmarked?: boolean }): string {
    const p = new URLSearchParams();
    const source = params.source ?? data.source;
    const bookmarked = params.bookmarked ?? data.bookmarked;
    if (source) p.set('source', source);
    if (bookmarked) p.set('bookmarked', '1');
    const qs = p.toString();
    return qs ? `/?${qs}` : '/';
  }
</script>

{#if !data.user}
  <Landing />
{:else}
<section class="space-y-6">
  <header class="space-y-2">
    <p class="font-mono text-sm uppercase tracking-widest text-muted">Saganta · News</p>
    <h1 class="font-display text-4xl leading-tight">Was heute wichtig ist.</h1>
    <p class="text-muted">
      {data.feed.total} Artikel{data.bookmarked ? ' · nur Bookmarks' : ''}.
    </p>
  </header>

  <nav class="flex flex-wrap items-center gap-2 text-sm">
    <a
      href={buildHref({ source: '', bookmarked: false })}
      class="rounded-full border px-3 py-1 {!data.source && !data.bookmarked
        ? 'border-accent-500 text-accent-300'
        : 'border-border text-muted hover:text-text'}"
    >
      Alle
    </a>
    <a
      href={buildHref({ source: '', bookmarked: true })}
      class="inline-flex items-center gap-1 rounded-full border px-3 py-1 transition-colors duration-fast ease-saganta {data.bookmarked
        ? 'border-warm-500 text-warm-500'
        : 'border-border text-muted hover:text-text'}"
    >
      <Icon name="bookmark" size={13} filled={data.bookmarked} /> Bookmarks
    </a>
    {#each uniqueBy(data.sources, (s) => s.id) as s (s.id)}
      <a
        href={buildHref({ source: s.slug, bookmarked: false })}
        class="rounded-full border px-3 py-1 {data.source === s.slug
          ? 'border-accent-500 text-accent-300'
          : 'border-border text-muted hover:text-text'}"
      >
        {s.name}
      </a>
    {/each}
  </nav>

  {#if failure}
    <div class="rounded border border-warm-500/40 bg-warm-500/10 p-3 text-sm">
      <div class="font-medium">News-API nicht erreichbar.</div>
      <div class="mt-1 font-mono text-xs text-muted">{failure}</div>
    </div>
  {/if}

  {#if data.feed.items.length === 0 && !failure}
    <p class="rounded border border-border bg-surface-2 px-4 py-6 text-center text-muted">
      {#if data.bookmarked}
        Noch keine Bookmarks.
      {:else if data.source}
        Keine Artikel von „{data.sources.find((s) => s.slug === data.source)?.name ??
          data.source}".
      {:else}
        Noch keine Artikel: Feeds werden gerade geladen.
      {/if}
    </p>
  {/if}

  <ul class="space-y-3">
    {#each uniqueBy(data.feed.items, (i) => i.id) as item (item.id)}
      <li
        class="rounded-lg border border-border bg-surface-2 p-4 {item.read ? 'opacity-60' : ''}"
      >
        <div class="flex items-baseline justify-between gap-2">
          <div class="flex items-center gap-2">
            <span class="font-mono text-xs uppercase tracking-wider text-muted">{item.source_name}</span>
            {#if imBriefing.has(item.id)}
              <a
                href="/briefing"
                class="rounded-full border border-accent-500/50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-accent-300 hover:bg-accent-500/10"
                title="Dieser Artikel steht in deinem heutigen Briefing"
              >
                Im Briefing
              </a>
            {/if}
          </div>
          <span class="font-mono text-xs text-muted">{fmtDate(item.published_at)}</span>
        </div>
        <a
          href={item.link}
          target="_blank"
          rel="noopener noreferrer"
          class="mt-1 block font-display text-xl leading-snug hover:text-accent-300"
        >
          {item.title}
        </a>
        {#if item.summary}
          <p class="mt-1 text-sm text-muted">{stripHtml(item.summary)}</p>
        {/if}
        <div class="mt-3 flex items-center gap-2">
          <form method="POST" action="?/bookmark" use:enhance>
            <input type="hidden" name="item_id" value={item.id} />
            <input type="hidden" name="value" value={(!item.bookmarked).toString()} />
            <button
              type="submit"
              class="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs transition-colors duration-fast ease-saganta {item.bookmarked
                ? 'text-warm-500'
                : 'text-muted hover:text-text'}"
              title={item.bookmarked ? 'Bookmark entfernen' : 'Bookmarken'}
            >
              <Icon name="bookmark" size={13} filled={item.bookmarked} />
              {item.bookmarked ? 'Gemerkt' : 'Merken'}
            </button>
          </form>
          <form method="POST" action="?/read" use:enhance>
            <input type="hidden" name="item_id" value={item.id} />
            <input type="hidden" name="value" value={(!item.read).toString()} />
            <button
              type="submit"
              class="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs text-muted transition-colors duration-fast ease-saganta hover:text-text"
              title={item.read ? 'Als ungelesen markieren' : 'Als gelesen markieren'}
            >
              <Icon name={item.read ? 'rotate-ccw' : 'check'} size={13} />
              {item.read ? 'Ungelesen' : 'Gelesen'}
            </button>
          </form>
          <!-- Cross-App wie im Briefing: Artikel als Notiz/Aufgabe in den Kalender. -->
          <a
            href={kalenderCaptureUrl(item.title)}
            class="inline-flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs text-muted transition-colors duration-fast ease-saganta hover:text-accent-300"
            title="Im Kalender notieren"
          >
            <Icon name="calendar" size={13} />
          </a>
        </div>
      </li>
    {/each}
  </ul>
</section>
{/if}
