<script lang="ts">
  import MarketingChrome from '$lib/MarketingChrome.svelte';

  // Platzhalter-AGB + Widerrufsbelehrung für ein kostenpflichtiges Angebot an
  // Verbraucher in Deutschland. Ersetzt keine Rechtsberatung; vor dem Start
  // juristisch prüfen und Anbieterdaten (siehe /impressum) ergänzen.
</script>

<svelte:head>
  <title>AGB & Widerruf · Saganta</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<MarketingChrome>
  <article class="mx-auto max-w-2xl px-6 py-20">
    <h1 class="font-display text-4xl tracking-tight">AGB & Widerrufsbelehrung</h1>

    <p class="mt-4 rounded-lg border border-warm-500/40 bg-warm-500/10 px-4 py-3 text-sm text-muted">
      Hinweis: Entwurf mit Platzhaltern. Vor dem öffentlichen Start juristisch prüfen und mit den
      Anbieterdaten aus dem Impressum ergänzen.
    </p>

    <section class="mt-10 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">1. Geltungsbereich</h2>
      <p>
        Diese Allgemeinen Geschäftsbedingungen gelten für die Nutzung der Saganta-Suite und der
        kostenpflichtigen Tarife zwischen dem im <a href="/impressum" class="text-accent-400 hover:underline">Impressum</a>
        genannten Anbieter und dir als Kundin oder Kunde.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">2. Vertragsgegenstand</h2>
      <p>
        Saganta stellt eine selbst gehostete App-Suite bereit. Der Leistungsumfang richtet sich nach
        dem gewählten Tarif (Frei, Einzel-Apps, Unlimited oder Business), wie auf der
        <a href="/preise" class="text-accent-400 hover:underline">Preisseite</a> beschrieben.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">3. Preise und Zahlung</h2>
      <p>
        Es gelten die zum Zeitpunkt der Bestellung angegebenen Preise inklusive Umsatzsteuer.
        Kostenpflichtige Tarife werden monatlich oder jährlich im Voraus abgerechnet.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">4. Laufzeit und Kündigung</h2>
      <p>
        Es besteht keine Mindestlaufzeit. Kostenpflichtige Tarife sind zum Ende des jeweils bezahlten
        Abrechnungszeitraums kündbar. Der kostenlose Tarif kann jederzeit beendet werden.
      </p>
    </section>

    <section class="mt-10 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Widerrufsbelehrung</h2>
      <p>
        Du hast das Recht, binnen vierzehn Tagen ohne Angabe von Gründen diesen Vertrag zu widerrufen.
        Die Widerrufsfrist beträgt vierzehn Tage ab dem Tag des Vertragsschlusses.
      </p>
      <p>
        Um dein Widerrufsrecht auszuüben, musst du uns mittels einer eindeutigen Erklärung
        (z. B. per E-Mail an <a href="mailto:hallo@saganta.de" class="text-accent-400 hover:underline">hallo@saganta.de</a>)
        über deinen Entschluss informieren. Zur Wahrung der Widerrufsfrist reicht es aus, dass du die
        Mitteilung vor Ablauf der Frist absendest.
      </p>
      <p>
        Hinweis zu digitalen Inhalten: Auf ausdrücklichen Wunsch kann die Leistung vor Ablauf der
        Widerrufsfrist beginnen; das Widerrufsrecht erlischt vorzeitig, wenn du dem zugestimmt und die
        Kenntnisnahme des Erlöschens bestätigt hast.
      </p>
    </section>

    <p class="mt-12 text-sm text-muted">
      Siehe auch <a href="/datenschutz" class="text-accent-400 hover:underline">Datenschutz</a>
      und <a href="/impressum" class="text-accent-400 hover:underline">Impressum</a>.
    </p>
  </article>
</MarketingChrome>
