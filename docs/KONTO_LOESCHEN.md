# Ein Konto loeschen: Stand, Weg und was noch fehlt

> Gebaut am 2026-10-06. Vorzustand gemessen am 2026-10-03:
> **von zwoelf Diensten hatte einer** einen Weg, die Daten eines Mandanten zu
> entfernen. Heute haben alle zwoelf einen, elf davon verkettet.

## Warum das kein Nebenthema ist

Ein in der Anmelde-Datenbank entferntes Konto hinterliess seinen vollstaendigen
Bestand in allen uebrigen Diensten. Das ist dreierlei:

1. **Stille Last.** Der Pruef-Sub `neues-konto-erstbesuch-999` aus einem
   Beweislauf vom 26.09. bekam **acht Naechte hintereinander um 04:36 ein
   vollstaendiges Briefing erzeugt**, samt moeglicher Sprachausgabe:
   `briefing_sched.py` nimmt jedes aktive Profil und fragt nie, ob dazu noch ein
   Konto gehoert. Ein verwaister Mandant ist kein Datenrest, sondern ein
   Verbraucher, der niemandem auffaellt.
2. **Ein nicht erfuellbares Loeschrecht** (DSGVO Art. 17). Das trifft schon
   Familie und Freunde, also die naechste Ausbaustufe, nicht erst Fremde.
3. **Wachsender Bestand.** Jedes Probierkonto bleibt fuer immer.

Darum gehoert es **vor** den zweiten echten Nutzer: wer erst Konten anlegt und
dann den Loeschweg baut, baut ihn gegen gewachsene Daten.

## Wie es gebaut ist

Zwei Schichten, und der Schnitt zwischen ihnen ist der eigentliche Entwurf:

| Wo | Was |
|---|---|
| `services/_geteilt/saganta_dienst/loeschen.py` | die **Mechanik**: Vorschau, Bericht, Reihenfolge, Transaktion, die drei Pruefungen, die Routen, der Programm-Einstieg |
| `services/<dienst>/app/konto.py` | der **Loeschplan** dieses Dienstes: welche Tabelle in welcher Reihenfolge faellt |

Der Plan liegt beim Dienst, weil nur er seine Fremdschluesselketten kennt. Ein
Werkzeug von aussen, das in zehn Datenbanken Zeilen entfernt, waere die
schlechtere Haelfte dieser Loesung.

### Zwei Bauarten, und warum

Die **sieben Saganta-Backends** teilen die Mechanik ueber das Paket
`saganta_dienst` (ein Build-Kontext, eine Datei). Die **vier nativen Dienste**
(`lager`, `mealprep`, `fitness`, `briefkasten`) tragen sie als Kopie in
`app/konto_mechanik.py`, weil sie **ohne das saganta-Repo baubar** bleiben
muessen; dasselbe gilt dort schon fuer `backend_auth.py` und
`mandant_ableiten.py`.

Vier Kopien driften. Bei `backend_auth.py` gibt es dafuer heute **keinen**
Abgleich, und die drei Fassungen sind gemessen verschieden. Damit es hier nicht
genauso endet, sind die Kopien **byte-identisch** und werden geprueft:

```bash
python3 scripts/loeschwege-abgleichen.py
```

Es vergleicht die Pruefsummen, verlangt je Dienst einen Plan und misst die
Abdeckung **im laufenden Container**, nicht am Quellbaum: ein Quellbaum-Lauf
beweist, dass die Datei stimmt, nicht dass der Dienst sie hat.

### Der Teil, auf den es ankommt: die drei Pruefungen

Eine Liste von Loeschschritten ist eine Liste, die man pflegen muss, und solche
Listen veralten in beide Richtungen. Wer morgen eine Tabelle mit `owner_sub`
hinzufuegt, faellt still aus dem Loeschweg, **und ein Loeschlauf meldet
weiterhin Erfolg.** Dagegen stehen drei Pruefungen, und jede hat eine andere
Quelle, weil jede nur ihre eigene Luecke findet:

**1. `abdeckung_pruefen` fragt die Modelle.** Das Soll kommt aus den
SQLAlchemy-Metadaten, also aus dem Ist der Modelle. Eine Tabelle gilt als
abgedeckt, wenn sie in einem Schritt steht, ausdruecklich als gemeinsamer
Bestand erklaert ist, oder per `ondelete="CASCADE"` an einer abgedeckten Tabelle
haengt (transitiv aufgeloest). Sie laeuft **ohne jede Daten** und damit im Test
je Dienst: der Befund soll vor den Daten da sein.

**2. `ungedeckte_live_tabellen` fragt die Datenbank.** Alles, was ein
Dienst per rohem SQL anlegt, steht in keinem Modell und ist fuer Pruefung 1
unsichtbar. Das ist keine theoretische Grenze: **der `briefkasten` behielt nach
einem als "sauber" gemeldeten Loeschlauf das Embedding des geloeschten Briefs**
in `letter_vec`, einer `vec0`-Virtualtabelle, die keinen Fremdschluessel haben
kann. Ein 384-dimensionaler Vektor kodiert den Inhalt und erlaubt
Aehnlichkeitssuche; er ist Nutzerinhalt. Gefunden wurde das erst bei einem
scharfen Lauf gegen eine **Kopie der Live-Datenbank**, nicht im Test.
_Woran man die Luecke erkennt, bevor sie zuschlaegt:_ der Abgleich zeigt je
Dienst „Modelle / in der DB". Beim `briefkasten` sind das 8 gegen 20, bei
`notizen` 5 gegen 10. Wo die Zahlen auseinanderliegen, entstehen diese Luecken.

**3. Die Restpruefung** fragt nach dem Loeschen und noch vor dem Commit, ob
irgendeine Tabelle den Mandanten noch traegt. Findet sie etwas, wird
zurueckgerollt. Ohne sie waere ein Schritt, dessen Bedingung nie greift, von
einem erfolgreichen Lauf nicht zu unterscheiden: beide melden null geloeschte
Zeilen, und das liest sich wie "war nichts da".

### Zwei Einstiege, ein Plan

* **Route** `GET /api/konto/bestand` und `POST /api/konto/loeschen` (Bestaetigung
  `"KONTO LOESCHEN"` im Rumpf), **nur in den sieben Saganta-Backends**. Der
  Mandant kommt dort immer aus dem Token; es gibt keinen Parameter, mit dem ein
  Aufrufer einen fremden `sub` nennen koennte. `/bestand` loescht nichts und ist
  zugleich der Auskunftsweg.
* **Programm** `docker exec -w /app <container> python -m app.konto --sub X
  [--loeschen]`, in allen elf. Fuer **verwaiste** Bestaende, deren Konto schon
  weg ist: fuer die laesst sich kein Token mehr ausstellen.

Die Trennung ist Absicht. Eine Netzroute, die einen beliebigen `sub`
entgegennimmt, waere eine Fernbedienung zum Loeschen fremder Daten und muesste
genau einmal falsch abgesichert sein. Der Betreiberweg verlangt Zugriff auf den
Wirt, den hat ohnehin nur, wer die Platte auch so loeschen koennte.

**Die vier nativen Dienste haben bewusst GAR KEINE Route.** Dort faellt
`get_db` fuer interne, headerlose Aufrufer auf `DEFAULT_OWNER_SUB` zurueck, und
das ist ein gewollter Pfad (life-ops und assets-api rufen so an). Eine
Loeschroute dahinter waere eine Fernbedienung, die beim ersten headerlosen
Aufruf **den Owner** trifft. Das Loeschrecht verlangt, dass der Betreiber
loeschen kann, nicht dass jeder Dienst eine Selbstbedienung anbietet.

## Das Werkzeug ueber alle Dienste

```bash
python3 scripts/konto-loeschen.py --sub <sub>              # nur zeigen
python3 scripts/konto-loeschen.py --sub <sub> --loeschen   # wirklich loeschen
```

Es verkettet die sieben Dienste dieses Repos und **benennt, was es nicht kann**,
mit Zeilenzahl. Der Rueckgabewert ist nur dann 0, wenn jeder verkettete Dienst
sauber war und nirgends ungeloeschter Bestand zurueckbleibt.

Gegenstueck: `verwaiste-mandanten.py` findet Mandanten ohne Konto, dieses hier
raeumt einen ab.

## Stand: zwoelf von zwoelf, elf davon verkettet

| Dienst | Bauart | Anmerkung |
|---|---|---|
| notizen | Paket | samt FTS5-Index (haelt den Klartext!) und Anhangdateien |
| tagebuch | Paket | Chiffrat und verpackte Schluessel |
| assets | Paket | Bilder liegen bei `marktwatch`, nicht hier |
| projectdeck | Paket | 7 Kindtabellen per CASCADE, Spalte heisst `owner` |
| news | Paket | Briefing-Profil zuerst, dazu die Sprachausgaben als Dateien |
| shell | Paket | inklusive `audit_log`, mit Begruendung in `konto.py` |
| mail | Paket | Nachrichten ueber ihr Konto, FK ohne CASCADE |
| lager | Kopie | 4 Tabellen, FKs ohne `ondelete`, Reihenfolge zwingend |
| mealprep | Kopie | Seed-Rezeptkatalog (`owner_sub NULL`) bleibt, eigene Rezepte fallen |
| fitness | Kopie | `exercise.created_by_sub` heisst anders und stand fast nicht im Plan |
| briefkasten | Kopie | ein Schritt plus die Einbettungen; alles haengt an **einer** CASCADE-Kante |
| kalender | eigener Weg | ✅ vorhanden, aber **bewusst nicht verkettet**, siehe unten |

Gemessen am 2026-10-06 an einer **Kopie der Live-Datenbanken**, scharf
gefahren: lager 62 Zeilen weg, mealprep 1540, fitness 89, briefkasten 2 plus die
Einbettung. Je Dienst mit Gegenprobe, dass der geteilte Bestand stehen bleibt
(mealprep 271 Zeilen Katalog, fitness 185, briefkasten die zwei lokalen Konten
ohne `sub`).

Zwei Dinge, die diese Probe aufgedeckt hat und die kein Test gefunden haette:
die Einbettungstabelle des `briefkastens` (siehe Pruefung 2) und dass
`postfach/routes_accounts.py` **Vertragskonten** loescht, nicht den Mandanten.
Wer nur den Namen liest, haelt dort einen Loeschweg fuer vorhanden.

### Warum der Kalender bewusst nicht verkettet ist

An seinem Owner-Sub haengt ueber den headerlosen Pfad `day-type/today` die
**Weckkette der Wohnung**. Ein verketteter Lauf, der versehentlich den Owner
traefe, nimmt die Heizung mit. Das Werkzeug nennt den Befehl, fuehrt ihn aber
nicht aus. Hier ist Nichtstun reversibel und Tun nicht.

### Was ausdruecklich nicht dazugehoert

**Das Konto in der Anmelde-Datenbank** (`saganta-auth`) wird hier nicht
geloescht. Reihenfolge ist: erst die Daten, dann die Anmeldung. Andersherum
entsteht genau der verwaiste Bestand, gegen den das Ganze gebaut ist.

## Was als naechstes zu tun ist

1. `saganta-auth` bekommt einen Weg, der das Werkzeug ruft und **danach** das
   Konto entfernt, damit die Reihenfolge nicht von Hand eingehalten werden muss.
2. Eine Wache, die meldet, wenn ein Profil ohne Konto arbeitet. Der Befund von
   damals waere so am ersten Morgen aufgefallen statt in der achten Nacht.
3. `loeschwege-abgleichen.py` in einen Timer, damit eine neue Tabelle auch dann
   auffaellt, wenn niemand die Tests laufen laesst.
4. Offen und bewusst nicht geloest: der Volltextindex haelt nach dem Loeschen
   **Tombstones** (FTS5 traegt ein `delete`-Kommando nach, raeumt die Bloecke
   aber erst beim Zusammenlegen). Logisch ist der Treffer weg, physisch koennen
   Reste in `*_fts_data` liegen, bis ein `optimize` laeuft. Ob das genuegt, ist
   eine Frage fuer den Fall, dass fremde Nutzer dazukommen.
