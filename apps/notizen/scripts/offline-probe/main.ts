import { mount } from 'svelte';
import './probe.css';
import Probe from './Probe.svelte';

// Erfundene Titel fuer die [[-Vorschlaege; kein Netz, kein Dienst.
const TITEL = ['Gartenplan 2027', 'Garten: Hochbeet', 'Gartenschlauch kaufen', 'Ärger mit dem Gartentor'];
window.fetch = (async (eingabe: RequestInfo | URL) => {
  const url = new URL(String(eingabe), location.href);
  const q = (url.searchParams.get('q') ?? '').toLocaleLowerCase('de-DE');
  const daten = TITEL.filter((t) => t.toLocaleLowerCase('de-DE').includes(q)).map((titel, i) => ({ id: i + 1, titel, archiviert: i === 2 }));
  return new Response(JSON.stringify(daten), { headers: { 'content-type': 'application/json' } });
}) as typeof fetch;

mount(Probe, { target: document.getElementById('app')! });
