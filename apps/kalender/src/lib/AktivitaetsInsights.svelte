<script lang="ts">
  import type { ActivityInsight } from '$lib/kalender-bff';
  import { Icon } from '@saganta/ui';
  import { activityIcon } from '$lib/cal';

  interface Props {
    insights?: ActivityInsight[];
    /** Ohne eigene Card rendern, für Einbettung in die „Einblicke"-Gruppe. */
    bare?: boolean;
  }
  let { insights = [], bare = false }: Props = $props();
</script>

{#snippet body()}
  <h3 class="mb-0.5 font-mono text-xs uppercase tracking-wider text-muted">Was Saganta gelernt hat</h3>
  <p class="mb-3 text-[11px] text-muted">aus deinen Rückmeldungen, passt sich mit der Zeit an</p>
  <ul class="space-y-2">
    {#each insights as ins (ins.activity_type)}
      <li class="flex items-start gap-2.5 rounded-lg border border-border bg-surface/60 px-3 py-2">
        <span class="mt-0.5 text-muted"><Icon name={activityIcon(ins.activity_type)} size={15} /></span>
        <div class="min-w-0 flex-1">
          <p class="text-sm">{ins.text}</p>
          <p class="text-[11px] text-muted">
            {ins.count} Rückmeldung{ins.count === 1 ? '' : 'en'}
          </p>
        </div>
      </li>
    {/each}
  </ul>
{/snippet}

{#if insights.length > 0}
  {#if bare}
    {@render body()}
  {:else}
    <section class="rounded-xl border border-border bg-surface-2/40 p-4">
      {@render body()}
    </section>
  {/if}
{/if}
