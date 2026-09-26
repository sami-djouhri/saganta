// Client-sichere Konstanten (kein $env-Import → auch im Browser-Bundle nutzbar).
export const DEFAULT_LIMIT = 50;

// Harte Obergrenze pro Quelle: briefkasten `/api/internal/letters` lehnt limit>200
// mit 422 ab (Query le=200), mail-api clamped intern auf max_page_size=200.
// Über 200 hinaus gibt es also nichts mehr zu holen → "Mehr laden" endet hier.
export const MAX_LIMIT = 200;
