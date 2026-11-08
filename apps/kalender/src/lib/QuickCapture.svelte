<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';

  interface Suggestion {
    type: 'event' | 'todo';
    title: string;
    date: string | null;
    start_time: string | null;
    end_time: string | null;
    confidence?: string;
    source?: string;
    dauer_min?: number | null;
    wiederholung?: string | null;
    ort?: string | null;
    vorschlaege?: { date: string; start_time: string; end_time: string; abschnitt: string }[];
  }

  function dauerText(min: number): string {
    const h = Math.floor(min / 60);
    const m = min % 60;
    if (!h) return `${m} Min.`;
    return m ? `${h} Std. ${m} Min.` : `${h} Std.`;
  }

  function tagText(iso: string): string {
    return new Date(`${iso}T12:00:00`).toLocaleDateString('de-DE', {
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
    });
  }

  interface Props {
    /** Vorbefüllung aus Cross-App-Deep-Link (?capture=). */
    prefill?: string;
    prefillDate?: string;
    /** Server-Action-Ergebnis (parsed / committed / error). */
    form?: {
      parsed?: Suggestion;
      committed?: { type: string; title: string };
      error?: string;
    } | null;
  }
  let { prefill = '', prefillDate = '', form = null }: Props = $props();

  // Beim ersten Render offen, wenn per Deep-Link ein Text kam.
  let open = $state(Boolean(prefill));
  let text = $state(prefill);
  let busy = $state(false);

  const suggestion = $derived(form?.parsed ?? null);
  // Dauer ohne Uhrzeit: nichts eintragen, sondern freie Zeiten vorschlagen;
  // angelegt wird erst die angetippte (Entscheid 2026-11-01).
  const ohneZeit = $derived(Boolean(suggestion?.dauer_min && !suggestion?.start_time));

  const TAGE: Record<string, string> = {
    MO: 'Montag', TU: 'Dienstag', WE: 'Mittwoch', TH: 'Donnerstag', FR: 'Freitag', SA: 'Samstag', SU: 'Sonntag',
  };
  /** Wie `wiederholungText` in Freitext.kt: aus der RRULE ein Satzteil. */
  function wiederholungText(regel: string): string {
    const t = Object.fromEntries(regel.split(';').map((p) => p.split('=')));
    const n = Number(t.INTERVAL ?? 1);
    if (t.BYDAY && TAGE[t.BYDAY]) return n > 1 ? `alle ${n} Wochen am ${TAGE[t.BYDAY]}` : `jeden ${TAGE[t.BYDAY]}`;
    const art: Record<string, [string, string]> = {
      DAILY: ['täglich', 'Tage'], WEEKLY: ['wöchentlich', 'Wochen'], MONTHLY: ['monatlich', 'Monate'], YEARLY: ['jährlich', 'Jahre'],
    };
    const a = art[t.FREQ];
    if (!a) return 'wiederholt';
    return n > 1 ? `alle ${n} ${a[1]}` : a[0];
  }
</script>

<section class="rounded-xl border border-border bg-surface-2/60 p-4">
  {#if !open}
    <button
      type="button"
      onclick={() => (open = true)}
      class="flex items-center gap-2 text-sm text-muted transition-colors duration-fast ease-saganta hover:text-text"
    >
      <span class="grid size-6 place-items-center rounded-md border border-border"
        ><Icon name="plus" size={14} /></span
      >
      Schnell erfassen: „Zahnarzt Dienstag 15 Uhr"
    </button>
  {:else}
    {#if form?.committed}
      <div class="flex items-center justify-between gap-3">
        <p class="text-sm text-erfolg">
          ✓ {form.committed.type === 'todo' ? 'Aufgabe' : 'Termin'} „{form.committed.title}" angelegt.
        </p>
        <button
          type="button"
          onclick={() => {
            text = '';
            open = false;
          }}
          class="text-sm text-muted hover:text-text"
        >
          Fertig
        </button>
      </div>
    {:else}
      <!-- Schritt 1: Freitext erkennen -->
      <form
        method="POST"
        action="?/captureParse"
        use:enhance={() => {
          busy = true;
          return async ({ update }) => {
            await update({ reset: false });
            busy = false;
          };
        }}
        class="flex flex-col gap-2 sm:flex-row"
      >
        <input
          name="text"
          bind:value={text}
          placeholder="z. B. Vertrag Fitnessstudio kündigen am 30.09."
          class="flex-1 rounded-lg border border-border-stark bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent-400"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          class="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-text disabled:opacity-50"
        >
          {busy ? 'Erkenne…' : 'Erkennen'}
        </button>
      </form>

      {#if form?.error}
        <p class="mt-2 text-sm text-kupfer">{form.error}</p>
      {/if}

      <!-- Schritt 2a: Block ohne Uhrzeit, freie Zeit wählen -->
      {#if suggestion && ohneZeit}
        <div class="mt-3 rounded-lg border border-accent-500/30 bg-accent-500/5 p-3">
          <p class="mb-1 text-xs uppercase tracking-wider text-muted">
            {suggestion.type === 'todo' ? 'Aufgabe' : 'Block'}
          </p>
          <p class="text-sm">
            <span class="font-medium">{suggestion.title}</span>
            <span class="text-muted">
              · {dauerText(suggestion.dauer_min ?? 0)}{suggestion.date ? ` · ${tagText(suggestion.date)}` : ''}{suggestion.ort ===
              'zuhause'
                ? ' · zu Hause'
                : ''}
            </span>
          </p>
          {#if suggestion.vorschlaege?.length}
            <p class="mt-2 text-xs text-muted">Freie Zeit wählen:</p>
            <div class="mt-1 flex flex-wrap gap-2">
              {#each suggestion.vorschlaege as v (v.date + v.start_time)}
                <form
                  method="POST"
                  action="?/captureCommit"
                  use:enhance={() => {
                    busy = true;
                    return async ({ update }) => {
                      await update();
                      busy = false;
                    };
                  }}
                >
                  <input type="hidden" name="type" value={suggestion.type} />
                  <input type="hidden" name="title" value={suggestion.title} />
                  <input type="hidden" name="date" value={v.date} />
                  <input type="hidden" name="start_time" value={v.start_time} />
                  <input type="hidden" name="end_time" value={v.end_time} />
                  <input type="hidden" name="dauer_min" value={suggestion.dauer_min} />
                  <button
                    type="submit"
                    disabled={busy}
                    class="flex min-h-11 flex-col items-start rounded-lg border border-border-stark px-3 py-1 text-left text-sm hover:border-accent-400 disabled:opacity-50"
                  >
                    <span class="text-xs text-muted">{tagText(v.date)}</span>
                    <span class="font-medium tabular-nums">{v.start_time}–{v.end_time}</span>
                  </button>
                </form>
              {/each}
            </div>
          {:else}
            <p class="mt-2 text-sm text-muted">
              {suggestion.date ? 'An diesem Tag ist kein Platz frei.' : 'In den nächsten sieben Tagen ist kein Platz frei.'}
            </p>
          {/if}
          {#if suggestion.type === 'todo' || !suggestion.vorschlaege?.length}
            <form method="POST" action="?/captureCommit" use:enhance class="mt-2">
              <input type="hidden" name="type" value="todo" />
              <input type="hidden" name="title" value={suggestion.title} />
              <input type="hidden" name="date" value={suggestion.date ?? ''} />
              <input type="hidden" name="dauer_min" value={suggestion.dauer_min} />
              <button type="submit" class="text-sm text-muted underline hover:text-text">Ohne Zeit als Aufgabe merken</button>
            </form>
          {/if}
        </div>
      <!-- Schritt 2: Vorschlag bestätigen/korrigieren -->
      {:else if suggestion}
        <form
          method="POST"
          action="?/captureCommit"
          use:enhance={() => {
            busy = true;
            return async ({ update }) => {
              await update();
              busy = false;
            };
          }}
          class="mt-3 rounded-lg border border-accent-500/30 bg-accent-500/5 p-3"
        >
          <p class="mb-2 text-xs uppercase tracking-wider text-muted">Erkannt als</p>
          {#if suggestion.wiederholung}
            <!-- Seit 2026-11-07: „jeden Montag", „alle 2 Wochen" … -->
            <p class="mb-2 text-sm">Wiederholt sich: <span class="font-medium">{wiederholungText(suggestion.wiederholung)}</span></p>
            <input type="hidden" name="wiederholung" value={suggestion.wiederholung} />
          {/if}
          <div class="flex flex-wrap items-end gap-2">
            <select
              name="type"
              value={suggestion.type}
              class="rounded-md border border-border-stark bg-surface px-2 py-1.5 text-sm text-text"
            >
              <option value="event">Termin</option>
              <option value="todo">Aufgabe</option>
            </select>
            <input
              name="title"
              value={suggestion.title}
              class="flex-1 rounded-md border border-border-stark bg-surface px-2 py-1.5 text-sm text-text"
            />
            <input
              name="date"
              type="date"
              value={suggestion.date ?? prefillDate}
              class="rounded-md border border-border-stark bg-surface px-2 py-1.5 text-sm text-text"
            />
            <input
              name="start_time"
              type="time"
              value={suggestion.start_time ?? ''}
              class="rounded-md border border-border-stark bg-surface px-2 py-1.5 text-sm text-text"
            />
            <button
              type="submit"
              disabled={busy}
              class="rounded-md bg-accent-500 px-4 py-1.5 text-sm font-medium text-black hover:bg-accent-400 disabled:opacity-50"
            >
              Anlegen
            </button>
          </div>
        </form>
      {/if}
    {/if}
  {/if}
</section>
