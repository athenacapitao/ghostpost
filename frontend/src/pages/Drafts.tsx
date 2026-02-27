import { useEffect, useState } from 'react';
import { api } from '../api/client';
import DraftReview from '../components/DraftReview';

interface DraftItem {
  id: number;
  thread_id: number | null;
  to_addresses: string[] | null;
  subject: string | null;
  body: string | null;
  status: string;
  created_at: string;
}

export default function Drafts() {
  const [drafts, setDrafts] = useState<DraftItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');

  const load = () => {
    setLoading(true);
    api.get<DraftItem[]>('/drafts', { status: filter })
      .then(setDrafts)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [filter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-100">Drafts</h1>
        <label htmlFor="drafts-filter" className="sr-only">
          Filter drafts by status
        </label>
        <select
          id="drafts-filter"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="pending">Pending</option>
          <option value="sent">Sent</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500" aria-live="polite">Loading...</p>
      ) : drafts.length === 0 ? (
        <p className="text-gray-500">No {filter} drafts.</p>
      ) : (
        <div className="space-y-3" aria-label={`${filter} drafts`}>
          {drafts.map(d => (
            <DraftReview key={d.id} draft={d} onAction={load} />
          ))}
        </div>
      )}
    </div>
  );
}
