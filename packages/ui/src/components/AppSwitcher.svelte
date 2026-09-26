<script lang="ts">
  import Icon from './Icon.svelte';
  import { appUrl, appsFuer } from '../apps';

  interface Props {
    /** id der aktiven App (hervorgehoben). Undefined = keine Hervorhebung. */
    currentAppId?: string;
    /**
     * Host der laufenden Anfrage (`page.url.host`). Bestimmt, in welchem Raum
     * die Ziel-Adressen gebildet werden: wer unter `.home` klickt, bleibt unter
     * `.home`. Ohne Angabe gilt der öffentliche Raum (Verhalten vor 2026-09-13).
     */
    host?: string | null;
  }
  let { currentAppId, host }: Props = $props();

  let apps = $derived(appsFuer(host));

  let open = $state(false);
  let wrap: HTMLDivElement | undefined = $state();

  function onWindowClick(e: MouseEvent) {
    if (open && wrap && !wrap.contains(e.target as Node)) open = false;
  }
  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') open = false;
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onKeydown} />

<div class="relative" bind:this={wrap}>
  <button
    type="button"
    onclick={() => (open = !open)}
    class="grid size-8 place-items-center rounded-md border border-border text-muted transition-colors duration-fast ease-saganta hover:bg-surface-2 hover:text-text"
    aria-haspopup="menu"
    aria-expanded={open}
    aria-label="App-Wechsler"
    title="Apps"
  >
    <Icon name="layout-grid" size={18} />
  </button>

  {#if open}
    <div
      role="menu"
      class="absolute left-0 top-full z-40 mt-1.5 w-72 overflow-hidden rounded-xl border border-border bg-surface-2 shadow-lg"
    >
      <div class="border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted">
        Saganta-Apps
      </div>
      <div class="grid max-h-[70vh] grid-cols-3 gap-1 overflow-y-auto p-2">
        {#each apps as app (app.id)}
          <a
            href={appUrl(app, host)}
            class="flex flex-col items-center gap-1.5 rounded-lg px-2 py-3 text-center transition-colors duration-fast ease-saganta hover:bg-surface {app.id ===
            currentAppId
              ? 'bg-accent-500/10 text-accent-300'
              : 'text-muted hover:text-text'}"
            aria-current={app.id === currentAppId ? 'page' : undefined}
            title={app.description}
          >
            <Icon name={app.icon} size={20} />
            <span class="text-xs leading-tight">{app.name}</span>
          </a>
        {/each}
      </div>
    </div>
  {/if}
</div>
