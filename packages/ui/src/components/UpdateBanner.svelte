<script lang="ts">
  // Nutzt den eingebauten SvelteKit-`updated`-Store: er wird `true`, sobald der
  // Poller (kit.version.pollInterval in svelte.config.js) eine neue deployte
  // Version erkennt. Ein Klick lädt die App mit den neuen Assets neu.
  import { updated } from '$app/stores';

  function reload() {
    location.reload();
  }
</script>

{#if $updated}
  <div
    role="status"
    aria-live="polite"
    class="fixed inset-x-0 bottom-0 z-[1000] flex justify-center px-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
  >
    <div
      class="flex items-center gap-3 rounded-lg border border-accent-400 bg-surface-2 px-4 py-3 shadow-lg"
    >
      <span class="text-sm text-text">Neue Version verfügbar</span>
      <button
        type="button"
        onclick={reload}
        class="rounded-md bg-accent-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-500"
      >
        Jetzt aktualisieren
      </button>
    </div>
  </div>
{/if}
