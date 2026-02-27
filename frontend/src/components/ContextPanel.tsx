import { useState, useEffect, useCallback } from 'react';
import { api, type ThreadDetail, type AuditEntry } from '../api/client';

const STATES = ['NEW', 'ACTIVE', 'WAITING_REPLY', 'FOLLOW_UP', 'GOAL_MET', 'ARCHIVED'];
const AUTO_REPLY_MODES = ['off', 'draft', 'auto'];

interface Props {
  thread: ThreadDetail;
  onUpdate: () => void;
}

export default function ContextPanel({ thread, onUpdate }: Props) {
  const [notes, setNotes] = useState(thread.notes || '');
  const [saving, setSaving] = useState(false);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);

  useEffect(() => {
    setNotes(thread.notes || '');
  }, [thread.notes]);

  useEffect(() => {
    api.get<AuditEntry[]>('/audit', { limit: 5 })
      .then(data => {
        const filtered = data.filter(e => e.thread_id === thread.id);
        setAuditLog(filtered.slice(0, 5));
      })
      .catch(() => {});
  }, [thread.id]);

  const updateState = async (state: string) => {
    await api.put(`/threads/${thread.id}/state`, { state });
    onUpdate();
  };

  const updateAutoReply = async (mode: string) => {
    await api.put(`/threads/${thread.id}/auto-reply`, { mode });
    onUpdate();
  };

  const updateFollowUp = async (days: number) => {
    await api.put(`/threads/${thread.id}/follow-up`, { days });
    onUpdate();
  };

  const saveNotes = useCallback(async () => {
    setSaving(true);
    try {
      await api.put(`/threads/${thread.id}/notes`, { notes });
    } finally {
      setSaving(false);
    }
  }, [thread.id, notes]);

  // Debounced auto-save for notes
  useEffect(() => {
    if (notes === (thread.notes || '')) return;
    const timer = setTimeout(saveNotes, 1500);
    return () => clearTimeout(timer);
  }, [notes, thread.notes, saveNotes]);

  const scoreColor = (score: number | null) => {
    if (score === null) return 'text-gray-500';
    if (score >= 80) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 space-y-4 sticky top-20">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Details</h2>

      {/* State dropdown */}
      <div>
        <label htmlFor={`state-${thread.id}`} className="text-xs text-gray-500 block mb-1">
          State
        </label>
        <select
          id={`state-${thread.id}`}
          value={thread.state}
          onChange={e => updateState(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
        >
          {STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {/* Auto-reply mode */}
      <div>
        <label htmlFor={`auto-reply-${thread.id}`} className="text-xs text-gray-500 block mb-1">
          Auto-Reply
        </label>
        <select
          id={`auto-reply-${thread.id}`}
          value={thread.auto_reply_mode}
          onChange={e => updateAutoReply(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
        >
          {AUTO_REPLY_MODES.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      {/* Follow-up days */}
      <div>
        <label htmlFor={`follow-up-${thread.id}`} className="text-xs text-gray-500 block mb-1">
          Follow-up (days)
        </label>
        <input
          id={`follow-up-${thread.id}`}
          type="number"
          value={thread.follow_up_days}
          onChange={e => updateFollowUp(Number(e.target.value))}
          min={1}
          max={90}
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
        />
      </div>

      {/* Security Score */}
      {thread.security_score_avg !== null && (
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Security Score</span>
          <span className={scoreColor(thread.security_score_avg)}>
            {thread.security_score_avg}/100
          </span>
        </div>
      )}

      {/* Category & Priority */}
      <div className="flex justify-between text-sm">
        <span className="text-gray-500">Category</span>
        <span className="text-gray-300">{thread.category || '-'}</span>
      </div>
      {thread.priority && (
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Priority</span>
          <span className="text-gray-300">{thread.priority}</span>
        </div>
      )}

      {/* Playbook */}
      {thread.playbook && (
        <div className="flex justify-between text-sm">
          <span className="text-gray-500">Playbook</span>
          <span className="text-gray-300">{thread.playbook}</span>
        </div>
      )}

      {/* Summary */}
      {thread.summary && (
        <div className="pt-2 border-t border-gray-800">
          <span className="text-xs text-gray-500">Summary</span>
          <p className="text-sm text-gray-300 mt-1">{thread.summary}</p>
        </div>
      )}

      {/* Notes (auto-save) */}
      <div className="pt-2 border-t border-gray-800">
        <div className="flex justify-between items-center mb-1">
          <label htmlFor={`notes-${thread.id}`} className="text-xs text-gray-500">
            Notes
          </label>
          {saving && <span className="text-xs text-blue-400">Saving...</span>}
        </div>
        <textarea
          id={`notes-${thread.id}`}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={3}
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 resize-none"
          placeholder="Add notes..."
        />
      </div>

      {/* Mini audit log */}
      {auditLog.length > 0 && (
        <div className="pt-2 border-t border-gray-800">
          <span className="text-xs text-gray-500">Recent Actions</span>
          <div className="mt-1 space-y-1" role="log" aria-label="Recent actions">
            {auditLog.map(entry => (
              <div key={entry.id} className="text-xs text-gray-400">
                <span className="text-gray-500">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                {' '}{entry.action_type}
                <span className="text-gray-600"> by {entry.actor}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
