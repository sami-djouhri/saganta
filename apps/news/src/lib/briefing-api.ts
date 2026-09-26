import type { SagantaUser } from '@saganta/auth';
import { backendSecret, newsApiFetch, newsApiToken } from './news-api';

export interface Interest {
  tag: string;
  weight: number;
}
export interface InterestOption {
  tag: string;
  label: string;
}
export interface BriefingProfile {
  enabled: boolean;
  interests: Interest[];
  free_topics: string[];
  feed_optout: string[];
  length: string;
  audio_enabled: boolean;
  voice: string;
  delivery_time: string;
  weather_lat: number | null;
  weather_lon: number | null;
  weather_place: string | null;
}
/** Tagesvorhersage aus Open-Meteo; null, wenn der Abruf scheiterte (Soft-Fail). */
export interface BriefingWeather {
  place: string;
  code: number | null;
  text: string;
  temp_min: number | null;
  temp_max: number | null;
  precipitation_mm: number | null;
  precipitation_probability: number | null;
  sunrise: string | null;
  sunset: string | null;
}
export interface BriefingItem {
  /** FeedItem-ID, der Griff, mit dem derselbe Artikel im News-Feed angefasst
   *  wird (gemerkt/gelesen). Ältere Briefings aus der Aufbewahrung haben sie
   *  noch nicht, deshalb optional. */
  id?: number;
  title: string;
  link: string;
  source: string;
  source_slug: string;
  summary: string;
  published_at: string | null;
  tags: string[];
  /** Zustand aus dem News-Feed (`UserItemState`), nicht aus dem Briefing. */
  read?: boolean;
  bookmarked?: boolean;
}
export interface BriefingSection {
  tag: string;
  label: string;
  items: BriefingItem[];
}
/** Ein Termin aus dem Kalender (naive Zeiten = Berlin-Wanduhr). */
export interface BriefingEvent {
  title?: string;
  start?: string;
  end?: string;
  all_day?: boolean;
}
/** Geplanter Lern-/Habit-Block aus dem Kalender. */
export interface BriefingSession {
  title?: string;
  category?: string;
  start?: string;
  end?: string;
}
/** „Dein Tag", der Kalender-Teil des Briefings. Null, wenn der Kalender nichts
 *  hergab (Soft-Fail: das Briefing bleibt gültig). */
export interface BriefingDay {
  day_type: string | null;
  events: BriefingEvent[];
  goals: { title?: string }[];
  sessions: BriefingSession[];
  tomorrow: { date: string; day_type: string | null; events: BriefingEvent[] } | null;
}
export interface BriefingContent {
  date: string;
  generated_at: string;
  day?: BriefingDay | null;
  top_story: BriefingItem | null;
  top_items: BriefingItem[];
  sections: BriefingSection[];
  item_count: number;
  spoken_text: string;
  weather?: BriefingWeather | null;
}
/** Ein Eintrag der Archiv-Liste (GET /history). */
export interface BriefingSummary {
  date: string;
  item_count: number;
  has_audio: boolean;
  top_title: string | null;
}
export interface BriefingToday {
  date: string;
  content: BriefingContent;
  has_audio: boolean;
  audio_mime: string | null;
}
export interface DeliveryConfig {
  feed_url: string | null;
  /** Abruf-Adresse fuer eine Heim-Automation (Home Assistant, Skript). */
  json_url: string | null;
  webhook_url: string | null;
  webhook_configured: boolean;
}
export interface PlanInfo {
  plan: string;
  features: Record<string, unknown>;
  pro_benefits: string[];
  is_pro: boolean;
  stripe_enabled?: boolean;
  plan_status?: string | null;
}

/** Ruft die news-api unter /api/news/briefing im Namen des Users auf (60s-Token). */
export function briefingFetch<T>(
  baseUrl: string,
  path: string,
  user: SagantaUser,
  fetcher: typeof fetch,
  init: RequestInit = {},
): Promise<T> {
  const token = newsApiToken(user, backendSecret());
  return newsApiFetch<T>(baseUrl, `/api/news/briefing${path}`, token, fetcher, init);
}
