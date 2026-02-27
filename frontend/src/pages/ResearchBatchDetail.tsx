import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { ResearchBatchDetail as BatchDetailType } from '../api/client';
import ResearchStatusBadge from '../components/ResearchStatusBadge';
import CampaignCard from '../components/CampaignCard';

export default function ResearchBatchDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [batch, setBatch] = useState<BatchDetailType | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchBatch = async () => {
    try {
      const data = await api.get<BatchDetailType>(`/research/batch/${id}`);
      setBatch(data);
      setLoading(false);
    } catch {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatch();
  }, [id]);

  // Poll while active — 3s for running batches
  useEffect(() => {
    if (!batch || ['completed', 'cancelled'].includes(batch.status)) return;
    const pollMs = batch.status === 'in_progress' ? 3000 : 5000;
    const interval = setInterval(fetchBatch, pollMs);
    return () => clearInterval(interval);
  }, [batch?.status]);

  const handlePause = async () => {
    try {
      await api.post(`/research/batch/${id}/pause`);
      fetchBatch();
    } catch { /* ignore */ }
  };

  const handleResume = async () => {
    try {
      await api.post(`/research/batch/${id}/resume`);
      fetchBatch();
    } catch { /* ignore */ }
  };

  const handleCancel = async () => {
    try {
      await api.post(`/research/batch/${id}/cancel`);
      fetchBatch();
    } catch { /* ignore */ }
  };

  if (loading || !batch) {
    return <div className="flex items-center justify-center py-20 text-gray-500">Loading batch...</div>;
  }

  const progress = batch.total_companies > 0
    ? Math.round(((batch.completed + batch.failed + batch.skipped) / batch.total_companies) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button onClick={() => navigate('/research')} className="text-sm text-gray-500 hover:text-gray-300 flex items-center gap-1">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        Back to Research
      </button>

      {/* Header */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h1 className="text-xl font-semibold text-gray-100">{batch.name}</h1>
            <p className="text-sm text-gray-400 mt-1">
              {batch.total_companies} companies · Created {new Date(batch.created_at).toLocaleDateString()}
              {batch.status === 'in_progress' && (
                <span className="ml-2 text-blue-400 inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
                  Live
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <ResearchStatusBadge status={batch.status} />
            {batch.status === 'in_progress' && (
              <>
                <button onClick={handlePause} className="px-3 py-1.5 text-sm bg-amber-600/20 text-amber-400 rounded-lg hover:bg-amber-600/30 border border-amber-500/30 transition-colors">
                  Pause
                </button>
                <button onClick={handleCancel} className="px-3 py-1.5 text-sm bg-red-600/20 text-red-400 rounded-lg hover:bg-red-600/30 border border-red-500/30 transition-colors">
                  Stop Batch
                </button>
              </>
            )}
            {batch.status === 'paused' && (
              <>
                <button onClick={handleResume} className="px-3 py-1.5 text-sm bg-blue-600/20 text-blue-400 rounded-lg hover:bg-blue-600/30 border border-blue-500/30 transition-colors">
                  Resume
                </button>
                <button onClick={handleCancel} className="px-3 py-1.5 text-sm bg-red-600/20 text-red-400 rounded-lg hover:bg-red-600/30 border border-red-500/30 transition-colors">
                  Stop Batch
                </button>
              </>
            )}
          </div>
        </div>

        {/* Progress */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-300">{progress}% complete</span>
            <div className="flex gap-3 text-xs">
              <span className="text-green-400">{batch.completed} done</span>
              {batch.failed > 0 && <span className="text-red-400">{batch.failed} failed</span>}
              {batch.skipped > 0 && <span className="text-gray-400">{batch.skipped} skipped</span>}
            </div>
          </div>
          <div className="bg-gray-800 rounded-full h-2">
            <div
              className="bg-blue-500 rounded-full h-2 transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Campaigns Grid */}
      <div>
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Campaigns</h2>
        {batch.campaigns.length === 0 ? (
          <div className="text-center py-8 text-gray-500">No campaigns in this batch</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {batch.campaigns.map(c => <CampaignCard key={c.id} campaign={c} />)}
          </div>
        )}
      </div>
    </div>
  );
}
