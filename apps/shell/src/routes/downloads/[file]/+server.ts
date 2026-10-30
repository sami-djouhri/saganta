import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { Readable } from 'node:stream';
import { join, basename } from 'node:path';
import type { RequestHandler } from './$types';

// Öffentlicher Auslieferungs-Endpunkt für native Apps (Auto-Updater):
//   GET /downloads/<app>.json                      → Versions-Manifest (Updater-Check)
//   GET /downloads/saganta-<app>.apk               → signierte APK (In-Place-Install)
//   GET /downloads/saganta-<app>-linux.pkg.tar.zst → Linux-Programm für pacman
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

// ⚠️ Die Endung wird als ganzes Suffix geprüft, nicht über das letzte `.`:
// ein pacman-Paket heißt `….pkg.tar.zst`, und ein Vergleich auf `.zst` allein
// würde jede andere zstd-Datei im Verzeichnis mit ausliefern.
//
// Die vier unteren Einträge kamen am 2026-10-25 mit dem pacman-Repo dazu:
// `pacman` holt zuerst `saganta.db` (die Paketliste), dann zu jedem Paket
// dessen `.sig`. Fehlt eines der Suffixe hier, antwortet der Endpunkt mit 404,
// und pacman meldet „failed retrieving file" -- was wie ein Netzproblem
// aussieht und keines ist.
const CONTENT_TYPES: Record<string, string> = {
  '.apk': 'application/vnd.android.package-archive',
  '.json': 'application/json; charset=utf-8',
  '.pkg.tar.zst': 'application/zstd',
  '.pkg.tar.zst.sig': 'application/pgp-signature',
  '.db': 'application/gzip',
  '.db.sig': 'application/pgp-signature',
  '.files': 'application/gzip',
  '.files.sig': 'application/pgp-signature',
  // Der öffentliche Signaturschlüssel. Er liegt bewusst neben den Paketen:
  // ein Schlüssel, den man sich anderswoher holen muss, ist der Schritt, an
  // dem eine Einbauanleitung abbricht.
  '.pub': 'application/pgp-keys',
};

/**
 * Erlaubtes Suffix dieses Namens, oder `undefined`.
 *
 * ⚠️ Es gibt Namen, auf die ZWEI Suffixe passen:
 * `saganta-notizen-app-….pkg.tar.zst.sig` endet auf `.pkg.tar.zst.sig` und auf
 * `.pkg.tar.zst`. Deshalb gewinnt hier der **längste** Treffer und nicht der
 * erste. Mit `find` entschiede die Reihenfolge der Schlüssel im Objekt
 * darüber, ob eine Signatur als zstd-Paket ausgeliefert wird -- eine
 * Eigenschaft, die beim nächsten Umsortieren unbemerkt kippt. So kann sie
 * nicht kippen.
 */
function suffixVon(name: string): string | undefined {
  return Object.keys(CONTENT_TYPES)
    .filter((s) => name.endsWith(s))
    .sort((a, b) => b.length - a.length)[0];
}

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
  const ext = suffixVon(name);
  const contentType = ext ? CONTENT_TYPES[ext] : undefined;
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
  if (ext !== '.json') {
    // Jedes Binärartefakt wird heruntergeladen, nicht angezeigt (APK, pacman-Paket).
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
