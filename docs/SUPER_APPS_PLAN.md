# Saganta App-Linie und Konsolidierung – Plan

Stand: 2026-06-30. Ziel: privacy-first, kostenpflichtiges Produkt im Proton-Stil.
Verkaufbare Apps als eigene SKUs, ein vergünstigtes Bundle, dazu eine Business-Variante.
Dieser Plan ist Grundlage VOR Code-Änderungen.

## Leitprinzip (wirtschaftlich)

- **Eigene App (SKU)** = eigenständiger Job UND allein verkaufbar.
- **Kostenloses Kleber-Feature** = allein zu dünn zum Verkaufen, erhöht aber den Wert der
  anderen Apps und die Bindung. Wird in jedem Plan mitgeliefert.

## Verkaufbare Apps (SKUs)

| App | Job | Quelle heute | Business-Variante |
|-----|-----|--------------|-------------------|
| Kalender | Planung, Termine, Tagesziele | saganta `apps/kalender` (live) | Team-Kalender |
| Post | Briefe (OCR) + alle Mailkonten | Briefkasten (nativ) + saganta `mail` | geteilte Postfächer |
| Mealprep | Rezepte, Wochenplan, Makros | host `mealprep` (live, :8096) | – |
| Lager | Haushaltsinventar inkl. Wertsachen/Elektronik | host `lager` (live, :8095) | **kleines ERP** |
| Kontakte | privates Adressbuch, Quelle für Geburtstage/Absender | NEU | CRM-light |
| News | Feeds, Trends, Bookmarks | saganta `news` (live) | – |
| ProjectDeck | Projekte, Entscheidungen, Deadlines | saganta `projectdeck` (live) | – |
| Fitness | Training, Fortschritt, gekoppelt an Mealprep | host `fitness` (live) | – |

## Kostenlose Kleber-Features (keine SKU)

- **Einkaufsliste**: dünne, geräteübergreifende Sammel-Oberfläche. Gespeist aus Mealprep
  (Rezeptbedarf) + Lager (Mindestbestand) + **manuellen Freitext-Einträgen** (Food oder nicht,
  erstklassig). Abgehakte Lebensmittel buchen optional in Lager zurück. Löst das Non-Food-Problem
  und ist zu dünn als eigene SKU, aber ein starker Bundle-Versüßer.
- **Geburtstage**: read-only Overlay im Kalender, Quelle ist Kontakte. Hält den Kalender schlank.

## Architektur-Entscheidungen

1. **Mealprep bleibt getrennt von Lager.** Anderer Job, eigenes Schema (Rezepte/Makros/Profile),
   einzeln verkaufbar. Liest Lager (Bestand) + Kalender (Timing) über API, wie heute schon
   (`lager_default`, `kalender_default`-Netze).
2. **Assets fällt in Lager.** Saganta-Assets ist nur ein Mirror von `lager.electronics` +
   Marktwert. Wird zur „Wertsachen/Elektronik"-Sicht IN Lager. Marktwert-Kopplung (marktwatch)
   erhalten. Keine eigene SKU mehr.
3. **Kontakte wird neue, eigene App.** Geteilte Personen-Entität für Kalender (Geburtstage),
   Post (Absender), Mealprep (Gäste). Verkaufbares Privacy-Produkt.
4. **Einkaufsliste als Kleber-Feature**, nicht als App und nicht im Lager-/Mealprep-Schema
   vergraben. Eigener dünner Dienst oder Modul, aber kostenlos und überall präsent.

## Konsolidierung der „daheim"-Suite

`daheim` (host, shell + registry) bündelt heute lager/mealprep/fitness unter `*.daheim.home`.
Diese drei Dienste wandern unter das Saganta-Dach (`*.saganta.de`), better-auth statt daheim-Auth.
`daheim` selbst wird damit überflüssig und kann nach Migration retiren.

## Phasen

**Phase 0 – Bestandsaufnahme (zuerst, live prüfen, keine Annahmen):**
Pro Quelle DB-Schema, Endpunkte, Auth-Pfad, Edge-Routing, AdGuard-Rewrites, control-map-Eintrag,
native Android-App dokumentieren. Quellen: lager, mealprep, fitness, briefkasten, saganta `mail`.

**Phase 1 – Eingliederung der bestehenden Dienste unter Saganta-Auth/-Edge:**
mealprep, lager, fitness an better-auth + Backend-JWT anbinden, Edge auf `*.saganta.de`,
SOPS-Vault-Einträge, control-map. Noch ohne Verschmelzung.

**Phase 2 – Post (Aggregation):** `apps/post` + `services/post-api` (BFF über Briefkasten + mail-api),
gemeinsame Inbox. Alt-Routen erst nach Verifikation retiren. (Aggregation bestätigt, kein Schema-Merge.)

**Phase 3 – Lager + Assets:** Assets-Sicht in Lager integrieren, saganta `assets`/`assets-api` retiren,
Lager-Frontend um Wertsachen-Ansicht erweitern.

**Phase 4 – Kontakte (neu) + Geburtstags-Overlay:** `apps/kontakte` + `services/kontakte-api`,
Kalender liest Geburtstage read-only.

**Phase 5 – Einkaufsliste (Kleber):** dünner Dienst, gespeist aus Mealprep + Lager + manuell,
Quick-View in Shell und Mobile.

**Phase 6 – Business/ERP:** Lager-Kern um Mehrnutzer, Lieferanten, Bestellungen, Rollen erweitern;
Feature-Gating privat vs. gewerblich auf demselben Inventar-Kern.

## Querschnitt

- Auth: durchgängig better-auth + Backend-JWT (`@saganta/auth`), kein OIDC.
- Pricing/Entitlement: Tarif (Free / Unlimited / Business) bzw. Einzel-App im BFF prüfen
  (siehe `apps/shell/src/lib/catalog.ts`). Free = Kalender/Kontakte/News + Kleber-Features.
- Privacy: alle Daten on-host, externe Aufrufe nur IMAP/SMTP (Post) auf Nutzer-Konten.
- Deploy: gezielt einzelne Dateien syncen + `--exclude='.env'`; NIE Full-Tree-Sync
  (überschreibt kanonische .env/compose, siehe Memory rsync-protect-env).
- Reihenfolge je App: Backend/Migration → BFF → Edge → live verifizieren → Android →
  control-map → Alt-Dienste retiren.

## Pricing (live im Frontend)

- **Frei**: Kalender, Kontakte, News + Einkaufsliste/Geburtstage, 1 GB.
- **Einzeln**: jede App 2–3 €/Monat.
- **Unlimited**: alle Apps, 9 €/Monat (7 € jährlich), 500 GB. Der Upsell, weil die Apps
  sich gegenseitig verstärken.
- **Business**: Mehrnutzer + Lager-ERP + Self-Hosting, individuell.
