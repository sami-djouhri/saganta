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
          class="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent-400"
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
        <p class="mt-2 text-sm text-warm-500">{form.error}</p>
      {/if}

      <!-- Schritt 2: Vorschlag bestätigen/korrigieren -->
      {#if suggestion}
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
          <div class="flex flex-wrap items-end gap-2">
            <select
              name="type"
              value={suggestion.type}
              class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text"
            >
              <option value="event">Termin</option>
              <option value="todo">Aufgabe</option>
            </select>
            <input
              name="title"
              value={suggestion.title}
              class="flex-1 rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text"
            />
            <input
              name="date"
              type="date"
              value={suggestion.date ?? prefillDate}
              class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text"
            />
            <input
              name="start_time"
              type="time"
              value={suggestion.start_time ?? ''}
              class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm text-text"
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
