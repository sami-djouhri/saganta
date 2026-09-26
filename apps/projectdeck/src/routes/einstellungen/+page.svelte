<script lang="ts">
  import { NAV } from '$lib/meta';
</script>

<h1 class="font-display text-2xl">Einstellungen</h1>
<div class="mt-6 flex flex-col gap-4">
  <section class="rounded-lg border border-border bg-surface-2/40 p-4 text-sm">
    <h2 class="font-medium">Kalender-Integration</h2>
    <p class="mt-1 text-muted">
      ProjectDeck pusht planbare Tasks an den nativen Saganta-Kalender und liest geplante Blöcke
      zurück. Pro Projekt über „⟳ Im Kalender planen". Frozen-/Shutdown-Projekte werden nie
      automatisch eingeplant.
    </p>
  </section>
  <section class="rounded-lg border border-border bg-surface-2/40 p-4 text-sm">
    <h2 class="font-medium">KI-Unterstützung</h2>
    <p class="mt-1 text-muted">
      Optional (serverseitig via <code class="font-mono">LLM_ENABLED</code>). Standardmäßig liefert
      ProjectDeck rein regelbasierte, erklärbare Empfehlungen; mit aktivem LLM (node2-Gemma) werden
      die Regel-Begründungen sprachlich verdichtet, nie ohne Begründung.
    </p>
  </section>
  <section class="rounded-lg border border-border bg-surface-2/40 p-4 text-sm">
    <h2 class="font-medium">Bereiche</h2>
    <ul class="mt-2 flex flex-wrap gap-2 text-muted">
      {#each NAV as n}<li class="rounded bg-surface px-2 py-0.5">{n.label}</li>{/each}
    </ul>
  </section>
</div>
