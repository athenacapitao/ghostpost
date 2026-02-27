import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ResearchCampaign, ResearchBatch, PaginatedResponse } from '../api/client';
import CampaignCard from '../components/CampaignCard';
import ResearchStatusBadge from '../components/ResearchStatusBadge';

export default function Research() {
  const [tab, setTab] = useState<'campaigns' | 'batches'>('campaigns');

  // Campaigns state
  const [campaigns, setCampaigns] = useState<ResearchCampaign[]>([]);
  const [campaignTotal, setCampaignTotal] = useState(0);
  const [campaignPage, setCampaignPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  // Batches state
  const [batches, setBatches] = useState<ResearchBatch[]>([]);
  const [batchesLoading, setBatchesLoading] = useState(false);

  // Fetch campaigns
  const fetchCampaigns = () => {
    const params: Record<string, string | number> = { page: campaignPage, page_size: 20 };
    if (statusFilter) params.status = statusFilter;
    return api.get<PaginatedResponse<ResearchCampaign>>('/research/', params)
      .then(data => {
        setCampaigns(data.items);
        setCampaignTotal(data.pages);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    setLoading(true);
    fetchCampaigns();
  }, [campaignPage, statusFilter]);

  // Auto-poll when any campaign is running
  const hasRunning = campaigns.some(c => c.status.startsWith('phase_') || c.status === 'queued');
  useEffect(() => {
    if (!hasRunning || tab !== 'campaigns') return;
    const interval = setInterval(fetchCampaigns, 5000);
    return () => clearInterval(interval);
  }, [hasRunning, tab, campaignPage, statusFilter]);

  // Fetch batches when tab switches
  useEffect(() => {
    if (tab !== 'batches') return;
    setBatchesLoading(true);
    api.get<PaginatedResponse<ResearchBatch> | ResearchBatch[]>('/research/batches')
      .then(data => {
        const items = Array.isArray(data) ? data : (data as PaginatedResponse<ResearchBatch>).items || [];
        setBatches(items);
        setBatchesLoading(false);
      })
      .catch(() => setBatchesLoading(false));
  }, [tab]);

  const handlePause = async (id: number) => {
    try {
      await api.post(`/research/batch/${id}/pause`);
      setBatches(prev => prev.map(b => b.id === id ? { ...b, status: 'paused' } : b));
    } catch { /* ignore — badge stays unchanged */ }
  };

  const handleResume = async (id: number) => {
    try {
      await api.post(`/research/batch/${id}/resume`);
      setBatches(prev => prev.map(b => b.id === id ? { ...b, status: 'in_progress' } : b));
    } catch { /* ignore */ }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Research</h1>
        <div className="flex gap-2">
          <Link
            to="/research/new"
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500 transition-colors"
          >
            New Campaign
          </Link>
          <Link
            to="/research/import"
            className="px-4 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 border border-gray-700 transition-colors"
          >
            CSV Import
          </Link>
          <Link
            to="/research/batch/new"
            className="px-4 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 border border-gray-700 transition-colors"
          >
            New Batch
          </Link>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-900 rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('campaigns')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            tab === 'campaigns' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          Campaigns
        </button>
        <button
          onClick={() => setTab('batches')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            tab === 'batches' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          Batches
        </button>
      </div>

      {/* Campaigns Tab */}
      {tab === 'campaigns' && (
        <>
          {/* Filter */}
          <div className="flex gap-3">
            <select
              value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setCampaignPage(1); }}
              className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">All statuses</option>
              <option value="queued">Queued</option>
              <option value="phase_1">Running</option>
              <option value="sent">Sent</option>
              <option value="draft_pending">Draft Ready</option>
              <option value="failed">Failed</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>

          {loading ? (
            <div className="text-center py-12 text-gray-500">Loading campaigns...</div>
          ) : campaigns.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 mb-4">No research campaigns yet</p>
              <Link
                to="/research/new"
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500"
              >
                Start Your First Campaign
              </Link>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {campaigns.map(c => <CampaignCard key={c.id} campaign={c} />)}
              </div>

              {/* Pagination */}
              {campaignTotal > 1 && (
                <div className="flex justify-center gap-2">
                  <button
                    onClick={() => setCampaignPage(p => Math.max(1, p - 1))}
                    disabled={campaignPage <= 1}
                    className="px-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded text-gray-400 hover:text-white disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="px-3 py-1.5 text-sm text-gray-400">
                    Page {campaignPage} of {campaignTotal}
                  </span>
                  <button
                    onClick={() => setCampaignPage(p => Math.min(campaignTotal, p + 1))}
                    disabled={campaignPage >= campaignTotal}
                    className="px-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded text-gray-400 hover:text-white disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Batches Tab */}
      {tab === 'batches' && (
        <>
          {batchesLoading ? (
            <div className="text-center py-12 text-gray-500">Loading batches...</div>
          ) : batches.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 mb-4">No batches yet</p>
              <Link
                to="/research/batch/new"
                className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-500"
              >
                Create Your First Batch
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {batches.map(batch => (
                <Link
                  key={batch.id}
                  to={`/research/batch/${batch.id}`}
                  className="block bg-gray-900 border border-gray-800 rounded-lg p-4 hover:bg-gray-800/50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <h3 className="text-sm font-medium text-gray-200">{batch.name}</h3>
                    <ResearchStatusBadge status={batch.status} />
                  </div>

                  {/* Progress bar */}
                  <div className="mb-2">
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                      <span>{batch.completed + batch.failed + batch.skipped} / {batch.total_companies}</span>
                      <span>
                        {batch.completed} done
                        {batch.failed > 0 && <>, <span className="text-red-400">{batch.failed} failed</span></>}
                      </span>
                    </div>
                    <div className="bg-gray-800 rounded-full h-1.5">
                      <div
                        className="bg-blue-500 rounded-full h-1.5 transition-all"
                        style={{ width: `${batch.total_companies > 0 ? ((batch.completed + batch.failed + batch.skipped) / batch.total_companies) * 100 : 0}%` }}
                      />
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs text-gray-500">
                      {new Date(batch.created_at).toLocaleDateString()}
                    </span>
                    {batch.status === 'in_progress' && (
                      <button
                        onClick={e => { e.preventDefault(); handlePause(batch.id); }}
                        className="text-xs text-amber-400 hover:text-amber-300"
                      >
                        Pause
                      </button>
                    )}
                    {batch.status === 'paused' && (
                      <button
                        onClick={e => { e.preventDefault(); handleResume(batch.id); }}
                        className="text-xs text-blue-400 hover:text-blue-300"
                      >
                        Resume
                      </button>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
