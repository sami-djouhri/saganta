import { createTransport, type Transporter } from 'nodemailer';

/**
 * Transaktionaler E-Mail-Versand des Auth-Service (Verifizierung + Passwort-Reset).
 *
 * Konfiguration rein über Env (SMTP_*). Ist kein SMTP-Host gesetzt, läuft der
 * Service im Homelab-Fallback: die Links werden auf die Konsole geloggt statt
 * versendet, so bleibt der Flow auch ohne hinterlegtes SMTP-Secret testbar,
 * ohne den Prozess hart zu blockieren. Produktiv MUSS SMTP_HOST gesetzt sein.
 */

const SMTP_HOST = process.env.SMTP_HOST ?? '';
const SMTP_PORT = Number(process.env.SMTP_PORT ?? 587);
// 465 = implizites TLS; 587 = STARTTLS. Default richtet sich nach dem Port.
const SMTP_SECURE = (process.env.SMTP_SECURE ?? (SMTP_PORT === 465 ? 'true' : 'false')) === 'true';
const SMTP_USER = process.env.SMTP_USER ?? '';
const SMTP_PASS = process.env.SMTP_PASS ?? '';
// ★ Keine Vorbelegung mit einer fremden Absender-Adresse (seit 2026-09-06):
// eine andere Installation haette sonst in fremdem Namen verschickt, und die
// Zustellung waere ohnehin an SPF/DKIM gescheitert. Leer heisst: kein Versand,
// dieselbe Linie wie ohne SMTP_HOST (siehe `enabled` unten).
const MAIL_FROM = process.env.MAIL_FROM ?? '';

// Öffentliche Web-Basis für klickbare Links. /api/auth wird am Edge zum
// Auth-Service geroutet → der Verify-Endpoint ist unter ${WEB}/api/auth erreichbar.
// BETTER_AUTH_URL ist Pflicht (auth.ts `required`), die dritte Stufe war
// deshalb unerreichbar und trug nur die Domaene der Ursprungs-Instanz.
const WEB_BASE_URL = (
  process.env.WEB_BASE_URL ??
  process.env.BETTER_AUTH_URL ??
  ''
).replace(/\/$/, '');

// ★ MAIL_FROM gehoert in die Bedingung: mit SMTP-Wirt, aber ohne
// Absender-Adresse gingen Mails mit leerem From hinaus, und die verwirft jeder
// halbwegs strenge Empfaenger. Lieber gar nicht senden und es sagen.
const enabled = Boolean(SMTP_HOST && MAIL_FROM);

// SG-03: Ohne SMTP darf der Verify-/Reset-Token NICHT im Klartext ins Log (Log-Leser
// = Kontoübernahme) und der Auth-Request darf nicht still "Erfolg" mit unzustellbarer
// Mail vortäuschen. Default fail-closed. Nur für lokale Entwicklung per Opt-in wieder
// auf Konsolen-Link umschaltbar (analog ALLOW_INSECURE_SECRETS-Muster der Suite).
const allowInsecureMailLog = process.env.AUTH_ALLOW_INSECURE_MAIL_LOG === 'true';

let transporter: Transporter | null = null;
function getTransport(): Transporter {
  if (!transporter) {
    transporter = createTransport({
      host: SMTP_HOST,
      port: SMTP_PORT,
      secure: SMTP_SECURE,
      auth: SMTP_USER ? { user: SMTP_USER, pass: SMTP_PASS } : undefined,
    });
  }
  return transporter;
}

function verifyLink(token: string): string {
  const callback = encodeURIComponent(`${WEB_BASE_URL}/?verified=1`);
  return `${WEB_BASE_URL}/api/auth/verify-email?token=${encodeURIComponent(token)}&callbackURL=${callback}`;
}

function resetLink(token: string): string {
  // Eigene Shell-Seite (kein better-auth-Redirect-Tanz): /reset liest den Token
  // und POSTet das neue Passwort serverseitig an /api/auth/reset-password.
  return `${WEB_BASE_URL}/reset?token=${encodeURIComponent(token)}`;
}

// --- Branding: schlichtes, marken-konsistentes HTML (dunkel, Akzent-Blau) ---

function shell(title: string, intro: string, ctaLabel: string, ctaUrl: string, foot: string): string {
  // Nachtstudie: warmes Tinten-Schwarz, Ivory-Text, Messing-CTA (dunkle Schrift
  // auf Akzent, wie suite-weit). Inline-Styles Pflicht (E-Mail-Clients).
  return `<!doctype html><html lang="de"><body style="margin:0;background:#16130f;font-family:Inter,Segoe UI,Helvetica,Arial,sans-serif;color:#f3ede2;padding:32px 0">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background:#1f1b15;border:1px solid #302920;border-radius:16px;overflow:hidden">
      <tr><td style="padding:32px 36px 8px">
        <div style="font-family:Georgia,'Times New Roman',serif;font-size:30px;letter-spacing:-.5px;color:#f3ede2">Saganta</div>
      </td></tr>
      <tr><td style="padding:8px 36px 0">
        <h1 style="font-size:20px;font-weight:600;margin:16px 0 8px;color:#f3ede2">${title}</h1>
        <p style="font-size:15px;line-height:1.6;color:#a69b8a;margin:0 0 24px">${intro}</p>
      </td></tr>
      <tr><td style="padding:0 36px 28px">
        <a href="${ctaUrl}" style="display:inline-block;background:#cf8524;color:#1b1408;text-decoration:none;font-size:15px;font-weight:600;padding:12px 24px;border-radius:10px">${ctaLabel}</a>
      </td></tr>
      <tr><td style="padding:0 36px 32px">
        <p style="font-size:13px;line-height:1.6;color:#8a7f6d;margin:0">${foot}</p>
        <p style="font-size:12px;line-height:1.6;color:#6c6254;margin:16px 0 0;word-break:break-all">Falls der Button nicht funktioniert:<br>${ctaUrl}</p>
      </td></tr>
    </table>
    <p style="font-size:12px;color:#6c6254;margin:20px 0 0">Saganta · deine private Suite</p>
  </td></tr></table></body></html>`;
}

async function deliver(to: string, subject: string, html: string, text: string, link: string): Promise<void> {
  if (!enabled) {
    if (allowInsecureMailLog) {
      // Nur lokale Dev: Link auf Konsole, damit der Flow ohne SMTP testbar bleibt.
      console.warn(`[saganta-auth] (SMTP aus, INSECURE-DEV-LOG) ${subject} → ${to}: ${link}`);
      return;
    }
    // Prod fail-closed: kein Token im Log, kein Fake-Erfolg. Der Auth-Request scheitert
    // sichtbar, statt einen unverifizierbaren Account/Reset still zu quittieren.
    console.error(`[saganta-auth] SMTP nicht konfiguriert (SMTP_HOST leer): Mail "${subject}" an ${to} NICHT versendet (Token nicht geloggt).`);
    throw new Error('mail delivery unavailable: SMTP not configured');
  }
  try {
    await getTransport().sendMail({ from: MAIL_FROM, to, subject, text, html });
    console.log(`[saganta-auth] Mail versendet: ${subject} → ${to}`);
  } catch (err) {
    // Versand-Fehler nicht verschlucken, aber auch den Auth-Request nicht
    // crashen: Link zusätzlich loggen, damit der Flow nicht komplett blockiert.
    console.error(`[saganta-auth] Mailversand fehlgeschlagen (${subject} → ${to})`, err);
    console.error(`[saganta-auth] Fallback-Link: ${link}`);
  }
}

export async function sendVerificationMail(to: string, name: string | undefined, token: string): Promise<void> {
  const link = verifyLink(token);
  const greet = name ? `Hallo ${name},` : 'Hallo,';
  const html = shell(
    'E-Mail bestätigen',
    `${greet} bitte bestätige deine E-Mail-Adresse, um deinen Saganta-Zugang zu aktivieren. Der Link ist 1 Stunde gültig.`,
    'E-Mail bestätigen',
    link,
    'Du hast kein Konto angelegt? Dann ignoriere diese Nachricht einfach.',
  );
  const text = `${greet}\n\nBestätige deine E-Mail-Adresse für Saganta (Link 1 Stunde gültig):\n${link}\n\nKein Konto angelegt? Diese Nachricht einfach ignorieren.`;
  await deliver(to, 'Bestätige deine Saganta-E-Mail', html, text, link);
}

export async function sendResetMail(to: string, name: string | undefined, token: string): Promise<void> {
  const link = resetLink(token);
  const greet = name ? `Hallo ${name},` : 'Hallo,';
  const html = shell(
    'Passwort zurücksetzen',
    `${greet} für dein Saganta-Konto wurde ein neues Passwort angefordert. Der Link ist 1 Stunde gültig.`,
    'Neues Passwort setzen',
    link,
    'Du hast das nicht angefordert? Dann ist nichts passiert: ignoriere diese Nachricht.',
  );
  const text = `${greet}\n\nSetze dein Saganta-Passwort neu (Link 1 Stunde gültig):\n${link}\n\nNicht angefordert? Diese Nachricht einfach ignorieren.`;
  await deliver(to, 'Saganta-Passwort zurücksetzen', html, text, link);
}

export const emailEnabled = enabled;
