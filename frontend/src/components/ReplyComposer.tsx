import { useState } from 'react';
import { api } from '../api/client';

interface Props {
  threadId: number;
  onSent: () => void;
}

export default function ReplyComposer({ threadId, onSent }: Props) {
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const sendReply = async () => {
    if (!body.trim()) return;
    setSending(true);
    setError('');
    setSuccess('');
    try {
      const data = await api.post<{ message: string; warnings?: string[] }>(
        `/threads/${threadId}/reply`,
        { body }
      );
      setSuccess(data.message || 'Reply sent!');
      setBody('');
      onSent();
      if (data.warnings?.length) {
        setSuccess(prev => prev + ' Warnings: ' + data.warnings!.join(', '));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  const saveDraft = async () => {
    if (!body.trim()) return;
    setSavingDraft(true);
    setError('');
    try {
      await api.post(`/threads/${threadId}/draft`, {
        to: '',
        subject: '',
        body,
      });
      setSuccess('Draft saved!');
      setBody('');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save draft');
    } finally {
      setSavingDraft(false);
    }
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 mt-4">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-2">Reply</h3>

      <textarea
        value={body}
        onChange={e => setBody(e.target.value)}
        rows={5}
        placeholder="Type your reply..."
        aria-label="Reply body"
        className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 resize-y focus:outline-none focus:ring-1 focus:ring-blue-500"
      />

      {error && <p className="text-xs text-red-400 mt-1" role="alert">{error}</p>}
      {success && <p className="text-xs text-green-400 mt-1" role="status">{success}</p>}

      <div className="flex gap-2 mt-2">
        <button
          onClick={sendReply}
          disabled={sending || !body.trim()}
          aria-busy={sending}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {sending ? 'Sending...' : 'Send Reply'}
        </button>
        <button
          onClick={saveDraft}
          disabled={savingDraft || !body.trim()}
          aria-busy={savingDraft}
          className="px-4 py-1.5 bg-gray-700 text-gray-300 text-sm rounded hover:bg-gray-600 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          {savingDraft ? 'Saving...' : 'Save Draft'}
        </button>
      </div>
    </div>
  );
}
