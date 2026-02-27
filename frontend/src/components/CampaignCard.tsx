import { Link } from 'react-router-dom';
import type { ResearchCampaign } from '../api/client';
import ResearchStatusBadge from './ResearchStatusBadge';
import PhaseProgress from './PhaseProgress';

function timeAgo(date: string): string {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function CampaignCard({ campaign }: { campaign: ResearchCampaign }) {
  const borderColor =
    campaign.status === 'sent' ? 'border-l-green-500' :
    campaign.status === 'draft_pending' ? 'border-l-purple-500' :
    campaign.status === 'failed' ? 'border-l-red-500' :
    campaign.status.startsWith('phase_') ? 'border-l-blue-500' :
    campaign.status === 'skipped' ? 'border-l-gray-600' :
    'border-l-gray-700';

  return (
    <Link
      to={`/research/${campaign.id}`}
      className={`block bg-gray-900 border border-gray-800 border-l-2 ${borderColor} rounded-lg p-4 hover:bg-gray-800/50 transition-colors`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-medium text-gray-200 truncate">{campaign.company_name}</h3>
          {campaign.contact_name && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">
              {campaign.contact_name}{campaign.contact_email ? ` · ${campaign.contact_email}` : ''}
            </p>
          )}
        </div>
        <ResearchStatusBadge status={campaign.status} />
      </div>

      <p className="text-xs text-gray-400 mt-2 line-clamp-2">{campaign.goal}</p>

      <div className="flex items-center justify-between mt-3">
        <PhaseProgress currentPhase={campaign.phase} status={campaign.status} compact />
        <span className="text-xs text-gray-500">{timeAgo(campaign.created_at)}</span>
      </div>

      {/* Running activity hint */}
      {campaign.status.startsWith('phase_') && campaign.research_data?.current_phase_name && (
        <p className="text-xs text-blue-400/70 mt-1.5 truncate animate-pulse">
          {campaign.research_data.current_phase_name}
        </p>
      )}
    </Link>
  );
}
