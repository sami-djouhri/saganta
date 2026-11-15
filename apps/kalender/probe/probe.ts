/**
 * Ansichtsprobe der Tagesdecke: rendert die Komponente mit echten Decken.
 *
 * Warum es das gibt: die Komponente war typgeprüft (`svelte-check` ohne Fehler)
 * und über die Klartext-Ausgabe des Backends auf der Datenseite abgedeckt, aber
 * nie im Bild zu sehen. Blockhöhen, der Verteilungsbalken und vor allem die
 * Erreichbarkeit der Entfernen-Zone am Handy lassen sich im Quelltext nicht
 * beurteilen.
 *
 * Die Decken kommen aus `kalender/scripts/decke-fixtures.py`, also aus
 * `baue_decke` selbst. Von Hand getippte Beispieldaten zeigen die Verteilung,
 * die man erwartet, und prüfen damit nur das eigene Wunschbild.
 *
 * Aufruf: `pnpm probe` im App-Ordner, dann `?fall=<name>` wählen.
 */
import { mount } from 'svelte';
import Tagesdecke from '../src/lib/Tagesdecke.svelte';
import MonthGrid from '../src/lib/MonthGrid.svelte';
import Gewohnheiten from '../src/lib/Gewohnheiten.svelte';
import fixtures from './decke-fixtures.json';
import './probe.css';

type Fall = keyof typeof fixtures;

const parameter = new URLSearchParams(location.search);
const gewuenscht = parameter.get('fall') as Fall | null;
const fall: Fall =
  gewuenscht && gewuenscht in fixtures ? gewuenscht : ('arbeitstag_fest' as Fall);

const ziel = document.getElementById('probe');
if (!ziel) throw new Error('Kein Einhängepunkt #probe');

// Der Rahmen bildet nach, was das echte Layout um die Komponente legt
// (PageContainer, Abstand, dunkles Thema). Ohne ihn misst man Blockhöhen in
// einer Breite, die es in der App nie gibt.
const rahmen = document.createElement('div');
rahmen.className = 'mx-auto w-full max-w-5xl px-4 py-6';
ziel.appendChild(rahmen);

const kopf = document.createElement('p');
kopf.className = 'mb-3 text-xs text-muted';
kopf.textContent = `Fall: ${fall}`;
rahmen.appendChild(kopf);

const halter = document.createElement('div');
rahmen.appendChild(halter);

// Seit 2026-11-13 zeigt die Probe auf Wunsch auch Monat und Gewohnheiten,
// mit erfundenen Daten (`?komponente=monat|gewohnheiten`). Keine echten Termine
// in einer Probe (Regel: keine Bildschirmfotos mit echten Daten).
const komponente = parameter.get('komponente');
if (komponente === 'monat') {
  kopf.textContent = 'Monat, erfundene Daten';
  const tag = (d: number) => `2026-11-${String(d).padStart(2, '0')}`;
  const typ = (t: string, d: number) => ({
    id: `${t}-${d}`, calendar_id: `daytype-${t}-0000-0000-000000000000`, title: t,
    start: `${tag(d)}T07:00:00`, end: `${tag(d)}T16:00:00`, all_day: false,
  });
  const events = [
    ...[2, 3, 4, 5, 9, 10, 11, 12, 16, 17, 18].map((d) => typ('arbeit', d)),
    ...[19, 20, 26, 27].map((d) => typ('schule', d)),
    { id: 'u', calendar_id: 'daytype-urlaub-0000-0000-000000000000', title: 'Urlaub',
      start: `${tag(23)}T00:00:00`, end: `${tag(25)}T00:00:00`, all_day: true },
    { id: 'f', calendar_id: 'daytype-feiertag-0000-0000-000000000000', title: 'Buß- und Bettag',
      start: `${tag(18)}T00:00:00`, end: `${tag(19)}T00:00:00`, all_day: true },
    { id: 't1', calendar_id: 'system-termine-0000', title: 'Zahnarzt', start: `${tag(10)}T17:30:00`,
      end: `${tag(10)}T18:00:00`, all_day: false },
    { id: 't2', calendar_id: 'system-termine-0000', title: 'Probetermin', start: `${tag(14)}T13:00:00`,
      end: `${tag(14)}T14:00:00`, all_day: false },
  ];
  mount(MonthGrid, {
    target: halter,
    props: { month: '2026-11', today: tag(14), events, calMeta: new Map(), selectedDay: null,
      onSelectDay: () => {}, onSelectEvent: () => {} },
  });
} else if (komponente === 'gewohnheiten') {
  kopf.textContent = 'Gewohnheiten, erfundene Daten';
  mount(Gewohnheiten, {
    target: halter,
    props: {
      fortschritt: [
        { habit_id: 'a', name: 'Lesen', color: '#4a9eff', target_hours: 2, completed_hours: 0.5 },
        { habit_id: 'b', name: 'Sport', color: '#3ec98a', target_hours: 1.5, completed_hours: 1.5 },
      ],
      sitzungen: [],
    },
  });
} else mount(Tagesdecke, {
  target: halter,
  props: {
    decke: fixtures[fall],
    beschaeftigt: false,
    // Die Rückrufe schreiben nur ins Protokoll. Ein echter Aufruf gehört nicht
    // in eine Ansichtsprobe, und ein Fehler darin sähe im Bild wie ein
    // Layoutfehler aus.
    onFestschreiben: () => console.log('festschreiben'),
    onNeuOrdnen: (r: string[]) => console.log('neu ordnen', r),
    onVerwerfen: (id: string) => console.log('verwerfen', id),
    onTagWechsel: (d: string) => console.log('tag wechsel', d),
  },
});
