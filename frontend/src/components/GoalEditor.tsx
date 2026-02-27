import { useState } from 'react';
import { api, type ThreadDetail } from '../api/client';

interface Props {
  thread: ThreadDetail;
  onUpdate: () => void;
}

export default function GoalEditor({ thread, onUpdate }: Props) {
  const [goalText, setGoalText] = useState('');
  const [criteria, setCriteria] = useState('');
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<{ met: boolean; reason: string } | null>(null);
  const [editing, setEditing] = useState(false);

  const setGoal = async () => {
    if (!goalText.trim()) return;
    await api.put(`/threads/${thread.id}/goal`, {
      goal: goalText,
      acceptance_criteria: criteria || undefined,
    });
    setGoalText('');
    setCriteria('');
    setEditing(false);
    onUpdate();
  };

  const clearGoal = async () => {
    await api.delete(`/threads/${thread.id}/goal`);
    onUpdate();
  };

  const updateStatus = async (status: string) => {
    await api.put(`/threads/${thread.id}/goal/status`, { status });
    onUpdate();
  };

  const checkGoal = async () => {
    setChecking(true);
    try {
      const result = await api.post<{ met: boolean; reason: string }>(
        `/threads/${thread.id}/goal/check`
      );
      setCheckResult(result);
      if (result.met) onUpdate();
    } finally {
      setChecking(false);
    }
  };

  const statusBadge = (status: string | null) => {
    const styles: Record<string, string> = {
      in_progress: 'bg-blue-500/20 text-blue-400',
      met: 'bg-green-500/20 text-green-400',
      abandoned: 'bg-gray-500/20 text-gray-400',
    };
    return styles[status || ''] || 'bg-gray-500/20 text-gray-400';
  };

  if (!thread.goal && !editing) {
    return (
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
        <div className="flex justify-between items-center">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Goal</h3>
          <button
            onClick={() => setEditing(true)}
            className="text-xs text-blue-400 hover:text-blue-300"
            type="button"
          >
            Set Goal
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-2">No goal set</p>
      </div>
    );
  }

  if (editing && !thread.goal) {
    return (
      <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Set Goal</h3>
        <label htmlFor={`goal-text-${thread.id}`} className="sr-only">Goal description</label>
        <input
          id={`goal-text-${thread.id}`}
          type="text"
          value={goalText}
          onChange={e => setGoalText(e.target.value)}
          placeholder="Goal description..."
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
          onKeyDown={e => e.key === 'Enter' && setGoal()}
        />
        <label htmlFor={`goal-criteria-${thread.id}`} className="sr-only">Acceptance criteria</label>
        <input
          id={`goal-criteria-${thread.id}`}
          type="text"
          value={criteria}
          onChange={e => setCriteria(e.target.value)}
          placeholder="Acceptance criteria (optional)..."
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
        />
        <div className="flex gap-2">
          <button
            onClick={setGoal}
            type="button"
            className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-500"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            type="button"
            className="px-3 py-1 bg-gray-700 text-gray-300 text-xs rounded hover:bg-gray-600"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800 p-4 space-y-2">
      <div className="flex justify-between items-center">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide">Goal</h3>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusBadge(thread.goal_status)}`}>
          {thread.goal_status || 'unknown'}
        </span>
      </div>
      <p className="text-sm text-gray-200">{thread.goal}</p>
      {thread.acceptance_criteria && (
        <p className="text-xs text-gray-400">Criteria: {thread.acceptance_criteria}</p>
      )}

      <div className="flex gap-2 pt-1 flex-wrap">
        <button
          onClick={checkGoal}
          disabled={checking}
          type="button"
          className="px-2 py-1 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-500 disabled:opacity-50"
        >
          {checking ? 'Checking...' : 'Check if Met'}
        </button>
        {thread.goal_status === 'in_progress' && (
          <button
            onClick={() => updateStatus('met')}
            type="button"
            className="px-2 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-500"
          >
            Mark Met
          </button>
        )}
        <button
          onClick={clearGoal}
          type="button"
          className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded hover:bg-gray-600"
        >
          Clear
        </button>
      </div>

      {checkResult && (
        <div
          className={`text-xs p-2 rounded mt-1 ${checkResult.met ? 'bg-green-900/30 text-green-400' : 'bg-gray-800 text-gray-400'}`}
          role="status"
        >
          {checkResult.met ? 'Goal Met!' : 'Not yet.'} {checkResult.reason}
        </div>
      )}
    </div>
  );
}
