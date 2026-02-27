import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ResearchCampaign } from '../api/client';
import ResearchStatusBadge from '../components/ResearchStatusBadge';
import PhaseTimeline, { PHASES } from '../components/PhaseTimeline';
import MarkdownViewer from '../components/MarkdownViewer';

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const justStarted = (location.state as { justStarted?: boolean } | null)?.justStarted;
  const [campaign, setCampaign] = useState<ResearchCampaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedPhase, setSelectedPhase] = useState<number | null>(null);
  const [phaseContent, setPhaseContent] = useState('');
  const [contentLoading, setContentLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const pollingRef = useRef(false);
  const selectedPhaseRef = useRef<number | null>(null);
  const userSelectedRef = useRef(false);

  const isTerminal = (status: string) =>
    ['sent', 'draft_pending', 'failed', 'skipped', 'cancelled'].includes(status);

  // Fetch campaign
  const fetchCampaign = async () => {
    if (pollingRef.current) return;
    pollingRef.current = true;
    try {
      const data = await api.get<ResearchCampaign>(`/research/${id}`);
      setCampaign(data);
      setLoading(false);

      // Auto-select latest completed phase (only if user hasn't manually selected)
      if (!userSelectedRef.current) {
        const latestCompleted = data.status.startsWith('phase_')
          ? data.phase - 1
          : ['sent', 'draft_pending'].includes(data.status)
            ? 6
            : data.status === 'failed'
              ? data.phase - 1
              : 0;
        if (latestCompleted > 0 && latestCompleted !== selectedPhaseRef.current) {
          selectedPhaseRef.current = latestCompleted;
          loadPhaseContent(latestCompleted, PHASES[latestCompleted - 1].file);
          setSelectedPhase(latestCompleted);
        }
      }
    } catch {
      setLoading(false);
    } finally {
      pollingRef.current = false;
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchCampaign();
  }, [id]);

  // Poll while campaign is active — 3s for running, 5s for queued
  useEffect(() => {
    if (!campaign || isTerminal(campaign.status)) return;
    const pollMs = campaign.status.startsWith('phase_') ? 3000 : 5000;
    const interval = setInterval(fetchCampaign, pollMs);
    return () => clearInterval(interval);
  }, [campaign?.status, id]);

  const loadPhaseContent = async (phase: number, filename: string, isUserClick = false) => {
    if (isUserClick) userSelectedRef.current = true;
    selectedPhaseRef.current = phase;
    setSelectedPhase(phase);
    setContentLoading(true);
    try {
      const data = await api.get<{ content: string }>(`/research/${id}/output/${filename}`);
      setPhaseContent(typeof data === 'string' ? data : data.content || '');
    } catch {
      setPhaseContent('*Output not available yet.*');
    } finally {
      setContentLoading(false);
    }
  };

  const handleRetry = async () => {
    setActionLoading('retry');
    try {
      await api.post(`/research/${id}/retry`);
      fetchCampaign();
    } finally {
      setActionLoading('');
    }
  };

  const handleSkip = async () => {
    setActionLoading('skip');
    try {
      await api.post(`/research/${id}/skip`);
      fetchCampaign();
    } finally {
      setActionLoading('');
    }
  };

  const handleCancel = async () => {
    setActionLoading('cancel');
    try {
      await api.post(`/research/${id}/cancel`);
      fetchCampaign();
    } finally {
      setActionLoading('');
    }
  };

  if (loading || !campaign) {
    return <div className="flex items-center justify-center py-20 text-gray-500">Loading campaign...</div>;
  }

  const isRunning = campaign.status.startsWith('phase_') || campaign.status === 'queued' || campaign.status === 'sending';

  return (
    <div>
      {/* Back link */}
      <button onClick={() => navigate('/research')} className="text-sm text-gray-500 hover:text-gray-300 mb-4 flex items-center gap-1">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        Back to Research
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Timeline + Output Viewer */}
        <div className="lg:col-span-8 space-y-6">
          {/* Phase Timeline */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">Pipeline Progress</h2>
              {isRunning && (
                <span className="text-xs text-blue-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
                  Live — updating every 3s
                </span>
              )}
            </div>
            {justStarted && isRunning && campaign.phase <= 1 && (
              <div className="mb-3 px-3 py-2 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-300">
                Pipeline started — watching progress live. Each phase takes 30s to 3min depending on web research results.
              </div>
            )}
            <PhaseTimeline
              currentPhase={campaign.phase}
              status={campaign.status}
              selectedPhase={selectedPhase}
              onPhaseClick={(phase, file) => loadPhaseContent(phase, file, true)}
              phaseStartedAt={campaign.research_data?.phase_started_at}
              completedPhases={campaign.research_data?.completed_phases}
            />
          </div>

          {/* Output Viewer */}
          {selectedPhase && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-gray-300">
                  {PHASES[selectedPhase - 1]?.name || `Phase ${selectedPhase}`}
                </h2>
                <span className="text-xs text-gray-500">{PHASES[selectedPhase - 1]?.file}</span>
              </div>
              {contentLoading ? (
                <div className="text-center py-8 text-gray-500">Loading output...</div>
              ) : (
                <MarkdownViewer content={phaseContent} />
              )}
            </div>
          )}

          {/* Empty state when no phase selected */}
          {!selectedPhase && !isRunning && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center">
              <p className="text-gray-500">Click a completed phase to view its output</p>
            </div>
          )}

          {/* Running indicator */}
          {isRunning && !selectedPhase && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center space-y-4">
              <div className="inline-flex items-center gap-3 text-blue-400">
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                <span className="font-medium">
                  {campaign.research_data?.current_phase_name || `Phase ${campaign.phase} of 6`}
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Click a completed phase above to preview its output while the pipeline continues
              </p>
            </div>
          )}
        </div>

        {/* Right: Campaign Info */}
        <div className="lg:col-span-4 space-y-4">
          {/* Company Card */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-lg font-semibold text-gray-100">{campaign.company_name}</h2>
              <ResearchStatusBadge status={campaign.status} />
            </div>

            {/* Contact */}
            {(campaign.contact_name || campaign.contact_email) && (
              <div>
                <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-1">Contact</h3>
                <p className="text-sm text-gray-300">{campaign.contact_name || ''}</p>
                {campaign.contact_email && (
                  <p className="text-xs text-gray-400">{campaign.contact_email}</p>
                )}
              </div>
            )}

            {/* Goal */}
            <div>
              <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-1">Goal</h3>
              <p className="text-sm text-gray-300">{campaign.goal}</p>
            </div>

            {/* Settings */}
            <div>
              <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Settings</h3>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-gray-500">Identity</span>
                  <p className="text-gray-300">{campaign.identity}</p>
                </div>
                <div>
                  <span className="text-gray-500">Language</span>
                  <p className="text-gray-300">{campaign.language}</p>
                </div>
                <div>
                  <span className="text-gray-500">Tone</span>
                  <p className="text-gray-300">{campaign.email_tone}</p>
                </div>
                <div>
                  <span className="text-gray-500">Mode</span>
                  <p className="text-gray-300">{campaign.auto_reply_mode}</p>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            <div className="text-xs text-gray-500 space-y-1 pt-2 border-t border-gray-800">
              <p>Created: {new Date(campaign.created_at).toLocaleString()}</p>
              {campaign.started_at && <p>Started: {new Date(campaign.started_at).toLocaleString()}</p>}
              {campaign.completed_at && <p>Completed: {new Date(campaign.completed_at).toLocaleString()}</p>}
            </div>

            {/* Error */}
            {campaign.error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-xs text-red-400 font-medium">Error</p>
                <p className="text-xs text-red-300 mt-1">{campaign.error}</p>
              </div>
            )}

            {/* Email Subject Preview */}
            {campaign.email_subject && (
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                <p className="text-xs text-green-400 font-medium">Email Subject</p>
                <p className="text-sm text-green-300 mt-1">{campaign.email_subject}</p>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
            <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-2">Actions</h3>

            {campaign.status === 'failed' && (
              <button
                onClick={handleRetry}
                disabled={!!actionLoading}
                className="w-full px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500 disabled:opacity-50 transition-colors"
              >
                {actionLoading === 'retry' ? 'Retrying...' : 'Retry Campaign'}
              </button>
            )}

            {campaign.status === 'queued' && (
              <button
                onClick={handleSkip}
                disabled={!!actionLoading}
                className="w-full px-4 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 border border-gray-700 disabled:opacity-50 transition-colors"
              >
                {actionLoading === 'skip' ? 'Skipping...' : 'Skip Campaign'}
              </button>
            )}

            {(campaign.status === 'sent' || campaign.status === 'draft_pending') && (
              <>
                <Link
                  to={`/compose?from_research=${campaign.id}`}
                  className="block w-full px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500 text-center transition-colors"
                >
                  Edit & Send
                </Link>
                {campaign.thread_id && (
                  <Link
                    to={`/threads/${campaign.thread_id}`}
                    className="block w-full px-4 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 border border-gray-700 text-center transition-colors"
                  >
                    View Thread
                  </Link>
                )}
              </>
            )}

            {isRunning && (
              <button
                onClick={handleCancel}
                disabled={!!actionLoading}
                className="w-full px-4 py-2 bg-red-600/20 text-red-400 text-sm rounded-lg hover:bg-red-600/30 border border-red-500/30 disabled:opacity-50 transition-colors"
              >
                {actionLoading === 'cancel' ? 'Stopping...' : 'Stop Campaign'}
              </button>
            )}
          </div>

          {/* Verbose Log */}
          {(campaign.research_data?.verbose_log?.length ?? 0) > 0 && (
            <VerboseLog entries={campaign.research_data!.verbose_log!} isRunning={isRunning} />
          )}
        </div>
      </div>
    </div>
  );
}

function VerboseLog({ entries, isRunning }: { entries: { ts: string; phase: number; msg: string }[]; isRunning: boolean }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  const phaseColor = (p: number) => {
    const colors: Record<number, string> = {
      0: 'text-gray-500',
      1: 'text-blue-400',
      2: 'text-cyan-400',
      3: 'text-amber-400',
      4: 'text-purple-400',
      5: 'text-green-400',
      6: 'text-emerald-400',
    };
    return colors[p] || 'text-gray-400';
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs text-gray-500 uppercase tracking-wider">Verbose Log</h3>
        <span className="text-xs text-gray-600">{entries.length} entries</span>
      </div>
      <div className="max-h-64 overflow-y-auto font-mono text-xs space-y-0.5 scrollbar-thin">
        {entries.map((e, i) => {
          const isFail = e.msg.startsWith('FAILED');
          return (
            <div key={i} className={`flex gap-2 ${isFail ? 'text-red-400' : 'text-gray-400'}`}>
              <span className="text-gray-600 shrink-0">{e.ts}</span>
              <span className={`shrink-0 w-6 text-right ${phaseColor(e.phase)}`}>
                {e.phase > 0 ? `P${e.phase}` : '--'}
              </span>
              <span className={isFail ? 'text-red-400' : 'text-gray-300'}>{e.msg}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
      {isRunning && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-blue-400">
          <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
          Streaming...
        </div>
      )}
    </div>
  );
}
