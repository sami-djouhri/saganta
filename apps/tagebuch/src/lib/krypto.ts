/**
 * Verschlüsselung des Tagebuchs, ausschließlich im Browser.
 *
 * ## Der Aufbau in einem Satz
 *
 * Es gibt einen einzigen Datenschlüssel (DEK), mit dem jeder Eintrag
 * verschlüsselt wird, und dieser DEK liegt auf dem Server nur *verpackt*:
 * einmal unter der Passphrase, einmal unter dem Wiederherstellungsschlüssel.
 *
 * Warum nicht die Einträge direkt mit der Passphrase verschlüsseln? Dann hinge
 * jeder einzelne Eintrag an ihr. Ein Passwortwechsel müsste den gesamten
 * Bestand neu verschlüsseln, ein zweiter Zugangsweg wäre unmöglich, und ein
 * Abbruch mitten im Wechsel hinterließe ein halb lesbares Tagebuch. Mit einem
 * verpackten DEK ist ein Wechsel das Neuverschnüren eines einzigen Pakets.
 *
 * ## Die Grenzen, ausdrücklich
 *
 * - Wer Passphrase **und** Wiederherstellungsschlüssel verliert, verliert die
 *   Einträge. Endgültig, auch aus jeder Sicherung. Das ist kein Mangel des
 *   Entwurfs, sondern seine Bedingung: gäbe es einen dritten Weg, hätte ihn
 *   auch jemand anderes.
 * - Der Schutz greift gegen jeden, der an die Datenbank kommt. Er greift nicht
 *   gegen jemanden, der den Browser während der Sitzung übernimmt: dort liegt
 *   der Klartext, das ist der Zweck.
 *
 * ## Verwandtschaft
 *
 * `apps/notizen/src/lib/krypto.ts` löst eine andere Aufgabe (ein Schlüssel je
 * Freigabe, Weitergabe im Adress-Fragment) mit denselben Grundbausteinen. Die
 * Base64-Helfer und `schluesselAusPasswort` sind dort wortgleich. Sie sind
 * hier bewusst noch einmal geschrieben statt geteilt: eine gemeinsame Schicht
 * müsste die laufenden Notizen-Freigaben mit umbauen, und das ist ein eigener
 * Schritt mit eigenem Risiko. Wer beides zusammenführt, fängt bei diesen
 * beiden Dateien an.
 */

/** OWASP-Empfehlung für PBKDF2-HMAC-SHA256 (Stand 2026). */
export const KDF_ITERATIONEN = 310_000;
export const KDF_NAME = 'PBKDF2-SHA256';

/**
 * Länge des Wiederherstellungsschlüssels in Bytes. 20 Byte sind 160 bit
 * Zufall, also weit jenseits dessen, was sich durchprobieren lässt, und
 * ergeben 32 Zeichen: acht Vierergruppen, die man abschreiben kann, ohne sich
 * zu verzählen.
 */
const WIEDERHERSTELLUNG_BYTES = 20;

/**
 * Crockford-Base32 ohne I, L, O und U. Das ist der Punkt an diesem Alphabet:
 * 1 und I, 0 und O sind auf Papier nicht zu unterscheiden, und wer den Zettel
 * ein Jahr später im Ordner findet, hat keine zweite Gelegenheit zum Raten.
 * U fehlt, damit aus Zufall kein anstößiges Wort entsteht.
 */
const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

export class KryptoFehler extends Error {
  constructor(
    message: string,
    readonly art: 'kein-sicherer-kontext' | 'falscher-schluessel' | 'defekt',
  ) {
    super(message);
    this.name = 'KryptoFehler';
  }
}

/**
 * Ist WebCrypto verfügbar?
 *
 * ★ Diese Prüfung ist keine Förmlichkeit. `crypto.subtle` gibt der Browser nur
 * im sicheren Kontext frei, also unter https oder auf localhost. Über blankes
 * `http://IP:Port` fehlt es, und ohne diese Abfrage scheitert die erste
 * Entschlüsselung mit einer Meldung, die wie eine falsche Passphrase aussieht.
 * Genau das ist beim Posteingang auf djouhri.de passiert und hat dort lange
 * nach dem falschen Fehler suchen lassen.
 */
export function sichererKontext(): boolean {
  return typeof crypto !== 'undefined' && typeof crypto.subtle !== 'undefined';
}

function fordereKontext(): void {
  if (!sichererKontext()) {
    throw new KryptoFehler(
      'Dieser Browser gibt die Verschlüsselung nicht frei. Das Tagebuch braucht eine https-Adresse ' +
        '(tagebuch.home.arpa), über eine nackte IP-Adresse funktioniert es nicht.',
      'kein-sicherer-kontext',
    );
  }
}

function inBase64(roh: ArrayBuffer | Uint8Array): string {
  const bytes = roh instanceof Uint8Array ? roh : new Uint8Array(roh);
  let text = '';
  // In Blöcken, weil String.fromCharCode(...langesArray) den Aufrufstapel
  // sprengt. Bei einem sehr langen Tag wäre das ein Absturz statt eines
  // gespeicherten Eintrags.
  const block = 0x8000;
  for (let i = 0; i < bytes.length; i += block) {
    text += String.fromCharCode(...bytes.subarray(i, i + block));
  }
  return btoa(text);
}

function ausBase64(text: string): Uint8Array {
  const roh = atob(text);
  const bytes = new Uint8Array(roh.length);
  for (let i = 0; i < roh.length; i++) bytes[i] = roh.charCodeAt(i);
  return bytes;
}

// --- Wiederherstellungsschlüssel -------------------------------------------

/** Erzeugt einen neuen Wiederherstellungsschlüssel in lesbarer Schreibweise. */
export function wiederherstellungsschluesselErzeugen(): string {
  fordereKontext();
  const bytes = crypto.getRandomValues(new Uint8Array(WIEDERHERSTELLUNG_BYTES));
  let bits = 0;
  let wert = 0;
  let zeichen = '';
  for (const b of bytes) {
    wert = (wert << 8) | b;
    bits += 8;
    while (bits >= 5) {
      zeichen += ALPHABET[(wert >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) zeichen += ALPHABET[(wert << (5 - bits)) & 31];
  return (zeichen.match(/.{1,4}/g) ?? []).join('-');
}

/**
 * Bringt einen abgetippten Schlüssel auf seine Normalform.
 *
 * Trennzeichen und Kleinschreibung fallen weg, und die vier verwechselbaren
 * Zeichen werden auf ihre Ziffer gezogen. Wer `O` statt `0` liest, soll nicht
 * an seinen eigenen Notfallzettel scheitern.
 */
export function schluesselNormalisieren(eingabe: string): string {
  return eingabe
    .toUpperCase()
    .replace(/[\s-]/g, '')
    .replace(/[IL]/g, '1')
    .replace(/O/g, '0');
}

// --- Schlüsselableitung ----------------------------------------------------

export function neuesSalz(): string {
  fordereKontext();
  return inBase64(crypto.getRandomValues(new Uint8Array(16)));
}

/**
 * Leitet aus einem Geheimnis den Schlüsselschlüssel (KEK) ab.
 *
 * Derselbe Weg für Passphrase und Wiederherstellungsschlüssel, nur mit
 * verschiedenem Salz. Das Ergebnis kann ausschließlich ver- und entpacken, es
 * verschlüsselt nie einen Eintrag.
 */
async function kekAbleiten(
  geheimnis: string,
  salzBase64: string,
  iterationen: number = KDF_ITERATIONEN,
): Promise<CryptoKey> {
  fordereKontext();
  const rohschluessel = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(geheimnis) as BufferSource,
    'PBKDF2',
    false,
    ['deriveKey'],
  );
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt: ausBase64(salzBase64) as BufferSource,
      iterations: iterationen,
      hash: 'SHA-256',
    },
    rohschluessel,
    { name: 'AES-GCM', length: 256 },
    false,
    ['wrapKey', 'unwrapKey'],
  );
}

// --- Der Datenschlüssel und seine Pakete -----------------------------------

/**
 * Erzeugt den Datenschlüssel.
 *
 * `extractable: true` ist nötig, damit er sich verpacken lässt. Das klingt
 * nach einer Schwächung, ist aber keine: extrahierbar heißt „von Code auf
 * dieser Seite", und dieser Code ist es, der ihn verpackt. Ohne das Recht
 * gäbe es kein Paket und damit keinen Weg, ihn über einen Neustart zu retten.
 */
async function dekErzeugen(): Promise<CryptoKey> {
  fordereKontext();
  return crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, [
    'encrypt',
    'decrypt',
  ]);
}

async function verpacken(dek: CryptoKey, kek: CryptoKey) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const paket = await crypto.subtle.wrapKey('raw', dek, kek, {
    name: 'AES-GCM',
    iv: iv as BufferSource,
  });
  return { wrap: inBase64(paket), iv: inBase64(iv) };
}

async function entpacken(wrapBase64: string, ivBase64: string, kek: CryptoKey): Promise<CryptoKey> {
  try {
    return await crypto.subtle.unwrapKey(
      'raw',
      ausBase64(wrapBase64) as BufferSource,
      kek,
      { name: 'AES-GCM', iv: ausBase64(ivBase64) as BufferSource },
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt'],
    );
  } catch {
    // AES-GCM prüft beim Entpacken sein eigenes Siegel. Schlägt das fehl, war
    // das Geheimnis falsch. Ein eigener Prüfwert in der Datenbank wäre
    // überflüssig und gäbe nur eine weitere Angriffsfläche zum Durchprobieren.
    throw new KryptoFehler('Passphrase oder Wiederherstellungsschlüssel passt nicht.', 'falscher-schluessel');
  }
}

export interface TresorPakete {
  kdf: string;
  kdf_iterationen: number;
  salz_passphrase: string;
  wrap_passphrase: string;
  wrap_passphrase_iv: string;
  salz_wiederherstellung: string;
  wrap_wiederherstellung: string;
  wrap_wiederherstellung_iv: string;
}

export interface NeuerTresor {
  pakete: TresorPakete;
  /** Nur hier und nur jetzt. Danach kennt ihn niemand mehr, auch der Server nicht. */
  wiederherstellungsschluessel: string;
  dek: CryptoKey;
}

/** Richtet einen Tresor ein: neuer DEK, zweimal verpackt. */
export async function tresorAnlegen(passphrase: string): Promise<NeuerTresor> {
  fordereKontext();
  const dek = await dekErzeugen();
  const wiederherstellungsschluessel = wiederherstellungsschluesselErzeugen();

  const salzPass = neuesSalz();
  const salzWied = neuesSalz();
  const [pass, wied] = await Promise.all([
    kekAbleiten(passphrase, salzPass).then((kek) => verpacken(dek, kek)),
    kekAbleiten(schluesselNormalisieren(wiederherstellungsschluessel), salzWied).then((kek) =>
      verpacken(dek, kek),
    ),
  ]);

  return {
    dek,
    wiederherstellungsschluessel,
    pakete: {
      kdf: KDF_NAME,
      kdf_iterationen: KDF_ITERATIONEN,
      salz_passphrase: salzPass,
      wrap_passphrase: pass.wrap,
      wrap_passphrase_iv: pass.iv,
      salz_wiederherstellung: salzWied,
      wrap_wiederherstellung: wied.wrap,
      wrap_wiederherstellung_iv: wied.iv,
    },
  };
}

export async function tresorOeffnen(pakete: TresorPakete, passphrase: string): Promise<CryptoKey> {
  const kek = await kekAbleiten(passphrase, pakete.salz_passphrase, pakete.kdf_iterationen);
  return entpacken(pakete.wrap_passphrase, pakete.wrap_passphrase_iv, kek);
}

export async function tresorOeffnenMitWiederherstellung(
  pakete: TresorPakete,
  schluessel: string,
): Promise<CryptoKey> {
  const kek = await kekAbleiten(
    schluesselNormalisieren(schluessel),
    pakete.salz_wiederherstellung,
    pakete.kdf_iterationen,
  );
  return entpacken(pakete.wrap_wiederherstellung, pakete.wrap_wiederherstellung_iv, kek);
}

export interface PassphrasePaket {
  kdf: string;
  kdf_iterationen: number;
  salz_passphrase: string;
  wrap_passphrase: string;
  wrap_passphrase_iv: string;
}

/**
 * Verpackt den bereits geöffneten DEK unter einer neuen Passphrase.
 *
 * Der Wiederherstellungs-Zweig wird dabei nicht angefasst, und das ist Absicht:
 * ein ausgedruckter Notfallzettel soll nicht ungültig werden, weil jemand sein
 * Passwort geändert hat.
 */
export async function passphraseNeuVerpacken(
  dek: CryptoKey,
  neuePassphrase: string,
): Promise<PassphrasePaket> {
  const salz = neuesSalz();
  const kek = await kekAbleiten(neuePassphrase, salz);
  const { wrap, iv } = await verpacken(dek, kek);
  return {
    kdf: KDF_NAME,
    kdf_iterationen: KDF_ITERATIONEN,
    salz_passphrase: salz,
    wrap_passphrase: wrap,
    wrap_passphrase_iv: iv,
  };
}

// --- Einträge --------------------------------------------------------------

/**
 * Was ein Eintrag enthält.
 *
 * ★ Die Skalen liegen **mit** im verschlüsselten Paket, obwohl dieselben Werte
 * anschließend offen an den Kalender gehen. Das ist kein Widerspruch, sondern
 * die Trennung der Zuständigkeiten: der Kalender braucht die Zahl für die
 * Tagesplanung und bekommt sie, das Tagebuch bleibt auch dann vollständig
 * lesbar, wenn es den Kalender einmal nicht gibt. Hinge die Stimmung nur dort,
 * wäre ein Eintrag ohne den Kalender ein halber Eintrag.
 */
export interface Eintragsinhalt {
  text: string;
  stimmung?: 'gut' | 'neutral' | 'mies' | null;
  energie?: 'hoch' | 'mittel' | 'niedrig' | null;
  schlaf?: 'gut' | 'mittel' | 'schlecht' | null;
}

export interface Verschluesselt {
  chiffrat: string;
  iv: string;
}

export async function eintragVerschluesseln(
  inhalt: Eintragsinhalt,
  dek: CryptoKey,
): Promise<Verschluesselt> {
  fordereKontext();
  // 96 bit ist die für GCM vorgesehene Länge, und jeder Eintrag bekommt einen
  // eigenen Wert. Ein zweites Mal derselbe wäre bei GCM kein
  // Schönheitsfehler, sondern der Verlust der Vertraulichkeit.
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const chiffrat = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: iv as BufferSource },
    dek,
    new TextEncoder().encode(JSON.stringify(inhalt)) as BufferSource,
  );
  return { chiffrat: inBase64(chiffrat), iv: inBase64(iv) };
}

export async function eintragEntschluesseln(
  verschluesselt: Verschluesselt,
  dek: CryptoKey,
): Promise<Eintragsinhalt> {
  fordereKontext();
  let klar: ArrayBuffer;
  try {
    klar = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: ausBase64(verschluesselt.iv) as BufferSource },
      dek,
      ausBase64(verschluesselt.chiffrat) as BufferSource,
    );
  } catch {
    throw new KryptoFehler('Dieser Eintrag lässt sich nicht öffnen.', 'falscher-schluessel');
  }
  const roh = new TextDecoder().decode(klar);
  try {
    const daten = JSON.parse(roh) as Partial<Eintragsinhalt>;
    return {
      text: typeof daten.text === 'string' ? daten.text : '',
      stimmung: daten.stimmung ?? null,
      energie: daten.energie ?? null,
      schlaf: daten.schlaf ?? null,
    };
  } catch {
    // Entschlüsselt, aber kein bekanntes Paket. Der Text ist wertvoller als
    // die Form: lieber roh anzeigen als einen Eintrag für kaputt erklären.
    return { text: roh, stimmung: null, energie: null, schlaf: null };
  }
}
