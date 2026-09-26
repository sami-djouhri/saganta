<script lang="ts">
  import { onMount } from 'svelte';

  interface Command {
    id: string;
    label: string;
    hint?: string;
    run: () => void;
  }

  interface Props {
    commands: Command[];
  }
  let { commands }: Props = $props();

  function autoFocus(node: HTMLInputElement) {
    queueMicrotask(() => node.focus());
  }

  let open = $state(false);
  let query = $state('');
  let dialog: HTMLDialogElement | undefined = $state();
  let listEl: HTMLUListElement | undefined = $state();
  // Hervorgehobener Eintrag für Pfeiltasten-Navigation.
  let selected = $state(0);

  const filtered = $derived(
    query
      ? commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
      : commands,
  );

  // Neue Eingabe → Auswahl auf den ersten Treffer; sonst nur an die Länge klemmen
  // (verhindert Out-of-Bounds und falschen aria-activedescendant nach dem Filtern).
  let lastQuery = '';
  $effect(() => {
    if (query !== lastQuery) {
      lastQuery = query;
      selected = 0;
    } else if (selected > filtered.length - 1) {
      selected = Math.max(0, filtered.length - 1);
    }
  });

  // Ausgewählten Eintrag im Blick halten, wenn er unter-/oberhalb des Sichtfelds liegt.
  $effect(() => {
    if (!open) return;
    const el = listEl?.querySelector<HTMLElement>(`[data-idx="${selected}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  });

  function runAt(i: number) {
    const cmd = filtered[i];
    if (cmd) {
      cmd.run();
      dialog?.close();
    }
  }

  // Navigation im Suchfeld: Pfeile wählen, Enter führt aus.
  function onInputKey(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selected = filtered.length ? (selected + 1) % filtered.length : 0;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selected = filtered.length ? (selected - 1 + filtered.length) % filtered.length : 0;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      runAt(selected);
    }
  }

  function handleKey(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      query = '';
      selected = 0;
      open = true;
      queueMicrotask(() => dialog?.showModal());
    } else if (e.key === 'Escape' && open) {
      open = false;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  });
</script>

<dialog
  bind:this={dialog}
  class="mx-auto mt-32 w-full max-w-xl rounded-lg border border-border bg-surface-2 p-0 text-text shadow-2xl backdrop:bg-black/40"
  onclose={() => (open = false)}
>
  <div class="border-b border-border p-3">
    <input
      type="text"
      bind:value={query}
      onkeydown={onInputKey}
      placeholder="Aktion suchen…"
      role="combobox"
      aria-expanded="true"
      aria-controls="cmd-list"
      aria-activedescendant={filtered[selected]?.id ? `cmd-${filtered[selected]?.id}` : undefined}
      aria-label="Aktion suchen"
      class="w-full bg-transparent outline-none placeholder:text-muted"
      use:autoFocus
    />
  </div>
  <ul id="cmd-list" role="listbox" bind:this={listEl} class="max-h-96 overflow-y-auto p-2">
    {#each filtered as cmd, i (cmd.id)}
      <li role="none">
        <button
          type="button"
          id="cmd-{cmd.id}"
          role="option"
          aria-selected={i === selected}
          data-idx={i}
          class="flex w-full items-center justify-between rounded px-3 py-2 text-left"
          class:bg-accent-600={i === selected}
          class:text-white={i === selected}
          onmousemove={() => (selected = i)}
          onclick={() => runAt(i)}
        >
          <span>{cmd.label}</span>
          {#if cmd.hint}<kbd class="text-xs" class:text-muted={i !== selected} class:text-white={i === selected}>{cmd.hint}</kbd>{/if}
        </button>
      </li>
    {/each}
    {#if filtered.length === 0}
      <li role="none" class="px-3 py-6 text-center text-sm text-muted">Keine Treffer.</li>
    {/if}
  </ul>
</dialog>
