// Mirrors app/web/schemas.py

export const FILE_STATUSES = [
  "discovered",
  "downloaded",
  "duplicate",
  "processing",
  "classified",
  "unclassified",
  "failed",
  "unsupported",
] as const;
export type FileStatus = (typeof FILE_STATUSES)[number];

export const CONTENT_TYPES = ["lecture", "previous_exam", "assignment", "answer_model", "summary"] as const;
export type ContentType = (typeof CONTENT_TYPES)[number];

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Me {
  username: string;
  csrf_token: string;
}

export interface Channel {
  id: number;
  telegram_id: number | null;
  name: string;
  username: string | null;
  enabled: boolean;
  last_message_id: number;
  last_run_at: string | null;
  status: "active" | "idle" | "error" | "disabled";
  last_error: string | null;
  created_at: string;
  file_count: number;
}

export interface Subject {
  id: number;
  code: string;
  name_ar: string;
  name_en: string;
  keywords: string[];
  counts: Partial<Record<ContentType, number>>;
  total: number;
}

export interface Classification {
  subject_code: string | null;
  content_type: ContentType | null;
  confidence: number | null;
  evidence: string[];
  status: "classified" | "unclassified";
  reason: string | null;
  classifier_version: string;
  updated_at: string;
}

export interface ChannelBrief {
  id: number;
  name: string;
  username: string | null;
}

export interface MessageBrief {
  id: number;
  telegram_message_id: number;
  message_date: string;
  caption: string | null;
  media_type: string;
  channel: ChannelBrief;
}

export interface FileItem {
  id: number;
  original_filename: string;
  extension: string;
  mime_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  status: FileStatus;
  error_message: string | null;
  telegram_document_id: number | null;
  duplicate_of_file_id: number | null;
  created_at: string;
  updated_at: string;
  message: MessageBrief;
  classification: Classification | null;
}

export interface LogEntry {
  id: number;
  stage: string;
  status: "success" | "failed" | "skipped";
  message: string | null;
  error_message: string | null;
  created_at: string;
  run_id: number | null;
  file_id: number | null;
}

export interface FileDetail extends FileItem {
  storage_path: string | null;
  relative_path: string | null;
  exists_on_disk: boolean;
  text_preview: string | null;
  text_length: number;
  telegram_link: string | null;
  message_metadata: Record<string, unknown>;
  logs: LogEntry[];
}

export interface Facets {
  extensions: string[];
  statuses: FileStatus[];
  content_types: ContentType[];
  subjects: string[];
  status_counts: Partial<Record<FileStatus, number>>;
}

export interface MessageItem {
  id: number;
  telegram_message_id: number;
  message_date: string;
  caption: string | null;
  media_type: string;
  file_name: string | null;
  file_size: number | null;
  channel: ChannelBrief;
  file_id: number | null;
  file_status: FileStatus | null;
}

export interface Run {
  id: number;
  kind: "collect" | "process";
  trigger: "cli" | "web" | "launchd";
  status: "running" | "success" | "failed" | "aborted";
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  new_count: number;
  duplicate_count: number;
  classified_count: number;
  unclassified_count: number;
  failed_count: number;
  unsupported_count: number;
  metadata_json: Record<string, unknown>;
}

export interface LogLine {
  seq: number;
  ts: string | null;
  level: string;
  event: string;
  logger: string | null;
  fields: Record<string, unknown>;
}

export interface RunDetail extends Run {
  logs: LogEntry[];
  log_lines: LogLine[];
}

export type JobState = "queued" | "running" | "succeeded" | "failed" | "locked";

export interface Job {
  id: string;
  kind: "collect" | "process" | "reclassify";
  args: string[];
  state: JobState;
  created_at: string;
  finished_at: string | null;
  exit_code: number | null;
  run_id: number | null;
  progress: { current?: number; total?: number | null; channel?: string; file_id?: number };
  counters: Record<string, number>;
  line_count: number;
}

export interface LockHolder {
  pid?: number;
  kind?: string;
  trigger?: string;
  started_at?: string;
}

export interface LockInfo {
  locked: boolean;
  holder: LockHolder | null;
  active_job: Job | null;
}

export interface Kpi {
  key: "total" | "classified" | "unclassified" | "duplicate" | "failed";
  value: number;
  sparkline: number[];
  last_7d: number;
  change_pct: number | null;
}

export interface DailyPoint {
  date: string;
  total: number;
  classified: number;
  unclassified: number;
  duplicate: number;
  failed: number;
  unsupported: number;
}

export interface SubjectRef {
  code: string;
  name_ar: string;
  name_en: string;
}

export interface Overview {
  kpis: Kpi[];
  daily: DailyPoint[];
  by_content_type: { content_type: ContentType; count: number }[];
  by_subject: (SubjectRef & { count: number })[];
  empty_subjects: SubjectRef[];
  recent_files: FileItem[];
  last_run: Run | null;
  pending: number;
}

export interface HealthCheck {
  key: string;
  status: "ok" | "warn" | "fail";
  detail: string;
  data: Record<string, unknown>;
}

export interface SystemStatus {
  db: boolean;
  telegram: boolean;
  telegram_configured: boolean;
  lock: { locked: boolean; holder: LockHolder | null };
  ai_provider: string;
}

export interface SettingRow {
  key: string;
  secret: boolean;
  configured: boolean;
  value: string | null;
}
