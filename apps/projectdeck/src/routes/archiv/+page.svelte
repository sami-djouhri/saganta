<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Archiv</h1>
<p class="mt-1 text-sm text-muted">Archivierte und abgeschaltete Projekte.</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Archiv ist leer." /></div>
