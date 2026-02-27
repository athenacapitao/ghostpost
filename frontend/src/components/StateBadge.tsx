const stateColors: Record<string, string> = {
  NEW: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  ACTIVE: 'bg-green-500/20 text-green-400 border-green-500/30',
  WAITING_REPLY: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  FOLLOW_UP: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  GOAL_MET: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  ARCHIVED: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

const stateLabels: Record<string, string> = {
  WAITING_REPLY: 'Waiting',
  FOLLOW_UP: 'Follow Up',
  GOAL_MET: 'Goal Met',
};

export default function StateBadge({ state }: { state: string }) {
  const colors = stateColors[state] || stateColors.ARCHIVED;
  const label = stateLabels[state] || state;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${colors}`}>
      {label}
    </span>
  );
}
