<script lang="ts">
  import { page } from '$app/stores';
  // Öffentliche Marketing-/Landingpage für das Saganta-Briefing (Nicht-Eingeloggte).
  // Deutsch-first, SEO-optimiert, Freemium-Positionierung.
  const loginUrl = 'https://saganta.de/login';
  const registerUrl = 'https://saganta.de/login?mode=register';

  const faq = [
    {
      q: 'Was ist das Saganta-Briefing?',
      a: 'Ein persönliches Nachrichten-Briefing: Du wählst deine Themen, die Engine bündelt aus vielen Quellen das Wichtigste und liefert es dir morgens als kurzen Text und als gesprochenes Audio – in rund zwei Minuten.',
    },
    {
      q: 'Wie höre ich mein Briefing auf Alexa oder im Podcast?',
      a: 'Jeder Account bekommt einen privaten Feed-Link. Den trägst du einmal in deine Podcast-App oder als Alexa-Flash-Briefing ein – ab dann spielt dein Briefing jeden Morgen automatisch. Kein Smart-Home-Schlüssel, kein Konto bei uns nötig auf dem Gerät.',
    },
    {
      q: 'Bleiben meine Daten privat?',
      a: 'Ja. Saganta ist privacy-first: kein Werbe-Tracking, deine Interessen bleiben deine. Wir verkaufen keine Daten und binden dich nicht an ein Ökosystem.',
    },
    {
      q: 'Was kostet es?',
      a: 'Der Einstieg ist kostenlos: ein Briefing pro Tag mit den Kernquellen, Standard-Stimme, in der App und als Podcast. Pro kostet rund 4 € im Monat und bringt Premium-Stimme, längere und mehrere Briefings, eigene Quellen und mehr.',
    },
    {
      q: 'Auf welchen Geräten funktioniert es?',
      a: 'Überall: im Browser (In-App-Player), in jeder Podcast-App, auf Alexa/Google-Speakern per Feed, und auf einem eigenen Lautsprecher (z. B. Raspberry Pi) über ein kleines Player-Skript.',
    },
  ];

  const jsonLd = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'SoftwareApplication',
        name: 'Saganta Briefing',
        applicationCategory: 'NewsApplication',
        operatingSystem: 'Web, Podcast, Alexa',
        description:
          'Persönliches KI-Nachrichten-Briefing aus deinen Themen – als Text und gesprochenes Audio, auf jedem Lautsprecher, privacy-first.',
        offers: [
          { '@type': 'Offer', name: 'Free', price: '0', priceCurrency: 'EUR' },
          { '@type': 'Offer', name: 'Pro', price: '4', priceCurrency: 'EUR' },
        ],
      },
      {
        '@type': 'FAQPage',
        mainEntity: faq.map((f) => ({
          '@type': 'Question',
          name: f.q,
          acceptedAnswer: { '@type': 'Answer', text: f.a },
        })),
      },
    ],
  };
</script>

<svelte:head>
  <title>Saganta Briefing – dein persönliches KI-Nachrichten-Briefing zum Anhören</title>
  <meta
    name="description"
    content="Dein Morgen in zwei Minuten: ein persönliches Nachrichten-Briefing aus deinen Themen, als Text und gesprochenes Audio. Auf jedem Lautsprecher, im Podcast oder auf Alexa – privacy-first, kostenlos starten."
  />
  <!-- ★ Aus der aufgerufenen Adresse gebaut (2026-09-06). Vorher stand hier
       die Domaene der Ursprungs-Instanz fest: eine selbst betriebene
       Installation haette Suchmaschinen damit auf eine fremde Seite
       verwiesen, also die eigenen Seiten aktiv entwertet. -->
  <link rel="canonical" href={`${$page.url.origin}/`} />
  <meta name="robots" content="index, follow" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Saganta News" />
  <meta property="og:title" content="Saganta Briefing – dein persönliches Nachrichten-Briefing zum Anhören" />
  <meta
    property="og:description"
    content="Deine Themen, morgens in zwei Minuten gesprochen. Auf jedem Lautsprecher, im Podcast oder auf Alexa. Privacy-first, kostenlos starten."
  />
  <meta property="og:url" content="https://news.saganta.de/" />
  <meta property="og:locale" content="de_DE" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Saganta Briefing – dein persönliches Nachrichten-Briefing" />
  <meta
    name="twitter:description"
    content="Deine Themen, morgens in zwei Minuten gesprochen. Auf jedem Gerät. Privacy-first."
  />
  {@html `<script type="application/ld+json">${JSON.stringify(jsonLd)}</` + `script>`}
</svelte:head>

<div class="mx-auto max-w-5xl px-6">
  <!-- Hero -->
  <section class="pt-16 pb-20 text-center sm:pt-24">
    <p class="font-mono text-xs uppercase tracking-[0.3em] text-accent-300">Saganta News · Briefing</p>
    <h1 class="mx-auto mt-4 max-w-3xl font-display text-5xl leading-[1.05] sm:text-6xl">
      Dein Morgen.<br />In zwei Minuten. <span class="text-accent-300">Gesprochen.</span>
    </h1>
    <p class="mx-auto mt-6 max-w-2xl text-lg text-muted">
      Ein persönliches Nachrichten-Briefing aus <strong class="text-text">deinen</strong> Themen –
      als kurzer Text und als Audio. Auf jedem Lautsprecher, im Podcast oder auf Alexa.
      Ohne dass du deine Daten hergibst.
    </p>
    <div class="mt-9 flex flex-wrap items-center justify-center gap-3">
      <a
        href={registerUrl}
        class="rounded-lg bg-accent-500 px-6 py-3 font-medium text-black transition-colors hover:bg-accent-400"
      >
        Kostenlos starten
      </a>
      <a
        href={loginUrl}
        class="rounded-lg border border-border px-6 py-3 font-medium text-muted transition-colors hover:text-text"
      >
        Anmelden
      </a>
    </div>
    <p class="mt-4 font-mono text-xs text-muted">Kostenlos starten · keine Kreditkarte · jederzeit kündbar</p>
  </section>

  <!-- Nutzen / Features -->
  <section class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
    {#each [
      { t: 'Nur deine Themen', d: 'Wähle Interessen mit Gewicht. Die Engine bündelt aus vielen Quellen genau das, was für dich zählt – nicht der Feed-Zufall.' },
      { t: 'Auf jedem Gerät', d: 'In-App-Player, privater Podcast-Feed, Alexa-Flash-Briefing oder eigener Lautsprecher. Kein Smart-Home-Schlüssel nötig.' },
      { t: 'Privat by design', d: 'Kein Werbe-Tracking, keine Datenweitergabe. Deine Interessen bleiben deine. Saganta ist privacy-first.' },
      { t: 'Frisch & redaktionell', d: 'KI fasst zusammen, gruppiert nach Themen und spricht flüssig – kein Vorlesen von Schlagzeilen.' },
    ] as f (f.t)}
      <div class="rounded-xl border border-border bg-surface-2 p-5">
        <h3 class="font-display text-lg">{f.t}</h3>
        <p class="mt-2 text-sm text-muted">{f.d}</p>
      </div>
    {/each}
  </section>

  <!-- So funktioniert es -->
  <section class="mt-24">
    <h2 class="text-center font-display text-3xl">So funktioniert's</h2>
    <div class="mt-10 grid gap-8 sm:grid-cols-3">
      {#each [
        { n: '1', t: 'Themen wählen', d: 'Politik, Wirtschaft, Tech, Wissenschaft, Sport – oder eigene Stichwörter. In 30 Sekunden eingerichtet.' },
        { n: '2', t: 'Wir bündeln nachts', d: 'Die Engine sammelt, entdoppelt, gewichtet und vertont dein Briefing – frisch für den nächsten Morgen.' },
        { n: '3', t: 'Morgens hören', d: 'In der App, im Podcast, auf Alexa oder deinem Lautsprecher. Ganz automatisch.' },
      ] as s (s.n)}
        <div class="text-center">
          <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-accent-500/50 font-display text-xl text-accent-300">
            {s.n}
          </div>
          <h3 class="mt-4 font-display text-xl">{s.t}</h3>
          <p class="mt-2 text-sm text-muted">{s.d}</p>
        </div>
      {/each}
    </div>
  </section>

  <!-- Preise -->
  <section class="mt-24">
    <h2 class="text-center font-display text-3xl">Preise</h2>
    <p class="mt-2 text-center text-muted">Kostenlos starten. Upgraden, wenn du mehr willst.</p>
    <div class="mx-auto mt-10 grid max-w-3xl gap-6 sm:grid-cols-2">
      <div class="rounded-2xl border border-border bg-surface-2 p-7">
        <p class="font-mono text-xs uppercase tracking-widest text-muted">Free</p>
        <p class="mt-2 font-display text-4xl">0 €</p>
        <ul class="mt-5 space-y-2 text-sm text-muted">
          <li>✓ 1 Briefing pro Tag</li>
          <li>✓ Kernquellen (Politik, Wirtschaft, Tech …)</li>
          <li>✓ Standard-Stimme</li>
          <li>✓ In-App-Player + privater Podcast-Feed</li>
        </ul>
        <a href={registerUrl} class="mt-6 block rounded-lg border border-border py-2.5 text-center text-sm font-medium hover:text-accent-300">
          Kostenlos starten
        </a>
      </div>
      <div class="relative rounded-2xl border border-accent-500/60 bg-accent-500/5 p-7">
        <span class="absolute -top-3 left-7 rounded-full bg-accent-500 px-3 py-0.5 font-mono text-xs text-black">Empfohlen</span>
        <p class="font-mono text-xs uppercase tracking-widest text-accent-300">Pro</p>
        <p class="mt-2 font-display text-4xl">~4 €<span class="text-base text-muted"> / Monat</span></p>
        <ul class="mt-5 space-y-2 text-sm">
          <li>✓ Alles aus Free</li>
          <li>✓ <strong>Premium-Stimme</strong> (natürliche Redaktion)</li>
          <li>✓ Längere &amp; mehrere Briefings pro Tag</li>
          <li>✓ Eigene Quellen &amp; Freitext-Themen</li>
          <li>✓ Smart-Home-Webhook &amp; Prioritäts-Generierung</li>
        </ul>
        <a href={registerUrl} class="mt-6 block rounded-lg bg-accent-500 py-2.5 text-center text-sm font-medium text-black hover:bg-accent-400">
          Pro holen
        </a>
      </div>
    </div>
  </section>

  <!-- FAQ -->
  <section class="mx-auto mt-24 max-w-3xl">
    <h2 class="text-center font-display text-3xl">Häufige Fragen</h2>
    <div class="mt-8 space-y-3">
      {#each faq as f (f.q)}
        <details class="group rounded-xl border border-border bg-surface-2 p-5">
          <summary class="cursor-pointer list-none font-display text-lg marker:hidden">
            {f.q}
          </summary>
          <p class="mt-2 text-sm text-muted">{f.a}</p>
        </details>
      {/each}
    </div>
  </section>

  <!-- Schluss-CTA -->
  <section class="my-24 rounded-2xl border border-border bg-surface-2 px-6 py-14 text-center">
    <h2 class="font-display text-3xl">Wach auf informiert – nicht überflutet.</h2>
    <p class="mx-auto mt-3 max-w-xl text-muted">
      Richte dein Briefing in einer Minute ein und hör es schon morgen früh.
    </p>
    <a
      href={registerUrl}
      class="mt-7 inline-block rounded-lg bg-accent-500 px-7 py-3 font-medium text-black transition-colors hover:bg-accent-400"
    >
      Jetzt kostenlos starten
    </a>
  </section>
</div>
