<script lang="ts">
  /**
   * Zeit von Hand im Web (seit 2026-11-08, Gleichstand-Luecke 6): laufender
   * Timer mit Stopp, darunter was heute gerade dran ist, mit Starten, Stoppen
   * und Erledigt. Gleiche Regeln wie die App (`$lib/handzeit`).
   *
   * Gerechnet wird erst nach dem Mount mit der Uhr des Browsers: der
   * SSR-Knoten laeuft auf UTC und laege mit jeder Wanduhrzeit zwei Stunden
   * daneben. Bis dahin zeigt der Block nur den Timer-Titel.
   */
  import { onMount } from 'svelte';
  import { enhance } from '$app/forms';
  import type { HabitSession, KalenderEvent } from '$lib/kalender-bff';
  import { fmtTime } from '$lib/cal';
  import {
    hakenFehler,
    hakenVorlage,
    laufzeitText,
    sitzungsSchritte,
    terminSchritte,
    verweisAuf,
    wanduhr,
    STARTEN_VORLAUF_MINUTEN,
    type LaufenderTimer,
    type Schritt,
  } from '$lib/handzeit';

  interface Props {
    timer?: LaufenderTimer | null;
    belege?: string[];
    termine?: KalenderEvent[];
    sitzungen?: HabitSession[];
    fehler?: string | null;
  }
  let { timer = null, belege = [], termine = [], sitzungen = [], fehler = null }: Props = $props();

  let jetzt = $state<Date | null>(null);
  onMount(() => {
    jetzt = new Date();
    const uhr = setInterval(() => (jetzt = new Date()), 30_000);
    return () => clearInterval(uhr);
  });

  interface Dran {
    schluessel: string;
    titel: string;
    typ: 'event' | 'session';
    id: string;
    start: string;
    ende: string;
    schritte: Schritt[];
  }

  const belegt = $derived(new Set(belege));
  const heute = $derived(jetzt ? jetzt.toDateString() : '');

  const dran = $derived.by((): Dran[] => {
    if (!jetzt) return [];
    const j = jetzt;
    const amTag = (iso: string | undefined) => wanduhr(iso)?.toDateString() === heute;
    const liste: Dran[] = [];
    for (const ev of termine) {
      const start = ev.start_at ?? ev.start ?? '';
      if (!amTag(start)) continue;
      const schritte = terminSchritte(ev, j, belegt.has(verweisAuf('event', ev.id)), timer);
      if (schritte.length) {
        liste.push({ schluessel: `e${ev.id}`, titel: ev.title, typ: 'event', id: ev.id, start, ende: ev.end_at ?? ev.end ?? '', schritte });
      }
    }
    for (const s of sitzungen) {
      if (!amTag(s.start)) continue;
      const schritte = sitzungsSchritte(s, j, belegt.has(verweisAuf('session', s.id)), timer);
      const beginn = wanduhr(s.start);
      // Wie die App: kommende Sitzungen erst ab dem Vorlauf, sonst stuende der
      // Abend schon am Morgen hier.
      const zeitig = beginn != null && j.getTime() >= beginn.getTime() - STARTEN_VORLAUF_MINUTEN * 60_000;
      if (schritte.length && (schritte.includes('stoppen') || zeitig)) {
        liste.push({ schluessel: `s${s.id}`, titel: s.habit_name ?? 'Sitzung', typ: 'session', id: s.id, start: s.start, ende: s.end, schritte });
      }
    }
    return liste.sort((a, b) => a.start.localeCompare(b.start));
  });

  // Offener Haken: Schluessel des Eintrags und die Felder.
  let haken = $state<{ schluessel: string; start: string; ende: string } | null>(null);
  const hakenProblem = $derived(haken && jetzt ? hakenFehler(haken.start, haken.ende, jetzt) : null);

  function hakenOeffnen(d: Dran) {
    if (!jetzt) return;
    haken = { schluessel: d.schluessel, ...hakenVorlage(d.start, d.ende, jetzt) };
  }

  const knopf = 'rounded-lg border border-border-stark px-3 py-1 text-xs hover:bg-surface-2';
  const feld = 'min-h-9 rounded-lg border border-border-stark bg-surface px-2 text-sm text-text';
</script>

{#if timer || dran.length > 0 || fehler}
  <section class="space-y-3 rounded-xl border border-border bg-surface-2/40 p-4">
    <h3 class="font-mono text-xs uppercase tracking-wider text-muted">Jetzt dran</h3>
    {#if fehler}
      <p class="text-sm text-kupfer">{fehler}</p>
    {/if}

    {#if timer}
      <div class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-accent-500/60 bg-accent-500/10 px-3 py-2">
        <div class="min-w-0">
          <span class="text-sm font-medium">⏱ {timer.titel ?? 'Timer'}</span>
          {#if jetzt}<span class="ml-2 font-mono text-xs tabular-nums text-muted">{laufzeitText(timer, jetzt)}</span>{/if}
        </div>
        <form method="POST" action="?/zeitStopp" use:enhance>
          <button type="submit" class="rounded-lg bg-accent-500 px-3 py-1 text-xs font-semibold text-accent-ink hover:bg-accent-400">Stoppen</button>
        </form>
      </div>
    {/if}

    {#each dran as d (d.schluessel)}
      <article class="space-y-2 rounded-lg border border-border bg-surface/60 p-3">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <strong class="min-w-0 truncate text-sm font-medium">{d.titel}</strong>
          <span class="shrink-0 font-mono text-xs tabular-nums text-muted">
            {fmtTime(d.start)}{d.ende ? `–${fmtTime(d.ende)}` : ''}
          </span>
        </div>
        <div class="flex flex-wrap gap-2">
          {#if d.schritte.includes('starten')}
            <form method="POST" action="?/zeitStart" use:enhance>
              <input type="hidden" name="titel" value={d.titel} />
              <input type="hidden" name="bezug_typ" value={d.typ} />
              <input type="hidden" name="bezug_id" value={d.id} />
              <button type="submit" class={knopf}>{timer ? 'Starten (anderen beenden)' : 'Starten'}</button>
            </form>
          {/if}
          {#if d.schritte.includes('stoppen')}
            <form method="POST" action="?/zeitStopp" use:enhance>
              <button type="submit" class={knopf}>Stoppen</button>
            </form>
          {/if}
          {#if d.schritte.includes('erledigt') && haken?.schluessel !== d.schluessel}
            <button type="button" class={knopf} onclick={() => hakenOeffnen(d)}>Erledigt</button>
          {/if}
        </div>
        {#if haken && haken.schluessel === d.schluessel}
          <form
            method="POST"
            action="?/zeitHaken"
            use:enhance={() => async ({ update }) => {
              haken = null;
              await update();
            }}
            class="flex flex-wrap items-end gap-2"
          >
            <input type="hidden" name="titel" value={d.titel} />
            <input type="hidden" name="bezug_typ" value={d.typ} />
            <input type="hidden" name="bezug_id" value={d.id} />
            <label class="flex flex-col gap-1 text-xs text-muted">
              Von
              <input type="datetime-local" name="start" bind:value={haken.start} required class={feld} />
            </label>
            <label class="flex flex-col gap-1 text-xs text-muted">
              Bis
              <input type="datetime-local" name="ende" bind:value={haken.ende} required class={feld} />
            </label>
            <button type="submit" disabled={hakenProblem != null} class="{knopf} disabled:opacity-50">Eintragen</button>
            <button type="button" class={knopf} onclick={() => (haken = null)}>Abbrechen</button>
            {#if hakenProblem}<p class="w-full text-xs text-kupfer">{hakenProblem}</p>{/if}
          </form>
        {/if}
      </article>
    {/each}
  </section>
{/if}
