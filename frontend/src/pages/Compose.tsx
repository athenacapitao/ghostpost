import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import type { ResearchCampaign } from '../api/client';
import IdentitySelect from '../components/IdentitySelect';

interface AgentContext {
  goal: string;
  acceptance_criteria: string;
  playbook: string;
  auto_reply_mode: string;
  follow_up_days: string;
  priority: string;
  category: string;
  notes: string;
}

const AGENT_CONTEXT_DEFAULTS: AgentContext = {
  goal: '',
  acceptance_criteria: '',
  playbook: '',
  auto_reply_mode: '',
  follow_up_days: '',
  priority: '',
  category: '',
  notes: '',
};

function buildAgentContextPayload(ctx: AgentContext): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  if (ctx.goal.trim()) payload.goal = ctx.goal.trim();
  if (ctx.acceptance_criteria.trim()) payload.acceptance_criteria = ctx.acceptance_criteria.trim();
  if (ctx.playbook) payload.playbook = ctx.playbook;
  if (ctx.auto_reply_mode) payload.auto_reply_mode = ctx.auto_reply_mode;
  if (ctx.follow_up_days.trim()) {
    const days = parseInt(ctx.follow_up_days, 10);
    if (!isNaN(days) && days > 0) payload.follow_up_days = days;
  }
  if (ctx.priority) payload.priority = ctx.priority;
  if (ctx.category.trim()) payload.category = ctx.category.trim();
  if (ctx.notes.trim()) payload.notes = ctx.notes.trim();
  return payload;
}

type Mode = 'direct' | 'research';

export default function Compose() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const fromResearchId = searchParams.get('from_research');

  const [mode, setMode] = useState<Mode>('direct');

  // Direct Send state
  const [to, setTo] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [cc, setCc] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [agentCtx, setAgentCtx] = useState<AgentContext>(AGENT_CONTEXT_DEFAULTS);

  // Research First state
  const [researchForm, setResearchForm] = useState({
    company_name: '',
    goal: '',
    contact_name: '',
    contact_email: '',
    contact_role: '',
    country: '',
    industry: '',
    identity: 'default',
    language: 'pt-PT',
    email_tone: 'direct-value',
    auto_reply_mode: 'draft-for-approval',
  });
  const [startingResearch, setStartingResearch] = useState(false);

  // Pre-fill from research
  const [researchBanner, setResearchBanner] = useState<{ company: string; id: string } | null>(null);

  useEffect(() => {
    if (!fromResearchId) return;
    // Fetch campaign data and email draft
    Promise.all([
      api.get<ResearchCampaign>(`/research/${fromResearchId}`),
      api.get<{ content: string }>(`/research/${fromResearchId}/output/06_email_draft.md`).catch(() => null),
    ]).then(([campaign, draft]) => {
      if (campaign.contact_email) setTo(campaign.contact_email);
      if (campaign.email_subject) setSubject(campaign.email_subject);
      setAgentCtx(prev => ({
        ...prev,
        goal: campaign.goal || '',
        auto_reply_mode: campaign.auto_reply_mode === 'draft-for-approval' ? 'draft' : campaign.auto_reply_mode || '',
      }));
      setResearchBanner({ company: campaign.company_name, id: fromResearchId });

      // Parse email body from draft markdown
      if (draft) {
        const content = typeof draft === 'string' ? draft : draft.content || '';
        const bodyMatch = content.match(/## Body\s*\n([\s\S]*?)(?=\n## |$)/);
        if (bodyMatch) {
          setBody(bodyMatch[1].trim());
        } else {
          // Try to extract body between --- delimiters
          const parts = content.split('---');
          if (parts.length >= 3) {
            setBody(parts.slice(1, -1).join('---').trim());
          }
        }
      }
    }).catch(() => {});
  }, [fromResearchId]);

  const setCtxField = (field: keyof AgentContext) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setAgentCtx(prev => ({ ...prev, [field]: e.target.value }));

  const setResearchField = (field: string) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => setResearchForm(prev => ({ ...prev, [field]: e.target.value }));

  const sendEmail = async () => {
    if (!to.trim() || !subject.trim() || !body.trim()) return;
    setSending(true);
    setError('');
    setSuccess('');
    try {
      const payload: Record<string, unknown> = { to: to.trim(), subject, body };
      if (cc.trim()) payload.cc = cc.split(',').map(s => s.trim()).filter(Boolean);
      Object.assign(payload, buildAgentContextPayload(agentCtx));

      const data = await api.post<{ message: string; thread_id?: number; warnings?: string[] }>('/compose', payload);
      let msg = data.message || 'Email sent!';
      if (data.thread_id != null) msg = `Email sent! Thread #${data.thread_id} created`;
      if (data.warnings?.length) msg += ' Warnings: ' + data.warnings.join(', ');
      setSuccess(msg);
      setTo(''); setSubject(''); setBody(''); setCc('');
      setAgentCtx(AGENT_CONTEXT_DEFAULTS);
      setResearchBanner(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to send');
    } finally {
      setSending(false);
    }
  };

  const saveDraft = async () => {
    if (!to.trim() || !subject.trim() || !body.trim()) return;
    setSending(true);
    setError('');
    setSuccess('');
    try {
      const payload: Record<string, unknown> = { to: to.trim(), subject, body };
      if (cc.trim()) payload.cc = cc.split(',').map(s => s.trim()).filter(Boolean);
      Object.assign(payload, buildAgentContextPayload(agentCtx));
      payload.draft = true;

      await api.post('/compose', payload);
      setSuccess('Draft saved!');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save draft');
    } finally {
      setSending(false);
    }
  };

  const startResearch = async () => {
    if (!researchForm.company_name.trim() || !researchForm.goal.trim()) return;
    setStartingResearch(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        company_name: researchForm.company_name.trim(),
        goal: researchForm.goal.trim(),
        identity: researchForm.identity,
        language: researchForm.language,
        email_tone: researchForm.email_tone,
        auto_reply_mode: researchForm.auto_reply_mode,
      };
      if (researchForm.contact_name.trim()) payload.contact_name = researchForm.contact_name.trim();
      if (researchForm.contact_email.trim()) payload.contact_email = researchForm.contact_email.trim();
      if (researchForm.contact_role.trim()) payload.contact_role = researchForm.contact_role.trim();
      if (researchForm.country.trim()) payload.country = researchForm.country.trim();
      if (researchForm.industry.trim()) payload.industry = researchForm.industry.trim();

      const data = await api.post<{ campaign_id: number }>('/research/', payload);
      navigate(`/research/${data.campaign_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start research');
    } finally {
      setStartingResearch(false);
    }
  };

  const inputClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const selectClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const labelClass = 'text-xs text-gray-500 block mb-1';

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">Compose</h1>

      {/* Research pre-fill banner */}
      {researchBanner && (
        <div className="mb-6 bg-blue-500/10 border border-blue-500/30 rounded-lg px-4 py-3 flex items-center justify-between">
          <p className="text-sm text-blue-300">
            Pre-filled from research on <strong>{researchBanner.company}</strong>
          </p>
          <Link to={`/research/${researchBanner.id}`} className="text-xs text-blue-400 hover:text-blue-300 underline">
            View Research
          </Link>
        </div>
      )}

      {/* Mode Toggle */}
      <div className="flex gap-1 bg-gray-900 rounded-lg p-1 w-fit mb-6">
        <button
          onClick={() => setMode('direct')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            mode === 'direct' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          Direct Send
        </button>
        <button
          onClick={() => setMode('research')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            mode === 'research' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          Research First
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column — Main Form */}
        <div className="lg:col-span-7 space-y-4">
          {mode === 'direct' ? (
            <>
              <div>
                <label className={labelClass}>To *</label>
                <input type="email" value={to} onChange={e => setTo(e.target.value)} placeholder="recipient@example.com" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>CC</label>
                <input type="text" value={cc} onChange={e => setCc(e.target.value)} placeholder="cc1@example.com, cc2@example.com" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Subject *</label>
                <input type="text" value={subject} onChange={e => setSubject(e.target.value)} placeholder="Subject line" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Body *</label>
                <textarea value={body} onChange={e => setBody(e.target.value)} rows={12} placeholder="Write your message..." className={`${inputClass} resize-y`} />
              </div>

              {error && <p className="text-sm text-red-400">{error}</p>}
              {success && <p className="text-sm text-green-400">{success}</p>}

              <div className="flex gap-3">
                <button
                  onClick={sendEmail}
                  disabled={sending || !to.trim() || !subject.trim() || !body.trim()}
                  className="px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {sending ? 'Sending...' : 'Send Email'}
                </button>
                <button
                  onClick={saveDraft}
                  disabled={sending || !to.trim() || !subject.trim() || !body.trim()}
                  className="px-6 py-2.5 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 border border-gray-700 disabled:opacity-50 transition-colors"
                >
                  Save as Draft
                </button>
              </div>
            </>
          ) : (
            <>
              <div>
                <label className={labelClass}>Company Name *</label>
                <input type="text" value={researchForm.company_name} onChange={setResearchField('company_name')} placeholder="e.g. Acme Corp" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Goal *</label>
                <textarea value={researchForm.goal} onChange={setResearchField('goal')} rows={3} placeholder="What do you want to achieve with this company?" className={`${inputClass} resize-y`} />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className={labelClass}>Contact Name</label>
                  <input type="text" value={researchForm.contact_name} onChange={setResearchField('contact_name')} placeholder="John Smith" className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Contact Email</label>
                  <input type="email" value={researchForm.contact_email} onChange={setResearchField('contact_email')} placeholder="john@acme.com" className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Contact Role</label>
                  <input type="text" value={researchForm.contact_role} onChange={setResearchField('contact_role')} placeholder="CTO" className={inputClass} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelClass}>Country</label>
                  <input type="text" value={researchForm.country} onChange={setResearchField('country')} placeholder="Portugal" className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Industry</label>
                  <input type="text" value={researchForm.industry} onChange={setResearchField('industry')} placeholder="Technology" className={inputClass} />
                </div>
              </div>

              {/* Info box */}
              <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
                <p className="text-sm text-gray-400">
                  The research pipeline will analyze the company, find opportunities, gather peer intelligence, and draft a personalized email for you to review before sending.
                </p>
              </div>

              {error && <p className="text-sm text-red-400">{error}</p>}

              <button
                onClick={startResearch}
                disabled={startingResearch || !researchForm.company_name.trim() || !researchForm.goal.trim()}
                className="w-full px-6 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {startingResearch ? 'Starting Research...' : 'Start Research Pipeline'}
              </button>
            </>
          )}
        </div>

        {/* Right Column — Agent Context */}
        <div className="lg:col-span-5">
          <div className="bg-gray-900 border border-gray-800 border-t-2 border-t-blue-500/50 rounded-lg p-4 sticky top-20">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
              {mode === 'direct' ? 'Agent Context' : 'Research Settings'}
            </h2>

            {mode === 'direct' ? (
              <div className="space-y-3">
                <div>
                  <label className={labelClass}>Goal</label>
                  <textarea value={agentCtx.goal} onChange={setCtxField('goal')} rows={2} placeholder="What should this thread achieve?" className={`${inputClass} resize-y`} />
                </div>
                <div>
                  <label className={labelClass}>Acceptance Criteria</label>
                  <textarea value={agentCtx.acceptance_criteria} onChange={setCtxField('acceptance_criteria')} rows={2} placeholder="How to know the goal is met" className={`${inputClass} resize-y`} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}>Playbook</label>
                    <select value={agentCtx.playbook} onChange={setCtxField('playbook')} className={selectClass}>
                      <option value="">(none)</option>
                      <option value="sales">Sales</option>
                      <option value="support">Support</option>
                      <option value="networking">Networking</option>
                      <option value="follow-up">Follow-up</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>Auto-Reply</label>
                    <select value={agentCtx.auto_reply_mode} onChange={setCtxField('auto_reply_mode')} className={selectClass}>
                      <option value="">Off</option>
                      <option value="draft">Draft</option>
                      <option value="auto">Auto</option>
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}>Follow-up Days</label>
                    <input type="number" min={1} value={agentCtx.follow_up_days} onChange={setCtxField('follow_up_days')} placeholder="3" className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>Priority</label>
                    <select value={agentCtx.priority} onChange={setCtxField('priority')} className={selectClass}>
                      <option value="">(none)</option>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className={labelClass}>Category</label>
                  <input type="text" value={agentCtx.category} onChange={setCtxField('category')} placeholder="e.g. business, personal" className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Notes</label>
                  <textarea value={agentCtx.notes} onChange={setCtxField('notes')} rows={2} placeholder="Additional context for the AI agent" className={`${inputClass} resize-y`} />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className={labelClass}>Sender Identity</label>
                  <IdentitySelect value={researchForm.identity} onChange={v => setResearchForm(p => ({ ...p, identity: v }))} className={selectClass} />
                </div>
                <div>
                  <label className={labelClass}>Language</label>
                  <select value={researchForm.language} onChange={setResearchField('language')} className={selectClass}>
                    <option value="pt-PT">Portuguese (PT)</option>
                    <option value="pt-BR">Portuguese (BR)</option>
                    <option value="en">English</option>
                    <option value="es">Spanish</option>
                    <option value="fr">French</option>
                    <option value="auto">Auto-detect</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Email Tone</label>
                  <select value={researchForm.email_tone} onChange={setResearchField('email_tone')} className={selectClass}>
                    <option value="direct-value">Direct Value</option>
                    <option value="consultative">Consultative</option>
                    <option value="relationship-first">Relationship First</option>
                    <option value="challenger-sale">Challenger Sale</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>After Research</label>
                  <select value={researchForm.auto_reply_mode} onChange={setResearchField('auto_reply_mode')} className={selectClass}>
                    <option value="draft-for-approval">Save as Draft (review first)</option>
                    <option value="autonomous">Send Automatically</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
