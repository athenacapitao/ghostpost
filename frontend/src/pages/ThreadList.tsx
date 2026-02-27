import { useEffect, useState, useCallback } from 'react';
import { api, type Thread, type PaginatedResponse } from '../api/client';
import ThreadListItem from '../components/ThreadListItem';
import { useWebSocket } from '../hooks/useWebSocket';

const STATES = ['ALL', 'NEW', 'ACTIVE', 'WAITING_REPLY', 'FOLLOW_UP', 'ARCHIVED'];

export default function ThreadList() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [state, setState] = useState('ALL');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchThreads = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (state !== 'ALL') params.state = state;
      if (search) params.q = search;
      const data = await api.get<PaginatedResponse<Thread>>('/threads', params);
      setThreads(data.items);
      setTotal(data.total);
      setPages(data.pages);
    } finally {
      setLoading(false);
    }
  }, [page, state, search]);

  useEffect(() => { fetchThreads(); }, [fetchThreads]);

  // Refresh on WS events
  useWebSocket(useCallback((event: { type: string; data: Record<string, unknown> }) => {
    if (event.type === 'sync_complete' || event.type === 'new_email') {
      fetchThreads();
    }
  }, [fetchThreads]));

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <input
          type="text"
          placeholder="Search threads..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          className="flex-1 bg-gray-900 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-gray-600"
        />
        <div className="flex gap-1 flex-wrap">
          {STATES.map(s => (
            <button
              key={s}
              onClick={() => { setState(s); setPage(1); }}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                state === s
                  ? 'bg-gray-700 text-white'
                  : 'bg-gray-900 text-gray-400 hover:bg-gray-800'
              }`}
            >
              {s === 'WAITING_REPLY' ? 'Waiting' : s === 'FOLLOW_UP' ? 'Follow Up' : s}
            </button>
          ))}
        </div>
      </div>

      {/* Count */}
      <div className="text-sm text-gray-500 mb-3">
        {total} thread{total !== 1 ? 's' : ''}
      </div>

      {/* Thread list */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : threads.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No threads found</div>
      ) : (
        <div className="space-y-2">
          {threads.map(t => (
            <ThreadListItem key={t.id} thread={t} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-3 py-1.5 rounded-md text-sm bg-gray-900 text-gray-400 hover:bg-gray-800 disabled:opacity-30"
          >
            Prev
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {pages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(pages, p + 1))}
            disabled={page === pages}
            className="px-3 py-1.5 rounded-md text-sm bg-gray-900 text-gray-400 hover:bg-gray-800 disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
