<script lang="ts">
  import MarketingChrome from '$lib/MarketingChrome.svelte';

  // Platzhalter-Datenschutzerklärung. Der Privacy-first-Ansatz (Self-Hosting auf
  // eigener Hardware, keine Tracker, keine Weitergabe) ist hier abgebildet, muss
  // aber vor dem Start juristisch geprüft und mit echten Anbieterdaten ergänzt werden.
</script>

<svelte:head>
  <title>Datenschutz · Saganta</title>
  <meta name="robots" content="noindex" />
</svelte:head>

<MarketingChrome>
  <article class="mx-auto max-w-2xl px-6 py-20">
    <h1 class="font-display text-4xl tracking-tight">Datenschutzerklärung</h1>

    <section class="mt-10 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Grundsatz</h2>
      <p>
        Saganta ist als private, selbst gehostete Suite gebaut. Deine Inhalte (Termine, Post,
        Inventar, Kontakte und weitere App-Daten) liegen auf eigener Hardware und werden weder
        ausgewertet noch an Dritte weitergegeben. Es gibt kein Werbe-Tracking und keinen Datenverkauf.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Verantwortlicher</h2>
      <p>
        Verantwortlich für die Datenverarbeitung ist der im
        <a href="/impressum" class="text-accent-400 hover:underline">Impressum</a> genannte Anbieter.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Welche Daten verarbeitet werden</h2>
      <ul class="list-disc space-y-1 pl-5">
        <li>Kontodaten: Name, E-Mail-Adresse und Passwort-Hash zur Anmeldung.</li>
        <li>App-Inhalte: die Daten, die du in den jeweiligen Apps selbst anlegst.</li>
        <li>Technische Protokolle: zur Absicherung und Fehlersuche, ohne Profilbildung.</li>
        <li>Externe Konten: bei der Post-App rufen wir auf deine Anweisung deine IMAP/SMTP-Konten ab.</li>
      </ul>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Rechtsgrundlagen</h2>
      <p>
        Die Verarbeitung erfolgt zur Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO), aufgrund
        berechtigter Interessen an einem sicheren Betrieb (lit. f) sowie, wo nötig, auf Basis
        deiner Einwilligung (lit. a).
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Speicherdauer &amp; automatische Löschung</h2>
      <p>
        Deine Inhalte bleiben gespeichert, solange dein Konto besteht. Zusätzlich räumt die Kalender-App
        automatisch auf (Grundsatz der Datensparsamkeit, Art. 5 Abs. 1 lit. e DSGVO):
      </p>
      <ul class="list-disc space-y-1 pl-5">
        <li>Abgeschlossene oder verworfene Trainings-/Gewohnheits-Sitzungen: nach 90 Tagen.</li>
        <li>Erledigte Aufgaben: nach 365 Tagen.</li>
        <li>Vergangene Tagesziele und interne Benachrichtigungs-Protokolle: nach 90 bis 365 Tagen.</li>
      </ul>
      <p>
        Termine und Kontakte bleiben als Nutzdaten erhalten und werden nicht automatisch gelöscht.
        Nach Löschung des Kontos werden alle Inhalte entfernt, soweit keine gesetzlichen
        Aufbewahrungspflichten entgegenstehen.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Deine Rechte &amp; wie du sie ausübst</h2>
      <p>
        Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung,
        Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO). Diese Rechte kannst du direkt
        in der App ausüben, ohne Anfrage:
      </p>
      <ul class="list-disc space-y-1 pl-5">
        <li><strong>Datenexport</strong> (Art. 20): In der Kalender-App unter „Meine Daten &amp; Datenschutz"
          lädst du alle deine Daten als strukturierte JSON-Datei herunter.</li>
        <li><strong>Konto-Löschung</strong> (Art. 17): Ebenfalls dort löschst du dein Konto samt aller
          Inhalte unwiderruflich. System-Feiertage bleiben unberührt.</li>
      </ul>
      <p>
        Für weitergehende Anfragen oder eine Beschwerde bei der Aufsichtsbehörde wende dich an die
        im <a href="/impressum" class="text-accent-400 hover:underline">Impressum</a> genannte Adresse.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Push-Benachrichtigungen</h2>
      <p>
        Wenn du Erinnerungen aktivierst, versendet die Kalender-App optional Push-Nachrichten über
        einen selbst betriebenen Benachrichtigungsdienst (ntfy). Die Übertragung erfolgt an den
        eigenen Server; es werden keine Inhalte an kommerzielle Push-Dienste (Firebase o. ä.)
        weitergegeben. Ohne aktivierte Erinnerungen werden keine solchen Nachrichten versendet.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Künstliche Intelligenz</h2>
      <p>
        Die Schnellerfassung („Zahnarzt morgen 15 Uhr") arbeitet regelbasiert und vollständig lokal.
        Nur falls du die optionale KI-Unterstützung aktivierst, wird der eingegebene Text an ein
        <strong>im eigenen Homelab betriebenes Sprachmodell</strong> gesendet. Es findet
        <strong>keine</strong> Übermittlung an externe KI-Anbieter oder Cloud-Dienste statt.
      </p>
    </section>

    <section class="mt-8 space-y-3 text-sm leading-relaxed text-muted">
      <h2 class="font-display text-xl text-text">Cookies</h2>
      <p>
        Saganta bindet keine Werbe- oder Analyse-Dienste Dritter ein und setzt keine Tracking-Cookies.
        Verwendet werden ausschließlich technisch notwendige Cookies für die Anmeldung und den
        Login-Status (Session-Cookie). Eine Einwilligung ist hierfür nach § 25 Abs. 2 TDDDG nicht
        erforderlich.
      </p>
    </section>
  </article>
</MarketingChrome>
