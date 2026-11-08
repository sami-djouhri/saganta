<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import { abstand, anlass, datumLang, gruppenStil, kuerzel } from '$lib/anzeige';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  let suche = $state('');
  let gruppe = $state('');

  const gefiltert = $derived(
    data.kontakte.filter((k) => {
      if (gruppe && k.gruppe !== gruppe) return false;
      const s = suche.trim().toLowerCase();
      if (!s) return true;
      return [k.name, k.telefon, k.email, k.adresse, k.gruppe, k.notiz].some((t) =>
        (t ?? '').toLowerCase().includes(s),
      );
    }),
  );

  const fehlermeldung = $derived(
    form && typeof form === 'object' && 'fehler' in form ? String(form.fehler) : null,
  );
  const umzug = $derived(form && typeof form === 'object' && 'umzug' in form ? form.umzug : null);
</script>

<svelte:head><title>Kontakte</title></svelte:head>

<div class="space-y-5">
  <header class="flex flex-wrap items-end justify-between gap-3">
    <div>
      <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Kontakte</p>
      <h1 class="font-display text-3xl leading-tight">Kontakte</h1>
    </div>
    <a
      href="/neu"
      class="inline-flex items-center gap-1.5 rounded-md bg-accent-500 px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent-400"
    >
      <Icon name="plus" size={15} /> Neuer Kontakt
    </a>
  </header>

  {#if data.fehler}
    <div class="rounded-lg border border-fehler/40 bg-fehler/10 p-3 text-sm">
      <p class="flex items-center gap-2 font-medium">
        <Icon name="alert-triangle" size={15} /> Die Kontakte konnten nicht geladen werden.
      </p>
      <p class="mt-1 text-muted">{data.fehler}</p>
      <a href="/" class="mt-2 inline-block underline hover:text-text">Erneut versuchen</a>
    </div>
  {/if}

  {#if fehlermeldung}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehlermeldung}</p>
  {/if}

  {#if umzug}
    <p class="rounded-lg border border-erfolg/40 bg-erfolg/10 px-3 py-2 text-sm">
      Aus dem Kalender übernommen: {umzug.uebernommen}{umzug.schon_da
        ? `, ${umzug.schon_da} waren schon da`
        : ''}.
    </p>
  {/if}

  {#if !data.kalenderAktuell}
    <form method="POST" action="?/abgleich" use:enhance class="flex flex-wrap items-center gap-3 rounded-lg border border-warnung/40 bg-warnung/10 px-3 py-2 text-sm">
      <span class="flex-1">Der Kalender hat die letzten Geburtstage noch nicht. Das wird alle zehn Minuten nachgeholt.</span>
      <Button type="submit" variant="ghost" size="sm">Jetzt senden</Button>
    </form>
  {/if}

  {#if data.anstehend.length > 0}
    <section class="rounded-xl border border-border bg-surface-2/50 p-4" aria-labelledby="anstehend">
      <h2 id="anstehend" class="mb-3 flex items-center gap-2 text-sm font-medium text-muted">
        <Icon name="cake" size={15} /> Die nächsten 30 Tage
      </h2>
      <ul class="space-y-1.5">
        {#each data.anstehend as a (a.kontakt_id + a.art + a.bezeichnung)}
          <li>
            <a href="/k/{a.kontakt_id}" class="flex items-baseline gap-3 rounded-md px-2 py-1 hover:bg-surface-2">
              <span class="w-24 shrink-0 text-sm {a.in_tagen === 0 ? 'font-semibold text-akzent' : 'text-muted'}"
                >{abstand(a.in_tagen)}</span
              >
              <span class="font-medium">{a.name}</span>
              <span class="text-sm text-muted">{anlass(a)} · {datumLang(a.datum).replace(/ \d{4}$/, '')}</span>
            </a>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if data.kontakte.length === 0 && !data.fehler}
    <div class="rounded-xl border border-border p-8 text-center">
      <p class="text-muted">Noch keine Kontakte. Die aus dem Kalender lassen sich übernehmen.</p>
      <form method="POST" action="?/umzug" use:enhance class="mt-4">
        <Button type="submit">Aus dem Kalender übernehmen</Button>
      </form>
    </div>
  {:else if data.kontakte.length > 0}
    <div class="flex flex-wrap items-center gap-2">
      <div class="flex min-w-48 flex-1 items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-1.5">
        <span class="text-muted"><Icon name="search" size={15} /></span>
        <input
          bind:value={suche}
          placeholder="Name, Nummer, Mail, Ort…"
          aria-label="Kontakte durchsuchen"
          class="min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        {#if suche}
          <button type="button" onclick={() => (suche = '')} class="text-muted hover:text-text" aria-label="Suche leeren">
            <Icon name="x" size={14} />
          </button>
        {/if}
      </div>
      <span class="text-sm text-muted">{gefiltert.length} von {data.kontakte.length}</span>
    </div>

    {#if data.gruppen.length > 0}
      <div class="flex flex-wrap gap-2" role="group" aria-label="Nach Gruppe filtern">
        <button
          type="button"
          onclick={() => (gruppe = '')}
          aria-pressed={gruppe === ''}
          class="rounded-full border px-3 py-1 text-xs {gruppe === '' ? 'border-border-stark bg-surface-2 text-text' : 'border-border text-muted'}"
          >Alle</button
        >
        {#each data.gruppen as g (g)}
          <button
            type="button"
            onclick={() => (gruppe = gruppe === g ? '' : g)}
            aria-pressed={gruppe === g}
            style={gruppenStil(g)}
            class="rounded-full border px-3 py-1 text-xs {gruppe && gruppe !== g ? 'opacity-50' : ''}">{g}</button
          >
        {/each}
      </div>
    {/if}

    {#if gefiltert.length === 0}
      <div class="rounded-xl border border-border p-6 text-center text-sm text-muted">
        <p>Kein Kontakt passt dazu.</p>
        <button type="button" class="mt-2 underline hover:text-text" onclick={() => { suche = ''; gruppe = ''; }}>Filter zurücksetzen</button>
      </div>
    {:else}
      <ul class="divide-y divide-border rounded-xl border border-border">
        {#each gefiltert as k (k.id)}
          <li>
            <a href="/k/{k.id}" class="flex items-center gap-3 px-4 py-3 hover:bg-surface-2/60">
              <span
                class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border text-xs font-semibold"
                style={k.gruppe ? gruppenStil(k.gruppe) : ''}
                aria-hidden="true">{kuerzel(k.name)}</span
              >
              <span class="min-w-0 flex-1">
                <span class="block truncate font-medium">{k.name}</span>
                <span class="block truncate text-sm text-muted">
                  {[k.telefon, k.email].filter(Boolean).join(' · ') || (k.geburtstag ? `Geburtstag ${datumLang(k.geburtstag)}` : '')}
                </span>
              </span>
              {#if k.gruppe}
                <span class="hidden rounded-full border px-2 py-0.5 text-xs sm:inline" style={gruppenStil(k.gruppe)}>{k.gruppe}</span>
              {/if}
              <Icon name="chevron-right" size={16} />
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</div>
