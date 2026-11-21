/**
 * Erfundene Daten fuer die Ansichtsprobe. Keine echten Projekte, Kontakte
 * oder Betraege; Mailadressen nur unter example.invalid.
 *
 * `?ansicht=liste` zeigt die Gliederung, sonst die Akte des Oberprojekts
 * „Spiele“; der Reiter kommt aus dem Anker (`#zeitleiste`, `#kontakte` ...).
 */
import { mount } from 'svelte';
import ProjektBaum from '../src/lib/components/ProjektBaum.svelte';
import Seite from '../src/routes/projekte/[slug]/+page.svelte';
import { baum } from '../src/lib/gliederung';
import type { Akte, Project } from '../src/lib/types';
import './probe.css';

const projekt = (id: number, name: string, eltern: number[], kinder: number[], offen = 0, hoch = 0, ueber = 0): Project =>
  ({
    id, owner: 'probe', slug: name.toLowerCase().replace(/[^a-z0-9]+/g, '-'), name, description: null,
    type: 'private', status: 'active', visibility: 'private', target_visibility: null, scheduling_mode: 'none',
    priority: 3, client_id: null, domain: null, repo_url: null, deployment_url: null,
    weekly_time_budget_minutes: 0, minimum_weekly_minutes: null, maximum_weekly_minutes: null,
    next_action: id === 6 ? 'Erste Fassung der Startseite entwerfen' : null, deadline_date: null, deadline_type: null,
    deadline_confidence: null, review_date: null, review_interval_days: null, sunset_date: null,
    public_target_date: null, maintenance_interval_days: null, energy_level_required: null,
    focus_level_required: null, can_auto_schedule: true, score: null, promised_scope: null,
    communication_notes: null, maintenance_mode: null, handover_status: null, last_reviewed_at: null,
    open_tasks: offen, open_high: hoch, overdue_tasks: ueber, done_7d: 0,
    eltern_ids: eltern, kinder_ids: kinder, created_at: '2026-11-01T10:00:00', updated_at: '2026-11-15T10:00:00',
  }) as Project;

const projekte = [
  projekt(1, 'Spiele', [], [2, 3, 7], 2, 1),
  projekt(2, 'Spiele-Dashboard', [1], [8, 9], 4, 1, 1),
  projekt(3, 'Spiele-Bot', [1, 4], [], 3),
  projekt(4, 'Discord-Bots', [], [3, 5], 1),
  projekt(5, 'Kräuter-Bot', [4], [], 6, 2),
  projekt(6, 'Probe-Webseite', [], [], 2),
  projekt(7, 'Spiel-Verwalter', [1], [], 1),
  projekt(8, 'Dashboard Web', [2], [], 2),
  projekt(9, 'Dashboard App', [2], [], 1),
];

const aufgabe = (id: string, titel: string, slug: string, mehr: Record<string, unknown> = {}) => ({
  id, titel, notiz: null, prioritaet: 'mittel', faellig: null, tag: null, start: null, ende: null,
  dauer_min: null, erledigt: false, erledigt_am: null, projekt: slug, wartet: false, wartet_grund: null,
  wartet_bis: null, weitere_projekte: null, notizen: [], ...mehr,
});

const akte = {
  projekt: projekte[0],
  pfad: [],
  eltern: [],
  kinder: [
    { id: 2, slug: 'spiele-dashboard', name: 'Spiele-Dashboard', status: 'active', offen: 7, hoch: 1, ueberfaellig: 1, erledigt_7: 2, naechstes_datum: '2026-11-20', unterprojekte: 2 },
    { id: 3, slug: 'spiele-bot', name: 'Spiele-Bot', status: 'active', offen: 3, hoch: 0, ueberfaellig: 0, erledigt_7: 0, naechstes_datum: '2026-12-01', unterprojekte: 0 },
    { id: 7, slug: 'spiel-verwalter', name: 'Spiel-Verwalter', status: 'active', offen: 1, hoch: 0, ueberfaellig: 0, erledigt_7: 1, naechstes_datum: null, unterprojekte: 0 },
  ],
  projekte: Object.fromEntries(projekte.filter((p) => [1, 2, 3, 7, 8, 9].includes(p.id)).map((p) => [p.slug, { id: p.id, name: p.name }])),
  aufgaben: [
    aufgabe('a1', 'Gemeinsames Farbschema für alle Teile festlegen', 'spiele', { prioritaet: 'hoch' }),
    aufgabe('a2', 'Spielerliste auf dem Handy zweispaltig', 'spiele-dashboard', { faellig: '2026-11-10' }),
    aufgabe('a3', 'Bescheid bei Serverstart testen', 'spiele-bot', {
      weitere_projekte: ['discord-bots'], notizen: [{ id: 11, titel: 'Ablauf beim Start', ausschnitt: '', tags: [] }],
    }),
    aufgabe('a4', 'Neustart-Knopf mit Rückfrage', 'dashboard-web', { tag: '2026-11-18' }),
    aufgabe('a5', 'Warteschlange für Befehle', 'spiele-bot', { wartet: true, wartet_grund: 'erst nach dem Umzug' }),
  ],
  aufgaben_fehlen: false,
  zeitleiste: [
    { art: 'frist', datum: '2026-11-10', uhrzeit: null, ende: null, titel: 'Spielerliste auf dem Handy zweispaltig', projekt: 'spiele-dashboard', ref: 'a2' },
    { art: 'termin', datum: '2026-11-17', uhrzeit: '18:00', ende: '19:30', titel: 'Abend mit Testspielern', projekt: 'spiele', ref: 't1', ort: 'Wohnzimmer' },
    { art: 'geplant', datum: '2026-11-18', uhrzeit: null, ende: null, titel: 'Neustart-Knopf mit Rückfrage', projekt: 'dashboard-web', ref: 'a4' },
    { art: 'meilenstein', datum: '2026-11-20', uhrzeit: null, ende: null, titel: 'Dashboard 2.0 fertig', projekt: 'spiele-dashboard', ref: '1' },
    { art: 'projektfrist', datum: '2026-12-01', uhrzeit: null, ende: null, titel: 'Frist: Spiele-Bot', projekt: 'spiele-bot', ref: null },
  ],
  termine_fehlen: false,
  kontakte: [
    { verweis_id: 1, kontakt_id: 'k1', rolle: 'Testspielerin', projekt: 'spiele', projekt_name: 'Spiele', name: 'Erika Muster', telefon: '0000 000000', email: 'erika@example.invalid', fehlt: false, unbekannt: false },
    { verweis_id: 2, kontakt_id: 'k2', rolle: 'Serverbetreuung', projekt: 'spiele-dashboard', projekt_name: 'Spiele-Dashboard', name: 'Max Beispiel', telefon: null, email: 'max@example.invalid', fehlt: false, unbekannt: false },
  ],
  budget: {
    verfuegbar: true,
    gesamt: { budget_cent: 20000, ausgaben_cent: 17350, einnahmen_cent: 0, rest_cent: 2650, anzahl_buchungen: 4 },
    je: {
      spiele: { projekt: 'spiele', budget_cent: 5000, ausgaben_cent: 2350, einnahmen_cent: 0, rest_cent: 2650, anzahl_buchungen: 2 },
      'spiele-dashboard': { projekt: 'spiele-dashboard', budget_cent: 15000, ausgaben_cent: 15000, einnahmen_cent: 0, rest_cent: 0, anzahl_buchungen: 2 },
    },
    letzte: [
      { datum: '2026-11-12', betrag_cent: -1299, text: 'Server-Miete November', kategorie: 'Technik' },
      { datum: '2026-11-02', betrag_cent: -1051, text: 'Domain', kategorie: 'Technik' },
    ],
  },
  notizen: [{ id: 21, titel: 'Ideen für den Winter', ausschnitt: '', tags: [], projekt: 'spiele-bot' }],
  notizen_fehlen: false,
} as unknown as Akte;

const ziel = document.getElementById('probe')!;
const rahmen = document.createElement('div');
rahmen.className = 'mx-auto w-full max-w-5xl px-4 py-6';
ziel.appendChild(rahmen);

if (new URLSearchParams(location.search).get('ansicht') === 'liste') {
  const nachName = (a: Project, b: Project) => a.name.localeCompare(b.name, 'de');
  mount(ProjektBaum, { target: rahmen, props: { knoten: baum(projekte, nachName) } });
} else {
  mount(Seite, {
    target: rahmen,
    props: {
      data: {
        project: projekte[0], aufgaben: [], aufgabenFehlen: false, assets: [], milestones: [], reviews: [],
        readiness: { project_id: 1, items: {}, completed: 0, total: 0 },
        shutdown: { project_id: 1, items: {}, completed: 0, total: 0 },
        notizen: [], akte, alleProjekte: projekte,
        kontaktAuswahl: [{ id: 'k3', name: 'Lena Probe', gruppe: null }],
      },
      form: null,
    } as never,
  });
}
