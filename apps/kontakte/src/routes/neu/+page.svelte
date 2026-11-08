<script lang="ts">
  import KontaktFormular from '$lib/components/KontaktFormular.svelte';
  import type { ActionData, PageData } from './$types';

  let { data, form }: { data: PageData; form: ActionData } = $props();
</script>

<svelte:head><title>Neuer Kontakt</title></svelte:head>

<div class="max-w-2xl space-y-5">
  <header>
    <a href="/" class="text-sm text-muted hover:text-text">← Kontakte</a>
    <h1 class="font-display text-3xl leading-tight">Neuer Kontakt</h1>
  </header>
  {#if form?.fehler}
    <p class="rounded-lg border border-fehler/40 bg-fehler/10 px-3 py-2 text-sm">{form.fehler}</p>
  {/if}
  <KontaktFormular gruppen={data.gruppen} aktion="" knopf="Anlegen" />
</div>
