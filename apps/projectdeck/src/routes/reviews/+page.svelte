<script lang="ts">
  import ProjectGrid from '$lib/components/ProjectGrid.svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<h1 class="font-display text-2xl">Fällige Durchsichten</h1>
<p class="mt-1 text-sm text-muted">
  Projekte, deren Durchsicht überfällig ist (das eingestellte Intervall ist abgelaufen). Was du bei einer Durchsicht
  entscheidest, hältst du im Reiter „Durchsichten" fest.
</p>
<div class="mt-6"><ProjectGrid projects={data.projects} empty="Keine überfälligen Reviews." /></div>
