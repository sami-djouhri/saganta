// Kanonischer lokaler ALTCHA/PoW-Captcha-Verify für Node/TS-Apps in der DMZ
// (netcup), dort ist der zentrale captcha-guard-Dienst NICHT erreichbar. Die App
// stellt die Challenge selbst aus (HMAC-signiert) und verifiziert lokal, inkl.
// Replay-Schutz. ALTCHA-Payload-Format → dasselbe Widget (public/captcha-guard/).
//
// Verwendung: nach <app>/lib/captcha.ts kopieren (oder via Sync verteilen).
// In Betrieb bei djouhri (~/sami-portfolio) + smarthome (~/technik-werkstatt).
//
// ENV:
//   CAPTCHA_HMAC_KEY    geheimer Schlüssel (>=16 Zeichen). Leer = Captcha AUS.
//   CAPTCHA_MAX_NUMBER  PoW-Schwierigkeit (Default 50000). "Später upgraden" = erhöhen.
import { createHash, createHmac, randomBytes, randomInt, timingSafeEqual } from 'crypto';

const HMAC_KEY = process.env.CAPTCHA_HMAC_KEY || '';
const MAX_NUMBER = Number(process.env.CAPTCHA_MAX_NUMBER || '50000');
const CHALLENGE_TTL_S = 300;

export function captchaEnabled(): boolean {
  return HMAC_KEY.length >= 16;
}

function sha256Hex(s: string): string {
  return createHash('sha256').update(s).digest('hex');
}
function hmacHex(msg: string): string {
  return createHmac('sha256', HMAC_KEY).update(msg).digest('hex');
}
function safeEq(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  return ba.length === bb.length && timingSafeEqual(ba, bb);
}

export interface Challenge {
  algorithm: 'SHA-256';
  challenge: string;
  salt: string;
  signature: string;
  maxnumber: number;
}

export function createChallenge(): Challenge {
  const expires = Math.floor(Date.now() / 1000) + CHALLENGE_TTL_S;
  const salt = `${randomBytes(12).toString('hex')}?expires=${expires}`;
  const number = randomInt(0, MAX_NUMBER + 1);
  const challenge = sha256Hex(salt + number);
  return { algorithm: 'SHA-256', challenge, salt, signature: hmacHex(challenge), maxnumber: MAX_NUMBER };
}

// Replay-Schutz: eine akzeptierte Signatur wird für ihr TTL-Fenster verbraucht.
// In-Memory pro Prozess (Next.js standalone = langlebig). Bei Mehr-Replica auf
// Redis o.ä. heben: Interface bleibt.
const REPLAY_TTL_MS = (CHALLENGE_TTL_S + 60) * 1000;
const seenSignatures = new Map<string, number>();

function seenBefore(sig: string): boolean {
  const now = Date.now();
  for (const [k, exp] of seenSignatures) if (exp <= now) seenSignatures.delete(k);
  if (seenSignatures.has(sig)) return true;
  seenSignatures.set(sig, now + REPLAY_TTL_MS);
  return false;
}

export function captchaOk(token: string | undefined | null): boolean {
  if (!captchaEnabled()) return true; // global deaktiviert
  if (!token || typeof token !== 'string') return false;
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(Buffer.from(token, 'base64').toString('utf8'));
  } catch {
    return false;
  }
  const { algorithm, challenge, salt, signature, number } = data as {
    algorithm?: string; challenge?: string; salt?: string; signature?: string; number?: number;
  };
  if (algorithm !== 'SHA-256') return false;
  if (typeof challenge !== 'string' || typeof salt !== 'string' || typeof signature !== 'string') return false;
  if (typeof number !== 'number' || number < 0 || number > MAX_NUMBER) return false;
  const q = salt.split('?')[1];
  if (q) {
    const exp = new URLSearchParams(q).get('expires');
    if (exp && Date.now() / 1000 > Number(exp)) return false;
  }
  if (!safeEq(sha256Hex(salt + number), challenge)) return false;
  if (!safeEq(hmacHex(challenge), signature)) return false;
  if (seenBefore(signature)) return false; // Replay-Guard zuletzt
  return true;
}
