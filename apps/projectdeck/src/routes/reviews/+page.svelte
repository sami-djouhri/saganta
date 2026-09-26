<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Reviews</h1>
<p class="mt-1 text-sm text-muted">
  Projekte mit überfälligem Review (review_interval_days überschritten). Review-Entscheidungen
  dokumentierst du im Projekt-Tab „Reviews".
</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Keine überfälligen Reviews." /></div>
