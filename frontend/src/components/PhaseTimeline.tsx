import { useEffect, useState } from 'react';

const PHASES = [
  { name: 'Input Collection', file: '00_input.md', desc: 'Validate inputs and set up campaign' },
  { name: 'Company Dossier', file: '01_company_dossier.md', desc: 'Deep research on the company' },
  { name: 'Opportunity Analysis', file: '02_opportunity_analysis.md', desc: 'Goal-specific opportunity mapping' },
  { name: 'Contacts Search', file: '03_contacts_search.md', desc: 'Find the best contact person' },
  { name: 'Person Research', file: '04b_person_profile.md', desc: 'Deep profile of the contact person' },
  { name: 'Peer Intelligence', file: '04_peer_intelligence.md', desc: 'Case studies and social proof' },
  { name: 'Value Proposition', file: '05_value_proposition_plan.md', desc: 'Strategic engagement plan' },
  { name: 'Email Draft', file: '06_email_draft.md', desc: 'Compose the final email' },
];

const PHASE_ACTIVITY: Record<number, string[]> = {
  1: ['Validating campaign inputs...', 'Setting up research directories...'],
  2: ['Searching for company information...', 'Fetching web pages...', 'Analyzing search results...', 'Synthesizing company dossier with LLM...'],
  3: ['Mapping opportunities to goal...', 'Identifying pain points and angles...', 'Building opportunity matrix...'],
  4: ['Searching for contacts and decision-makers...', 'Extracting email addresses...', 'Ranking candidates by relevance...'],
  5: ['Researching contact background...', 'Finding thought leadership and publications...', 'Building person profile...'],
  6: ['Researching similar companies...', 'Finding case studies and references...', 'Building social proof...'],
  7: ['Creating engagement strategy...', 'Building value proposition...', 'Defining talking points...'],
  8: ['Composing email draft...', 'Applying tone and identity...', 'Finalizing email content...'],
};

export { PHASES };

function ElapsedTime({ since }: { since: string }) {
  const [elapsed, setElapsed] = useState('');

  useEffect(() => {
    const update = () => {
      const start = new Date(since).getTime();
      const now = Date.now();
      const secs = Math.floor((now - start) / 1000);
      if (secs < 60) setElapsed(`${secs}s`);
      else if (secs < 3600) setElapsed(`${Math.floor(secs / 60)}m ${secs % 60}s`);
      else setElapsed(`${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [since]);

  return <span className="text-xs text-gray-500 tabular-nums">{elapsed}</span>;
}

function ActivityCycler({ phase }: { phase: number }) {
  const messages = PHASE_ACTIVITY[phase] || ['Processing...'];
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
  }, [phase]);

  useEffect(() => {
    if (messages.length <= 1) return;
    const interval = setInterval(() => {
      setIndex(prev => (prev + 1) % messages.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [messages.length, phase]);

  return (
    <span className="text-xs text-blue-300/70 animate-pulse">{messages[index]}</span>
  );
}

interface PhaseTimelineProps {
  currentPhase: number;
  status: string;
  selectedPhase: number | null;
  onPhaseClick: (phase: number, filename: string) => void;
  phaseStartedAt?: string | null;
  completedPhases?: Record<string, { name: string; completed_at: string }> | null;
}

export default function PhaseTimeline({
  currentPhase, status, selectedPhase, onPhaseClick,
  phaseStartedAt, completedPhases,
}: PhaseTimelineProps) {
  const isFailed = status === 'failed';
  const isTerminal = ['sent', 'draft_pending', 'skipped'].includes(status);

  return (
    <div className="space-y-0">
      {PHASES.map((phase, i) => {
        const phaseNum = i + 1;
        const isCompleted = phaseNum < currentPhase || (phaseNum === currentPhase && isTerminal) || (phaseNum <= 6 && isTerminal && currentPhase >= phaseNum);
        const isActive = phaseNum === currentPhase && status.startsWith('phase_');
        const isFailedPhase = phaseNum === currentPhase && isFailed;
        const isClickable = isCompleted;
        const isSelected = selectedPhase === phaseNum;

        // Get completed phase timing
        const completedInfo = completedPhases?.[String(phaseNum)];

        let iconClass = 'border-gray-700 bg-gray-900 text-gray-600';
        let icon = <span className="text-xs">{phaseNum}</span>;

        if (isCompleted) {
          iconClass = 'border-green-500/50 bg-green-500/20 text-green-400';
          icon = (
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          );
        } else if (isActive) {
          iconClass = 'border-blue-500/50 bg-blue-500/20 text-blue-400';
          icon = (
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
          );
        } else if (isFailedPhase) {
          iconClass = 'border-red-500/50 bg-red-500/20 text-red-400';
          icon = (
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          );
        }

        return (
          <div key={i}>
            <button
              type="button"
              disabled={!isClickable}
              onClick={() => isClickable && onPhaseClick(phaseNum, phase.file)}
              className={`w-full flex items-start gap-3 px-3 py-3 rounded-lg text-left transition-colors ${
                isClickable ? 'hover:bg-gray-800/50 cursor-pointer' : 'cursor-default'
              } ${isSelected ? 'bg-gray-800/70' : ''}`}
            >
              {/* Icon + connector line */}
              <div className="flex flex-col items-center shrink-0">
                <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center ${iconClass}`}>
                  {icon}
                </div>
                {i < PHASES.length - 1 && (
                  <div className={`w-0.5 h-6 mt-1 ${isCompleted ? 'bg-green-500/30' : isActive ? 'bg-blue-500/20' : 'bg-gray-800'}`} />
                )}
              </div>

              {/* Text */}
              <div className="min-w-0 flex-1 pt-0.5">
                <div className="flex items-center justify-between gap-2">
                  <div className={`text-sm font-medium ${
                    isCompleted ? 'text-gray-200' :
                    isActive ? 'text-blue-400' :
                    isFailedPhase ? 'text-red-400' :
                    'text-gray-500'
                  }`}>
                    {phase.name}
                  </div>
                  {/* Elapsed time for active phase */}
                  {isActive && phaseStartedAt && (
                    <ElapsedTime since={phaseStartedAt} />
                  )}
                  {/* Completed time badge */}
                  {isCompleted && completedInfo && (
                    <span className="text-xs text-gray-600">
                      {new Date(completedInfo.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                {/* Static description for inactive, activity cycler for active */}
                {isActive ? (
                  <ActivityCycler phase={phaseNum} />
                ) : (
                  <div className="text-xs text-gray-500 mt-0.5">{phase.desc}</div>
                )}
              </div>
            </button>
          </div>
        );
      })}
    </div>
  );
}
