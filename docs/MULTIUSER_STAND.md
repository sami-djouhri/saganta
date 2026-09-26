# Was einem zweiten Nutzer heute begegnet

Gemessen am 30.08.2026 an den laufenden Diensten, nicht aus dem Quelltext
abgeleitet. Nachstellen mit `scripts/mandanten-probe.sh` (Struktur) und
`scripts/zweiter-nutzer-probe.sh` (Verhalten).

## Kurz

Er kann sich registrieren, bekommt seine Bestaetigungsmail, meldet sich an, und
danach ist Saganta fuer ihn fast leer: fuenf von sieben Backends antworten mit
403. Offen sind der Nachrichtenteil und die Shell.

## Zugang

| Schritt | Stand |
|---|---|
| Registrierung | offen, `emailAndPassword.enabled`, kein `disableSignUp` |
| Bestaetigungsmail | geht raus, seit 29.08.2026 (SMTP ueber mail.djouhri.de) |
| Anmeldung | erst nach Bestaetigung, `requireEmailVerification: true` |
| Sitzung | 90 Tage, taeglich gleitend verlaengert |

## Was er dann sieht

| Backend | Gate (ALLOWED_SUBS) | Datentrennung darunter |
|---|---|---|
| notizen-api | nur Owner | `owner_sub` auf jeder Tabelle |
| projectdeck-api | nur Owner | `projects.owner`, Kinder ueber Fremdschluessel |
| assets-api | nur Owner | `owner_sub`, seit 30.08.2026 |
| mail-api | nur Owner | `mail_accounts.sub`, Nachrichten haengen daran |
| kalender-bff | nur Owner | keine eigene Ablage, reicht den Sub durch |
| news-api | **offen** | Briefing und Feed-Zustand je Sub, Artikel gemeinsam |
| shell-api | **offen** | `user_settings` je Sub, Standardwerte fuer Neue |

Das Gate ist die Bremse, nicht die Trennung. Wo es zu ist, ist die Trennung
ungeprueft: die Frage wird gar nicht erst gestellt. Deshalb steht in der Tabelle
beides.

## Was offen ist

**Audio ist nicht gedeckelt.** Ein neu registrierter Nutzer kann ein
Briefing-Profil mit `audio_enabled` anlegen, und der Scheduler synthetisiert ihm
ab dem naechsten Morgen taeglich eine Sprachfassung. Das Kosten-Gating in
`plans.py` deckt die LLM-Aufrufe ab (die redigierte Premium-Stimme ist Pro), aber
nicht die Synthese selbst: die laeuft auch fuer Free. Sie ist zugleich der teurere
Teil, denn XTTS auf LXC 101 arbeitet single-threaded und braucht 20 bis 40
Sekunden je Briefing, und die Standard-Wunschzeit ist bei allen 06:30.

Belegt ist das nicht theoretisch: das Diagnose-Profil vom 28.08. hat drei Tage
lang taeglich eine Sprachfassung erzeugt, die niemand gehoert hat.

**Das Gate zu oeffnen ist eine Owner-Entscheidung.** Technisch steht dem seit dem
30.08. nichts mehr im Weg, die Trennung traegt in allen Diensten. Was fehlt, ist
die Antwort auf die Produktfrage: soll sich jeder anmelden koennen, und was
bekommt er dann.
