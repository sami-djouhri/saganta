/**
 * Verschlüsselung für geteilte Notizen: ausschließlich im Browser.
 *
 * Das Verfahren ist AES-GCM mit 256 bit. Der Schlüssel entsteht hier und geht
 * auf zwei möglichen Wegen zum Empfänger:
 *
 * 1. **Im Adress-Fragment** (`…/AbCdEf#schlüssel`). Alles hinter dem `#` sendet
 *    der Browser nicht an den Server, der Schlüssel steht also in der Adresse,
 *    kommt aber nie in einem Zugriffsprotokoll, keinem Zwischenspeicher und
 *    keiner Datenbank an. Wer den Link hat, hat den Schlüssel; wer nur den
 *    Server hat, hat nichts.
 * 2. **Aus einem Passwort abgeleitet** (PBKDF2). Dann steht in der Adresse gar
 *    kein Schlüssel, und der Empfänger braucht etwas, das man ihm auf einem
 *    anderen Weg sagt.
 *
 * Beides ist nur so stark wie der Weg, auf dem der Link verschickt wird, wer
 * Link und Passwort in denselben Chat schreibt, hat nichts gewonnen. Die
 * Oberfläche sagt das an der Stelle, an der man es entscheidet.
 */

/** OWASP-Empfehlung für PBKDF2-HMAC-SHA256 (Stand 2026). */
export const KDF_ITERATIONEN = 310_000;
export const ALGO = 'AES-GCM-256';

function inBase64(roh: ArrayBuffer | Uint8Array): string {
  const bytes = roh instanceof Uint8Array ? roh : new Uint8Array(roh);
  let text = '';
  // In Blöcken, weil String.fromCharCode(...langesArray) den Aufrufstapel
  // sprengt, bei einer 4-MiB-Notiz wäre das ein Absturz statt einer Freigabe.
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

/** Base64 in der Variante, die ohne Umkodierung in eine Adresse passt. */
function inBase64Url(roh: ArrayBuffer | Uint8Array): string {
  return inBase64(roh).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function ausBase64Url(text: string): Uint8Array {
  const gefüllt = text.replace(/-/g, '+').replace(/_/g, '/');
  return ausBase64(gefüllt + '='.repeat((4 - (gefüllt.length % 4)) % 4));
}

export interface Verschluesselt {
  chiffrat: string;
  iv: string;
}

export async function neuerSchluessel(): Promise<CryptoKey> {
  return crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, [
    'encrypt',
    'decrypt',
  ]);
}

export async function schluesselExportieren(key: CryptoKey): Promise<string> {
  return inBase64Url(await crypto.subtle.exportKey('raw', key));
}

export async function schluesselImportieren(kodiert: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    ausBase64Url(kodiert) as BufferSource,
    { name: 'AES-GCM' },
    false,
    ['encrypt', 'decrypt'],
  );
}

export function neuesSalz(): string {
  return inBase64(crypto.getRandomValues(new Uint8Array(16)));
}

export async function schluesselAusPasswort(
  passwort: string,
  salzBase64: string,
  iterationen: number = KDF_ITERATIONEN,
): Promise<CryptoKey> {
  const rohschluessel = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(passwort) as BufferSource,
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
    ['encrypt', 'decrypt'],
  );
}

export async function verschluesseln(klartext: string, key: CryptoKey): Promise<Verschluesselt> {
  // 96 bit ist die für GCM vorgesehene Länge; jeder Vorgang bekommt einen
  // eigenen Wert. Ein zweites Mal derselbe wäre bei GCM kein Schönheitsfehler,
  // sondern der Verlust der Vertraulichkeit.
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const chiffrat = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: iv as BufferSource },
    key,
    new TextEncoder().encode(klartext) as BufferSource,
  );
  return { chiffrat: inBase64(chiffrat), iv: inBase64(iv) };
}

export async function entschluesseln(
  chiffratBase64: string,
  ivBase64: string,
  key: CryptoKey,
): Promise<string> {
  const klar = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: ausBase64(ivBase64) as BufferSource },
    key,
    ausBase64(chiffratBase64) as BufferSource,
  );
  return new TextDecoder().decode(klar);
}

/**
 * Titel und Text zusammen verschlüsseln.
 *
 * Der Titel muss mit hinein: bliebe er außen vor, stünde er im Klartext in der
 * Datenbank und die Zusicherung „der Server weiß nichts vom Inhalt" wäre für
 * die aussagekräftigste Zeile der Notiz nicht wahr.
 */
export function paketSchnueren(titel: string, inhalt: string): string {
  return JSON.stringify({ titel, inhalt });
}

export function paketOeffnen(roh: string): { titel: string; inhalt: string } {
  try {
    const daten = JSON.parse(roh) as { titel?: unknown; inhalt?: unknown };
    return {
      titel: typeof daten.titel === 'string' ? daten.titel : '',
      inhalt: typeof daten.inhalt === 'string' ? daten.inhalt : roh,
    };
  } catch {
    // Ältere oder fremd erzeugte Freigaben können reiner Text sein.
    return { titel: '', inhalt: roh };
  }
}
