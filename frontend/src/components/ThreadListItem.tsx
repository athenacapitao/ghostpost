import { Link } from 'react-router-dom';
import type { Thread } from '../api/client';
import StateBadge from './StateBadge';

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

export default function ThreadListItem({ thread }: { thread: Thread }) {
  return (
    <Link
      to={`/threads/${thread.id}`}
      className="block p-4 rounded-lg bg-gray-900 border border-gray-800 hover:border-gray-700 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <StateBadge state={thread.state} />
            {thread.priority && (
              <span className="text-xs text-gray-500">{thread.priority}</span>
            )}
          </div>
          <h3 className="font-medium text-gray-100 truncate">
            {thread.subject || '(no subject)'}
          </h3>
          {thread.category && (
            <span className="text-xs text-gray-500 mt-1">{thread.category}</span>
          )}
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="text-xs text-gray-500">
            {timeAgo(thread.last_activity_at)}
          </span>
          <span className="text-xs text-gray-600">
            {thread.email_count} {thread.email_count === 1 ? 'email' : 'emails'}
          </span>
        </div>
      </div>
    </Link>
  );
}
