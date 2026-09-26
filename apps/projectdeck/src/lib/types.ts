export interface Project {
  id: number;
  owner: string;
  slug: string;
  name: string;
  description: string | null;
  type: string;
  status: string;
  visibility: string;
  target_visibility: string | null;
  scheduling_mode: string;
  priority: number;
  client_id: string | null;
  domain: string | null;
  repo_url: string | null;
  deployment_url: string | null;
  weekly_time_budget_minutes: number;
  minimum_weekly_minutes: number | null;
  maximum_weekly_minutes: number | null;
  next_action: string | null;
  deadline_date: string | null;
  deadline_type: string | null;
  deadline_confidence: number | null;
  review_date: string | null;
  review_interval_days: number | null;
  sunset_date: string | null;
  public_target_date: string | null;
  maintenance_interval_days: number | null;
  energy_level_required: string | null;
  focus_level_required: string | null;
  can_auto_schedule: boolean;
  score: number | null;
  promised_scope: string | null;
  communication_notes: string | null;
  maintenance_mode: string | null;
  handover_status: string | null;
  last_reviewed_at: string | null;
  /** Nicht erledigte Aufgaben; die Listenroute zaehlt sie in einer Abfrage. */
  open_tasks?: number;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: number;
  project_id: number;
  title: string;
  description: string | null;
  status: string;
  priority: number;
  estimated_minutes: number | null;
  remaining_minutes: number | null;
  deadline: string | null;
  can_schedule: boolean;
  can_split: boolean;
  min_block_minutes: number | null;
  max_block_minutes: number | null;
  scheduled_event_id: string | null;
  completed_at: string | null;
}

export interface Asset {
  id: number;
  project_id: number;
  type: string;
  label: string;
  value: string;
  url: string | null;
  visibility: string;
}

export interface Milestone {
  id: number;
  project_id: number;
  title: string;
  description: string | null;
  target_date: string | null;
  status: string;
}

export interface Review {
  id: number;
  project_id: number;
  review_date: string;
  decision: string;
  notes: string | null;
  next_action: string | null;
  new_status: string | null;
  new_priority: number | null;
  new_weekly_budget_minutes: number | null;
  created_at: string;
}

export interface ReadinessItem {
  done: boolean;
  note: string | null;
}
export interface Readiness {
  project_id: number;
  items: Record<string, ReadinessItem>;
  completed: number;
  total: number;
}

export interface DeadlineRisk {
  project_id: number;
  slug: string;
  name: string;
  deadline_date: string | null;
  deadline_type: string | null;
  days_until_deadline: number | null;
  total_remaining_minutes: number;
  available_scheduling_minutes: number | null;
  deadline_pressure: number | null;
  risk_level: string;
  has_schedulable_tasks: boolean;
}

export interface Finding {
  rule_id: string;
  severity: string;
  project_id: number;
  slug: string;
  name: string;
  message: string;
  bucket: string;
}

export interface TimeBlock {
  id: number;
  project_id: number;
  task_id: number | null;
  calendar_event_id: string | null;
  planned_start: string | null;
  planned_end: string | null;
  actual_minutes: number | null;
  status: string;
}

export interface Dashboard {
  week_iso: string;
  total_projects: number;
  live_projects: number;
  counts: Record<string, number>;
  tiles: Record<string, Project[]>;
  findings: Finding[];
}

export interface WeeklyFocus {
  id: number;
  owner: string;
  week_iso: string;
  project_ids: number[];
  maintenance_project_ids: number[];
}

export interface AISuggest {
  kind: string;
  source: string;
  summary: string;
  reasoning: string[];
  data: Record<string, unknown>;
}
