<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Zur Veröffentlichung</h1>
<p class="mt-1 text-sm text-muted">
  Projekte, die öffentlich werden sollen. Wie weit ein Projekt dafür ist, pflegst du im
  Projekt selbst, im Reiter „Veröffentlichung".
</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Kein Projekt soll öffentlich werden." /></div>
