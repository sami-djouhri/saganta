import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { Readable } from 'node:stream';
import { join, basename } from 'node:path';
import type { RequestHandler } from './$types';

// Öffentlicher Auslieferungs-Endpunkt für native Apps (Auto-Updater):
//   GET /downloads/<app>.json           → Versions-Manifest (Updater-Check)
//   GET /downloads/saganta-<app>.apk    → signierte APK (In-Place-Install)
//
// Bewusst dynamisch (kein static/), damit ein neues Release NUR die Dateien ins
// gemountete Volume legt (release.sh), ohne shell-Rebuild. Der Pfad ist in
// hooks.server.ts publicPaths freigeschaltet (Updater hat keine Session).
//
// Sicherheit: nur Basename (kein Path-Traversal), nur .apk/.json, nur aus dem
// Downloads-Verzeichnis. Die APK ist kein Geheimnis (installierbares App-Binary).
//
// WICHTIG: Die APK wird als Stream ausgeliefert (nicht als Buffer im Response-Body).
// `new Response(nodeBuffer)` interpretiert die Bytes sonst als Text → mangelt binäre
// Sequenzen → der sha256-Check des Updaters schlägt fehl. Der Stream ist binärsicher.

const DOWNLOADS_DIR = env.DOWNLOADS_DIR || '/app/downloads';

const CONTENT_TYPES: Record<string, string> = {
  '.apk': 'application/vnd.android.package-archive',
  '.json': 'application/json; charset=utf-8',
};

/**
 * Erlaubte Herkuenfte fuer den Cross-Origin-Abruf des Manifests.
 *
 * Der Android-Hinweis in `@saganta/ui` laeuft in den Sub-Apps (kalender.saganta.de,
 * projectdeck.saganta.de) und fragt von dort das Manifest hier ab. Ohne diesen Header
 * blockt der Browser die Antwort und der Hinweis bliebe stumm aus, ohne Fehlermeldung.
 * Die APK braucht das nicht: die holt ein normaler Navigations-Link.
 *
 * Bewusst eine Allowlist statt `*`: das Manifest ist zwar oeffentlich, aber es nennt
 * Pruefsummen und Versionsstaende, die nirgends sonst gebraucht werden.
 */
const ORIGIN_ERLAUBT = /^https:\/\/([a-z0-9-]+\.)?saganta\.(de|home)$/;

export const GET: RequestHandler = async ({ params, request }) => {
  const name = basename(params.file ?? ''); // Path-Traversal neutralisieren
  const ext = name.slice(name.lastIndexOf('.'));
  const contentType = CONTENT_TYPES[ext];
  if (!contentType || name !== params.file) {
    throw error(404, 'Nicht gefunden');
  }

  const full = join(DOWNLOADS_DIR, name);
  let size: number;
  try {
    const s = await stat(full);
    if (!s.isFile()) throw new Error('not a file');
    size = s.size;
  } catch {
    throw error(404, 'Nicht gefunden');
  }

  const headers: Record<string, string> = {
    'content-type': contentType,
    'content-length': String(size),
    // Beides immer frisch. Die APK durfte bis 2026-08-22 einen Tag lang gecacht werden:
    // bei gleichbleibendem Dateinamen lieferte Cloudflare nach einem Release aber bis zu
    // 24 h die ALTE Datei aus, waehrend das Manifest schon die neue Pruefsumme nannte.
    // Der Updater lud dann die alte APK, die sha256 passte nicht, das Update brach ab,
    // ohne sichtbaren Fehler ausser „geht nicht". Nachgewiesen an projectdeck 0.5.0.
    // Der Ursprungsabruf kostet hier nichts: ~2 MB, eine Handvoll Geraete.
    'cache-control': 'no-cache',
  };
  if (ext === '.apk') {
    headers['content-disposition'] = `attachment; filename="${name}"`;
  } else {
    const origin = request.headers.get('origin');
    if (origin && ORIGIN_ERLAUBT.test(origin)) {
      headers['access-control-allow-origin'] = origin;
      // Ohne Vary wuerde ein Cache die Antwort fuer eine Herkunft an eine andere
      // ausliefern, die gar nicht auf der Liste steht.
      headers['vary'] = 'Origin';
    }
  }

  // Binärsicherer Stream (kein Buffer-als-Body-Mangling).
  const webStream = Readable.toWeb(createReadStream(full)) as unknown as ReadableStream;
  return new Response(webStream, { headers });
};
