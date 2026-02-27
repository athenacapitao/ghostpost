import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import IdentitySelect from '../components/IdentitySelect';

export default function ResearchNew() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    company_name: '',
    goal: '',
    contact_name: '',
    contact_email: '',
    contact_role: '',
    cc: '',
    extra_context: '',
    country: '',
    industry: '',
    identity: 'default',
    language: 'pt-PT',
    email_tone: 'direct-value',
    auto_reply_mode: 'draft-for-approval',
    max_auto_replies: '3',
  });

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [field]: e.target.value }));

  const submit = async () => {
    if (!form.company_name.trim() || !form.goal.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      const payload: Record<string, unknown> = {
        company_name: form.company_name.trim(),
        goal: form.goal.trim(),
        identity: form.identity,
        language: form.language,
        email_tone: form.email_tone,
        auto_reply_mode: form.auto_reply_mode,
        max_auto_replies: parseInt(form.max_auto_replies) || 3,
      };
      if (form.contact_name.trim()) payload.contact_name = form.contact_name.trim();
      if (form.contact_email.trim()) payload.contact_email = form.contact_email.trim();
      if (form.contact_role.trim()) payload.contact_role = form.contact_role.trim();
      if (form.cc.trim()) payload.cc = form.cc.trim();
      if (form.extra_context.trim()) payload.extra_context = form.extra_context.trim();
      if (form.country.trim()) payload.country = form.country.trim();
      if (form.industry.trim()) payload.industry = form.industry.trim();

      const data = await api.post<{ campaign_id: number; status: string }>('/research/', payload);
      navigate(`/research/${data.campaign_id}`, { state: { justStarted: true } });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start campaign');
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const selectClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const labelClass = 'text-xs text-gray-500 block mb-1';

  return (
    <div className="max-w-2xl">
      <button onClick={() => navigate('/research')} className="text-sm text-gray-500 hover:text-gray-300 mb-4 flex items-center gap-1">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        Back to Research
      </button>

      <h1 className="text-xl font-semibold mb-6">New Research Campaign</h1>

      <div className="space-y-6">
        {/* Target Company */}
        <div>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">Target Company</h2>
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Company Name *</label>
              <input type="text" value={form.company_name} onChange={set('company_name')} placeholder="e.g. Acme Corp" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Goal *</label>
              <textarea value={form.goal} onChange={set('goal')} rows={3} placeholder="What do you want to achieve with this company?" className={`${inputClass} resize-y`} />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Contact Name</label>
                <input type="text" value={form.contact_name} onChange={set('contact_name')} placeholder="John Smith" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Contact Email</label>
                <input type="email" value={form.contact_email} onChange={set('contact_email')} placeholder="john@acme.com" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Contact Role</label>
                <input type="text" value={form.contact_role} onChange={set('contact_role')} placeholder="CTO" className={inputClass} />
              </div>
            </div>
            <div>
              <label className={labelClass}>CC Recipients</label>
              <input type="text" value={form.cc} onChange={set('cc')} placeholder="cc1@example.com, cc2@example.com" className={inputClass} />
              <p className="text-xs text-gray-600 mt-1">Comma-separated email addresses</p>
            </div>
            <div>
              <label className={labelClass}>Extra Context</label>
              <textarea value={form.extra_context} onChange={set('extra_context')} rows={3} placeholder="Any additional context for the research pipeline (e.g. mutual connections, recent news, specific angles to explore...)" className={`${inputClass} resize-y`} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Country</label>
                <input type="text" value={form.country} onChange={set('country')} placeholder="Portugal" className={inputClass} />
              </div>
              <div>
                <label className={labelClass}>Industry</label>
                <input type="text" value={form.industry} onChange={set('industry')} placeholder="Technology" className={inputClass} />
              </div>
            </div>
          </div>
        </div>

        {/* Campaign Settings */}
        <div>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">Campaign Settings</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Sender Identity</label>
              <IdentitySelect value={form.identity} onChange={v => setForm(p => ({ ...p, identity: v }))} className={selectClass} />
            </div>
            <div>
              <label className={labelClass}>Language</label>
              <select value={form.language} onChange={set('language')} className={selectClass}>
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
              <select value={form.email_tone} onChange={set('email_tone')} className={selectClass}>
                <option value="direct-value">Direct Value</option>
                <option value="consultative">Consultative</option>
                <option value="relationship-first">Relationship First</option>
                <option value="challenger-sale">Challenger Sale</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>After Sending</label>
              <select value={form.auto_reply_mode} onChange={set('auto_reply_mode')} className={selectClass}>
                <option value="draft-for-approval">Save as Draft</option>
                <option value="autonomous">Send Automatically</option>
              </select>
            </div>
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          onClick={submit}
          disabled={submitting || !form.company_name.trim() || !form.goal.trim()}
          className="w-full px-6 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? 'Starting Research...' : 'Start Research'}
        </button>
      </div>
    </div>
  );
}
