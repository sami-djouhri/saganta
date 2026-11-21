<script lang="ts">
  import { untrack } from 'svelte';
  import { enhance } from '$app/forms';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Button, Icon, eingerueckt } from '@saganta/ui';
  import Hervorhebung from '$lib/components/Hervorhebung.svelte';
  import { VERBINDEN_HOECHSTENS } from '$lib/sammel';
  import { HAT_BESCHRIFTUNG, HAT_FILTER, OHNE_BUCH, SORTIERUNGEN, umschalten as inListe } from '$lib/filter';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  // Dieselben sieben Farben wie die App (NotizbuchDialog.kt): nebeneinander
  // unterscheidbar, und ein Notizbuch sieht auf beiden Seiten gleich aus.
  const FARBEN = ['#2563EB', '#059669', '#D97706', '#DC2626', '#7C3AED', '#0891B2', '#64748B'];

  let aktuellesBuch = $derived(data.notizbuecher.find((b) => String(b.id) === data.notizbuch) ?? null);
  let buchBearbeiten = $state(false);

  // Mehrfachauswahl (wie in der App seit 0.3.0). Die Auswahl gilt der
  // angezeigten Liste: wechselt der Filter, fällt heraus, was nicht mehr da ist.
  let auswahlModus = $state(false);
  let auswahl = $state<number[]>([]);
  let sichtbar = $derived(new Set(data.notizen.map((n) => n.id)));
  let gewaehlt = $derived(auswahl.filter((id) => sichtbar.has(id)));
  function umschalten(id: number) {
    auswahl = auswahl.includes(id) ? auswahl.filter((x) => x !== id) : [...auswahl, id];
  }
  function auswahlBeenden() {
    auswahlModus = false;
    auswahl = [];
  }

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

  // Irgendein Filter außer der Suche gesetzt? Dann gibt es „Filter zurücksetzen“.
  let filterAktiv = $derived(
    Boolean(data.notizbuch || data.gewaehlteTags.length || data.hat.length || data.sortierung || data.projekt || data.archivierte),
  );
  function ohneFilter(): string {
    const ziel = new URL($page.url);
    for (const feld of ['buch', 'tag', 'hat', 'sort', 'projekt', 'nur', 'archiv']) ziel.searchParams.delete(feld);
    return `${ziel.pathname}${ziel.search}` || '/';
  }
  function sortieren(wert: string) {
    goto(filterAdresse('sort', wert || null), { noScroll: true });
  }

  function filterAdresse(feld: string, wert: string | null): string {
    const ziel = new URL($page.url);
    if (wert === null) ziel.searchParams.delete(feld);
    else ziel.searchParams.set(feld, wert);
    return `${ziel.pathname}${ziel.search}` || '/';
  }

  // Projektfilter: ein anderes Projekt setzt „nur dieses" zurueck, sonst
  // stuende der Schalter an einem Projekt, fuer das er nie gewaehlt wurde.
  function projektWaehlen(wert: string) {
    const ziel = new URL($page.url);
    if (wert) ziel.searchParams.set('projekt', wert);
    else ziel.searchParams.delete('projekt');
    ziel.searchParams.delete('nur');
    goto(`${ziel.pathname}${ziel.search}`, { noScroll: true });
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
    <h1 class="font-display text-3xl">Notizen</h1>
    <form method="POST" action="?/anlegen" use:enhance class="flex w-full items-center gap-2 sm:w-auto">
      {#if data.notizbuch}
        <input type="hidden" name="notizbuch_id" value={data.notizbuch} />
      {/if}
      <input
        name="titel"
        placeholder="Titel der neuen Notiz"
        class="min-w-0 flex-1 rounded-md border border-border-stark bg-surface px-3 py-2 text-base max-md:min-h-11 sm:w-56 sm:flex-none sm:text-sm"
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
      class="w-full rounded-md border border-border-stark bg-surface py-2 pl-10 pr-3 text-base max-md:min-h-11 sm:text-sm"
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
          class="grid size-11 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text lg:size-9"
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
            class="min-w-0 flex-1 rounded-md border border-border-stark bg-surface px-2 py-1 text-sm"
          />
          <Button type="submit" size="sm" variant="ghost">OK</Button>
        </form>
      {/if}

      <!-- Am Handy EINE waagerecht wischbare Zeile Chips statt einer Liste:
           als umbrechende Chips standen die Notizbuecher in drei Zeilen, und die
           erste Notiz begann erst bei rund 620 px (gemessen 2026-11-14). -->
      <nav class="-mx-1 mt-2 flex gap-1.5 overflow-x-auto px-1 pb-1 text-sm lg:mx-0 lg:flex-col lg:gap-0.5 lg:overflow-visible lg:px-0 lg:pb-0">
        <a
          href={filterAdresse('buch', null)}
          class="flex shrink-0 items-center rounded-full border border-border-stark px-3 py-1.5 max-lg:min-h-11 lg:rounded-md lg:border-0 lg:px-2 {!data.notizbuch
            ? 'bg-surface-2 text-text'
            : 'text-muted hover:text-text'}">Alle</a
        >
        <a
          href={filterAdresse('buch', data.notizbuch === OHNE_BUCH ? null : OHNE_BUCH)}
          class="flex shrink-0 items-center rounded-full border border-border-stark px-3 py-1.5 max-lg:min-h-11 lg:rounded-md lg:border-0 lg:px-2 {data.notizbuch === OHNE_BUCH
            ? 'bg-surface-2 text-text'
            : 'text-muted hover:text-text'}">Ohne Notizbuch</a
        >
        {#each data.notizbuecher as buch (buch.id)}
          <div class="group flex shrink-0 items-center gap-1 lg:shrink">
            <a
              href={filterAdresse('buch', String(buch.id))}
              class="min-w-0 flex-1 truncate rounded-full border border-border-stark px-3 py-1.5 max-lg:flex max-lg:min-h-11 max-lg:items-center lg:rounded-md lg:border-0 lg:px-2 {data.notizbuch ===
              String(buch.id)
                ? 'bg-surface-2 text-text'
                : 'text-muted hover:text-text'}"
            >
              {#if buch.farbe}<span
                  class="mr-1 inline-block size-2 rounded-full align-middle"
                  style="background-color: {buch.farbe}"
                  aria-hidden="true"
                ></span>{/if}{buch.name}
              <span class="ml-1 text-xs text-muted">{buch.anzahl_notizen}</span>
            </a>
            <form
              method="POST"
              action="?/notizbuchLoeschen"
              use:enhance
              class="hidden transition-opacity lg:block lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100"
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

      {#if aktuellesBuch}
        {#if buchBearbeiten}
          <form
            method="POST"
            action="?/notizbuchAendern"
            use:enhance={() =>
              ({ result, update }) => {
                if (result.type === 'success') buchBearbeiten = false;
                return update();
              }}
            class="mt-3 flex flex-col gap-2 rounded-md border border-border p-3"
          >
            <input type="hidden" name="id" value={aktuellesBuch.id} />
            <input type="hidden" name="sortierung" value={aktuellesBuch.sortierung} />
            <label class="text-xs text-muted" for="buch-name">Name</label>
            <input
              id="buch-name"
              name="name"
              value={aktuellesBuch.name}
              class="rounded-md border border-border-stark bg-surface px-2 py-1 text-sm"
            />
            <fieldset class="flex flex-wrap gap-2">
              <legend class="mb-1 text-xs text-muted">Farbe</legend>
              {#each FARBEN as f (f)}
                <label class="cursor-pointer" title={f}>
                  <input
                    type="radio"
                    name="farbe"
                    value={f}
                    checked={(aktuellesBuch.farbe ?? '#2563EB').toUpperCase() === f}
                    class="peer sr-only"
                  />
                  <span
                    class="block size-6 rounded-full ring-offset-2 ring-offset-surface peer-checked:ring-2 peer-checked:ring-text peer-focus-visible:ring-2 peer-focus-visible:ring-akzent"
                    style="background-color: {f}"
                  ></span>
                </label>
              {/each}
            </fieldset>
            <div class="flex gap-2">
              <Button type="submit" size="sm">Speichern</Button>
              <Button type="button" size="sm" variant="ghost" onclick={() => (buchBearbeiten = false)}>
                Abbrechen
              </Button>
            </div>
          </form>
          <!-- Entfernen auch am Handy: das kleine x in der Liste gibt es nur am
               PC (Hover), unter lg fehlte der Weg ganz. -->
          <form method="POST" action="?/notizbuchLoeschen" use:enhance class="mt-2">
            <input type="hidden" name="id" value={aktuellesBuch.id} />
            <Button type="submit" size="sm" variant="danger" title="Die Notizen darin bleiben">
              <Icon name="trash" size={14} /> Notizbuch entfernen
            </Button>
          </form>
        {:else}
          <button
            type="button"
            class="mt-2 flex min-h-11 items-center gap-2 text-sm text-muted hover:text-text lg:min-h-9"
            onclick={() => (buchBearbeiten = true)}
          >
            <Icon name="pen" size={14} /> „{aktuellesBuch.name}" bearbeiten
          </button>
        {/if}
      {/if}

      {#if data.projekte.length}
        <h2 class="mt-4 text-xs font-semibold uppercase tracking-wide text-muted lg:mt-6">Projekt</h2>
        <select
          aria-label="Nach Projekt filtern"
          value={data.projekt}
          onchange={(e) => projektWaehlen(e.currentTarget.value)}
          class="mt-2 min-h-11 w-full rounded-md border border-border-stark bg-surface-2 px-2 text-sm outline-none focus:border-accent-500 lg:min-h-9"
        >
          <option value="">Alle Projekte</option>
          {#each data.projekte as z (z.schluessel)}
            <option value={z.slug} selected={z.erstes && z.slug === data.projekt}>{eingerueckt(z)}</option>
          {/each}
        </select>
        {#if data.projekt && (data.unterprojekte > 0 || data.nurDieses)}
          <a
            href={filterAdresse('nur', data.nurDieses ? null : '1')}
            aria-current={data.nurDieses ? "true" : undefined}
            class="mt-2 flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm lg:min-h-9 {data.nurDieses
              ? 'border-accent-500 bg-accent-500/10 text-akzent'
              : 'border-border-stark text-muted hover:text-text'}"
          >
            <Icon name="folder" size={14} /> Nur dieses Projekt
          </a>
          {#if !data.nurDieses}
            <p class="mt-1 text-xs text-muted">
              Mit {data.unterprojekte === 1 ? 'einem Unterprojekt' : `${data.unterprojekte} Unterprojekten`}.
            </p>
          {/if}
        {/if}
      {/if}

      {#if data.tags.length}
        <h2 class="mt-4 text-xs font-semibold uppercase tracking-wide text-muted lg:mt-6">
          Tags{#if data.gewaehlteTags.length > 1}<span class="ml-1 normal-case tracking-normal">· alle gewählten</span>{/if}
        </h2>
        <div class="-mx-1 mt-2 flex gap-1 overflow-x-auto px-1 pb-1 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0">
          {#each data.tags as tag (tag)}
            <a
              href={filterAdresse('tag', inListe(data.gewaehlteTags, tag))}
              aria-current={data.gewaehlteTags.includes(tag) ? "true" : undefined}
              class="flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs max-lg:min-h-11 max-lg:px-3 {data.gewaehlteTags.includes(tag)
                ? 'border-accent-500 bg-accent-500/10 text-akzent'
                : 'border-border-stark text-muted hover:text-text'}">{tag}</a
            >
          {/each}
        </div>
      {/if}

      <h2 class="mt-4 text-xs font-semibold uppercase tracking-wide text-muted lg:mt-6">Hat</h2>
      <div class="-mx-1 mt-2 flex gap-1 overflow-x-auto px-1 pb-1 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0">
        {#each HAT_FILTER as h (h)}
          <a
            href={filterAdresse('hat', inListe(data.hat, h))}
            aria-current={data.hat.includes(h) ? "true" : undefined}
            class="flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs max-lg:min-h-11 max-lg:px-3 {data.hat.includes(h)
              ? 'border-accent-500 bg-accent-500/10 text-akzent'
              : 'border-border-stark text-muted hover:text-text'}">{HAT_BESCHRIFTUNG[h]}</a
          >
        {/each}
      </div>

      <h2 class="mt-4 text-xs font-semibold uppercase tracking-wide text-muted lg:mt-6">Sortierung</h2>
      <select
        aria-label="Sortierung"
        value={data.sortierung}
        onchange={(e) => sortieren(e.currentTarget.value)}
        class="mt-2 min-h-11 w-full rounded-md border border-border-stark bg-surface-2 px-2 text-sm outline-none focus:border-accent-500 lg:min-h-9"
      >
        {#each SORTIERUNGEN as o (o.wert)}
          <option value={o.wert}>{o.name}</option>
        {/each}
      </select>
      {#if data.suche && !data.sortierung}
        <p class="mt-1 text-xs text-muted">Bei einer Suche zuerst die besten Treffer.</p>
      {/if}

      {#if filterAktiv}
        <a href={ohneFilter()} class="mt-4 flex min-h-11 items-center gap-2 text-sm text-akzent hover:underline lg:min-h-9">
          <Icon name="x" size={14} /> Filter zurücksetzen
        </a>
      {/if}

      <a
        href={filterAdresse('archiv', data.archivierte ? null : '1')}
        class="mt-4 flex min-h-11 items-center gap-2 text-sm lg:mt-6 lg:min-h-9 {data.archivierte
          ? 'text-text'
          : 'text-muted hover:text-text'}"
      >
        <Icon name="archive" size={14} />
        {data.archivierte ? 'Archiv verlassen' : 'Archiv zeigen'}
      </a>
    </aside>

    <!-- Notizen -->
    <section class="min-w-0 flex-1">
      {#if form && 'fehler' in form}
        <p class="mb-3 rounded-md border border-fehler/60 bg-fehler/10 px-3 py-2 text-sm text-fehler">
          {form.fehler}
        </p>
      {/if}
      {#if form && 'sammelMeldung' in form}
        <p class="mb-3 rounded-md border border-border bg-surface-2/40 px-3 py-2 text-sm" role="status">
          {form.sammelMeldung}
          {#if 'papierkorb' in form && form.papierkorb}<a href="/papierkorb" class="ml-1 underline">Zum Papierkorb</a>{/if}
        </p>
      {/if}

      {#if data.notizen.length}
        <div class="mb-3 flex flex-wrap items-center gap-2">
          {#if !auswahlModus}
            <Button type="button" size="sm" variant="ghost" onclick={() => (auswahlModus = true)}>
              <Icon name="check" size={14} /> Auswählen
            </Button>
          {:else}
            <form
              method="POST"
              action="?/sammel"
              use:enhance={({ submitter, cancel }) => {
                if (
                  submitter?.getAttribute('value') === 'loeschen' &&
                  !confirm(`${gewaehlt.length === 1 ? '1 Notiz' : `${gewaehlt.length} Notizen`} in den Papierkorb legen?`)
                ) {
                  cancel();
                  return;
                }
                return async ({ result, update }) => {
                  if (result.type === 'success') auswahlBeenden();
                  await update();
                };
              }}
              class="flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface-2/40 px-3 py-2"
            >
              {#each gewaehlt as id (id)}<input type="hidden" name="id" value={id} />{/each}
              <span class="text-sm">{gewaehlt.length} gewählt</span>
              <button
                type="button"
                class="min-h-11 px-2 text-xs text-muted underline hover:text-text md:min-h-0"
                onclick={() =>
                  (auswahl = gewaehlt.length === data.notizen.length ? [] : data.notizen.map((n) => n.id))}
              >
                {gewaehlt.length === data.notizen.length ? 'keine' : 'alle'}
              </button>
              {#if gewaehlt.length}
                {#if gewaehlt.length >= 2}
                  <!-- Eigene Aktion: verbindet jede gewählte Notiz mit jeder anderen. -->
                  <Button
                    type="submit"
                    formaction="?/verbinden"
                    size="sm"
                    variant="ghost"
                    disabled={gewaehlt.length > VERBINDEN_HOECHSTENS}
                    title={gewaehlt.length > VERBINDEN_HOECHSTENS
                      ? `Höchstens ${VERBINDEN_HOECHSTENS} auf einmal`
                      : 'Jede gewählte Notiz mit jeder anderen verbinden'}
                  >
                    <Icon name="link" size={14} /> Verbinden
                  </Button>
                {/if}
                <Button type="submit" name="aktion" value="anheften" size="sm" variant="ghost">Anheften</Button>
                <Button type="submit" name="aktion" value="loesen" size="sm" variant="ghost">Lösen</Button>
                <Button
                  type="submit"
                  name="aktion"
                  value={data.archivierte ? 'zurueckholen' : 'archivieren'}
                  size="sm"
                  variant="ghost">{data.archivierte ? 'Aus dem Archiv' : 'Archivieren'}</Button
                >
                <select
                  name="buch"
                  aria-label="Ziel-Notizbuch"
                  class="rounded-md border border-border-stark bg-surface px-2 py-1 text-sm max-md:min-h-11"
                >
                  <option value="">ohne Notizbuch</option>
                  {#each data.notizbuecher as b (b.id)}<option value={b.id}>{b.name}</option>{/each}
                </select>
                <Button type="submit" name="aktion" value="verschieben" size="sm" variant="ghost">Verschieben</Button>
                <Button type="submit" name="aktion" value="loeschen" size="sm" variant="ghost">
                  <Icon name="trash" size={14} /> Löschen
                </Button>
              {/if}
              <Button type="button" size="sm" variant="ghost" onclick={auswahlBeenden}>Fertig</Button>
            </form>
          {/if}
        </div>
      {/if}

      {#if data.notizen.length === 0}
        <div class="rounded-lg border border-dashed border-border-stark px-6 py-16 text-center text-muted">
          {#if data.suche}
            <p>Keine Notiz enthält „{data.suche}".</p>
            <a href={filterAdresse('q', null)} class="mt-4 inline-flex min-h-11 items-center rounded-md border border-border-stark px-4 text-sm text-text hover:bg-surface-2">Suche zurücksetzen</a>
          {:else if data.projekt}
            <p>Keine Notiz an „{data.projektName}"{data.nurDieses ? '' : ' oder seinen Unterprojekten'}.</p>
            <a href={filterAdresse('projekt', null)} class="mt-4 inline-flex min-h-11 items-center rounded-md border border-border-stark px-4 text-sm text-text hover:bg-surface-2">Alle Notizen</a>
          {:else if data.archivierte}
            <p>Nichts im Archiv.</p>
            <a href={filterAdresse('archiv', null)} class="mt-4 inline-flex min-h-11 items-center rounded-md border border-border-stark px-4 text-sm text-text hover:bg-surface-2">Alle Notizen</a>
          {:else}
            <p>Noch keine Notiz. Titel oben eintippen und anlegen.</p>
          {/if}
        </div>
      {:else}
        <!-- Drei Spalten erst ab 2xl: neben Rahmen- und Notizbuchleiste waren es bei
             1400 px drei Karten zu 240 px, fast jeder Titel brach um. -->
        <ul class="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
          {#each data.notizen as notiz (notiz.id)}
            <li>
              <a
                href="/notiz/{notiz.id}"
                onclick={(e) => {
                  if (!auswahlModus) return;
                  e.preventDefault();
                  umschalten(notiz.id);
                }}
                aria-pressed={auswahlModus ? gewaehlt.includes(notiz.id) : undefined}
                class="flex h-full flex-col rounded-lg border bg-surface-2/40 p-4 transition-colors hover:border-accent-700 {auswahlModus &&
                gewaehlt.includes(notiz.id)
                  ? 'border-akzent ring-1 ring-akzent'
                  : 'border-border'}"
              >
                <div class="flex items-start justify-between gap-2">
                  {#if auswahlModus}
                    <span
                      class="mt-0.5 grid size-4 shrink-0 place-items-center rounded border {gewaehlt.includes(notiz.id)
                        ? 'border-akzent bg-akzent text-surface'
                        : 'border-border-stark'}"
                      aria-hidden="true"
                    >
                      {#if gewaehlt.includes(notiz.id)}<Icon name="check" size={12} />{/if}
                    </span>
                  {/if}
                  <h3 class="min-w-0 flex-1 font-medium leading-tight">
                    {#if data.suche}
                      <Hervorhebung text={notiz.titel || 'Ohne Titel'} begriffe={suchbegriffe} />
                    {:else}
                      {notiz.titel || 'Ohne Titel'}
                    {/if}
                  </h3>
                  {#if notiz.angeheftet}
                    <span class="shrink-0 text-akzent" title="Angeheftet">
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
                    <span class="flex items-center gap-1 text-akzent" title="Geteilte Links">
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
