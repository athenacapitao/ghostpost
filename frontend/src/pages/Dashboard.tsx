import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Stats, AuditEntry, Thread, ResearchCampaign, PaginatedResponse } from '../api/client';

interface ThreadWithGoal extends Thread {
  goal_status?: string | null;
}

interface DashboardData {
  stats: Stats | null;
  audit: AuditEntry[];
  threads: ThreadWithGoal[];
  pendingDrafts: number;
  quarantined: number;
  researchActive: number;
  researchRecent: ResearchCampaign[];
}

function timeAgo(date: string): string {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function activityLink(entry: AuditEntry): string | null {
  const d = entry.details || {};
  const tid = entry.thread_id || (d.thread_id as number | undefined);

  // Thread-level actions
  if (tid) return `/threads/${tid}`;

  // Research
  if (d.campaign_id) return `/research/${d.campaign_id}`;
  if (d.batch_id) return `/research/batch/${d.batch_id}`;

  // Drafts
  if (entry.action_type.includes('draft')) return '/drafts';

  // Blocklist / security
  if (entry.action_type.startsWith('blocklist_') || entry.action_type.startsWith('quarantine_'))
    return '/settings';

  return null;
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardData>({
    stats: null, audit: [], threads: [], pendingDrafts: 0, quarantined: 0,
    researchActive: 0, researchRecent: [],
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<Stats>('/stats'),
      api.get<AuditEntry[]>('/audit', { limit: 15 }),
      api.get<{ items: ThreadWithGoal[] }>('/threads', { limit: 200 }),
      api.get<any>('/drafts', { status: 'pending' }),
      api.get<any[]>('/security/quarantine'),
      api.get<PaginatedResponse<ResearchCampaign>>('/research/', { page: 1, page_size: 100 }).catch(() => ({ items: [], total: 0, page: 1, page_size: 100, pages: 0 })),
    ]).then(([stats, audit, threadsRes, draftsRes, quarantine, researchRes]) => {
      const researchItems = researchRes.items || [];
      setData({
        stats,
        audit: Array.isArray(audit) ? audit : [],
        threads: threadsRes.items || [],
        pendingDrafts: Array.isArray(draftsRes) ? draftsRes.length : (draftsRes?.items || []).length,
        quarantined: (quarantine || []).length,
        researchActive: researchItems.filter((c: ResearchCampaign) => c.status.startsWith('phase_') || c.status === 'queued').length,
        researchRecent: researchItems.slice(0, 3),
      });
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="flex items-center justify-center py-20 text-gray-500">Loading dashboard...</div>;
  }

  const nonArchived = data.threads.filter(t => t.state !== 'ARCHIVED');
  const achievedGoals = data.threads.filter(t => t.goal_status === 'achieved').length;
  const totalGoals = data.threads.filter(t => t.goal_status).length;
  const goalRate = totalGoals > 0 ? Math.round((achievedGoals / totalGoals) * 100) : 0;
  const needsAttention = nonArchived.filter(t =>
    t.priority === 'high' || t.priority === 'critical' || t.state === 'FOLLOW_UP'
  ).slice(0, 8);

  const cards = [
    { label: 'Active Threads', value: data.stats?.active_threads ?? 0, color: 'text-blue-400' },
    { label: 'Pending Drafts', value: data.pendingDrafts, color: 'text-purple-400' },
    { label: 'Quarantined', value: data.quarantined, color: 'text-red-400' },
    { label: 'Research Active', value: data.researchActive, color: 'text-cyan-400' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {cards.map(card => (
          <div key={card.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400">{card.label}</div>
            <div className={`text-2xl font-bold mt-1 ${card.color}`}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Two Column Layout */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Activity Feed */}
        <div>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Recent Activity</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
            {data.audit.length === 0 ? (
              <div className="p-4 text-sm text-gray-500">No recent activity</div>
            ) : (
              data.audit.map(entry => {
                const href = activityLink(entry);
                const threadId = entry.thread_id || (entry.details?.thread_id as number | undefined);
                const content = (
                  <>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-gray-300">{entry.action_type.replace(/_/g, ' ')}</span>
                      {threadId && (
                        <span className="text-xs text-blue-400 ml-2">#{threadId}</span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500 ml-2 shrink-0">{timeAgo(entry.timestamp)}</span>
                  </>
                );
                return href ? (
                  <Link key={entry.id} to={href} className="px-4 py-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors">
                    {content}
                  </Link>
                ) : (
                  <div key={entry.id} className="px-4 py-3 flex items-center justify-between">
                    {content}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Needs Attention */}
        <div>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Needs Attention</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-lg divide-y divide-gray-800">
            {needsAttention.length === 0 ? (
              <div className="p-4 text-sm text-gray-500">All clear</div>
            ) : (
              needsAttention.map(t => (
                <Link
                  key={t.id}
                  to={`/threads/${t.id}`}
                  className="block px-4 py-3 hover:bg-gray-800/50 transition-colors"
                >
                  <div className="text-sm text-gray-200 truncate">{t.subject || '(no subject)'}</div>
                  <div className="flex gap-2 mt-1">
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">{t.state}</span>
                    {t.priority && (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        t.priority === 'critical' ? 'bg-red-900/50 text-red-300' :
                        t.priority === 'high' ? 'bg-amber-900/50 text-amber-300' :
                        'bg-gray-800 text-gray-400'
                      }`}>{t.priority}</span>
                    )}
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Goal Progress */}
      {totalGoals > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Goal Progress</h2>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-gray-300">{achievedGoals} of {totalGoals} goals achieved</span>
              <span className="text-gray-400">{goalRate}%</span>
            </div>
            <div className="bg-gray-800 rounded-full h-2">
              <div
                className="bg-green-500 rounded-full h-2 transition-all"
                style={{ width: `${goalRate}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Storage */}
      {data.stats && (
        <div className="text-xs text-gray-500 flex gap-4">
          <span>{data.stats.total_emails} emails</span>
          <span>{data.stats.total_contacts} contacts</span>
          <span>{data.stats.total_attachments} attachments</span>
          <span>{data.stats.db_size_mb.toFixed(1)} MB</span>
        </div>
      )}
    </div>
  );
}
