import { useEffect, useState } from 'react';
import { api, type Stats as StatsType, type SyncStatus } from '../api/client';

export default function Stats() {
  const [stats, setStats] = useState<StatsType | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    api.get<StatsType>('/stats').then(setStats);
    api.get<SyncStatus>('/sync/status').then(setSyncStatus);
  }, []);

  const triggerSync = async () => {
    setSyncing(true);
    try {
      await api.post('/sync');
      // Poll status
      const poll = setInterval(async () => {
        const s = await api.get<SyncStatus>('/sync/status');
        setSyncStatus(s);
        if (!s.running) {
          clearInterval(poll);
          setSyncing(false);
          api.get<StatsType>('/stats').then(setStats);
        }
      }, 2000);
    } catch {
      setSyncing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-100">Dashboard</h1>
        <button
          onClick={triggerSync}
          disabled={syncing}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white text-sm font-medium transition-colors"
        >
          {syncing ? 'Syncing...' : 'Sync Now'}
        </button>
      </div>

      {/* Stats grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <StatCard label="Threads" value={stats.total_threads} />
          <StatCard label="Emails" value={stats.total_emails} />
          <StatCard label="Contacts" value={stats.total_contacts} />
          <StatCard label="Attachments" value={stats.total_attachments} />
          <StatCard label="Unread" value={stats.unread_emails} highlight />
          <StatCard label="DB Size" value={`${stats.db_size_mb} MB`} />
        </div>
      )}

      {/* Sync status */}
      {syncStatus && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Sync Status
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Status</span>
              <p className={syncStatus.running ? 'text-yellow-400' : 'text-green-400'}>
                {syncStatus.running ? 'Running' : 'Idle'}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Last Sync</span>
              <p className="text-gray-300">
                {syncStatus.last_sync
                  ? new Date(syncStatus.last_sync).toLocaleString()
                  : 'Never'}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Emails Synced</span>
              <p className="text-gray-300">{syncStatus.emails_synced}</p>
            </div>
            <div>
              <span className="text-gray-500">Threads Synced</span>
              <p className="text-gray-300">{syncStatus.threads_synced}</p>
            </div>
          </div>
          {syncStatus.error && (
            <div className="mt-3 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {syncStatus.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight,
}: {
  label: string;
  value: number | string;
  highlight?: boolean;
}) {
  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${highlight ? 'text-blue-400' : 'text-gray-100'}`}>
        {value}
      </div>
    </div>
  );
}
