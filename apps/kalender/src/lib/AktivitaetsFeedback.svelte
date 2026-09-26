<script lang="ts">
  import { enhance } from '$app/forms';
  import { Icon } from '@saganta/ui';
  import type { ReviewableActivity } from '$lib/kalender-bff';
  import { activityIcon } from '$lib/cal';

  interface Props {
    activity: ReviewableActivity;
  }
  let { activity }: Props = $props();

  // Nach dem Absenden lädt der Server reviewable neu (Aktivität verschwindet):
  // `done` überbrückt den Moment bis dahin mit einem kurzen Danke.
  let done = $state(false);
  let expanded = $state(false);

  const icon = $derived(activityIcon(activity.activity_type));
  const zeit = $derived(activity.start.slice(11, 16)); // naive Berlin-ISO → HH:MM

  const WD = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  // "2026-07-23" → "Do 23.7." (UTC-Konstruktion → kein Zeitzonen-Drift beim Wochentag)
  function fmtTag(iso: string): string {
    const [y, m, d] = iso.split('-').map(Number);
    const wd = WD[new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)).getUTCDay()];
    return `${wd} ${d}.${m}.`;
  }
  const tag = $derived(fmtTag(activity.occurrence_date));
</script>

<li class="rounded-lg border border-border bg-surface/60 px-3 py-2.5">
  {#if done}
    <p class="text-sm text-erfolg">✓ Notiert: danke!</p>
  {:else}
    <div class="mb-2 flex items-center gap-2">
      <span class="mt-0.5 text-muted"><Icon name={icon} size={15} /></span>
      <span class="min-w-0 flex-1 truncate text-sm font-medium">{activity.title}</span>
      <span class="shrink-0 text-xs text-muted">{tag} · {zeit}</span>
    </div>

    <form
      method="POST"
      action="?/activityFeedback"
      use:enhance={() =>
        async ({ result, update }) => {
          if (result.type === 'success') done = true;
          await update({ reset: false });
        }}
    >
      <input type="hidden" name="event_id" value={activity.instance_id} />

      <!-- 1-Tap: jeder Button sendet sofort mit seinem energy_after-Wert -->
      <div class="flex gap-2">
        <button
          type="submit"
          name="energy_after"
          value="energetisiert"
          class="flex-1 rounded-md border border-border px-2 py-1.5 text-sm hover:border-erfolg/40 hover:bg-erfolg/10"
          >💪 stark</button
        >
        <button
          type="submit"
          name="energy_after"
          value="ok"
          class="flex-1 rounded-md border border-border px-2 py-1.5 text-sm hover:border-info/40 hover:bg-info/10"
          >🙂 ok</button
        >
        <button
          type="submit"
          name="energy_after"
          value="erschöpft"
          class="flex-1 rounded-md border border-border px-2 py-1.5 text-sm hover:border-fehler/40 hover:bg-fehler/10"
          >🥵 kaputt</button
        >
      </div>

      <!-- Optionale Randnotiz + Zufriedenheit (wird mit dem energy-Tap mitgesendet) -->
      {#if expanded}
        <div class="mt-3 space-y-3 border-t border-border pt-3">
          <div class="space-y-1.5">
            <p class="text-xs uppercase tracking-wider text-muted">Zufrieden?</p>
            <div class="flex gap-2">
              {#each ['gut', 'mittel', 'schlecht'] as s}
                <label class="cursor-pointer">
                  <input type="radio" name="satisfaction" value={s} class="peer sr-only" />
                  <span
                    class="block rounded-md border border-border px-2.5 py-1 text-sm capitalize peer-checked:border-accent-500 peer-checked:bg-accent-500/15 peer-checked:text-accent-200"
                    >{s}</span
                  >
                </label>
              {/each}
            </div>
          </div>
          <textarea
            name="note"
            rows="2"
            maxlength="2000"
            placeholder="Kurze Randnotiz, was gelernt, was nochmal vertiefen, wie war's?"
            class="w-full rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm outline-none focus:border-accent-400"
          ></textarea>
          <p class="text-xs text-muted">Tippe oben ein Gefühl an, um die Notiz zu speichern.</p>
        </div>
      {:else}
        <button
          type="button"
          onclick={() => (expanded = true)}
          class="mt-2 inline-flex items-center gap-1 text-xs text-muted hover:text-accent-300"
          ><Icon name="plus" size={12} /> Notiz / Details</button
        >
      {/if}
    </form>
  {/if}
</li>
