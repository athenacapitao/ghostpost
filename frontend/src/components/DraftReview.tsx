import { api } from '../api/client';

interface DraftItem {
  id: number;
  thread_id: number | null;
  to_addresses: string[] | null;
  subject: string | null;
  body: string | null;
  status: string;
  created_at: string;
}

interface Props {
  draft: DraftItem;
  onAction: () => void;
}

export default function DraftReview({ draft, onAction }: Props) {
  const approve = async () => {
    await api.post(`/drafts/${draft.id}/approve`);
    onAction();
  };

  const reject = async () => {
    await api.post(`/drafts/${draft.id}/reject`);
    onAction();
  };

  return (
    <article className="bg-gray-900 rounded-lg border border-gray-800 p-4">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="text-sm font-medium text-gray-200">
            {draft.subject || '(no subject)'}
          </h3>
          <p className="text-xs text-gray-500">
            To: {draft.to_addresses?.join(', ') || 'unknown'}
            {draft.thread_id && ` | Thread #${draft.thread_id}`}
          </p>
        </div>
        <time
          className="text-xs text-gray-500 shrink-0 ml-4"
          dateTime={draft.created_at}
        >
          {new Date(draft.created_at).toLocaleString()}
        </time>
      </div>

      {draft.body && (
        <pre className="text-sm text-gray-300 bg-gray-800 rounded p-3 mt-2 whitespace-pre-wrap font-sans max-h-40 overflow-y-auto">
          {draft.body}
        </pre>
      )}

      {draft.status === 'pending' && (
        <div className="flex gap-2 mt-3">
          <button
            onClick={approve}
            className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-500 focus:outline-none focus:ring-2 focus:ring-green-400"
            aria-label={`Approve and send draft: ${draft.subject || 'no subject'}`}
          >
            Approve &amp; Send
          </button>
          <button
            onClick={reject}
            className="px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-500 focus:outline-none focus:ring-2 focus:ring-red-400"
            aria-label={`Reject draft: ${draft.subject || 'no subject'}`}
          >
            Reject
          </button>
        </div>
      )}
    </article>
  );
}
