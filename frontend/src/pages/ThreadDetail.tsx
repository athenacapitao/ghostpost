import { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api, type ThreadDetail as ThreadDetailType } from '../api/client';
import EmailCard from '../components/EmailCard';
import StateSelector from '../components/StateSelector';
import ContextPanel from '../components/ContextPanel';
import GoalEditor from '../components/GoalEditor';
import ReplyComposer from '../components/ReplyComposer';

export default function ThreadDetail() {
  const { id } = useParams<{ id: string }>();
  const [thread, setThread] = useState<ThreadDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadThread = useCallback(() => {
    if (!id) return;
    api.get<ThreadDetailType>(`/threads/${id}`)
      .then(setThread)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    setLoading(true);
    loadThread();
  }, [loadThread]);

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;
  if (error) return <div className="text-center py-12 text-red-400">{error}</div>;
  if (!thread) return <div className="text-center py-12 text-gray-500">Thread not found</div>;

  const sortedEmails = [...thread.emails].sort(
    (a, b) => new Date(a.date || 0).getTime() - new Date(b.date || 0).getTime()
  );

  return (
    <div>
      <Link to="/" className="text-sm text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to threads
      </Link>

      <div className="flex flex-col lg:flex-row gap-6">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <StateSelector state={thread.state} threadId={thread.id} onUpdate={loadThread} />
            {thread.priority && (
              <span className="text-xs text-gray-500 uppercase">{thread.priority}</span>
            )}
          </div>
          <h1 className="text-xl font-bold text-gray-100 mb-4">
            {thread.subject || '(no subject)'}
          </h1>

          <div className="space-y-3">
            {sortedEmails.map(email => (
              <EmailCard key={email.id} email={email} />
            ))}
          </div>

          {/* Reply Composer */}
          <ReplyComposer threadId={thread.id} onSent={loadThread} />
        </div>

        {/* Interactive Sidebar */}
        <div className="lg:w-80 shrink-0 space-y-4">
          <ContextPanel thread={thread} onUpdate={loadThread} />
          <GoalEditor thread={thread} onUpdate={loadThread} />
        </div>
      </div>
    </div>
  );
}
