/**
 * Ist eine Kurz-Basis vom Browser aus ueberhaupt erreichbar?
 *
 * Diese Frage gehoert in den Browser und nirgendwo sonst hin. Der Server kann
 * sie nicht beantworten (andere Namenswelt, siehe `meta.ts`), und ein Waechter
 * beantwortet sie fuer den Bestand, aber nicht fuer den Moment, in dem jemand
 * einen Link weitergibt. Bei einer verschluesselten Freigabe mit Schluessel im
 * Fragment zaehlt genau dieser Moment: die angezeigte Adresse ist der einzige
 * Ort, an dem der Schluessel existiert. Zeigt sie auf einen Namen, den niemand
 * oeffnen kann, und faellt der Dialog zu, ist der Inhalt endgueltig verloren,
 * mit einer Erfolgsmeldung davor.
 */

/** Antwortet die Basis? Jede HTTP-Antwort zaehlt, auch 404. */
export async function basisErreichbar(
  basis: string,
  eigenerUrsprung: string,
  holen: typeof fetch = fetch,
  frist_ms = 2500,
): Promise<boolean> {
  // Der eigene Ursprung braucht keine Probe: waere er nicht erreichbar, haette
  // der Nutzer diese Seite nicht vor sich. Das spart im Normalfall jede
  // Verzoegerung, denn ohne eigene Kurz-Domaene ist genau das der Fall.
  try {
    if (new URL(basis).origin === new URL(eigenerUrsprung).origin) return true;
  } catch {
    return false;
  }

  try {
    // `no-cors`, weil eine fremde Kurz-Domaene keine CORS-Kopfzeilen fuer diese
    // App setzen muss und auch nicht sollte. Die Antwort ist dann undurchsichtig
    // und ihr Status unlesbar, aber mehr braucht es nicht: unterschieden wird
    // "etwas hat geantwortet" von "der Name loest nicht auf". Ein 404 ist eine
    // Antwort und damit ein Beweis, dass der Name traegt.
    await holen(basis, {
      method: 'GET',
      mode: 'no-cors',
      cache: 'no-store',
      redirect: 'follow',
      signal: AbortSignal.timeout(frist_ms),
    });
    return true;
  } catch {
    return false;
  }
}
