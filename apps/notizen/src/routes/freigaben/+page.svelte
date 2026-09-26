<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const ZUSTAND_TEXT: Record<string, string> = {
    aktiv: 'aktiv',
    widerrufen: 'zurückgezogen',
    abgelaufen: 'abgelaufen',
    verbraucht: 'aufgebraucht',
    gesperrt: 'gesperrt',
    quelle_weg: 'Notiz gelöscht',
  };

  function datum(roh: string | null): string {
    if (!roh) return '–';
    const d = new Date(roh);
    return Number.isNaN(d.getTime()) ? '–' : d.toLocaleDateString('de-DE');
  }

  let aktive = $derived(data.freigaben.filter((f) => f.zustand === 'aktiv'));
  let erledigte = $derived(data.freigaben.filter((f) => f.zustand !== 'aktiv'));
</script>

<div class="flex flex-col gap-6">
  <header>
    <h1 class="font-display text-2xl">Geteilte Links</h1>
    <p class="mt-1 text-sm text-muted">
      Alles, was von hier aus nach draußen zeigt, an einem Ort, damit nichts unbemerkt offen
      bleibt.
    </p>
  </header>

  {#if data.freigaben.length === 0}
    <p class="rounded-lg border border-dashed border-border px-6 py-16 text-center text-muted">
      Noch nichts geteilt.
    </p>
  {:else}
    {#snippet tabelle(liste: typeof data.freigaben, ueberschrift: string)}
      {#if liste.length}
        <section>
          <h2 class="text-xs font-semibold uppercase tracking-wide text-muted">{ueberschrift}</h2>
          <ul class="mt-2 flex flex-col gap-2">
            {#each liste as f (f.id)}
              <li class="rounded-lg border border-border p-3">
                <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span
                    class="text-muted"
                    title={f.modus === 'chiffriert' ? 'Verschlüsselt' : 'Offen'}
                  >
                    <Icon name={f.modus === 'chiffriert' ? 'shield' : 'globe'} size={16} />
                  </span>
                  {#if f.notiz_id}
                    <a href="/notiz/{f.notiz_id}" class="font-medium hover:underline">
                      {f.notiz_titel || 'Ohne Titel'}
                    </a>
                  {:else}
                    <span class="font-medium text-muted">{f.notiz_titel || 'Ohne Titel'}</span>
                  {/if}
                  <span
                    class="rounded-full border px-2 py-0.5 text-xs {f.zustand === 'aktiv'
                      ? 'border-border text-muted'
                      : 'border-accent-700/60 text-accent-400'}"
                  >
                    {ZUSTAND_TEXT[f.zustand] ?? f.zustand}
                  </span>
                  {#if f.zustand === 'aktiv'}
                    <form method="POST" action="?/widerrufen" use:enhance class="ml-auto">
                      <input type="hidden" name="id" value={f.id} />
                      <button type="submit" class="text-xs text-muted underline hover:text-text">
                        zurückziehen
                      </button>
                    </form>
                  {/if}
                </div>
                <div class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                  <code class="truncate">{data.freigabeBasis}/{f.merkmal}</code>
                  <span>{f.abrufe}{f.max_abrufe ? ` von ${f.max_abrufe}` : ''} geöffnet</span>
                  <span>angelegt {datum(f.erstellt_am)}</span>
                  {#if f.ablauf_am}<span>läuft ab {datum(f.ablauf_am)}</span>{/if}
                  {#if f.letzter_abruf_am}<span>zuletzt {datum(f.letzter_abruf_am)}</span>{/if}
                  {#if f.passwortgeschuetzt}<span>mit Passwort</span>{/if}
                </div>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
    {/snippet}

    {@render tabelle(aktive, 'Aktiv')}
    {@render tabelle(erledigte, 'Nicht mehr abrufbar')}
  {/if}
</div>
