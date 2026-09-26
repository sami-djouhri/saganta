<script lang="ts">
  /**
   * „Dein Tag" im Kalender: Befinden erfassen, Kapazitaet sehen, einen Anstoss
   * bekommen.
   *
   * ★★ **Was hier seit 2026-09-13 NICHT mehr steht, ist der Punkt.** Vorher trug
   * dieser Block zusaetzlich: die Verfall-Warnung, sechs Vorschlaege
   * nebeneinander, eine Entscheidungsfrage, den vollstaendigen „Plane meinen
   * Tag"-Ablauf mit Vorschau und Bestaetigung, die Wochenquoten und das
   * Aktivitaets-Feedback. Zusammen mit Terminliste, Gewohnheiten,
   * Schnellerfassung, Feierabend, Einblicken, Zeitverteilung, Legende, Zielen
   * und Aufgaben ergab das **dreizehn Baustellen auf einer Seite**. Ein Kalender,
   * auf dem man den Kalender suchen muss.
   *
   * Die Planung ist in die **Aufgaben-App** gezogen, wo die Aufgaben liegen, aus
   * denen geplant wird. Hier bleibt, was den **Tag** betrifft:
   *
   *  - das Befinden (es steuert die Kapazitaet und damit die Planung drueben),
   *  - die Kapazitaet selbst als eine Zeile,
   *  - **ein** naechster Anstoss statt sechs Vorschlaegen.
   *
   * ★ Der Anstoss bleibt bewusst erhalten (Owner: „Vorschlaege will ich nicht
   * gaenzlich abschalten"). Reduziert ist die **Menge**, nicht die Sache: sechs
   * gleichrangige Vorschlaege sind keine Empfehlung, sondern eine zweite Liste
   * zum Durchsehen. Einer mit Begruendung ist eine.
   */
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { AssistantToday, KalenderSuggestion } from '$lib/kalender-bff';
  import { activityIcon } from '$lib/cal';

  interface Props {
    assistant: AssistantToday | null;
    today: string;
    /** Adresse der Aufgaben-App im aktuellen Raum. */
    aufgabenBasis: string;
  }
  let { assistant, today, aufgabenBasis }: Props = $props();

  const cap = $derived(assistant?.capacity ?? null);
  const hasCheckin = $derived(!!assistant?.has_checkin);
  const freeMin = $derived(assistant?.free_minutes ?? 0);

  // Nur der staerkste Vorschlag. Das Backend sortiert nach `score`; `top_suggestion`
  // ist dessen eigene Wahl und hat Vorrang, sonst der erste der Liste.
  const anstoss = $derived<KalenderSuggestion | null>(
    assistant?.top_suggestion ?? assistant?.suggestions?.[0] ?? null,
  );
  const weitere = $derived(Math.max(0, (assistant?.suggestions?.length ?? 0) - 1));

  // Psychologisch codierte Stufen: geladen = leg los, erschoepft = schonen.
  // ★ Der Rueckfall steht mit `!` am Ende, nicht als `?? LEVEL.normal`: ein
  // Indexzugriff kann hier `undefined` sein, und ohne den festen Wert war der
  // Ausdruck vier Zeilen weiter unten als „moeglicherweise undefiniert" markiert.
  const STUFE: Record<string, { label: string; rahmen: string; punkt: string; symbol: string }> = {
    geladen: {
      label: 'Geladen',
      rahmen: 'border-erfolg/40 bg-erfolg/10 text-erfolg',
      punkt: 'bg-erfolg',
      symbol: 'zap',
    },
    normal: {
      label: 'Normal',
      rahmen: 'border-info/40 bg-info/10 text-info',
      punkt: 'bg-info',
      symbol: 'gauge',
    },
    geschont: {
      label: 'Geschont',
      rahmen: 'border-warnung/40 bg-warnung/10 text-warnung',
      punkt: 'bg-warnung',
      symbol: 'battery',
    },
    'erschöpft': {
      label: 'Erschöpft',
      rahmen: 'border-fehler/40 bg-fehler/10 text-fehler',
      punkt: 'bg-fehler',
      symbol: 'armchair',
    },
  };
  const stufe = $derived(STUFE[cap?.level ?? 'normal'] ?? STUFE.normal!);

  function dauer(m: number): string {
    if (!m) return '';
    if (m < 60) return `${m} min`;
    return `${String(Math.round((m / 60) * 10) / 10).replace('.', ',')} h`;
  }
</script>

<section class="space-y-4 rounded-xl border border-border bg-surface-2/40 p-4">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <h2 class="font-display text-lg">Dein Tag</h2>
    <div class="flex items-center gap-2">
      {#if cap}
        <span
          class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium {stufe.rahmen}"
          title={cap.reason}
        >
          <Icon name={stufe.symbol} size={13} />{stufe.label}
        </span>
      {/if}
      {#if freeMin > 0}
        <span class="inline-flex items-center gap-1 text-xs text-muted">
          <Icon name="clock" size={12} />{dauer(freeMin)} frei
        </span>
      {/if}
    </div>
  </div>

  {#if cap}
    <p class="-mt-2 text-sm text-muted">
      {cap.reason}{cap.strain_level === 'kritisch' ? ' · Belastung kritisch' : ''}
    </p>
  {/if}

  <!-- Check-in. Offen, solange er fehlt: er ist die Eingabe, aus der Kapazitaet
       und Tagesplanung entstehen. Ist er erfasst, klappt er zu. -->
  <details
    open={!hasCheckin}
    class="group rounded-lg border {hasCheckin
      ? 'border-border bg-surface/60'
      : 'border-accent-500/40 bg-accent-500/[0.06]'}"
  >
    <summary class="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-sm">
      <span class="text-muted"><Icon name={hasCheckin ? 'circle-check' : 'sunrise'} size={15} /></span>
      <span class="min-w-0 flex-1">
        {#if hasCheckin}
          <span class="text-muted"
            >Erfasst{cap?.checkin?.energy ? ` · Energie ${cap.checkin.energy}` : ''}{cap?.checkin
              ?.sleep_quality
              ? ` · ${cap.checkin.sleep_quality} geschlafen`
              : ''}</span
          >
        {:else}
          <span class="font-medium">Wie fühlst du dich heute?</span>
        {/if}
      </span>
      <Icon
        name="chevron-down"
        size={15}
        class="shrink-0 text-muted transition-transform duration-200 group-open:rotate-180"
      />
    </summary>

    <form method="POST" action="?/checkin" use:enhance class="space-y-3 border-t border-border px-3 py-3">
      {#snippet skala(
        titel: string,
        symbol: string,
        feld: string,
        werte: readonly string[],
        aktuell: string | null | undefined,
      )}
        <fieldset class="space-y-1.5">
          <legend class="flex items-center gap-1.5 text-xs uppercase tracking-wider text-muted">
            <Icon name={symbol} size={12} />{titel}
          </legend>
          <div class="flex gap-1.5">
            {#each werte as w (w)}
              <label class="cursor-pointer">
                <input type="radio" name={feld} value={w} class="peer sr-only" checked={aktuell === w} />
                <!-- Gefuellt statt nur umrandet: ein Rahmen in accent-500 kommt im
                     hellen Thema auf 2,63:1 gegen die Flaeche und liegt damit unter
                     dem Richtwert 3:1 fuer flaechige Bedienelemente (WCAG 1.4.11). -->
                <span
                  class="block rounded-md border border-border px-2.5 py-1 text-sm capitalize peer-checked:border-accent-500 peer-checked:bg-accent-500 peer-checked:font-medium peer-checked:text-accent-ink"
                  >{w}</span
                >
              </label>
            {/each}
          </div>
        </fieldset>
      {/snippet}

      {@render skala('Energie', 'battery', 'energy', ['hoch', 'mittel', 'niedrig'], cap?.checkin?.energy)}
      {@render skala('Geschlafen', 'bed', 'sleep_quality', ['gut', 'mittel', 'schlecht'], cap?.checkin?.sleep_quality)}

      <fieldset class="space-y-1.5">
        <legend class="flex items-center gap-1.5 text-xs uppercase tracking-wider text-muted">
          <Icon name="dumbbell" size={12} />Körperlich
        </legend>
        <div class="flex gap-1.5">
          <label class="cursor-pointer">
            <input
              type="radio"
              name="physical_ready"
              value="true"
              class="peer sr-only"
              checked={cap?.checkin?.physical_ready === true}
            />
            <span
              class="block rounded-md border border-border px-2.5 py-1 text-sm peer-checked:border-erfolg peer-checked:bg-erfolg peer-checked:font-medium peer-checked:text-surface"
              >fit</span
            >
          </label>
          <label class="cursor-pointer">
            <input
              type="radio"
              name="physical_ready"
              value="false"
              class="peer sr-only"
              checked={cap?.checkin?.physical_ready === false}
            />
            <span
              class="block rounded-md border border-border px-2.5 py-1 text-sm peer-checked:border-warnung peer-checked:bg-warnung peer-checked:font-medium peer-checked:text-surface"
              >angeschlagen</span
            >
          </label>
        </div>
      </fieldset>

      <button
        type="submit"
        class="rounded-md border border-accent-500 px-3 py-1.5 text-sm text-accent-300 hover:bg-accent-500/10"
        >Tag abstimmen</button
      >
    </form>
  </details>

  <!-- Ein Anstoss, nicht sechs. -->
  {#if anstoss}
    <div class="rounded-lg border border-border bg-surface/60 p-3">
      <p class="flex items-center gap-1.5 text-xs uppercase tracking-wider text-muted">
        <Icon name="sparkles" size={12} /> Naheliegend jetzt
      </p>
      <p class="mt-1.5 flex items-center gap-2 text-sm font-medium">
        <span class="text-muted"><Icon name={activityIcon(anstoss.kind)} size={15} /></span>
        {anstoss.title}
        {#if anstoss.duration_min}
          <span class="text-xs font-normal text-muted">{dauer(anstoss.duration_min)}</span>
        {/if}
      </p>
      {#if anstoss.reason}
        <p class="mt-0.5 text-xs text-muted">{anstoss.reason}</p>
      {/if}
      {#if weitere > 0}
        <p class="mt-1.5 text-xs text-muted">
          {weitere} weitere{weitere === 1 ? 'r Vorschlag' : ' Vorschläge'} in den
          <a href="{aufgabenBasis}/" class="underline hover:text-text">Aufgaben</a>.
        </p>
      {/if}
    </div>
  {/if}

  <!-- Der Weg zur Planung. Sie liegt dort, wo die Aufgaben liegen. -->
  <a
    href="{aufgabenBasis}/"
    class="flex items-center justify-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-muted transition-colors duration-fast ease-saganta hover:border-accent-500/60 hover:text-text"
  >
    <Icon name="list-todo" size={15} /> Aufgaben und Tagesplanung
    <Icon name="arrow-right" size={14} />
  </a>
</section>
