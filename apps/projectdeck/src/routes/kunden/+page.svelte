<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Kundenprojekte</h1>
<p class="mt-1 text-sm text-muted">Getrennt von privaten Experimenten. Hard-Deadlines haben Vorrang.</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Keine Kundenprojekte." /></div>
