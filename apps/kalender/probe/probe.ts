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

mount(Tagesdecke, {
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
