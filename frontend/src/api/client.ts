const API_BASE = '/api';

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('ghostpost_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['X-API-Key'] = token;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { ...headers, ...options.headers },
    ...options,
  });

  if (response.status === 401) {
    // Redirect to login on auth failure
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Unauthorized');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, body.detail || response.statusText);
  }

  return response.json();
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number>) => {
    const qs = params ? '?' + new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString() : '';
    return request<T>(`${path}${qs}`);
  },

  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'DELETE',
      body: body ? JSON.stringify(body) : undefined,
    }),
};

// Types
export interface Thread {
  id: number;
  gmail_thread_id: string;
  subject: string | null;
  category: string | null;
  state: string;
  priority: string | null;
  summary: string | null;
  email_count: number;
  last_activity_at: string | null;
  created_at: string;
}

export interface Email {
  id: number;
  gmail_id: string;
  thread_id: number;
  from_address: string | null;
  to_addresses: string[] | null;
  cc: string[] | null;
  subject: string | null;
  body_plain: string | null;
  body_html: string | null;
  date: string | null;
  is_read: boolean;
  is_sent: boolean;
  is_draft: boolean;
  attachments: Attachment[];
  created_at: string;
}

export interface Attachment {
  id: number;
  filename: string | null;
  content_type: string | null;
  size: number | null;
}

export interface ThreadDetail {
  id: number;
  gmail_thread_id: string;
  subject: string | null;
  category: string | null;
  summary: string | null;
  state: string;
  priority: string | null;
  auto_reply_mode: string;
  follow_up_days: number;
  next_follow_up_date: string | null;
  playbook: string | null;
  goal: string | null;
  acceptance_criteria: string | null;
  goal_status: string | null;
  notes: string | null;
  security_score_avg: number | null;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string | null;
  emails: Email[];
}

export interface DraftItem {
  id: number;
  thread_id: number | null;
  to_addresses: string[] | null;
  subject: string | null;
  body: string | null;
  status: string;
  created_at: string;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  action_type: string;
  thread_id: number | null;
  actor: string;
  details: Record<string, unknown> | null;
}

export interface SecurityEventItem {
  id: number;
  timestamp: string;
  event_type: string;
  severity: string;
  email_id: number | null;
  thread_id: number | null;
  quarantined: boolean;
  resolution: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Stats {
  total_threads: number;
  active_threads: number;
  archived_threads: number;
  total_emails: number;
  total_contacts: number;
  total_attachments: number;
  unread_emails: number;
  db_size_mb: number;
}

export interface SyncStatus {
  running: boolean;
  last_sync: string | null;
  emails_synced: number;
  threads_synced: number;
  error: string | null;
}

// --- Research ---

export interface ResearchCampaign {
  id: number;
  company_name: string;
  company_slug: string;
  country: string | null;
  industry: string | null;
  identity: string;
  goal: string;
  language: string;
  contact_name: string | null;
  contact_email: string | null;
  contact_role: string | null;
  email_tone: string;
  auto_reply_mode: string;
  status: string;
  phase: number;
  error: string | null;
  email_subject: string | null;
  output_dir: string | null;
  batch_id: number | null;
  thread_id: number | null;
  queue_position: number;
  research_data: {
    phase_started_at?: string;
    current_phase_name?: string;
    completed_phases?: Record<string, { name: string; completed_at: string }>;
    dossier?: { sources_count: number; pages_fetched: number; confidence: string };
    verbose_log?: { ts: string; phase: number; msg: string }[];
  } | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ResearchBatch {
  id: number;
  name: string;
  total_companies: number;
  completed: number;
  failed: number;
  skipped: number;
  status: string;
  created_at: string;
}

export interface ResearchBatchDetail extends ResearchBatch {
  campaigns: ResearchCampaign[];
}

export interface BatchImportCompany {
  company_name: string;
  goal: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_role: string | null;
  industry: string | null;
  country: string | null;
  cc: string | null;
  extra_context: string | null;
}

export interface BatchImportPreview {
  companies: BatchImportCompany[];
  warnings: string[];
  errors: string[];
  column_mapping: Record<string, string>;
  total: number;
}

export interface BatchImportResult {
  batch_id: number;
  status: string;
  total_companies: number;
  warnings: string[];
}

export async function uploadBatchCSV(params: {
  file?: File;
  csvText?: string;
  defaults?: string;
  name?: string;
  dryRun: boolean;
}): Promise<BatchImportPreview | BatchImportResult> {
  const token = localStorage.getItem('ghostpost_token');
  const form = new FormData();
  if (params.file) form.append('file', params.file);
  if (params.csvText) form.append('csv_text', params.csvText);
  if (params.defaults) form.append('defaults', params.defaults);
  if (params.name) form.append('name', params.name);
  form.append('dry_run', String(params.dryRun));

  const headers: Record<string, string> = {};
  if (token) headers['X-API-Key'] = token;

  const resp = await fetch('/api/research/batch/import', {
    method: 'POST',
    credentials: 'include',
    headers,
    body: form,
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
  }
  return resp.json();
}

export interface ResearchIdentity {
  id: string;
  company_name: string;
  sender_name: string;
  sender_email: string;
  industry: string | null;
}
