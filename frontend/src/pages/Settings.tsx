import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

type SettingsMap = Record<string, string>;

interface SyncStatus {
  running: boolean;
  last_sync: string | null;
  emails_synced: number;
  threads_synced: number;
  error: string | null;
}

interface Toast {
  id: number;
  kind: 'success' | 'error';
  message: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function toBoolean(value: string): boolean {
  return value === 'true';
}

function formatSyncTime(isoString: string | null): string {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">{title}</h2>
      {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
    </div>
  );
}

function FieldRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
      <div className="flex-1 min-w-0 pr-6">
        <div className="text-sm text-gray-200">{label}</div>
        {description && <div className="text-xs text-gray-500 mt-0.5">{description}</div>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 ${
        checked ? 'bg-blue-600' : 'bg-gray-700'
      }`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  );
}

function ToastList({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null;
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-6 right-6 z-50 flex flex-col gap-2"
    >
      {toasts.map(t => (
        <div
          key={t.id}
          className={`flex items-center gap-3 px-4 py-3 rounded-lg border text-sm shadow-lg ${
            t.kind === 'success'
              ? 'bg-gray-900 border-green-700 text-green-300'
              : 'bg-gray-900 border-red-700 text-red-300'
          }`}
        >
          <span>{t.kind === 'success' ? '✓' : '✕'}</span>
          <span>{t.message}</span>
          <button
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss notification"
            className="ml-2 text-gray-500 hover:text-gray-300 transition-colors"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

const DEFAULTS: SettingsMap = {
  reply_style: 'professional',
  default_follow_up_days: '3',
  commitment_threshold: '500',
  notification_new_email: 'true',
  notification_goal_met: 'true',
  notification_security_alert: 'true',
  notification_draft_ready: 'true',
  notification_stale_thread: 'true',
};

const REPLY_STYLE_OPTIONS = ['professional', 'casual', 'formal', 'custom'] as const;
type ReplyStyleOption = (typeof REPLY_STYLE_OPTIONS)[number];

export default function Settings() {
  const [settings, setSettings] = useState<SettingsMap>({ ...DEFAULTS });
  const [customReplyStyle, setCustomReplyStyle] = useState('');
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastCounter = useRef(0);

  // ── Toast helpers ──────────────────────────────────────────────────────────

  function addToast(kind: Toast['kind'], message: string) {
    const id = ++toastCounter.current;
    setToasts(prev => [...prev, { id, kind, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4000);
  }

  function dismissToast(id: number) {
    setToasts(prev => prev.filter(t => t.id !== id));
  }

  // ── Load ───────────────────────────────────────────────────────────────────

  useEffect(() => {
    Promise.all([
      api.get<SettingsMap>('/settings'),
      api.get<SyncStatus>('/sync/status'),
    ])
      .then(([fetchedSettings, syncData]) => {
        const merged = { ...DEFAULTS, ...fetchedSettings };
        // If reply_style is not one of the known options, treat it as custom
        const knownStyles: string[] = [...REPLY_STYLE_OPTIONS].filter(s => s !== 'custom');
        if (!knownStyles.includes(merged.reply_style)) {
          setCustomReplyStyle(merged.reply_style);
          merged.reply_style = 'custom';
        }
        setSettings(merged);
        setSyncStatus(syncData);
      })
      .catch(() => addToast('error', 'Failed to load settings'))
      .finally(() => setLoading(false));
  }, []);

  // ── Setters ────────────────────────────────────────────────────────────────

  function set(key: string, value: string) {
    setSettings(prev => ({ ...prev, [key]: value }));
  }

  function setNotification(key: string, value: boolean) {
    set(key, String(value));
  }

  // ── Save ───────────────────────────────────────────────────────────────────

  async function handleSave() {
    setSaving(true);
    try {
      const payload = { ...settings };

      // Resolve custom reply style to its actual string value
      if (payload.reply_style === 'custom') {
        const trimmed = customReplyStyle.trim();
        if (!trimmed) {
          addToast('error', 'Custom reply style cannot be empty');
          setSaving(false);
          return;
        }
        payload.reply_style = trimmed;
      }

      // Validate numeric fields
      const followUpDays = parseInt(payload.default_follow_up_days, 10);
      if (isNaN(followUpDays) || followUpDays < 1 || followUpDays > 90) {
        addToast('error', 'Follow-up days must be between 1 and 90');
        setSaving(false);
        return;
      }

      const threshold = parseInt(payload.commitment_threshold, 10);
      if (isNaN(threshold) || threshold < 0 || threshold > 1000) {
        addToast('error', 'Commitment threshold must be between 0 and 1000');
        setSaving(false);
        return;
      }

      await api.put('/settings/bulk', { settings: payload });
      addToast('success', 'Settings saved');
    } catch {
      addToast('error', 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  // ── Force sync ─────────────────────────────────────────────────────────────

  async function handleForceSync() {
    setSyncing(true);
    try {
      await api.post('/sync/trigger');
      addToast('success', 'Sync triggered — this may take a moment');
      // Refresh sync status after a brief delay
      setTimeout(async () => {
        try {
          const updated = await api.get<SyncStatus>('/sync/status');
          setSyncStatus(updated);
        } catch {
          // Non-critical, ignore
        }
      }, 3000);
    } catch {
      addToast('error', 'Failed to trigger sync');
    } finally {
      setSyncing(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading settings...
      </div>
    );
  }

  const replyStyleValue = settings.reply_style as ReplyStyleOption;

  const notificationKeys: { key: string; label: string; description: string }[] = [
    { key: 'notification_new_email', label: 'New email', description: 'Notify when new email arrives' },
    { key: 'notification_goal_met', label: 'Goal met', description: 'Notify when a thread goal is achieved' },
    { key: 'notification_security_alert', label: 'Security alert', description: 'Notify on injection or anomaly detection' },
    { key: 'notification_draft_ready', label: 'Draft ready', description: 'Notify when a reply draft is generated' },
    { key: 'notification_stale_thread', label: 'Stale thread', description: 'Notify on follow-up reminders' },
  ];

  return (
    <div className="space-y-8 max-w-2xl">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Settings</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* ── Reply Style ─────────────────────────────────────────────────── */}
      <section aria-labelledby="section-reply-style">
        <SectionHeader
          title="Reply Style"
          description="Controls the default tone used when the agent composes replies"
        />
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 divide-y divide-gray-800">
          <FieldRow label="Default tone" description="Applied to all outgoing replies unless overridden per thread">
            <select
              id="reply_style"
              value={replyStyleValue}
              onChange={e => set('reply_style', e.target.value)}
              className="bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              {REPLY_STYLE_OPTIONS.map(opt => (
                <option key={opt} value={opt}>
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </option>
              ))}
            </select>
          </FieldRow>

          {replyStyleValue === 'custom' && (
            <FieldRow label="Custom style instructions" description="Describe the tone and style for the agent to follow">
              <input
                type="text"
                value={customReplyStyle}
                onChange={e => setCustomReplyStyle(e.target.value)}
                placeholder="e.g. concise and direct with bullet points"
                className="bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-1.5 w-64 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 placeholder-gray-600"
              />
            </FieldRow>
          )}
        </div>
      </section>

      {/* ── Follow-up Settings ───────────────────────────────────────────── */}
      <section aria-labelledby="section-followup">
        <SectionHeader
          title="Follow-up Settings"
          description="Controls when the agent flags threads that have gone quiet"
        />
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 divide-y divide-gray-800">
          <FieldRow
            label="Default follow-up days"
            description="Number of days of inactivity before a thread is flagged for follow-up (1–90)"
          >
            <input
              type="number"
              min={1}
              max={90}
              value={settings.default_follow_up_days}
              onChange={e => set('default_follow_up_days', e.target.value)}
              className="bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-1.5 w-20 text-right focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              aria-label="Default follow-up days"
            />
          </FieldRow>
        </div>
      </section>

      {/* ── Commitment Threshold ─────────────────────────────────────────── */}
      <section aria-labelledby="section-commitment">
        <SectionHeader
          title="Commitment Threshold"
          description="Minimum risk score that triggers a commitment warning before sending (0–1000)"
        />
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 divide-y divide-gray-800">
          <FieldRow
            label="Threshold score"
            description="Emails with a commitment score above this value require manual review"
          >
            <div className="flex items-center gap-3">
              <input
                type="range"
                min={0}
                max={1000}
                step={10}
                value={settings.commitment_threshold}
                onChange={e => set('commitment_threshold', e.target.value)}
                className="w-32 accent-blue-500"
                aria-label="Commitment threshold slider"
              />
              <input
                type="number"
                min={0}
                max={1000}
                value={settings.commitment_threshold}
                onChange={e => set('commitment_threshold', e.target.value)}
                className="bg-gray-800 border border-gray-700 text-gray-100 text-sm rounded-md px-3 py-1.5 w-20 text-right focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                aria-label="Commitment threshold value"
              />
            </div>
          </FieldRow>
        </div>
      </section>

      {/* ── Notifications ────────────────────────────────────────────────── */}
      <section aria-labelledby="section-notifications">
        <SectionHeader
          title="Notifications"
          description="Choose which events generate in-app notifications"
        />
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 divide-y divide-gray-800">
          {notificationKeys.map(({ key, label, description }) => (
            <FieldRow key={key} label={label} description={description}>
              <Toggle
                checked={toBoolean(settings[key] ?? 'true')}
                onChange={val => setNotification(key, val)}
                label={`Toggle ${label} notifications`}
              />
            </FieldRow>
          ))}
        </div>
      </section>

      {/* ── Sync Status ──────────────────────────────────────────────────── */}
      <section aria-labelledby="section-sync">
        <SectionHeader
          title="Sync Status"
          description="Gmail synchronization health and manual trigger"
        />
        <div className="bg-gray-900 border border-gray-800 rounded-lg px-4 divide-y divide-gray-800">
          <FieldRow label="Last sync" description="Time of the most recent completed sync">
            <span className="text-sm text-gray-400">
              {syncStatus ? formatSyncTime(syncStatus.last_sync) : '—'}
            </span>
          </FieldRow>

          {syncStatus && (
            <FieldRow label="Emails synced" description="Count from the last sync run">
              <span className="text-sm text-gray-400">{syncStatus.emails_synced.toLocaleString()}</span>
            </FieldRow>
          )}

          {syncStatus?.error && (
            <FieldRow label="Last error" description="Error from the most recent sync attempt">
              <span className="text-sm text-red-400 max-w-xs truncate" title={syncStatus.error}>
                {syncStatus.error}
              </span>
            </FieldRow>
          )}

          <FieldRow
            label="Force sync"
            description={syncStatus?.running ? 'Sync is currently running' : 'Manually trigger a full Gmail sync'}
          >
            <button
              onClick={handleForceSync}
              disabled={syncing || (syncStatus?.running ?? false)}
              className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed text-gray-200 text-sm rounded-md border border-gray-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              {syncing ? 'Triggering...' : syncStatus?.running ? 'Running...' : 'Sync Now'}
            </button>
          </FieldRow>
        </div>
      </section>

      {/* Sticky save bar visible on smaller viewports */}
      <div className="sm:hidden fixed bottom-0 inset-x-0 bg-gray-950 border-t border-gray-800 px-4 py-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      <ToastList toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
