const PHASE_NAMES = ['Input', 'Dossier', 'Opportunity', 'Peers', 'Value Plan', 'Email'];

interface PhaseProgressProps {
  currentPhase: number;
  status: string;
  compact?: boolean;
}

export default function PhaseProgress({ currentPhase, status, compact }: PhaseProgressProps) {
  const isFailed = status === 'failed';
  const isTerminal = ['sent', 'draft_pending', 'skipped'].includes(status);
  const isRunning = status.startsWith('phase_');

  return (
    <div className={`flex items-center ${compact ? 'gap-1' : 'gap-1.5'}`}>
      {PHASE_NAMES.map((name, i) => {
        const phaseNum = i + 1;
        const isCompleted = phaseNum < currentPhase || (phaseNum === currentPhase && isTerminal);
        const isActive = phaseNum === currentPhase && isRunning;
        const isFailedPhase = phaseNum === currentPhase && isFailed;

        let dotClass = 'bg-gray-700 border-gray-600';
        if (isCompleted) dotClass = 'bg-green-500 border-green-400';
        else if (isActive) dotClass = 'bg-blue-500 border-blue-400 animate-pulse';
        else if (isFailedPhase) dotClass = 'bg-red-500 border-red-400';

        return (
          <div key={i} className="flex items-center gap-1">
            {i > 0 && (
              <div className={`h-px ${compact ? 'w-1.5' : 'w-3'} ${
                isCompleted || isActive || isFailedPhase ? 'bg-gray-600' : 'bg-gray-800'
              }`} />
            )}
            <div
              className={`${compact ? 'w-2 h-2' : 'w-2.5 h-2.5'} rounded-full border ${dotClass}`}
              title={`${name} (Phase ${phaseNum})`}
            />
          </div>
        );
      })}
      {!compact && (
        <span className="text-xs text-gray-500 ml-1">
          {isTerminal ? '6/6' : isRunning ? `${currentPhase}/6` : isFailed ? `Failed at ${currentPhase}` : '0/6'}
        </span>
      )}
    </div>
  );
}
