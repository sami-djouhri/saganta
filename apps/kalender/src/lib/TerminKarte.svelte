<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon, NotizenBlock } from '@saganta/ui';
  import type { NotizKurz } from '@saganta/notizen-anschluss';
  import type { KalenderEvent } from '$lib/kalender-bff';
  import { startOf, timeCol } from '$lib/cal';
  import {
    artText,
    erinnerungText,
    kartenDatum,
    schnellgriffe,
    terminRechte,
    wiederholungText,
    type Schnellgriff,
  } from '$lib/terminkarte';
  import ProjektMarke from '$lib/ProjektMarke.svelte';

  /**
   * Termin-Karte (seit 2026-11-21, Owner-Wahl, wie in der App): ein Klick auf
   * einen Termin zeigt zuerst ihn, mit Schnellgriffen; der Editor kommt erst
   * ueber „Bearbeiten". Vorher stand jeder Klick direkt im Formular.
   */
  interface Props {
    ev: KalenderEvent;
    heute: string; // YYYY-MM-DD
    kalenderName?: string;
    farbe?: string;
    projektName?: string | null;
    notizen?: NotizKurz[];
    notizenBasis?: string;
    notizenStumm?: boolean;
    notizFehler?: string | null;
    laeuft?: boolean;
    onSchnellgriff: (g: Schnellgriff) => void;
    onBearbeiten: () => void;
    onLoeschen: (modus: 'serie' | 'vorkommen' | 'ab_hier') => void;
    onClose: () => void;
  }
  let {
    ev,
    heute,
    kalenderName = '',
    farbe = '#8a8aa0',
    projektName = null,
    notizen = [],
    notizenBasis = '',
    notizenStumm = false,
    notizFehler = null,
    laeuft = false,
    onSchnellgriff,
    onBearbeiten,
    onLoeschen,
    onClose,
  }: Props = $props();

  const rechte = $derived(terminRechte(ev));
  const griffe = $derived(schnellgriffe(ev));
  const istVorkommen = $derived(String(ev.id).includes('::'));
  const zeilen = $derived(
    [
      ['Ort', ev.location],
      ['Kalender', kalenderName],
      ['Wiederholung', wiederholungText(ev.recurrence_rule)],
      ['Art', artText(ev.activity_type)],
      ['Erinnerung', erinnerungText(ev.reminder_minutes)],
    ].filter(([, wert]) => !!wert) as [string, string][],
  );
  let loeschenOffen = $state(false);

  function onKey(e: KeyboardEvent): void {
    if (e.key === 'Escape') onClose();
  }
  function loeschen(modus: 'serie' | 'vorkommen' | 'ab_hier'): void {
    if (modus === 'serie' && !confirm(istVorkommen ? `Ganze Reihe „${ev.title}“ löschen?` : `„${ev.title}“ löschen?`)) return;
    onLoeschen(modus);
  }
</script>

<svelte:window onkeydown={onKey} />

<div
  class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 pt-[8vh] backdrop-blur-sm"
  role="presentation"
  onclick={(e) => {
    if (e.target === e.currentTarget) onClose();
  }}
>
  <div class="w-full max-w-lg space-y-4">
    <div class="space-y-4 rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl">
      <div class="flex items-start gap-3">
        <span class="mt-2 h-3 w-3 shrink-0 rounded-full" style="background-color:{farbe}"></span>
        <div class="min-w-0 flex-1">
          <h3 class="font-display text-2xl leading-tight">{ev.title}</h3>
          {#if ev.projekt}<div class="mt-1"><ProjektMarke slug={ev.projekt} name={projektName} /></div>{/if}
        </div>
        <button type="button" onclick={onClose} class="rounded-lg p-1 text-muted hover:bg-white/5" aria-label="Schließen"
          ><Icon name="x" size={18} /></button
        >
      </div>

      <div>
        <div class="text-sm text-muted">{kartenDatum(ev, heute)}</div>
        <div class="text-lg font-semibold">{ev.all_day ? 'ganztägig' : timeCol(ev)}</div>
      </div>

      {#if zeilen.length > 0}
        <dl class="grid grid-cols-[7.5rem_1fr] gap-x-3 gap-y-1.5 text-sm">
          {#each zeilen as [was, wert] (was)}
            <dt class="text-muted">{was}</dt>
            <dd class="min-w-0 break-words">{wert}</dd>
          {/each}
        </dl>
      {/if}
      {#if ev.description}
        <p class="whitespace-pre-line text-sm text-muted">{ev.description}</p>
      {/if}
      {#if !rechte.bearbeiten}
        <p class="text-xs text-muted">Wird vom Kalender erzeugt und hier nicht geändert.</p>
      {/if}

      {#if griffe.length > 0}
        <div class="flex flex-wrap gap-2">
          {#each griffe as g (g.schluessel)}
            <button
              type="button"
              disabled={laeuft}
              onclick={() => onSchnellgriff(g)}
              class="rounded-full border border-border px-3 py-1.5 text-sm hover:bg-white/5 disabled:opacity-50"
              >{g.text}</button
            >
          {/each}
        </div>
        {#if istVorkommen}<p class="text-xs text-muted">Verschieben trifft nur diesen Termin der Serie.</p>{/if}
      {/if}

      {#if rechte.bearbeiten}
        <div class="flex items-center gap-2 pt-1">
          <button
            type="button"
            onclick={() => (istVorkommen ? (loeschenOffen = !loeschenOffen) : loeschen('serie'))}
            class="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-accent hover:bg-white/5"
            ><Icon name="trash-2" size={15} /> Löschen</button
          >
          <span class="flex-1"></span>
          <button
            type="button"
            onclick={onBearbeiten}
            class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-bg hover:opacity-90"
            ><Icon name="pen" size={15} /> Bearbeiten</button
          >
        </div>
        {#if istVorkommen && loeschenOffen}
          <div class="flex flex-wrap gap-2">
            <button type="button" onclick={() => loeschen('vorkommen')} class="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-white/5">Nur dieser Termin</button>
            <button type="button" onclick={() => loeschen('ab_hier')} class="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-white/5">Dieser und alle folgenden</button>
            <button type="button" onclick={() => loeschen('serie')} class="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-white/5">Ganze Reihe</button>
          </div>
        {/if}
      {/if}
    </div>

    {#if rechte.bearbeiten}
      <div class="rounded-2xl border border-border bg-surface-2 p-6 shadow-2xl">
        <NotizenBlock
          typ="termin"
          ref={ev.id}
          label={ev.title}
          {notizen}
          {notizenBasis}
          stumm={notizenStumm}
          fehler={notizFehler}
          {enhance}
        />
      </div>
    {/if}
  </div>
</div>
