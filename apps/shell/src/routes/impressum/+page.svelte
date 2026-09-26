<script lang="ts">
  import MarketingChrome from '$lib/MarketingChrome.svelte';

  // Betreiber ist Sami Djouhri (siehe djouhri.de). Rechtlich verbindliche
  // Pflichtangaben (Anschrift, USt-IdNr.) sind noch Platzhalter und muessen
  // vor dem oeffentlichen Start ergaenzt werden (§ 5 DDG / § 18 MStV).
  const provider = {
    name: 'Sami Djouhri',
    street: 'PLATZHALTER: Straße und Hausnummer',
    city: 'PLATZHALTER: PLZ und Ort',
    country: 'Deutschland',
    email: 'hallo@saganta.de',
    website: 'https://djouhri.de',
    phone: 'PLATZHALTER: Telefonnummer (optional)',
    vatId: 'PLATZHALTER: USt-IdNr. (falls vorhanden)',
    responsible: 'Sami Djouhri',
  };
</script>

<svelte:head>
  <title>Impressum · Saganta</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<MarketingChrome>
  <article class="mx-auto max-w-2xl px-6 py-20">
    <h1 class="font-display text-4xl tracking-tight">Impressum</h1>

    <p class="mt-4 rounded-lg border border-warm-500/40 bg-warm-500/10 px-4 py-3 text-sm text-muted">
      Hinweis: Dieses Impressum enthält Platzhalter und muss vor dem öffentlichen Start mit
      den echten Anbieterdaten ausgefüllt werden.
    </p>

    <section class="mt-10 space-y-2 text-sm leading-relaxed">
      <h2 class="font-display text-xl text-text">Angaben gemäß § 5 DDG</h2>
      <p class="text-muted">
        {provider.name}<br />
        {provider.street}<br />
        {provider.city}<br />
        {provider.country}
      </p>
    </section>

    <section class="mt-8 space-y-2 text-sm leading-relaxed">
      <h2 class="font-display text-xl text-text">Kontakt</h2>
      <p class="text-muted">
        E-Mail: <a href="mailto:{provider.email}" class="text-accent-400 hover:underline">{provider.email}</a><br />
        Web: <a href={provider.website} class="text-accent-400 hover:underline" rel="noopener" target="_blank">djouhri.de</a><br />
        Telefon: {provider.phone}
      </p>
    </section>

    <section class="mt-8 space-y-2 text-sm leading-relaxed">
      <h2 class="font-display text-xl text-text">Umsatzsteuer-Identifikationsnummer</h2>
      <p class="text-muted">{provider.vatId}</p>
    </section>

    <section class="mt-8 space-y-2 text-sm leading-relaxed">
      <h2 class="font-display text-xl text-text">Redaktionell verantwortlich</h2>
      <p class="text-muted">{provider.responsible}</p>
    </section>

    <section class="mt-8 space-y-2 text-sm leading-relaxed">
      <h2 class="font-display text-xl text-text">Streitschlichtung</h2>
      <p class="text-muted">
        Die Europäische Kommission stellt eine Plattform zur Online-Streitbeilegung bereit:
        <a href="https://ec.europa.eu/consumers/odr/" class="text-accent-400 hover:underline" rel="noopener" target="_blank">https://ec.europa.eu/consumers/odr/</a>.
        Wir sind nicht verpflichtet und nicht bereit, an Streitbeilegungsverfahren vor einer
        Verbraucherschlichtungsstelle teilzunehmen.
      </p>
    </section>

    <p class="mt-12 text-sm text-muted">
      Mehr zum Umgang mit deinen Daten in der
      <a href="/datenschutz" class="text-accent-400 hover:underline">Datenschutzerklärung</a>.
    </p>
  </article>
</MarketingChrome>
