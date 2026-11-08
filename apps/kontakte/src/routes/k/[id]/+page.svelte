<script lang="ts">
  import { enhance } from '$app/forms';
  import { page } from '$app/stores';
  import { Button, Icon, NotizenBlock, appUrlById } from '@saganta/ui';
  import KontaktFormular from '$lib/components/KontaktFormular.svelte';
  import { datumLang, gruppenStil, kuerzel, telAdresse } from '$lib/anzeige';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  const k = $derived(data.kontakt);
  const notizenBasis = $derived(appUrlById('notizen', $page.url.host));
  const kalenderBasis = $derived(appUrlById('calendar', $page.url.host));

  function wocheVon(start: string | null): string {
    return start && /^\d{4}-\d{2}-\d{2}/.test(start) ? start.slice(0, 10) : '';
  }
  function zeitKurz(start: string | null): string {
    if (!start) return '';
    const datum = datumLang(start.slice(0, 10));
    const uhr = /T(\d{2}:\d{2})/.exec(start)?.[1];
    return uhr && uhr !== '00:00' ? `${datum}, ${uhr}` : datum;
  }

  const fehlermeldung = $derived(form && 'fehler' in form ? String(form.fehler) : null);
  const notizFehler = $derived(form && 'notizFehler' in form ? String(form.notizFehler) : null);
</script>

<svelte:head><title>{k.name} · Kontakte</title></svelte:head>

<div class="max-w-2xl space-y-6">
  <header class="space-y-3">
    <a href="/" class="text-sm text-muted hover:text-text">← Kontakte</a>
    <div class="flex items-center gap-4">
      <span
        class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border text-lg font-semibold"
        style={k.gruppe ? gruppenStil(k.gruppe) : ''}
        aria-hidden="true">{kuerzel(k.name)}</span
      >
      <div class="min-w-0">
        <h1 class="truncate font-display text-3xl leading-tight">{k.name}</h1>
        {#if k.gruppe}
          <span class="mt-1 inline-block rounded-full border px-2 py-0.5 text-xs" style={gruppenStil(k.gruppe)}>{k.gruppe}</span>
        {/if}
      </div>
    </div>
    <div class="flex flex-wrap gap-2">
      {#if k.telefon}
        <a href={telAdresse(k.telefon)} class="inline-flex items-center gap-1.5 rounded-md border border-border-stark px-3 py-1.5 text-sm hover:bg-surface-2">
          <Icon name="smartphone" size={15} /> Anrufen
        </a>
      {/if}
      {#if k.email}
        <a href="mailto:{k.email}" class="inline-flex items-center gap-1.5 rounded-md border border-border-stark px-3 py-1.5 text-sm hover:bg-surface-2">
          <Icon name="mail" size={15} /> Mail
        </a>
      {/if}
    </div>
  </header>

  {#if fehlermeldung}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{fehlermeldung}</p>
  {/if}
  {#if form && 'gespeichert' in form}
    <p class="rounded-lg border border-erfolg/40 bg-erfolg/10 px-3 py-2 text-sm">Gespeichert.</p>
  {/if}

  {#key k.geaendert_am}
    <KontaktFormular kontakt={k} gruppen={data.gruppen} aktion="?/speichern" knopf="Speichern" />
  {/key}

  <section class="space-y-3" aria-labelledby="termine">
    <h2 id="termine" class="flex items-center gap-2 font-medium"><Icon name="calendar" size={16} /> Termine</h2>
    {#if k.termine.length === 0}
      <p class="text-sm text-muted">Noch kein Termin verknüpft.</p>
    {:else}
      <ul class="divide-y divide-border rounded-lg border border-border">
        {#each k.termine as t (t.ref)}
          <li class="flex items-center gap-3 px-3 py-2">
            <a
              href="{kalenderBasis}/?view=week{wocheVon(t.start) ? `&week=${wocheVon(t.start)}` : ''}"
              class="min-w-0 flex-1 hover:underline"
            >
              <span class="block truncate">{t.label || '(ohne Titel)'}</span>
              <span class="block text-xs text-muted">{zeitKurz(t.start)}</span>
            </a>
            <form method="POST" action="?/terminLoesen" use:enhance>
              <input type="hidden" name="ref" value={t.ref} />
              <button type="submit" class="text-muted hover:text-text" aria-label="Verknüpfung lösen"><Icon name="x" size={14} /></button>
            </form>
          </li>
        {/each}
      </ul>
    {/if}

    <form method="GET" class="flex gap-2">
      <input
        name="terminsuche"
        value={data.terminsuche ?? ''}
        placeholder="Termin suchen…"
        aria-label="Termin suchen"
        class="min-w-0 flex-1 rounded-md border border-border-stark bg-surface-2 px-3 py-1.5 text-sm"
      />
      <Button type="submit" variant="ghost" size="sm"><Icon name="search" size={15} /> Suchen</Button>
    </form>
    {#if data.funde}
      {#if data.funde.stumm}
        <p class="text-sm text-warnung">Der Kalender antwortet gerade nicht. <a href="?terminsuche={encodeURIComponent(data.terminsuche ?? '')}" class="underline">Erneut versuchen</a></p>
      {:else if data.funde.treffer.length === 0}
        <p class="text-sm text-muted">Kein Termin gefunden (60 Tage zurück bis 180 Tage voraus).</p>
      {:else}
        <ul class="space-y-1">
          {#each data.funde.treffer as f (f.ref)}
            <li>
              <form method="POST" action="?/terminVerknuepfen" use:enhance class="flex items-center gap-3 rounded-md px-2 py-1 hover:bg-surface-2">
                <input type="hidden" name="ref" value={f.ref} />
                <input type="hidden" name="label" value={f.label} />
                <input type="hidden" name="start" value={f.start ?? ''} />
                <span class="min-w-0 flex-1 truncate text-sm">{f.label} <span class="text-muted">· {zeitKurz(f.start)}</span></span>
                <Button type="submit" variant="ghost" size="sm">Verknüpfen</Button>
              </form>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  </section>

  <section aria-label="Notizen">
    <NotizenBlock
      typ="kontakt"
      ref={k.id}
      label={k.name}
      notizen={data.notizen}
      {notizenBasis}
      fehler={notizFehler}
      {enhance}
    />
  </section>

  <form method="POST" action="?/loeschen" use:enhance class="border-t border-border pt-4">
    <button type="submit" class="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fehler">
      <Icon name="archive" size={15} /> In den Papierkorb
    </button>
  </form>
</div>
