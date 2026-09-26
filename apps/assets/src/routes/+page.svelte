<script lang="ts">
  import type { PageData } from './$types';
  import type { Asset } from '$lib/assets-api';

  interface Props {
    data: PageData;
  }
  let { data }: Props = $props();

  // Dedup gegen Svelte-5 `each_key_duplicate`: dynamische Backend-Daten können
  // denselben id-Key doppelt liefern (z. B. Message-IDs über mehrere IMAP-Konten)
  // → Client-Hydration-Crash legt die Seite lahm. Eindeutige Keys erzwingen. (2026-06-28)
  function uniqueBy<T>(arr: readonly T[], key: (x: T) => unknown): T[] {
    const seen = new Set<unknown>();
    return arr.filter((x) => {
      const k = key(x);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  function fmtEur(v: number | null): string {
    // Explizites 'de-DE' → deterministisch (Tausenderpunkte) unabhängig von der
    // Laufzeit-Locale, kein SSR/Client-Drift.
    return v == null ? '–' : `${Math.round(v).toLocaleString('de-DE')} €`;
  }

  function fmtDelta(v: number): string {
    const s = Math.round(v).toLocaleString('de-DE');
    return `${v > 0 ? '+' : ''}${s} €`;
  }

  function badgeClass(status: string): string {
    if (status === 'critical') return 'bg-fehler/20 text-fehler';
    if (status === 'homelab_active') return 'bg-accent-500/20 text-accent-300';
    if (status === 'daily_use') return 'bg-erfolg/20 text-erfolg';
    return 'bg-muted/20 text-muted';
  }

  const grouped = $derived.by(() => {
    const map = new Map<string, Asset[]>();
    for (const a of data.assets) {
      const k = a.category ?? 'Ohne Kategorie';
      const bucket = map.get(k) ?? [];
      bucket.push(a);
      map.set(k, bucket);
    }
    // innerhalb der Kategorie wertvollstes zuerst (ohne Marktwert ans Ende)
    for (const list of map.values()) {
      list.sort((a, b) => (b.market_value_eur ?? -Infinity) - (a.market_value_eur ?? -Infinity));
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  });

  // Portfolio-Kennzahlen. Δ nur über Assets MIT beiden Werten (Markt+Kauf),
  // sonst vergliche man unterschiedliche Mengen.
  const stats = $derived.by(() => {
    let market = 0;
    let purchase = 0;
    let withMarket = 0;
    let bothMarket = 0;
    let bothPurchase = 0;
    let bothCount = 0;
    for (const a of data.assets) {
      if (a.market_value_eur != null) {
        market += a.market_value_eur;
        withMarket++;
      }
      if (a.purchase_price_eur != null) purchase += a.purchase_price_eur;
      if (a.market_value_eur != null && a.purchase_price_eur != null) {
        bothMarket += a.market_value_eur;
        bothPurchase += a.purchase_price_eur;
        bothCount++;
      }
    }
    return { market, purchase, withMarket, delta: bothMarket - bothPurchase, bothCount };
  });

  const failure = $derived(data.failures?.api);
</script>

<section class="space-y-8">
  <header class="space-y-2">
    <p class="font-mono text-sm uppercase tracking-widest text-muted">Saganta · Assets</p>
    <h1 class="font-display text-4xl leading-tight">
      Was du besitzt, und was es heute wert ist.
    </h1>
    <p class="text-muted">
      {data.assets.length} Asset{data.assets.length === 1 ? '' : 's'}, davon
      {data.recommendations.length} Verkaufsempfehlung{data.recommendations.length === 1 ? '' : 'en'}.
    </p>
  </header>

  {#if data.assets.length > 0}
    <dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <div class="rounded-lg border border-border bg-surface-2 px-4 py-3">
        <dt class="font-mono text-xs uppercase tracking-wider text-muted">Marktwert heute</dt>
        <dd class="mt-1 font-display text-2xl">{fmtEur(stats.market)}</dd>
        <dd class="text-xs text-muted">{stats.withMarket} bewertet</dd>
      </div>
      <div class="rounded-lg border border-border bg-surface-2 px-4 py-3">
        <dt class="font-mono text-xs uppercase tracking-wider text-muted">Einkaufswert</dt>
        <dd class="mt-1 font-display text-2xl">{fmtEur(stats.purchase)}</dd>
      </div>
      {#if stats.bothCount > 0}
        <div class="rounded-lg border border-border bg-surface-2 px-4 py-3">
          <dt class="font-mono text-xs uppercase tracking-wider text-muted">Δ vs. Einkauf</dt>
          <dd
            class="mt-1 font-display text-2xl {stats.delta >= 0
              ? 'text-erfolg'
              : 'text-fehler'}"
          >
            {fmtDelta(stats.delta)}
          </dd>
          <dd class="text-xs text-muted">über {stats.bothCount} mit beiden Werten</dd>
        </div>
      {/if}
    </dl>
  {/if}

  {#if failure}
    <div class="rounded border border-warm-500/40 bg-warm-500/10 p-3 text-sm">
      <div class="font-medium">Assets-API nicht erreichbar.</div>
      <div class="mt-1 font-mono text-xs text-muted">{failure}</div>
    </div>
  {/if}

  {#if data.assets.length === 0 && !failure}
    <p class="rounded border border-border bg-surface-2 px-4 py-6 text-center text-muted">
      Noch keine Assets erfasst, über lager-Sync oder manuell anlegen.
    </p>
  {/if}

  {#if data.recommendations.length > 0}
    <div class="rounded-lg border border-warm-500/40 bg-warm-500/5 p-6">
      <h2 class="mb-3 font-display text-2xl">Verkaufen lohnt sich</h2>
      <ul class="space-y-2">
        {#each uniqueBy(data.recommendations, (x) => x.id) as a (a.id)}
          <li class="flex items-baseline justify-between gap-4 text-sm">
            <div class="min-w-0">
              <div class="truncate">{a.name}</div>
              {#if a.resale_reason}
                <div class="truncate text-xs text-muted">{a.resale_reason}</div>
              {/if}
            </div>
            <span class="shrink-0 font-mono text-warm-500">{fmtEur(a.market_value_eur)}</span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  {#each grouped as [cat, list] (cat)}
    <div class="space-y-2">
      <h2 class="font-mono text-sm uppercase tracking-wider text-muted">{cat}</h2>
      <ul class="space-y-1">
        {#each uniqueBy(list, (x) => x.id) as a (a.id)}
          <li class="flex items-center gap-4 rounded border border-border bg-surface-2 px-4 py-3">
            <div class="min-w-0 flex-1">
              <div class="flex items-baseline gap-2">
                <span class="truncate font-medium">{a.name}</span>
                <span class="rounded px-1.5 py-0.5 text-xs {badgeClass(a.usage_status)}">
                  {a.usage_status}
                </span>
                {#if a.source !== 'saganta'}
                  <span class="text-xs text-muted">· {a.source}</span>
                {/if}
              </div>
              {#if a.location || a.resale_reason}
                <div class="text-xs text-muted">
                  {a.location ?? ''}{a.location && a.resale_reason ? ' · ' : ''}{a.resale_reason ?? ''}
                </div>
              {/if}
            </div>
            <div class="text-right">
              <div class="font-mono text-sm">{fmtEur(a.market_value_eur)}</div>
              {#if a.purchase_price_eur != null}
                <div class="text-xs text-muted">
                  kauf: {fmtEur(a.purchase_price_eur)}
                </div>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    </div>
  {/each}
</section>
