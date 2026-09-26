<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Public Pipeline</h1>
<p class="mt-1 text-sm text-muted">
  Projekte mit einem Public-Ziel (Target Visibility). Public-Readiness pflegst du im jeweiligen
  Projekt-Tab „Public Readiness".
</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Keine Public-Kandidaten." /></div>
