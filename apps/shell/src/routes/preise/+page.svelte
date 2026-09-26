<script lang="ts">
  import { page } from '$app/stores';
  import { Icon } from '@saganta/ui';
  import { inview } from '$lib/inview';
  import MarketingChrome from '$lib/MarketingChrome.svelte';
  import { plans, appPlans, compareRows } from '$lib/catalog';
  import type { PageData } from './$types';

  // data.user aus dem Root-Layout (Parent-Merge) → login-bewusste Nav-CTAs.
  let { data }: { data: PageData } = $props();

  let yearly = $state(true);

  const faqs = [
    {
      q: 'Warum ist Saganta nicht komplett kostenlos?',
      a: 'Weil ein kostenloses Produkt am Ende mit deinen Daten bezahlt wird. Saganta finanziert sich über faire Tarife, damit du der Kunde bist und nicht die Ware. Der kostenlose Tarif bleibt trotzdem dauerhaft nutzbar.',
    },
    {
      q: 'Einzelne Apps oder Unlimited, was lohnt sich?',
      a: 'Ab zwei bis drei Apps ist Unlimited fast immer günstiger. Vor allem verstärken sich die Apps gegenseitig: Mealprep nutzt das Lager, der Kalender zeigt Geburtstage aus den Kontakten, die Einkaufsliste sammelt aus allem.',
    },
    {
      q: 'Kann ich jederzeit kündigen?',
      a: 'Ja. Keine Mindestlaufzeit, keine Kündigungsfrist. Du kannst monatlich kündigen oder zwischen Einzel-Apps und Unlimited wechseln.',
    },
    {
      q: 'Was bedeutet Self-Hosting im Business-Tarif?',
      a: 'Saganta läuft auf eigener Hardware in deinem Haus oder deiner Firma. Im Business-Tarif richten wir die Suite auf deiner Infrastruktur mit eigener Domain ein, sodass keine Daten das Haus verlassen.',
    },
    {
      q: 'Komme ich wieder an meine Daten heraus?',
      a: 'Jederzeit. Deine Daten gehören dir und lassen sich exportieren. Es gibt keine Sperre, die dich im System hält.',
    },
  ];

  const compareCols = [
    { id: 'free', name: 'Frei' },
    { id: 'unlimited', name: 'Unlimited' },
    { id: 'business', name: 'Business' },
  ];

  function priceLabel(p: (typeof plans)[number]): { big: string; sub: string } {
    if (p.priceMonthly === null) return { big: '0 €', sub: p.priceNote ?? '' };
    if (p.priceMonthly === undefined) return { big: 'Auf Anfrage', sub: p.priceNote ?? '' };
    const val = yearly && p.priceYearly !== undefined ? p.priceYearly : p.priceMonthly;
    return { big: `${val} €`, sub: yearly && p.priceYearly !== undefined ? 'pro Monat, jährlich' : 'pro Monat' };
  }
</script>

<svelte:head>
  <title>Preise · Saganta</title>
  <meta
    name="description"
    content="Saganta-Tarife: einzelne Apps oder alles im Unlimited-Bundle, plus Business. Privacy first, keine Werbung, kein Datenverkauf."
  />
  <meta name="theme-color" content="#161310" />
  <!-- ★ Aus der aufgerufenen Adresse gebaut (2026-09-06). Vorher stand hier
       die Domaene der Ursprungs-Instanz fest: eine selbst betriebene
       Installation haette Suchmaschinen damit auf eine fremde Seite
       verwiesen, also die eigenen Seiten aktiv entwertet. -->
  <link rel="canonical" href={`${$page.url.origin}/preise`} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Saganta" />
  <meta property="og:title" content="Preise · Saganta" />
  <meta
    property="og:description"
    content="Einzelne Apps oder alles im Unlimited-Bundle, plus Business. Privacy first, keine Werbung, kein Datenverkauf."
  />
  <meta property="og:url" content="https://saganta.de/preise" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Preise · Saganta" />
  <meta
    name="twitter:description"
    content="Einzelne Apps oder alles im Unlimited-Bundle, plus Business. Privacy first, keine Werbung, kein Datenverkauf."
  />
</svelte:head>

<MarketingChrome active="preise" user={data.user}>
  <section class="mx-auto max-w-6xl px-6 pb-10 pt-20 text-center sm:pt-24">
    <p class="font-mono text-xs uppercase tracking-widest text-accent-400">Preise</p>
    <h1 class="mt-4 font-display text-4xl tracking-tight sm:text-6xl">
      Bezahlen statt bezahlt werden
    </h1>
    <p class="mx-auto mt-5 max-w-xl text-lg text-muted">
      Buche einzelne Apps oder nimm alles im Unlimited-Bundle, deutlich günstiger.
      Saganta finanziert sich über faire Tarife, nicht über deine Daten.
    </p>

    <div class="mt-8 flex items-center justify-center gap-3 text-sm">
      <span class:text-text={!yearly} class:text-muted={yearly}>Monatlich</span>
      <button
        type="button"
        role="switch"
        aria-checked={yearly}
        aria-label="Zwischen monatlicher und jährlicher Zahlung umschalten"
        onclick={() => (yearly = !yearly)}
        class="relative h-6 w-11 rounded-full border border-border bg-surface-2 transition-colors duration-fast"
        class:bg-accent-500={yearly}
      >
        <span
          class="absolute top-0.5 size-4 rounded-full bg-white transition-all duration-fast"
          class:left-0.5={!yearly}
          class:left-[1.375rem]={yearly}
        ></span>
      </button>
      <span class:text-text={yearly} class:text-muted={!yearly}>
        Jährlich
        <span class="ml-1 rounded-full bg-erfolg/15 px-2 py-0.5 text-xs text-erfolg">sparen</span>
      </span>
    </div>
  </section>

  <!-- Haupt-Tarife -->
  <section class="mx-auto max-w-6xl px-6 pb-16">
    <div class="grid gap-6 lg:grid-cols-3">
      {#each plans as p, i (p.id)}
        {@const price = priceLabel(p)}
        <div
          use:inview={{ delay: i * 80 }}
          class="relative flex flex-col rounded-3xl border bg-surface-2/60 p-8 backdrop-blur-sm transition-colors duration-base ease-saganta"
          class:border-accent-500={p.highlight}
          class:border-border={!p.highlight}
        >
          {#if p.highlight}
            <span class="absolute -top-3 left-8 rounded-full bg-accent-500 px-3 py-1 text-xs font-semibold text-accent-ink">
              Beste Wahl
            </span>
          {/if}
          <h2 class="font-display text-2xl">{p.name}</h2>
          <p class="mt-1 text-sm text-muted">{p.tagline}</p>
          <div class="mt-6 flex items-baseline gap-2">
            <span class="font-display text-4xl tracking-tight">{price.big}</span>
            <span class="text-sm text-muted">{price.sub}</span>
          </div>
          <a
            href={p.cta.href}
            class="mt-6 rounded-xl px-5 py-3 text-center text-sm font-semibold transition-all duration-fast ease-saganta"
            class:bg-accent-500={p.highlight}
            class:text-white={p.highlight}
            class:hover:bg-accent-400={p.highlight}
            class:border={!p.highlight}
            class:border-border={!p.highlight}
            class:text-text={!p.highlight}
            class:hover:bg-surface-2={!p.highlight}
          >
            {p.cta.label}
          </a>
          <ul class="mt-7 space-y-3 text-sm">
            {#each p.features as f (f)}
              <li class="flex items-start gap-2.5">
                <span class="mt-0.5 text-accent-400"><Icon name="check" size={16} /></span>
                <span>{f}</span>
              </li>
            {/each}
          </ul>
        </div>
      {/each}
    </div>
  </section>

  <!-- Einzeln buchen -->
  <section class="mx-auto max-w-6xl px-6 pb-20">
    <div use:inview class="mb-8 max-w-2xl">
      <h2 class="font-display text-3xl tracking-tight">Lieber einzeln?</h2>
      <p class="mt-3 text-muted">
        Nimm nur die Apps, die du brauchst. Ab zwei oder drei Apps lohnt sich Unlimited fast immer,
        weil die Apps zusammen mehr können als jede für sich.
      </p>
    </div>
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {#each appPlans as a, i (a.id)}
        <div
          use:inview={{ delay: i * 40 }}
          class="flex flex-col rounded-2xl border border-border bg-surface-2/40 p-5 transition-colors duration-base ease-saganta hover:border-accent-500/40"
        >
          <div class="mb-3 grid size-10 place-items-center rounded-lg bg-accent-500/12 text-accent-300">
            <Icon name={a.icon} size={20} />
          </div>
          <h3 class="font-display text-lg">{a.name}</h3>
          <p class="mt-1 flex-1 text-sm leading-relaxed text-muted">{a.description}</p>
          <p class="mt-4 text-sm">
            <span class="font-display text-2xl">{a.priceMonthly} €</span>
            <span class="text-muted">/ Monat</span>
          </p>
        </div>
      {/each}
    </div>
  </section>

  <!-- Vergleichsmatrix -->
  <section class="mx-auto max-w-6xl px-6 pb-24">
    <h2 use:inview class="mb-8 font-display text-3xl tracking-tight">Tarife im Vergleich</h2>
    <div class="overflow-x-auto rounded-2xl border border-border">
      <table class="w-full border-collapse text-sm">
        <thead>
          <tr class="border-b border-border bg-surface-2/40">
            <th class="px-5 py-4 text-left font-medium text-muted">Funktion</th>
            {#each compareCols as c (c.id)}
              <th class="px-5 py-4 text-center font-display text-base">{c.name}</th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each compareRows as row (row.label)}
            <tr class="border-b border-border/60 last:border-0">
              <td class="px-5 py-3.5 text-muted">{row.label}</td>
              {#each compareCols as c (c.id)}
                {@const v = row.values[c.id]}
                <td class="px-5 py-3.5 text-center">
                  {#if v === true}
                    <span class="inline-flex text-accent-400"><Icon name="check" size={17} /></span>
                  {:else if v === false || v === undefined}
                    <span class="text-border">·</span>
                  {:else}
                    <span class="text-text">{v}</span>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>

  <!-- Privacy-Versprechen -->
  <section class="border-t border-border">
    <div use:inview class="mx-auto grid max-w-6xl gap-8 px-6 py-20 sm:grid-cols-3">
      <div>
        <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
          <Icon name="shield" size={20} />
        </div>
        <h3 class="font-display text-xl">Privacy first</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">
          Deine Daten verlassen die eigene Hardware nicht. Keine Auswertung, kein Mitlesen,
          keine Weitergabe an Dritte.
        </p>
      </div>
      <div>
        <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
          <Icon name="zap" size={20} />
        </div>
        <h3 class="font-display text-xl">Ehrliche Preise</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">
          Du zahlst für ein Produkt, nicht mit deiner Aufmerksamkeit. Keine versteckten
          Kosten, jederzeit kündbar.
        </p>
      </div>
      <div>
        <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
          <Icon name="check" size={20} />
        </div>
        <h3 class="font-display text-xl">Ohne Risiko testen</h3>
        <p class="mt-2 text-sm leading-relaxed text-muted">
          Starte kostenlos und wechsle, wann du willst. Kein Abozwang, keine Kündigungsfristen.
        </p>
      </div>
    </div>
  </section>

  <!-- FAQ -->
  <section class="border-t border-border">
    <div class="mx-auto max-w-3xl px-6 py-20">
      <h2 use:inview class="mb-10 text-center font-display text-3xl tracking-tight sm:text-4xl">Häufige Fragen</h2>
      <div class="space-y-3">
        {#each faqs as f, i (f.q)}
          <details
            use:inview={{ delay: i * 50 }}
            class="group rounded-2xl border border-border bg-surface-2/40 p-5 transition-colors duration-base ease-saganta hover:border-accent-500/40"
          >
            <summary class="flex cursor-pointer items-center justify-between gap-4 font-display text-lg">
              {f.q}
              <span class="text-muted transition-transform duration-fast group-open:rotate-45"><Icon name="plus" size={18} /></span>
            </summary>
            <p class="mt-3 text-sm leading-relaxed text-muted">{f.a}</p>
          </details>
        {/each}
      </div>
    </div>
  </section>

  <section class="mx-auto max-w-3xl px-6 py-24 text-center">
    <h2 class="font-display text-4xl tracking-tight sm:text-5xl">Bereit, einzuziehen?</h2>
    <p class="mx-auto mt-4 max-w-md text-lg text-muted">
      Erstelle dein Konto und richte deine Suite in wenigen Minuten ein.
    </p>
    <a
      href="/login?mode=register"
      class="mt-8 inline-block rounded-xl bg-accent-500 px-8 py-3.5 text-base font-semibold text-accent-ink shadow-[0_10px_40px_-8px] shadow-accent-500/40 transition-all duration-base ease-saganta hover:-translate-y-0.5 hover:bg-accent-400"
    >
      Kostenlos starten
    </a>
  </section>
</MarketingChrome>
