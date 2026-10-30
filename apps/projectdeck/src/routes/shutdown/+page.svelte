<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Abschaltkandidaten</h1>
<p class="mt-1 text-sm text-muted">
  Projekte mit Status „Abschalt-Kandidat" oder gesetztem Abschalt-Datum. Im Reiter „Abschalten"
  findest du die Abschalt-Liste und die KI-Empfehlung.
</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Nichts zum Abschalten." /></div>
