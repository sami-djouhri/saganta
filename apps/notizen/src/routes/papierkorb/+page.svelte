<script lang="ts">
  import { enhance } from '$app/forms';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  function datum(roh: string): string {
    const d = new Date(roh);
    return Number.isNaN(d.getTime()) ? '–' : d.toLocaleDateString('de-DE');
  }

  // Der Dienst raeumt nach 30 Tagen auf (gleiche Frist wie in der App).
  function restTage(roh: string): number | null {
    const d = new Date(roh);
    if (Number.isNaN(d.getTime())) return null;
    return Math.max(0, 30 - Math.floor((Date.now() - d.getTime()) / 86_400_000));
  }
</script>

<div class="flex flex-col gap-6">
  <header>
    <h1 class="font-display text-2xl">Papierkorb</h1>
    <p class="mt-1 text-sm text-muted">
      Gelöschte Notizen bleiben 30 Tage hier. Zurückgeholt wird die Notiz samt Verknüpfungen,
      Anhänge kommen nicht mit.
    </p>
  </header>

  {#if form?.fehler}
    <p class="rounded-lg border border-accent-700/60 px-4 py-2 text-sm text-akzent">
      Zurückholen ging nicht: {form.fehler}
    </p>
  {/if}

  {#if data.eintraege.length === 0}
    <p class="rounded-lg border border-dashed border-border px-6 py-16 text-center text-muted">
      Der Papierkorb ist leer.
    </p>
  {:else}
    <ul class="flex flex-col gap-2">
      {#each data.eintraege as e (e.id)}
        {@const rest = restTage(e.geloescht_am)}
        <li class="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border p-3">
          <span class="font-medium">{e.titel || 'Ohne Titel'}</span>
          <span class="text-xs text-muted">
            gelöscht {datum(e.geloescht_am)}{#if rest !== null}, noch {rest}
              {rest === 1 ? 'Tag' : 'Tage'}{/if}{#if e.anhaenge}, {e.anhaenge}
              {e.anhaenge === 1 ? 'Anhang geht' : 'Anhänge gehen'} verloren{/if}
          </span>
          <form method="POST" action="?/wiederherstellen" use:enhance class="ml-auto">
            <input type="hidden" name="id" value={e.id} />
            <button type="submit" class="text-xs text-muted underline hover:text-text">
              zurückholen
            </button>
          </form>
        </li>
      {/each}
    </ul>
  {/if}
</div>
