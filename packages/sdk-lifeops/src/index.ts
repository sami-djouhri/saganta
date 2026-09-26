/**
 * Stub-Client für life-ops-api (host:8110). Vom BFF konsumiert.
 * Wichtig: Der KI-Endpoint /api/calendar/suggest-slots wird in life-ops-api
 * neu angelegt (siehe Plan §4), der Stub spiegelt das Soll-Interface.
 */

export interface SlotSuggestion {
  start: string;
  end: string;
  score: number;
  reason: string;
  // Nur diese beiden Werte setzt life-ops-api (routes_calendar.py: entweder
  // 'host-small' oder 'deterministic'). Hier stand bis 2026-08-29 zusaetzlich
  // 'node2-qwen14b' als dritte Moeglichkeit. Der Server hat sie nie gesendet,
  // und ein 14B liegt auf node2 auch nicht mehr.
  source: 'host-small' | 'deterministic';
}

export interface SuggestSlotsInput {
  horizon_hours: number;
  duration_min: number;
  task_id?: string;
  context?: string;
}

export interface ServiceRisk {
  service: string;
  severity?: 'info' | 'soft' | 'urgent';
  detail?: string;
}

export interface MemoryOpen {
  id: string;
  title: string;
  source?: string;
}

// Das Briefing von life-ops-api fuehrt weiterhin ein Feld `knowledge_gateway`
// (Adapter-Zustand des Homelab-Recalls). Es ist hier bewusst NICHT typisiert:
// Saganta ist eigenstaendig und zeigt keinen Homelab-Betriebszustand. Wer den
// Adapter-Stand sehen will, nimmt Cockpit oder das dev-portal, dort gehoert er
// hin. Das Feld bleibt im Payload, weil Cockpit es liest.
export interface TodayBriefing {
  date: string;
  generated_at?: string;
  open_points: { id: string; title: string; severity: 'info' | 'soft' | 'urgent' }[];
  calendar: { id: string; title: string; start: string; end: string }[];
  service_risks?: ServiceRisk[];
  memory_open?: MemoryOpen[];
  weather?: unknown;
}

export interface LifeOpsClientOptions {
  baseUrl: string;
  token: string;
  fetch?: typeof fetch;
}

export class LifeOpsClient {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly fetch: typeof fetch;

  constructor(opts: LifeOpsClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, '');
    this.token = opts.token;
    this.fetch = opts.fetch ?? fetch;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await this.fetch(this.baseUrl + path, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(init.headers ?? {}),
      },
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`LifeOps ${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }

  today(): Promise<TodayBriefing> {
    return this.request('/api/today');
  }

  suggestSlots(input: SuggestSlotsInput): Promise<SlotSuggestion[]> {
    return this.request('/api/calendar/suggest-slots', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  }
}
