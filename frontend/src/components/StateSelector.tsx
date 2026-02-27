import { useState, useRef, useEffect } from 'react';
import { api } from '../api/client';

const STATES = ['NEW', 'ACTIVE', 'WAITING_REPLY', 'FOLLOW_UP', 'GOAL_MET', 'ARCHIVED'] as const;

const stateColors: Record<string, string> = {
  NEW: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  ACTIVE: 'bg-green-500/20 text-green-400 border-green-500/30',
  WAITING_REPLY: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  FOLLOW_UP: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  GOAL_MET: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  ARCHIVED: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const stateLabels: Record<string, string> = {
  NEW: 'New',
  ACTIVE: 'Active',
  WAITING_REPLY: 'Waiting',
  FOLLOW_UP: 'Follow Up',
  GOAL_MET: 'Goal Met',
  ARCHIVED: 'Archived',
};

interface Props {
  state: string;
  threadId: number;
  onUpdate: () => void;
}

export default function StateSelector({ state, threadId, onUpdate }: Props) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  async function changeState(newState: string) {
    if (newState === state) { setOpen(false); return; }
    setSaving(true);
    try {
      await api.put(`/threads/${threadId}/state`, { state: newState, reason: 'Manual update' });
      onUpdate();
    } catch {
      // silent fail — thread will reload with current state
    } finally {
      setSaving(false);
      setOpen(false);
    }
  }

  const colors = stateColors[state] || stateColors.ARCHIVED;
  const label = stateLabels[state] || state;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={saving}
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border cursor-pointer hover:opacity-80 transition-opacity ${colors}`}
      >
        {saving ? 'Saving...' : label}
        <svg className="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 py-1 min-w-[140px]">
          {STATES.map(s => (
            <button
              key={s}
              onClick={() => changeState(s)}
              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-800 transition-colors ${
                s === state ? 'opacity-50 cursor-default' : 'cursor-pointer'
              }`}
            >
              <span className={`inline-block w-2 h-2 rounded-full mr-2 ${stateColors[s].split(' ')[0]}`} />
              {stateLabels[s]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
