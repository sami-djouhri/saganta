# Lizenz, und wie daraus spaeter Geld werden kann

Stand 2026-09-13. Entscheidung des Eigentuemers: **Open Core plus gehostete
Instanz**, also Kern offen, einzelne Funktionen zahlungspflichtig, und zusaetzlich
ein Betrieb fuer Leute, die nicht selbst hosten wollen.

Dieses Dokument haelt fest, was dafuer schon steht, was daran heute noch nicht
stimmt, und welche Entscheidung **vor** der Veroeffentlichung faellt und welche
danach noch offen ist. Es ist keine Rechtsberatung; die Texte in `LICENSE`,
`COPYRIGHT` und `CONTRIBUTING.md` sind uebliche Bausteine, aber wer damit
wirklich Umsatz macht, laesst sie einmal anwaltlich ansehen.

## Was jetzt steht

| Datei | Zweck |
|---|---|
| `LICENSE` | AGPL-3.0, unveraendert |
| `COPYRIGHT` | wem das Programm gehoert, und warum das getrennt steht |
| `CONTRIBUTING.md` | die Rechteeinraeumung, die jeder fremde Beitrag braucht |

## Die eine Sache, die sich nicht nachholen laesst

Alles andere in diesem Dokument kann man spaeter aendern. **Das hier nicht:**

In dem Augenblick, in dem ein fremder Beitrag ohne Rechteeinraeumung
zusammengefuehrt wird, gehoeren die Rechte daran seinem Verfasser. Ab da braucht
**jede** Lizenzentscheidung dessen Zustimmung, und zwar dauerhaft. Wer nach zwei
Jahren vierzig Beitragende hat und umlizenzieren will, muss vierzig Menschen
wiederfinden und ueberzeugen; wer einen davon nicht erreicht, muss dessen Code
herausoperieren.

Deshalb steht die Einraeumung in `CONTRIBUTING.md` und wird ueber
`git commit -s` (Signed-off-by) eingeholt. ⚠️ **Das ist eine Regel, die jemand
befolgen muss, und damit keine Zusicherung.** Wer zusammenfuehrt, prueft die
Zeile; auf GitHub laesst sich das mit einer DCO-Pruefung erzwingen, und genau
das sollte eingeschaltet sein, bevor das Repo oeffentlich wird.

## AGPL ist bereits die Lizenz zum Umdrehen

Das ist kein Zufall und war die richtige Wahl. Die AGPL verlangt von jedem, der
die Software **als Dienst** anbietet, den eigenen Quelltext offenzulegen, auch
ohne Weitergabe des Programms. Fuer Firmen ist das in aller Regel unannehmbar.
Wer Saganta kommerziell einsetzen will, kommt damit von selbst auf den Eigentuemer
zu und kauft eine gesonderte Lizenz. Das ist der Weg, auf dem GitLab und Sentry
Geld verdient haben, und er steht offen, **solange die Rechte ungeteilt sind**.

Was einmal unter der AGPL veroeffentlicht ist, bleibt unter ihr verfuegbar. Eine
spaetere Aenderung gilt fuer kuenftige Fassungen; die alte bleibt forkbar. In der
Praxis ist das selten ein Problem, weil ein Fork ohne Weiterentwicklung veraltet.

## Open Core: was das hier konkret hiesse

Heute steht das Tarifmodell vollstaendig im offenen Teil:
`services/_geteilt/saganta_dienst/tarife.py` (die Merkmalstabelle), `plans.py`,
der Stripe-Anschluss, und die Durchsetzung in `news-api`. Fuenf Merkmale trennen
Free von Pro: laengeres Briefing, Sprachausgabe, redigierte Premium-Stimme,
Webhook-Zustellung, eigene Stichwoerter.

★ **Solange dieser Code offen ist, kostet er einen Selbsthoster eine Zeile.**
`MERKMALE[FREI]["briefing.audio"] = True`, fertig. Das ist keine Luecke, sondern
die Natur der Sache: offener Code laesst sich aendern. Wer Open Core will, muss
die Pro-**Implementierungen** aus dem oeffentlichen Repo heraushalten, nicht nur
die Schalter.

Damit stehen drei Wege offen, und sie schliessen einander nicht aus:

### A) Tabelle offen, Implementierungen privat

Die Merkmalstabelle bleibt, wo sie ist: sie ist Struktur und erklaert dem
Selbsthoster ehrlich, was es gibt. Die Pro-Funktionen wandern in ein zweites,
privates Repo und werden zur Laufzeit dazugeladen; fehlen sie, meldet der Kern
das Merkmal als nicht verfuegbar.

*Kosten:* Jede Pro-Funktion braucht eine saubere Schnittstelle. Der Kern darf
nicht direkt in den Pro-Code greifen, sonst bricht das oeffentliche Repo beim
Bauen. Das ist laufende Arbeit bei jeder neuen Funktion.

*Ehrlich betrachtet:* Bei den heutigen fuenf Merkmalen lohnt das den Aufwand
nicht. Sie sind klein, und sie herauszuoperieren zerrisse mehr Code, als sie
wert sind. Der Weg wird interessant, sobald es ein Merkmal gibt, das wirklich
schwer nachzubauen ist.

### B) Gehostete Instanz verkaufen

Der Code bleibt vollstaendig offen. Verkauft wird, was ein Selbsthoster **nicht
mitbekommt**: der Betrieb. Sicherungen, Aktualisierungen, Erreichbarkeit,
Mandantentrennung, Abrechnung, jemand der antwortet.

★ Der Stripe-Anschluss im Repo passt genau hierzu und verliert dabei nichts: fuer
einen Selbsthoster ist eine Abrechnung wertlos, weil er keine Kunden hat. Genau
deshalb ist dieser Weg der, der bei offenem Code am wenigsten ausgehoehlt werden
kann.

*Kosten:* Betriebsarbeit und Haftung, kein Lizenzgeschaeft. Es verdient erst
Geld, wenn wirklich fuer Fremde gehostet wird.

### C) Kommerzielle Lizenz auf Anfrage

Kostet nichts an Vorbereitung ausser dem, was oben schon steht, und laeuft
nebenher. Eine Zeile im README genuegt: wer die AGPL nicht erfuellen kann, moege
sich melden.

## Empfehlung

**C sofort** (eine Zeile), **B als Ziel**, **A erst dann, wenn ein Merkmal es
verdient.** Die Reihenfolge folgt daraus, was jeweils vorbereitet sein muss: C
ist fertig, B ist Betriebsarbeit ohne Codeumbau, A ist Codeumbau mit laufenden
Kosten.

Was heute auf keinen Fall passieren darf, ist einen fremden Beitrag ohne
Rechteeinraeumung zusammenzufuehren. Alles andere bleibt entscheidbar.

## Vor dem Scharfschalten

- [ ] DCO-Pruefung im GitHub-Repo einschalten (erzwingt den Sign-off)
- [ ] Zeile ins oeffentliche README: kommerzielle Lizenz auf Anfrage, mit Adresse
- [ ] `SECURITY.md` mit einer Adresse fuer Sicherheitsmeldungen
- [ ] Pruefen, dass `exclude.txt` alles Instanz-Eigene faengt (`publish.sh --scrub`)
