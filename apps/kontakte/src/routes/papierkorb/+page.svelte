<script lang="ts">
  import { enhance } from '$app/forms';
  import { Button, Icon } from '@saganta/ui';
  import { datumLang } from '$lib/anzeige';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();

  // Rueckgaengig direkt nach dem Loeschen: dieselbe Leiste wie in den anderen Apps.
  const frisch = $derived(data.kontakte.find((k) => k.id === data.geloescht) ?? null);
</script>

<svelte:head><title>Papierkorb · Kontakte</title></svelte:head>

<div class="max-w-2xl space-y-5">
  <header>
    <p class="font-mono text-xs uppercase tracking-widest text-muted">Saganta · Kontakte</p>
    <h1 class="font-display text-3xl leading-tight">Papierkorb</h1>
    <p class="mt-1 text-sm text-muted">Gelöschte Kontakte bleiben 30 Tage, dann sind sie endgültig weg.</p>
  </header>

  {#if frisch}
    <form method="POST" action="?/wiederherstellen" use:enhance class="flex items-center gap-3 rounded-lg border border-border-stark bg-surface-2 px-3 py-2 text-sm">
      <input type="hidden" name="id" value={frisch.id} />
      <span class="flex-1">„{frisch.name}“ liegt im Papierkorb.</span>
      <Button type="submit" variant="ghost" size="sm"><Icon name="rotate-ccw" size={14} /> Rückgängig</Button>
    </form>
  {/if}

  {#if data.fehler}
    <div class="rounded-lg border border-fehler/40 bg-fehler/10 p-3 text-sm">
      <p>{data.fehler}</p>
      <a href="/papierkorb" class="mt-1 inline-block underline">Erneut versuchen</a>
    </div>
  {/if}
  {#if form && 'fehler' in form}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{form.fehler}</p>
  {/if}
  {#if form && 'zurueck' in form}
    <p class="rounded-lg border border-erfolg/40 bg-erfolg/10 px-3 py-2 text-sm">„{form.zurueck}“ ist zurück.</p>
  {/if}

  {#if data.kontakte.length === 0 && !data.fehler}
    <div class="rounded-xl border border-border p-8 text-center">
      <p class="text-muted">Der Papierkorb ist leer.</p>
      <a href="/" class="mt-3 inline-block underline hover:text-text">Zu den Kontakten</a>
    </div>
  {:else}
    <ul class="divide-y divide-border rounded-xl border border-border">
      {#each data.kontakte as k (k.id)}
        <li class="flex items-center gap-3 px-4 py-3">
          <span class="min-w-0 flex-1">
            <span class="block truncate font-medium">{k.name}</span>
            <span class="block text-xs text-muted">gelöscht am {datumLang(k.geloescht_am)}</span>
          </span>
          <form method="POST" action="?/wiederherstellen" use:enhance>
            <input type="hidden" name="id" value={k.id} />
            <Button type="submit" variant="ghost" size="sm">Wiederherstellen</Button>
          </form>
          <form method="POST" action="?/endgueltig" use:enhance>
            <input type="hidden" name="id" value={k.id} />
            <button type="submit" class="text-sm text-muted hover:text-fehler">Endgültig löschen</button>
          </form>
        </li>
      {/each}
    </ul>
  {/if}
</div>
