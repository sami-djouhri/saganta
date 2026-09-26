<script lang="ts">
  import { page } from '$app/stores';
  import { Icon, appsFuer } from '@saganta/ui';
  import { inview } from '$lib/inview';

  interface Props {
    /** Banner nach erfolgreicher E-Mail-Bestätigung (?verified=1). */
    verified?: boolean;
  }
  let { verified = false }: Props = $props();

  // ★ Welche Apps es gibt, sagt der kanonische Katalog (`@saganta/ui`), nicht
  // diese Datei. Bis 2026-09-16 stand hier eine zweite Liste, und sie war der
  // Wahrheit um vier Apps hinterher: Aufgaben, Notizen, News, Besitz und
  // Fitness fehlten, dafuer stand „Kontakte" als eigene App auf der
  // Startseite, obwohl Kontakte zum Kalender gehoeren. Wer heute eine App
  // ergaenzt, muss hier nichts nachziehen.
  //
  // Nur der Werbetext je App steht hier: der Katalog traegt eine kurze
  // Funktionsbeschreibung fuer den App-Wechsler, auf einer Produktseite will
  // man einen Satz mehr. Fehlt einer, greift die Katalogbeschreibung.
  const werbetexte: Record<string, string> = {
    calendar:
      'Termine, Tagesziele und Gewohnheiten an einem Ort. Geburtstage erscheinen automatisch aus deinen Kontakten.',
    post: 'Physische Briefe und alle E-Mail-Konten in einer App. Scannen, per OCR durchsuchen, lesen und versenden.',
    mealprep:
      'Rezepte, Wochenplan und Makros. Erzeugt die Einkaufsliste aus Plan und Lagerbestand, ganz von selbst.',
    lager: 'Haushaltsinventar mit Mindestbestand und Barcode. Sieht, was zur Neige geht, bevor es fehlt.',
    assets: 'Geräte, Garantien und Marktwerte im Blick. Was im Haus steht, was es wert ist, wie lange es noch Garantie hat.',
    projectdeck:
      'Projekte, Entscheidungen und Deadlines im Blick. Eine ruhige Kommandozentrale für alles Laufende.',
    aufgaben: 'Aufgaben, Tagesziele und der geplante Tag. Verknüpft mit Projekten und dem Kalender.',
    notizen: 'Notizbücher mit Anhängen und geteilten Notizen. Verweise auf Projekte und Termine halten.',
    news: 'Deine Quellen, dein Briefing. Was wichtig ist, ohne Empfehlungsalgorithmus und ohne Werbung.',
    fitness: 'Trainingspläne und erfasste Sätze. Fortschritt je Muskelgruppe statt eines Bauchgefühls.',
    tagebuch:
      'Ende-zu-Ende verschlüsselt im Browser. Der Server verwahrt nur Chiffrat, lesen kannst nur du.',
  };

  // Die Shell ist die Übersicht, keine App: sie gehört nicht in die Liste der
  // Werkzeuge. `appsFuer` blendet zusätzlich aus, was es im Raum des Aufrufers
  // nicht gibt (Tagebuch ist bewusst nur im Heimnetz).
  const apps = $derived(
    appsFuer($page.url.host)
      .filter((a) => a.id !== 'shell')
      .map((a) => ({ icon: a.icon, title: a.name, text: werbetexte[a.id] ?? a.description })),
  );

  // Das Feature-Gitter zeichnet seine Trennlinien über `gap-px` auf farbigem
  // Grund. Eine unvollständige letzte Reihe wäre dort ein sichtbares Loch,
  // deshalb wird sie aufgefüllt statt die App-Zahl an das Raster anzupassen.
  // Zwei Werte, weil das Raster ab sm zwei und ab lg drei Spalten hat.
  const fuellZwei = $derived((2 - (apps.length % 2)) % 2);
  const fuellDrei = $derived((3 - (apps.length % 3)) % 3);

  const principles = [
    {
      icon: 'eye',
      title: 'Privat by design',
      text: 'Selbst gehostet auf eigener Hardware. Kein Tracking, keine Werbung, keine Datenweitergabe. Deine Daten verlassen dein Zuhause nicht.',
    },
    {
      icon: 'shield',
      title: 'Du bist der Kunde',
      text: 'Saganta finanziert sich über faire Tarife, nicht über deine Daten. Du zahlst für ein Produkt, kein verstecktes Geschäft auf deine Kosten.',
    },
    {
      icon: 'check',
      title: 'Zusammen gedacht',
      text: 'Kalender, Aufgaben, Mealprep und Lager teilen sich Kontext. Die Suite arbeitet leise im Hintergrund, präsent, wenn du sie brauchst.',
    },
  ];

  // Die Apps als Fenster der Fassade. Ein paar bleiben dunkel (nicht jeder Raum ist
  // beleuchtet), beim Überfahren „geht das Licht an".
  //
  // Dieselbe Quelle wie oben. Die Anzahl wird im Text abgeleitet, nicht
  // ausgeschrieben: hier stand dreimal „Sieben", einmal davon auf der
  // oeffentlichen Startseite. Welches Fenster dunkel ist, haengt an der
  // Position und nicht an der App, damit ein neuer Eintrag nichts umstellt.
  const houseWindows = $derived(
    apps.map((a, i) => ({ icon: a.icon, name: a.title, lit: i % 4 !== 2 })),
  );

  // Die Fassade verteilt ihre Fenster gleichmaessig auf so wenige Reihen wie
  // moeglich (hoechstens sieben je Reihe). Mit fest sieben Spalten standen bei
  // zehn Apps sieben oben und drei unten, und das Haus sah schief aus.
  const fassadeSpalten = $derived(
    Math.max(1, Math.ceil(houseWindows.length / Math.max(1, Math.ceil(houseWindows.length / 7)))),
  );

  // Drei-Schritt-Erklärung für die Landing (füllt die „Wie fange ich an?"-Lücke).
  const steps = [
    {
      n: '01',
      title: 'Konto erstellen',
      text: 'In zwei Minuten registriert, E-Mail bestätigt, fertig. Kostenlos und ohne Zahlungsdaten.',
    },
    {
      n: '02',
      title: 'Apps wählen',
      text: 'Nimm einzelne Apps oder gleich die ganze Suite. Jederzeit erweiterbar, nichts ist in Stein gemeißelt.',
    },
    {
      n: '03',
      title: 'Überall nutzen',
      text: 'Im Browser und als native Android-App. Ein Konto, synchron auf allen deinen Geräten.',
    },
  ];
</script>

<svelte:head>
  <title>Saganta, deine private Suite</title>
  <meta
    name="description"
    content="Saganta bündelt Kalender, Aufgaben, Post, Notizen, Mealprep, Lager und mehr zu einer ruhigen, selbst gehosteten Suite. Privat, werbefrei und ganz unter deiner Kontrolle."
  />
  <meta name="theme-color" content="#161310" />
  <!-- ★ Aus der aufgerufenen Adresse gebaut (2026-09-06). Vorher stand hier
       die Domaene der Ursprungs-Instanz fest: eine selbst betriebene
       Installation haette Suchmaschinen damit auf eine fremde Seite
       verwiesen, also die eigenen Seiten aktiv entwertet. -->
  <link rel="canonical" href={`${$page.url.origin}/`} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Saganta" />
  <meta property="og:title" content="Saganta, deine private Suite" />
  <meta
    property="og:description"
    content="Kalender, Aufgaben, Post, Notizen, Mealprep, Lager und mehr in einer selbst gehosteten Suite. Privat, werbefrei, unter deiner Kontrolle."
  />
  <meta property="og:url" content={`${$page.url.origin}/`} />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Saganta, deine private Suite" />
  <meta
    name="twitter:description"
    content="Kalender, Aufgaben, Post, Notizen, Mealprep, Lager und mehr in einer selbst gehosteten Suite. Privat, werbefrei, unter deiner Kontrolle."
  />
</svelte:head>

<div class="landing min-h-dvh overflow-x-clip bg-surface text-text">
  <!-- Atmosphäre: Gradient-Mesh + Korn -->
  <div class="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
    <div class="mesh mesh-a"></div>
    <div class="mesh mesh-b"></div>
    <div class="grain"></div>
  </div>

  <!-- Nav -->
  <header class="sticky top-0 z-30 border-b border-border/50 bg-surface/70 backdrop-blur-xl">
    <nav class="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
      <a href="/" class="flex items-center gap-2.5 font-display text-2xl tracking-tight"><svg viewBox="0 0 100 100" class="h-7 w-7" aria-hidden="true"><path d="M 69 27 A 19 19 0 1 0 50 46 A 19 19 0 1 1 31 73" fill="none" stroke="#dd9c3f" stroke-width="12.5" stroke-linecap="round"/><circle cx="69" cy="27" r="6" fill="currentColor"/><circle cx="31" cy="73" r="6" fill="currentColor"/></svg><span>Saganta</span></a>
      <div class="flex items-center gap-4 text-sm sm:gap-6">
        <a href="/apps" class="text-sm font-medium text-muted transition-colors duration-fast ease-saganta hover:text-text">Apps</a>
        <a href="/preise" class="text-sm font-medium text-muted transition-colors duration-fast ease-saganta hover:text-text">Preise</a>
      </div>
      <div class="flex items-center gap-1.5">
        <a
          href="/login"
          class="rounded-lg px-4 py-2 text-sm font-medium text-muted transition-colors duration-fast ease-saganta hover:text-text"
        >
          Anmelden
        </a>
        <a
          href="/login?mode=register"
          class="rounded-lg bg-accent-500 px-4 py-2 text-sm font-semibold text-accent-ink shadow-sm transition-colors duration-fast ease-saganta hover:bg-accent-400"
        >
          Konto erstellen
        </a>
      </div>
    </nav>
  </header>

  {#if verified}
    <div class="mx-auto max-w-6xl px-6 pt-6">
      <p class="rounded-lg border border-erfolg/40 bg-erfolg/10 px-4 py-3 text-center text-sm text-erfolg">
        E-Mail bestätigt. Du kannst dich jetzt anmelden.
      </p>
    </div>
  {/if}

  <!-- Hero: die Fassade bei Dämmerung, die Apps sind die beleuchteten Fenster deines Zuhauses -->
  <section class="relative mx-auto max-w-5xl px-6 pb-8 pt-16 text-center sm:pt-24">
        <p class="reveal inline-flex items-center gap-2 rounded-full border border-border bg-surface-2/70 px-3 py-1 text-xs text-muted" style="--d:0ms">
          <span class="size-1.5 rounded-full bg-accent-400"></span>
          Deine private Suite, selbst gehostet
        </p>
        <h1 class="reveal mx-auto mt-7 max-w-3xl font-display text-[3.4rem] leading-[0.98] tracking-tight sm:text-[5.3rem]" style="--d:80ms">
          Dein digitales
          <span class="relative whitespace-nowrap italic text-accent-200">
            Zuhause
            <svg class="absolute -bottom-2 left-0 w-full" height="12" viewBox="0 0 300 12" fill="none" aria-hidden="true">
              <path d="M3 8C60 3 150 2 297 7" stroke="var(--color-accent-400)" stroke-width="3" stroke-linecap="round" opacity="0.85" />
            </svg>
          </span>
        </h1>
        <p class="reveal mx-auto mt-8 max-w-xl text-lg leading-relaxed text-muted" style="--d:160ms">
          {houseWindows.length} Werkzeuge, ein Haus. Kalender, Aufgaben, Post, Mealprep und mehr: ruhig
          verbunden, privat und ganz unter deiner Kontrolle.
        </p>
        <div class="reveal mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row" style="--d:240ms">
          <a
            href="/login?mode=register"
            class="rounded-xl bg-accent-500 px-6 py-3 text-center text-base font-semibold text-accent-ink shadow-[0_10px_40px_-8px] shadow-accent-500/40 transition-all duration-base ease-saganta hover:-translate-y-0.5 hover:bg-accent-400 hover:shadow-accent-400/50"
          >
            Kostenlos starten
          </a>
          <a
            href="/login"
            class="rounded-xl border border-border bg-surface-2/50 px-6 py-3 text-center text-base font-medium text-text transition-colors duration-fast ease-saganta hover:bg-surface-2"
          >
            Anmelden
          </a>
        </div>
        <p class="reveal mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-muted" style="--d:320ms">
          <span class="inline-flex items-center gap-1.5"><Icon name="check" size={14} /> Selbst gehostet</span>
          <span class="inline-flex items-center gap-1.5"><Icon name="check" size={14} /> Keine Werbung</span>
          <span class="inline-flex items-center gap-1.5"><Icon name="check" size={14} /> Keine Tracker</span>
        </p>

    <!-- Die Fassade: dein Zuhause bei Dämmerung; die Fenster (Apps) leuchten. Signatur. -->
    <div class="reveal facade" style="--d:380ms">
      <div class="facade-eave" aria-hidden="true"></div>
      <div class="facade-body">
        <div class="windows" style="--fassade-spalten: {fassadeSpalten}">
          {#each houseWindows as w (w.name)}
            <div class="window" class:lit={w.lit} title={w.name}>
              <span class="win-icon"><Icon name={w.icon} size={19} /></span>
              <span class="win-name">{w.name}</span>
            </div>
          {/each}
        </div>
      </div>
      <div class="facade-spill" aria-hidden="true"></div>
    </div>
    <p class="reveal mx-auto mt-10 max-w-md text-sm text-muted" style="--d:460ms">
      <span class="text-text">{houseWindows.length} Räume, ein Konto.</span> Fahr über ein dunkles Fenster, mach Licht.
    </p>
  </section>

  <!-- Verzicht-Strip -->
  <section class="border-y border-border/60 bg-surface-2/30">
    <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-6 py-5 text-center text-sm text-muted">
      <span class="font-display text-base text-text">Worauf Saganta verzichtet:</span>
      <span>Werbe-Tracker</span>
      <span class="text-border">·</span>
      <span>Cloud-Konzerne</span>
      <span class="text-border">·</span>
      <span>Datenverkauf</span>
      <span class="text-border">·</span>
      <span>Abo-Fallen</span>
    </div>
  </section>

  <!-- Features -->
  <section class="mx-auto max-w-6xl px-6 py-24">
    <div class="mb-14 max-w-2xl">
      <p class="font-mono text-xs uppercase tracking-widest text-accent-400">Die Suite</p>
      <h2 class="mt-3 font-display text-4xl tracking-tight sm:text-5xl">Eine Suite, viele Werkzeuge</h2>
      <p class="mt-4 text-lg text-muted">
        Jede App für sich nützlich, zusammen mehr als die Summe ihrer Teile.
      </p>
    </div>
    <div class="grid gap-px overflow-hidden rounded-3xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
      {#each apps as f, i (f.title)}
        <div use:inview={{ delay: i * 70 }} class="group relative bg-surface p-7 shadow-[inset_0_1px_0_rgba(243,237,226,0.04)] transition-colors duration-base ease-saganta hover:bg-surface-2">
          <div class="mb-5 grid size-12 place-items-center rounded-xl bg-accent-500/12 text-accent-300 ring-1 ring-accent-500/15 transition-all duration-base ease-saganta group-hover:scale-105 group-hover:bg-accent-500/20 group-hover:shadow-[0_0_28px_-4px] group-hover:shadow-accent-500/40">
            <Icon name={f.icon} size={24} />
          </div>
          <h3 class="font-display text-2xl">{f.title}</h3>
          <p class="mt-2 text-sm leading-relaxed text-muted">{f.text}</p>
        </div>
      {/each}
      {#each Array(fuellZwei) as _, i (`z${i}`)}
        <div class="hidden bg-surface sm:block lg:hidden" aria-hidden="true"></div>
      {/each}
      {#each Array(fuellDrei) as _, i (`d${i}`)}
        <div class="hidden bg-surface lg:block" aria-hidden="true"></div>
      {/each}
    </div>
  </section>

  <!-- Manifest / Privacy -->
  <section class="relative overflow-hidden border-y border-border">
    <div class="mesh mesh-c pointer-events-none absolute inset-0" aria-hidden="true"></div>
    <div class="relative mx-auto max-w-6xl px-6 py-28">
      <div use:inview class="max-w-3xl">
        <p class="font-mono text-xs uppercase tracking-widest text-warm-500">Das Versprechen</p>
        <p class="mt-5 font-display text-3xl leading-snug tracking-tight sm:text-[2.6rem] sm:leading-[1.2]">
          Deine Daten gehören dir. Saganta läuft auf eigener Hardware,
          <span class="text-muted">keine Cloud-Konzerne, kein Mitlesen, keine Auswertung.</span>
          Privatsphäre ist hier kein Feature, sondern die Grundlage.
        </p>
      </div>
      <div class="mt-16 grid gap-10 sm:grid-cols-3">
        {#each principles as p (p.title)}
          <div>
            <div class="mb-4 grid size-11 place-items-center rounded-lg border border-border bg-surface text-accent-300">
              <Icon name={p.icon} size={20} />
            </div>
            <h3 class="font-display text-xl">{p.title}</h3>
            <p class="mt-2 text-sm leading-relaxed text-muted">{p.text}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <!-- So funktioniert's -->
  <section class="mx-auto max-w-6xl px-6 py-24">
    <div use:inview class="mb-14 max-w-2xl">
      <p class="font-mono text-xs uppercase tracking-widest text-accent-400">In drei Schritten</p>
      <h2 class="mt-3 font-display text-4xl tracking-tight sm:text-5xl">So funktioniert's</h2>
      <p class="mt-4 text-lg text-muted">Von der Anmeldung bis zur gelebten Routine, ohne Umwege.</p>
    </div>
    <div class="grid gap-x-8 gap-y-10 sm:grid-cols-3">
      {#each steps as s, i (s.n)}
        <div use:inview={{ delay: i * 90 }} class="relative">
          <span class="font-display text-5xl text-accent-500/30">{s.n}</span>
          <h3 class="mt-3 font-display text-2xl">{s.title}</h3>
          <p class="mt-2 text-sm leading-relaxed text-muted">{s.text}</p>
        </div>
      {/each}
    </div>
  </section>

  <!-- Closing CTA -->
  <section use:inview class="mx-auto max-w-3xl px-6 py-28 text-center">
    <h2 class="font-display text-5xl tracking-tight sm:text-6xl">Bereit, einzuziehen?</h2>
    <p class="mx-auto mt-5 max-w-md text-lg text-muted">
      Erstelle dein Konto und richte deine Suite in wenigen Minuten ein.
    </p>
    <a
      href="/login?mode=register"
      class="mt-9 inline-block rounded-xl bg-accent-500 px-8 py-3.5 text-base font-semibold text-accent-ink shadow-[0_10px_40px_-8px] shadow-accent-500/40 transition-all duration-base ease-saganta hover:-translate-y-0.5 hover:bg-accent-400 hover:shadow-accent-400/50"
    >
      Konto erstellen
    </a>
  </section>

  <!-- Footer -->
  <footer class="border-t border-border">
    <div class="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-10 text-sm text-muted sm:flex-row">
      <span class="flex items-center gap-2 font-display text-xl text-text"><svg viewBox="0 0 100 100" class="h-5 w-5" aria-hidden="true"><path d="M 69 27 A 19 19 0 1 0 50 46 A 19 19 0 1 1 31 73" fill="none" stroke="#dd9c3f" stroke-width="12.5" stroke-linecap="round"/></svg><span>Saganta</span></span>
      <span>Selbst gehostet · privat · werbefrei</span>
      <nav class="flex items-center gap-5">
        <a href="/preise" class="hover:text-text">Preise</a>
        <a href="/apps" class="hover:text-text">Apps</a>
        <a href="/impressum" class="hover:text-text">Impressum</a>
        <a href="/datenschutz" class="hover:text-text">Datenschutz</a>
        <a href="/login" class="text-accent-400 hover:underline">Anmelden</a>
      </nav>
    </div>
  </footer>
</div>

<style>
  /* Atmosphärische Farbflächen: driften langsam, Korn darüber für Tiefe. */
  .mesh {
    position: absolute;
    border-radius: 9999px;
    filter: blur(90px);
    opacity: 0.5;
  }
  .mesh-a {
    top: -12rem;
    left: -8rem;
    width: 38rem;
    height: 38rem;
    background: radial-gradient(circle, var(--color-accent-500), transparent 65%);
    animation: drift-a 26s ease-in-out infinite alternate;
  }
  .mesh-b {
    top: 18rem;
    right: -10rem;
    width: 32rem;
    height: 32rem;
    background: radial-gradient(circle, #c8884a, transparent 65%);
    opacity: 0.22;
    animation: drift-b 32s ease-in-out infinite alternate;
  }
  .mesh-c {
    background:
      radial-gradient(40rem 24rem at 15% 0%, rgba(207, 133, 36, 0.16), transparent 70%),
      radial-gradient(34rem 24rem at 100% 100%, rgba(200, 136, 74, 0.12), transparent 70%);
  }
  .grain {
    position: absolute;
    inset: 0;
    opacity: 0.035;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  @keyframes drift-a {
    to {
      transform: translate(4rem, 3rem) scale(1.12);
    }
  }
  @keyframes drift-b {
    to {
      transform: translate(-3rem, -2rem) scale(1.08);
    }
  }

  /* Eintritts-Reveal mit gestaffeltem Delay (--d je Element). */
  .reveal {
    opacity: 0;
    transform: translateY(14px);
    animation: reveal 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    animation-delay: var(--d, 0ms);
  }
  @keyframes reveal {
    to {
      opacity: 1;
      transform: none;
    }
  }

  /* Die Fassade: dein Zuhause bei Dämmerung; die Fenster (Apps) leuchten warm. */
  .facade {
    position: relative;
    margin: 4rem auto 0;
    max-width: 44rem;
  }
  /* Traufe/Dachkante: eine warme, beleuchtete Oberkante. */
  .facade-eave {
    position: absolute;
    left: 4%;
    right: 4%;
    top: -7px;
    height: 10px;
    border-radius: 12px 12px 0 0;
    background: linear-gradient(180deg, rgba(240, 180, 94, 0.5), rgba(207, 133, 36, 0.02));
  }
  .facade-body {
    position: relative;
    border-radius: 14px 14px 9px 9px;
    border: 1px solid var(--color-border);
    border-top-color: rgba(221, 156, 60, 0.3);
    background: linear-gradient(180deg, rgba(31, 27, 21, 0.92), rgba(17, 14, 11, 0.96));
    padding: 1.5rem 1.4rem 1.7rem;
    box-shadow: 0 44px 100px -34px rgba(0, 0, 0, 0.85);
  }
  .windows {
    display: grid;
    grid-template-columns: repeat(var(--fassade-spalten, 7), minmax(0, 1fr));
    gap: 0.7rem;
  }
  @media (max-width: 640px) {
    .windows {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
  }
  .window {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    aspect-ratio: 3 / 4;
    border-radius: 3px 3px 2px 2px;
    border: 1px solid rgba(221, 156, 60, 0.1);
    background: linear-gradient(180deg, rgba(243, 237, 226, 0.02), rgba(0, 0, 0, 0.18));
    color: rgb(var(--saganta-muted));
    overflow: hidden;
    transition:
      background 0.45s var(--saganta-ease),
      box-shadow 0.45s var(--saganta-ease),
      border-color 0.45s var(--saganta-ease),
      color 0.45s var(--saganta-ease);
  }
  /* Fensterkreuz (Sprossen). */
  .window::before,
  .window::after {
    content: '';
    position: absolute;
    background: rgba(221, 156, 60, 0.12);
    pointer-events: none;
  }
  .window::before {
    left: 0;
    right: 0;
    top: 52%;
    height: 1px;
  }
  .window::after {
    top: 0;
    bottom: 0;
    left: 50%;
    width: 1px;
  }
  .window.lit {
    border-color: rgba(246, 201, 138, 0.5);
    background: linear-gradient(180deg, rgba(246, 201, 138, 0.32), rgba(224, 162, 76, 0.08));
    box-shadow:
      inset 0 0 34px -4px rgba(246, 201, 138, 0.75),
      0 0 36px -10px rgba(224, 162, 76, 0.7);
    color: rgb(var(--saganta-text));
  }
  .window.lit .win-icon {
    color: #f0b45e;
  }
  .win-icon,
  .win-name {
    position: relative;
    z-index: 1;
  }
  .win-name {
    font-size: 10px;
    letter-spacing: 0.02em;
  }
  /* Über jedem Fenster geht auf Hover das Licht an. */
  .window:hover {
    border-color: rgba(246, 201, 138, 0.6);
    background: linear-gradient(180deg, rgba(246, 201, 138, 0.3), rgba(224, 162, 76, 0.09));
    box-shadow:
      inset 0 0 30px -6px rgba(246, 201, 138, 0.7),
      0 0 40px -8px rgba(224, 162, 76, 0.65);
    color: rgb(var(--saganta-text));
  }
  .window:hover .win-icon {
    color: #f6c98a;
  }
  /* Warmes Licht, das unter der Fassade auf den Boden fällt. */
  .facade-spill {
    position: absolute;
    left: 8%;
    right: 8%;
    bottom: -2.75rem;
    height: 4.5rem;
    z-index: -1;
    background: radial-gradient(60% 100% at 50% 0%, rgba(224, 162, 76, 0.24), transparent 72%);
    filter: blur(16px);
  }

  /* Scroll-Reveal (use:inview setzt die Klassen). */
  :global(.landing .reveal-init) {
    opacity: 0;
    transform: translateY(20px);
    transition:
      opacity 0.7s cubic-bezier(0.22, 1, 0.36, 1),
      transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
    will-change: opacity, transform;
  }
  :global(.landing .reveal-in) {
    opacity: 1;
    transform: none;
  }

  @media (prefers-reduced-motion: reduce) {
    .mesh-a,
    .mesh-b {
      animation: none;
    }
    .reveal {
      opacity: 1;
      transform: none;
      animation: none;
    }
  }
</style>
