const statusColors: Record<string, string> = {
  queued: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  phase_1: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  phase_2: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  phase_3: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  phase_4: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  phase_5: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  phase_6: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  sending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  sent: 'bg-green-500/20 text-green-400 border-green-500/30',
  draft_pending: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  skipped: 'bg-gray-500/20 text-gray-500 border-gray-500/30',
  pending: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  in_progress: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  paused: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  completed: 'bg-green-500/20 text-green-400 border-green-500/30',
  cancelled: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const PHASE_NAMES: Record<string, string> = {
  phase_1: 'Collecting Input',
  phase_2: 'Researching',
  phase_3: 'Analyzing',
  phase_4: 'Peer Intel',
  phase_5: 'Value Plan',
  phase_6: 'Writing Email',
};

const statusLabels: Record<string, string> = {
  draft_pending: 'Draft Ready',
  in_progress: 'Running',
};

export default function ResearchStatusBadge({ status }: { status: string }) {
  const colors = statusColors[status] || statusColors.queued;
  const isRunning = status.startsWith('phase_');
  const label = PHASE_NAMES[status] || statusLabels[status] || status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, ' ');

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${colors}`}>
      {isRunning && (
        <svg className="animate-spin w-3 h-3" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {label}
    </span>
  );
}
